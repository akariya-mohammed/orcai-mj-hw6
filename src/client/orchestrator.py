"""The MCP client / game orchestrator.

Holds the autonomous game loop: setup negotiation in natural language, then 6
sub-games (3 as cop, 3 as thief) where on every turn the acting agent's strategy
picks a move, its persona *announces* it in free language, the opponent persona
*interprets* that language back into a move, and the authoritative engine applies
it. Every event is logged to JSONL; at the end the score is computed and the JSON
report is built (and optionally emailed).

For the local level both agent "bodies" live in this process around one
authoritative :class:`SubGame`; the same loop drives networked MCP servers at the
cloud / cross-group levels (the bodies become remote).
"""

from __future__ import annotations

import argparse
import logging
import random
from datetime import datetime
from typing import Any

from ..config import AppConfig, load_config
from ..engine.game import Move, Role, Status, new_sub_game
from ..engine.scoring import Match, SubGameResult, score_sub_game, summarize_match
from ..reliability import TokenGatekeeper, Watchdog
from ..report import LogBook, build_internal_report
from ..strategy import make_decider
from .llm import build_llm
from .personas import Persona

logger = logging.getLogger(__name__)


def _now_iso(cfg: AppConfig) -> str:
    tz_name = cfg.email.get("timezone", "UTC")
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(tz_name)).isoformat(timespec="seconds")
    except Exception:  # pragma: no cover - tz db missing
        return datetime.now().isoformat(timespec="seconds")


class Orchestrator:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.rng = random.Random(cfg.strategy.get("seed", 7))
        self.gatekeeper = TokenGatekeeper(cfg.llm.get("max_tokens_budget", 400000), name="hw6")
        self.llm = build_llm(cfg)
        self.personas = {
            Role.COP: Persona(Role.COP, self.llm, self.gatekeeper),
            Role.THIEF: Persona(Role.THIEF, self.llm, self.gatekeeper),
        }
        self.deciders = {
            Role.COP: make_decider(Role.COP, cfg, rng=self.rng),
            Role.THIEF: make_decider(Role.THIEF, cfg, rng=self.rng),
        }

    # --- one sub-game ------------------------------------------------------
    def _play_sub_game(self, index: int, our_role: Role, log: LogBook) -> SubGameResult:
        g = self.cfg.game
        sub = new_sub_game(
            rows=g["grid_size"][0],
            cols=g["grid_size"][1],
            origin=g["origin"],
            diagonal=g["diagonal_moves"],
            max_moves=g["max_moves"],
            max_barriers=g["max_barriers"],
            thief_moves_first=g["thief_moves_first"],
            rng=self.rng,
        )

        # --- setup negotiation (natural language) ---
        setup_cop = (
            f"Cop here. Proposing a {g['grid_size'][0]}x{g['grid_size'][1]} board, "
            f"origin {g['origin']}, max {g['max_moves']} moves, diagonals "
            f"{'on' if g['diagonal_moves'] else 'off'}. I start at {sub.cop}."
        )
        setup_thief = f"Thief agrees on those rules. I start at {sub.thief}."
        log.write(
            "setup",
            sub_game=index,
            our_role=our_role.value,
            cop=setup_cop,
            thief=setup_thief,
            start={"cop": list(sub.cop), "thief": list(sub.thief)},
        )

        # --- play ---
        while sub.status is Status.PLAYING:
            mover = sub.turn
            opponent = mover.other
            move: Move = self.deciders[mover](sub, mover)
            sentence = self.personas[mover].announce(move, sub)
            parsed = self.personas[opponent].interpret(sentence, sub, mover)
            mismatch = parsed is None or (parsed.kind, parsed.cell) != (move.kind, move.cell)

            sub.apply(mover, move)  # announcer is authoritative for its own move
            log.write(
                "turn",
                sub_game=index,
                round=sub.move_count,
                mover=mover.value,
                message=sentence,
                interpreted=(
                    None if parsed is None else {"kind": parsed.kind, "cell": list(parsed.cell)}
                ),
                interpretation_mismatch=mismatch,
                **sub.snapshot(),
            )
            if mismatch:
                logger.warning(
                    "sub-game %d: interpretation mismatch on %s turn", index, mover.value
                )

        cop_pts, thief_pts = score_sub_game(sub.status, self.cfg.scoring)
        log.write(
            "sub_game_end",
            sub_game=index,
            our_role=our_role.value,
            outcome=sub.status.value,
            cop_points=cop_pts,
            thief_points=thief_pts,
            rounds=sub.move_count,
        )
        return SubGameResult(index, our_role, sub.status, cop_pts, thief_pts, sub.move_count)

    # --- full match --------------------------------------------------------
    def run_match(self, *, log_path: str | None = None) -> dict[str, Any]:
        n = self.cfg.game["num_sub_games"]
        half = n // 2
        schedule = [Role.COP] * half + [Role.THIEF] * (n - half)

        ts = _now_iso(self.cfg).replace(":", "").replace("-", "")
        log_file = log_path or str(self.cfg.path("logs") / f"match-{ts}.jsonl")
        match = Match()

        with (
            Watchdog(self.cfg.llm.get("watchdog_timeout", 180), name="hw6") as wd,
            LogBook(log_file) as log,
        ):
            log.write(
                "match_start",
                provider=self.llm.name,
                grid=self.cfg.game["grid_size"],
                num_sub_games=n,
                strategy=self.cfg.strategy,
            )
            for i, our_role in enumerate(schedule, start=1):
                wd.pet()
                result = self._play_sub_game(i, our_role, log)
                match.add(result)
                logger.info(
                    "sub-game %d/%d (%s): %s  cop=%d thief=%d  rounds=%d",
                    i,
                    n,
                    our_role.value,
                    result.status.value,
                    result.cop_points,
                    result.thief_points,
                    result.rounds,
                )
            summary = summarize_match(match)
            log.write("match_end", **summary, tokens=self.gatekeeper.summary())

        report = build_internal_report(
            self.cfg,
            summary,
            cop_mcp_url=self._mcp_url("cop"),
            thief_mcp_url=self._mcp_url("thief"),
            generated_at=_now_iso(self.cfg),
        )
        report_path = self.cfg.path("artefacts") / "internal_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        import json

        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "summary": summary,
            "report": report,
            "log_file": log_file,
            "report_file": str(report_path),
        }

    def _mcp_url(self, which: str) -> str:
        s = self.cfg.servers[which]
        return f"http://{s['host']}:{s['port']}/mcp"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a HW6 Cops & Robbers self-play match.")
    parser.add_argument("--provider", help="override llm.provider (e.g. mock, ollama, anthropic)")
    parser.add_argument("--grid", type=int, help="override grid size (square, e.g. 5)")
    parser.add_argument("--sub-games", type=int, help="override number of sub-games")
    parser.add_argument("--email", action="store_true", help="send the report by email (Gmail API)")
    parser.add_argument("--log", help="path for the JSONL match log")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = load_config()
    if args.provider:
        cfg.raw["llm"]["provider"] = args.provider
    if args.grid:
        cfg.raw["game"]["grid_size"] = [args.grid, args.grid]
    if args.sub_games:
        cfg.raw["game"]["num_sub_games"] = args.sub_games

    orch = Orchestrator(cfg)
    out = orch.run_match(log_path=args.log)
    summary = out["summary"]
    print("\n=== MATCH SUMMARY ===")
    for sg in summary["sub_games"]:
        print(
            f"  sub-game {sg['index']} [{sg.get('our_role','-')}]: {sg['outcome']:9s} "
            f"cop={sg['cop_points']:2d} thief={sg['thief_points']:2d} rounds={sg['rounds']}"
        )
    print(
        f"  TOTALS  cop={summary['totals']['cop']}  thief={summary['totals']['thief']}  "
        f"our_total={summary['our_total']}"
    )
    print(f"  log:    {out['log_file']}")
    print(f"  report: {out['report_file']}")

    if args.email:
        from ..mailer import send_report

        status = send_report(cfg, out["report"], subject_suffix="internal self-play result")
        print(f"  email:  {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

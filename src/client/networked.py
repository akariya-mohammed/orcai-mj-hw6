"""Networked cross-group orchestrator (the bonus path).

Drives a 6-microgame match across **MCP servers reached over the wire** via a
FastMCP ``Client``. Each turn it calls the mover's ``my_move`` tool (which returns
the agent's natural-language message), relays that message to the opponent's
``observe`` tool, and reads the resulting status — exactly the loopback flow, now
distributed.

Role rotation for the bonus: sub-games 1–3 our group is **cop** (our cop server
vs the partner's thief server); 4–6 we are **thief** (partner's cop vs our
thief). A group's total is the points it earned in the role it held each game.

A *target* is anything FastMCP's ``Client`` accepts: a URL string
(``http://host:port/mcp``) for a real remote server, or an in-process FastMCP
server object for the offline self-test (``--selftest``) that proves the path
without a daemon or a partner.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import random
from typing import Any

from ..config import AppConfig, load_config
from ..engine.game import Role, Status, new_sub_game
from ..engine.scoring import Match, SubGameResult, score_sub_game, summarize_match
from ..report import build_bonus_report
from ..report.logbook import LogBook

logger = logging.getLogger(__name__)


def _extract(result: Any) -> dict[str, Any]:
    """Pull the tool's dict return out of a FastMCP CallToolResult (version-robust)."""
    for attr in ("data", "structured_content", "structuredContent"):
        val = getattr(result, attr, None)
        if isinstance(val, dict):
            return val
    # Fallback: first text content block parsed as JSON.
    content = getattr(result, "content", None)
    if content:
        import json

        text = getattr(content[0], "text", None)
        if text:
            return json.loads(text)
    raise RuntimeError(f"could not extract dict from tool result: {result!r}")


async def _call(client, tool: str, **args) -> dict[str, Any]:
    return _extract(await client.call_tool(tool, args))


async def _play_sub_game(cop_client, thief_client, *, start, cop_token, thief_token, log, index):
    await _call(cop_client, "setup", cop=list(start[0]), thief=list(start[1]), token=cop_token)
    snap = await _call(
        thief_client, "setup", cop=list(start[0]), thief=list(start[1]), token=thief_token
    )
    turn = snap["snapshot"]["turn"]
    status = snap["snapshot"]["status"]
    rounds = 0
    log.write("setup", sub_game=index, start={"cop": list(start[0]), "thief": list(start[1])})

    while status == Status.PLAYING.value:
        if turn == Role.COP.value:
            out = await _call(cop_client, "my_move", token=cop_token)
            await _call(
                thief_client, "observe", message=out["message"], mover="cop", token=thief_token
            )
        else:
            out = await _call(thief_client, "my_move", token=thief_token)
            await _call(
                cop_client, "observe", message=out["message"], mover="thief", token=cop_token
            )
        status = out["status"]
        turn = out["snapshot"]["turn"]
        rounds = out["snapshot"]["move_count"]
        log.write(
            "turn",
            sub_game=index,
            mover=("cop" if out["message"][:3].lower() == "cop" else "thief"),
            message=out["message"],
            **out["snapshot"],
        )

    return Status(status), rounds


async def run_networked_match(
    cfg: AppConfig,
    *,
    our_cop,
    our_thief,
    opp_cop,
    opp_thief,
    tokens: dict[str, str],
    opponent_meta: dict[str, Any],
    log_path: str | None = None,
) -> dict[str, Any]:
    """Play the cross-group match across MCP targets; return summary + bonus report."""
    from fastmcp import Client

    rng = random.Random(cfg.strategy.get("seed", 7))
    schedule = [Role.COP, Role.COP, Role.COP, Role.THIEF, Role.THIEF, Role.THIEF]
    match = Match()
    g = cfg.game
    log_file = log_path or str(cfg.path("logs") / "bonus-match.jsonl")

    with LogBook(log_file) as log:
        log.write("bonus_match_start", schedule=[r.value for r in schedule], grid=g["grid_size"])
        for i, our_role in enumerate(schedule, start=1):
            if our_role is Role.COP:
                cop_t, thief_t = our_cop, opp_thief
                cop_tok, thief_tok = tokens["our_cop"], tokens["opp_thief"]
            else:
                cop_t, thief_t = opp_cop, our_thief
                cop_tok, thief_tok = tokens["opp_cop"], tokens["our_thief"]

            sub = new_sub_game(
                rows=g["grid_size"][0],
                cols=g["grid_size"][1],
                origin=g["origin"],
                diagonal=g["diagonal_moves"],
                max_moves=g["max_moves"],
                max_barriers=g["max_barriers"],
                thief_moves_first=g["thief_moves_first"],
                rng=rng,
            )
            async with Client(cop_t) as cc, Client(thief_t) as tc:
                status, rounds = await _play_sub_game(
                    cc,
                    tc,
                    start=(sub.cop, sub.thief),
                    cop_token=cop_tok,
                    thief_token=thief_tok,
                    log=log,
                    index=i,
                )
            cop_pts, thief_pts = score_sub_game(status, cfg.scoring)
            match.add(SubGameResult(i, our_role, status, cop_pts, thief_pts, rounds))
            logger.info(
                "bonus sub-game %d (%s): %s  cop=%d thief=%d rounds=%d",
                i,
                our_role.value,
                status.value,
                cop_pts,
                thief_pts,
                rounds,
            )

        summary = summarize_match(match)
        # Per-group totals: group_1 = us (points in the role we held); group_2 = them.
        g1 = sum(
            (r.cop_points if r.our_role is Role.COP else r.thief_points) for r in match.results
        )
        g2 = sum(
            (r.thief_points if r.our_role is Role.COP else r.cop_points) for r in match.results
        )
        totals_by_group = {"group_1": g1, "group_2": g2}
        bonus_claim = "group_1" if g1 > g2 else ("group_2" if g2 > g1 else "tie")
        log.write(
            "bonus_match_end", totals_by_group=totals_by_group, bonus_claim=bonus_claim, **summary
        )

    from .orchestrator import _now_iso

    report = build_bonus_report(
        cfg,
        summary,
        our_role_schedule=[r.value for r in schedule],
        opponent=opponent_meta,
        totals_by_group=totals_by_group,
        bonus_claim=bonus_claim,
        mutual_agreement=True,
        generated_at=_now_iso(cfg),
    )
    import json

    report_path = cfg.path("artefacts") / "bonus_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "summary": summary,
        "report": report,
        "totals_by_group": totals_by_group,
        "bonus_claim": bonus_claim,
        "log_file": log_file,
        "report_file": str(report_path),
    }


def _selftest_targets(cfg):
    """Build two in-process FastMCP servers (cop, thief) for an offline self-test."""
    from ..servers.app import build_mcp_server

    cop_srv, _ = build_mcp_server(Role.COP, cfg)
    thief_srv, _ = build_mcp_server(Role.THIEF, cfg)
    return cop_srv, thief_srv


def main(argv: list[str] | None = None) -> int:
    import os

    parser = argparse.ArgumentParser(description="Run the cross-group (bonus) networked match.")
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="play against our own in-process servers (no partner, no network)",
    )
    parser.add_argument("--provider", help="override llm.provider (e.g. mock)")
    parser.add_argument("--our-cop-url")
    parser.add_argument("--our-thief-url")
    parser.add_argument("--opp-cop-url")
    parser.add_argument("--opp-thief-url")
    parser.add_argument("--email", action="store_true")
    parser.add_argument("--to-self", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s :: %(message)s",
        datefmt="%H:%M:%S",
    )
    cfg = load_config()
    if args.provider:
        cfg.raw["llm"]["provider"] = args.provider

    our_cop_tok = os.environ.get(cfg.servers["cop"]["token_env"], "")
    our_thief_tok = os.environ.get(cfg.servers["thief"]["token_env"], "")
    opp_tok = os.environ.get(cfg.bonus["opponent"].get("token_env", "OPPONENT_MCP_TOKEN"), "")
    tokens = {
        "our_cop": our_cop_tok,
        "our_thief": our_thief_tok,
        # Partner token if provided; else fall back to ours (covers the self-over-HTTP test).
        "opp_cop": opp_tok or our_cop_tok,
        "opp_thief": opp_tok or our_thief_tok,
    }

    if args.selftest:
        cfg.raw["llm"]["provider"] = cfg.llm["provider"] if args.provider else "mock"
        cop_srv, thief_srv = _selftest_targets(cfg)
        our_cop = opp_cop = cop_srv
        our_thief = opp_thief = thief_srv
        opponent_meta = {
            "group_code": cfg.identity.get("group_code", ""),
            "group_name": "SELFTEST (in-process)",
            "members": [],
        }
    else:
        our_cop = args.our_cop_url or "http://{host}:{port}/mcp".format(**cfg.servers["cop"])
        our_thief = args.our_thief_url or "http://{host}:{port}/mcp".format(**cfg.servers["thief"])
        opp_cop = args.opp_cop_url or cfg.bonus["opponent"].get("cop_url") or our_cop
        opp_thief = args.opp_thief_url or cfg.bonus["opponent"].get("thief_url") or our_thief
        opponent_meta = {
            "group_code": "partner",
            "cop_url": opp_cop,
            "thief_url": opp_thief,
            "our_cop_url": our_cop,
            "our_thief_url": our_thief,
        }

    out = asyncio.run(
        run_networked_match(
            cfg,
            our_cop=our_cop,
            our_thief=our_thief,
            opp_cop=opp_cop,
            opp_thief=opp_thief,
            tokens=tokens,
            opponent_meta=opponent_meta,
        )
    )

    print("\n=== BONUS MATCH SUMMARY ===")
    for sg in out["summary"]["sub_games"]:
        print(
            f"  sub-game {sg['index']} [{sg.get('our_role','-')}]: {sg['outcome']:9s} rounds={sg['rounds']}"
        )
    print(f"  totals_by_group={out['totals_by_group']}  bonus_claim={out['bonus_claim']}")
    print(f"  log:    {out['log_file']}")
    print(f"  report: {out['report_file']}")

    if args.email:
        from ..mailer import send_report

        status = send_report(
            cfg, out["report"], subject_suffix="bonus cross-group result", to_self=args.to_self
        )
        print(f"  email:  {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

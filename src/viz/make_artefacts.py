"""Generate committed artefacts for the report (UI/UX + RL visualizations).

    python -m src.viz.make_artefacts

Produces under ``artefacts/``:
  * sample_board.png            — a played-out sub-game (cop/thief trails, barriers)
  * qtable_thief_heatmap.png    — learned thief evasion value map
  * qtable_cop_heatmap.png      — learned cop pursuit value map
  * internal_report.json        — the JSON email body (dry-run)
  * email_dry_run.json          — the rendered outgoing email body
And copies a full match log to ``logs/sample-match.jsonl``.
"""

from __future__ import annotations

import random
import shutil

from ..config import load_config
from ..engine.game import Role, Status, new_sub_game
from ..strategy import make_decider
from ..strategy.qlearning import QConfig, QLearner
from .board_render import render_board
from .qtable_heatmap import render_qtable_heatmap


def _play_with_trails(cfg, rng):
    g = cfg.game
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
    cop_decide = make_decider(Role.COP, cfg, rng=rng)
    thief_decide = make_decider(Role.THIEF, cfg, rng=rng)
    cop_trail = [sub.cop]
    thief_trail = [sub.thief]
    while sub.status is Status.PLAYING:
        role = sub.turn
        move = (cop_decide if role is Role.COP else thief_decide)(sub, role)
        sub.apply(role, move)
        cop_trail.append(sub.cop)
        thief_trail.append(sub.thief)
    return sub, cop_trail, thief_trail


def main() -> None:
    cfg = load_config()
    cfg.raw["llm"]["provider"] = "mock"
    art = cfg.path("artefacts")
    art.mkdir(parents=True, exist_ok=True)
    rng = random.Random(cfg.strategy.get("seed", 7))

    # 1) sample board image from a played sub-game
    sub, cop_trail, thief_trail = _play_with_trails(cfg, rng)
    g = cfg.game
    render_board(
        g["grid_size"][0],
        g["grid_size"][1],
        g["origin"],
        sub.cop,
        sub.thief,
        sorted(sub.board.barriers),
        title=f"Sample sub-game — {sub.status.value} in {sub.move_count} rounds",
        out_path=art / "sample_board.png",
        cop_trail=cop_trail,
        thief_trail=thief_trail,
    )
    print("wrote", art / "sample_board.png")

    # 2) Q-table heatmaps (train compactly for a quick artefact)
    rows, cols = g["grid_size"]
    qcfg = QConfig(train_episodes=1500)
    centre = (g["origin"] + rows // 2, g["origin"] + cols // 2)

    thief_q = QLearner(
        Role.THIEF,
        rows,
        cols,
        origin=g["origin"],
        diagonal=g["diagonal_moves"],
        max_moves=g["max_moves"],
        config=qcfg,
    )
    thief_q.train()
    render_qtable_heatmap(
        thief_q.value_grid(centre),
        centre,
        g["origin"],
        "Thief Q-values (evasion)",
        art / "qtable_thief_heatmap.png",
    )
    print("wrote", art / "qtable_thief_heatmap.png")

    cop_q = QLearner(
        Role.COP,
        rows,
        cols,
        origin=g["origin"],
        diagonal=g["diagonal_moves"],
        max_moves=g["max_moves"],
        config=qcfg,
    )
    cop_q.train()
    render_qtable_heatmap(
        cop_q.value_grid(centre),
        centre,
        g["origin"],
        "Cop Q-values (pursuit)",
        art / "qtable_cop_heatmap.png",
    )
    print("wrote", art / "qtable_cop_heatmap.png")

    # 3) a full match -> report + sample log, plus dry-run email
    from ..client.orchestrator import Orchestrator
    from ..mailer import send_report

    orch = Orchestrator(cfg)
    out = orch.run_match()
    sample_log = cfg.path("logs") / "sample-match.jsonl"
    shutil.copyfile(out["log_file"], sample_log)
    print("wrote", sample_log)
    print("wrote", out["report_file"])

    status = send_report(cfg, out["report"], subject_suffix="internal self-play result")
    print("email dry-run ->", status.get("saved"))


if __name__ == "__main__":
    main()

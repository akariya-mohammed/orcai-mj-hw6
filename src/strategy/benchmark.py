"""Strategy tournament — quantify who wins, to justify our agent choice.

Runs many randomized sub-games between a chosen cop strategy and thief strategy
and reports the cop's capture rate vs the thief's survival rate. This is the
evidence that our agents beat a typical (heuristic) opponent in both roles.

    python -m src.strategy.benchmark
    python -m src.strategy.benchmark --games 200 --grid 5
"""

from __future__ import annotations

import argparse
import random

from ..engine.game import Role, Status, new_sub_game
from ..engine.scoring import run_sub_game
from . import heuristic
from .minimax import make_minimax
from .qlearning import QConfig, QLearner

_QCACHE: dict = {}


def build_decider(kind: str, role: Role, *, grid: int, max_moves: int, depth: int, seed: int):
    rng = random.Random(seed + (0 if role is Role.COP else 1))
    if kind == "heuristic":
        return heuristic.make_heuristic(role, rng)
    if kind == "minimax":
        return make_minimax(role, depth, rng)
    if kind == "qlearning":
        key = (kind, role, grid)
        ql = _QCACHE.get(key)
        if ql is None:
            ql = QLearner(
                role,
                grid,
                grid,
                max_moves=max_moves,
                config=QConfig(train_episodes=2000),
                seed=seed,
            )
            ql.train()
            _QCACHE[key] = ql
        return ql.decide
    raise ValueError(f"unknown strategy: {kind}")


def benchmark(
    cop_kind: str,
    thief_kind: str,
    *,
    games: int = 100,
    grid: int = 5,
    max_moves: int = 25,
    max_barriers: int = 5,
    depth: int = 4,
    seed: int = 7,
) -> dict:
    cop_wins = 0
    rng = random.Random(seed)
    cop_decide = build_decider(
        cop_kind, Role.COP, grid=grid, max_moves=max_moves, depth=depth, seed=seed
    )
    thief_decide = build_decider(
        thief_kind, Role.THIEF, grid=grid, max_moves=max_moves, depth=depth, seed=seed
    )
    total_rounds = 0
    for _ in range(games):
        sub = new_sub_game(
            rows=grid, cols=grid, max_moves=max_moves, max_barriers=max_barriers, rng=rng
        )
        status = run_sub_game(sub, cop_decide, thief_decide)
        total_rounds += sub.move_count
        if status is Status.COP_WIN:
            cop_wins += 1
    return {
        "cop": cop_kind,
        "thief": thief_kind,
        "games": games,
        "cop_win_rate": round(cop_wins / games, 3),
        "thief_survival_rate": round((games - cop_wins) / games, 3),
        "avg_rounds": round(total_rounds / games, 1),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cops & Robbers strategy tournament.")
    p.add_argument("--games", type=int, default=100)
    p.add_argument("--grid", type=int, default=5)
    p.add_argument("--depth", type=int, default=4)
    args = p.parse_args(argv)

    kw = {"games": args.games, "grid": args.grid, "depth": args.depth}
    matchups = [
        ("minimax", "heuristic", "OUR cop vs THEIR thief  (we play cop)"),
        ("heuristic", "minimax", "THEIR cop vs OUR thief  (we play thief)"),
        ("heuristic", "heuristic", "baseline: heuristic vs heuristic"),
        ("minimax", "minimax", "minimax vs minimax"),
    ]
    print(
        f"\n=== Strategy tournament ({args.games} games, {args.grid}x{args.grid}, depth {args.depth}) ==="
    )
    print(f"{'matchup':<40} {'cop win%':>9} {'thief surv%':>12} {'avg rounds':>11}")
    for cop_kind, thief_kind, label in matchups:
        r = benchmark(cop_kind, thief_kind, **kw)
        print(
            f"{label:<40} {r['cop_win_rate']*100:>8.0f}% {r['thief_survival_rate']*100:>11.0f}% {r['avg_rounds']:>11}"
        )
    print(
        "\nWe play 3 sub-games as cop + 3 as thief. Higher 'cop win%' (row 1) and "
        "higher 'thief surv%' (row 2) both push points to US."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

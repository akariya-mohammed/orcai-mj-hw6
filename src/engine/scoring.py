"""Scoring and the full-match (6 sub-game) driver.

Scoring follows the assignment table (per sub-game):

    | outcome    | cop pts | thief pts |
    | Cop wins   |   20    |     5     |
    | Thief wins |    5    |    10     |

A full game is 6 sub-games. In cross-group play a group plays 3 as cop and 3 as
thief; a group's total is the sum of the points it earned in the role it held
each sub-game (max 90 = 3x20 + 3x10, min 30 = 6x5).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .game import Move, Role, Status, SubGame

# A decision function: given the live sub-game and which role is to move, pick a Move.
DecideFn = Callable[[SubGame, Role], Move]


def score_sub_game(status: Status, scoring: dict[str, int]) -> tuple[int, int]:
    """Return ``(cop_points, thief_points)`` for a finished sub-game."""
    if status is Status.COP_WIN:
        return scoring["cop_win"], scoring["thief_loss"]
    if status is Status.THIEF_WIN:
        return scoring["cop_loss"], scoring["thief_win"]
    raise ValueError(f"sub-game not finished: {status}")


def run_sub_game(
    sub: SubGame,
    cop_decide: DecideFn,
    thief_decide: DecideFn,
    *,
    on_step: Callable[[SubGame], None] | None = None,
) -> Status:
    """Drive one sub-game to completion using the two decision functions."""
    guard = 0
    hard_cap = sub.max_moves * 4 + 10  # safety against a misbehaving strategy
    while sub.status is Status.PLAYING:
        role = sub.turn
        decide = cop_decide if role is Role.COP else thief_decide
        move = decide(sub, role)
        sub.apply(role, move)
        if on_step is not None:
            on_step(sub)
        guard += 1
        if guard > hard_cap:  # pragma: no cover - defensive
            raise RuntimeError("sub-game exceeded safety cap; strategy likely stuck")
    return sub.status


@dataclass
class SubGameResult:
    index: int
    our_role: Role | None
    status: Status
    cop_points: int
    thief_points: int
    rounds: int

    def to_dict(self) -> dict[str, Any]:
        d = {
            "index": self.index,
            "outcome": self.status.value,
            "cop_points": self.cop_points,
            "thief_points": self.thief_points,
            "rounds": self.rounds,
        }
        if self.our_role is not None:
            d["our_role"] = self.our_role.value
            d["our_points"] = self.cop_points if self.our_role is Role.COP else self.thief_points
        return d


@dataclass
class Match:
    """Aggregates the results of a 6-sub-game game."""

    results: list[SubGameResult] = field(default_factory=list)

    def add(self, result: SubGameResult) -> None:
        self.results.append(result)

    @property
    def cop_total(self) -> int:
        return sum(r.cop_points for r in self.results)

    @property
    def thief_total(self) -> int:
        return sum(r.thief_points for r in self.results)

    def our_total(self) -> int:
        """Sum of points earned in the role our group held each sub-game."""
        return sum(
            (r.cop_points if r.our_role is Role.COP else r.thief_points)
            for r in self.results
            if r.our_role is not None
        )


def summarize_match(match: Match) -> dict[str, Any]:
    """A plain-dict summary suitable for logs and the JSON report body."""
    return {
        "sub_games": [r.to_dict() for r in match.results],
        "totals": {"cop": match.cop_total, "thief": match.thief_total},
        "our_total": match.our_total(),
        "num_sub_games": len(match.results),
    }

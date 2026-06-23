"""Deterministic pursuit/evasion heuristics.

These always produce a legal move and give the LLM-narrated game something
sensible to do even without any training. They are also the opponent used while
training the Q-learner, and the fallback when the Q-table has never seen a state.
"""

from __future__ import annotations

import random

from ..engine.board import chebyshev
from ..engine.game import Move, Role, SubGame


def _mobility(sub: SubGame, cell: tuple[int, int]) -> int:
    """How many free neighbours a cell has — a proxy for "not getting cornered"."""
    return len(sub.board.neighbors(cell, free_only=True))


def thief_decide(sub: SubGame, rng: random.Random) -> Move:
    """Thief: maximise distance from the cop, breaking ties toward open space."""
    legal = [m for m in sub.legal_moves(Role.THIEF) if m.kind == "move"]
    if not legal:  # trapped — engine will score it as a capture
        raise RuntimeError("thief has no legal move")

    def key(m: Move) -> tuple[int, int, float]:
        return (chebyshev(m.cell, sub.cop), _mobility(sub, m.cell), rng.random())

    return max(legal, key=key)


def cop_decide(sub: SubGame, rng: random.Random) -> Move:
    """Cop: close the gap; if it can't, drop a barrier on the thief's best escape."""
    moves = [m for m in sub.legal_moves(Role.COP) if m.kind == "move"]
    barriers = [m for m in sub.legal_moves(Role.COP) if m.kind == "barrier"]
    cur = chebyshev(sub.cop, sub.thief)

    if moves:
        best = min(chebyshev(m.cell, sub.thief) for m in moves)
        closing = [m for m in moves if chebyshev(m.cell, sub.thief) == best]
        if best < cur:
            return rng.choice(closing)

    # Cannot get closer this turn: try to cut off the thief's likely escape.
    if barriers:
        thief_escapes = sub.board.neighbors(sub.thief, free_only=True)
        if thief_escapes:
            # The cell the thief would most like to flee to (farthest from cop).
            target = max(thief_escapes, key=lambda c: chebyshev(c, sub.cop))
            for b in barriers:
                if b.cell == target:
                    return b

    if moves:
        # Hold the line: pick a closest-distance move (keep pressure on).
        best = min(chebyshev(m.cell, sub.thief) for m in moves)
        closing = [m for m in moves if chebyshev(m.cell, sub.thief) == best]
        return rng.choice(closing)
    if barriers:
        return rng.choice(barriers)
    raise RuntimeError("cop has no legal action")


def make_heuristic(role: Role, rng: random.Random):
    """Return a ``DecideFn`` closure for ``role`` bound to ``rng``."""

    def decide(sub: SubGame, r: Role) -> Move:
        return cop_decide(sub, rng) if r is Role.COP else thief_decide(sub, rng)

    return decide

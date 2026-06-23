"""Adversarial search strategy — depth-limited minimax with alpha-beta pruning.

This is the "brute-force" win-path the lecturer hinted at. Both agents search a
few plies ahead: the **cop maximizes** a board evaluation (small distance, thief
cornered, capture soon) and the **thief minimizes** it (stay far, stay mobile,
run out the clock). Barrier placement is part of the cop's search, so it learns
to wall the thief into a corner rather than chase forever.

Deterministic and explainable — no training required. Selectable per role in
``config.yaml`` (``strategy.cop: minimax``).
"""

from __future__ import annotations

import math
import random

from ..engine.board import chebyshev
from ..engine.game import Move, Role, Status, SubGame

_BIG = 10_000


def _nearest_edge_distance(sub: SubGame, cell: tuple[int, int]) -> int:
    b = sub.board
    return min(cell[0] - b.origin, b.max_row - cell[0], cell[1] - b.origin, b.max_col - cell[1])


def evaluate(sub: SubGame) -> float:
    """Board value from the COP's perspective (higher = better for the cop)."""
    if sub.status is Status.COP_WIN:
        return _BIG - sub.move_count  # capture, sooner is better
    if sub.status is Status.THIEF_WIN:
        return -_BIG + sub.move_count  # escape, later is "less bad" for cop

    dist = chebyshev(sub.cop, sub.thief)
    thief_mobility = len(sub.board.neighbors(sub.thief, free_only=True))
    thief_edge = _nearest_edge_distance(sub, sub.thief)  # small = cornered = good for cop
    # Cop wants: close distance, low thief mobility, thief near a wall.
    return -10.0 * dist - 2.0 * thief_mobility - 1.5 * thief_edge


def evaluate_thief(sub: SubGame) -> float:
    """Board value from the THIEF's perspective (higher = better for the thief).

    Not just the negation of the cop eval: the thief also values **running the
    clock** (``move_count``) — surviving moves is the actual win condition — so a
    depth-limited search prefers the line that delays capture longest.
    """
    if sub.status is Status.THIEF_WIN:
        return _BIG + sub.move_count
    if sub.status is Status.COP_WIN:
        return -_BIG + 100.0 * sub.move_count  # delaying capture is strongly better

    dist = chebyshev(sub.cop, sub.thief)
    thief_mobility = len(sub.board.neighbors(sub.thief, free_only=True))
    thief_edge = _nearest_edge_distance(sub, sub.thief)  # large = central = safe
    return 10.0 * dist + 2.0 * thief_mobility + 1.5 * thief_edge + 5.0 * sub.move_count


def _ordered_moves(sub: SubGame, role: Role) -> list[Move]:
    moves = sub.legal_moves(role)
    # Move ordering helps alpha-beta: cop tries closing moves first, thief fleeing.
    if role is Role.COP:
        moves.sort(key=lambda m: chebyshev(m.cell, sub.thief))
    else:
        moves.sort(key=lambda m: -chebyshev(m.cell, sub.cop))
    return moves


def _search(sub: SubGame, depth: int, alpha: float, beta: float, max_role: Role, eval_fn) -> float:
    """Alpha-beta where ``max_role`` maximizes ``eval_fn`` and the other side minimizes."""
    if sub.status is not Status.PLAYING or depth == 0:
        return eval_fn(sub)

    if sub.turn is max_role:  # maximizing player's turn
        best = -math.inf
        for m in _ordered_moves(sub, sub.turn):
            child = sub.clone()
            child.apply(sub.turn, m, validate=False)
            best = max(best, _search(child, depth - 1, alpha, beta, max_role, eval_fn))
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best
    else:  # opponent minimizes the maximizer's eval
        best = math.inf
        for m in _ordered_moves(sub, sub.turn):
            child = sub.clone()
            child.apply(sub.turn, m, validate=False)
            best = min(best, _search(child, depth - 1, alpha, beta, max_role, eval_fn))
            beta = min(beta, best)
            if alpha >= beta:
                break
        return best


def best_move(sub: SubGame, role: Role, depth: int, rng: random.Random) -> Move:
    """Pick ``role``'s best action by alpha-beta search to ``depth`` plies.

    Each role maximizes its *own* evaluation (cop: capture; thief: survive) — so
    minimax is strong in both roles, not just the cop's.
    """
    eval_fn = evaluate if role is Role.COP else evaluate_thief
    scored: list[tuple[float, Move]] = []
    for m in _ordered_moves(sub, role):
        child = sub.clone()
        child.apply(role, m, validate=False)
        scored.append((_search(child, depth - 1, -math.inf, math.inf, role, eval_fn), m))

    best_val = max(s for s, _ in scored)
    candidates = [m for s, m in scored if abs(s - best_val) < 1e-9]
    return rng.choice(candidates)


def make_minimax(role: Role, depth: int, rng: random.Random):
    """Return a ``DecideFn`` for ``role`` using minimax to ``depth`` plies."""

    def decide(sub: SubGame, r: Role) -> Move:
        return best_move(sub, r, depth, rng)

    return decide

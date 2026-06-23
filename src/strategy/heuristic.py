"""Deterministic pursuit/evasion heuristics.

These always produce a legal move and give the LLM-narrated game something
sensible to do even without any training. They are also the opponent used while
training the Q-learner, and the fallback when the Q-table has never seen a state.
"""

from __future__ import annotations

import random
from collections import deque

from ..engine.board import chebyshev
from ..engine.game import Move, Role, SubGame


def _mobility(sub: SubGame, cell: tuple[int, int]) -> int:
    """How many free neighbours a cell has — a proxy for "not getting cornered"."""
    return len(sub.board.neighbors(cell, free_only=True))


def _centrality(sub: SubGame, cell: tuple[int, int]) -> int:
    """Distance to the nearest wall — higher = more central = harder to corner."""
    b = sub.board
    return min(cell[0] - b.origin, b.max_row - cell[0], cell[1] - b.origin, b.max_col - cell[1])


def _bfs_dist(sub: SubGame, source: tuple[int, int]) -> dict[tuple[int, int], int]:
    """King-move BFS distance from ``source`` over free cells."""
    dist = {source: 0}
    q = deque([source])
    while q:
        cur = q.popleft()
        for nxt in sub.board.neighbors(cur, free_only=True):
            if nxt not in dist:
                dist[nxt] = dist[cur] + 1
                q.append(nxt)
    return dist


def _voronoi_area(sub: SubGame, thief_cell: tuple[int, int], cop_cell: tuple[int, int]) -> int:
    """Cells the thief reaches strictly before the cop — its "room to run".

    This is the classic pursuit-evasion area-control heuristic: maximising the
    region you own keeps escape space and delays capture.
    """
    d_thief = _bfs_dist(sub, thief_cell)
    d_cop = _bfs_dist(sub, cop_cell)
    owned = 0
    for cell, dt in d_thief.items():
        dc = d_cop.get(cell)
        if dc is None or dt < dc:
            owned += 1
    return owned


def thief_decide(sub: SubGame, rng: random.Random) -> Move:
    """Thief: maximise *area control* first, then distance / centrality / mobility.

    Area control (Voronoi region the thief reaches before the cop) is a much
    stronger survival signal than raw distance: it keeps the thief in the largest
    open region and away from being walled into a corner, which is what runs the
    clock out to the move limit. Distance, centrality and mobility break ties.
    """
    legal = [m for m in sub.legal_moves(Role.THIEF) if m.kind == "move"]
    if not legal:  # trapped — engine will score it as a capture
        raise RuntimeError("thief has no legal move")

    def key(m: Move) -> tuple[int, int, int, int, float]:
        # Distance first (don't get caught), then area control (keep room to run),
        # then centrality and mobility.
        return (
            chebyshev(m.cell, sub.cop),
            _voronoi_area(sub, m.cell, sub.cop),
            _centrality(sub, m.cell),
            _mobility(sub, m.cell),
            rng.random(),
        )

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

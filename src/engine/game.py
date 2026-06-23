"""Game state, rules, and the single-race / full-match state machines.

The rules implemented here are the assignment's defaults (they can be *extended*
by mutual agreement between groups, never overridden):

* Cop and Thief move one step per turn, in any allowed direction.
* The Cop wins by occupying the Thief's cell (capture).
* The Thief wins by surviving ``max_moves`` rounds without being caught.
* The Cop may, instead of moving, place a barrier on an adjacent free cell
  (staying put); at most ``max_barriers`` over the sub-game.
* Neither agent may enter a barrier. A Thief with no legal move is caught.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .board import Board, Cell, chebyshev, delta_to_direction


class Role(str, Enum):
    COP = "cop"
    THIEF = "thief"

    @property
    def other(self) -> Role:
        return Role.THIEF if self is Role.COP else Role.COP


class Status(str, Enum):
    SETUP = "setup"
    PLAYING = "playing"
    COP_WIN = "cop_win"
    THIEF_WIN = "thief_win"


@dataclass(frozen=True)
class Move:
    """A single action. ``kind`` is ``"move"`` or ``"barrier"``.

    For a ``move`` the agent relocates to ``cell``. For a ``barrier`` (cop only)
    the agent stays put and marks ``cell`` impassable.
    """

    kind: str
    cell: Cell
    direction: str | None = None

    def describe(self) -> str:
        if self.kind == "barrier":
            return f"place barrier at {self.cell}"
        d = f" ({self.direction})" if self.direction else ""
        return f"move to {self.cell}{d}"


@dataclass
class SubGame:
    """One race (sub-game): a state machine over a single board."""

    board: Board
    cop: Cell
    thief: Cell
    max_moves: int
    max_barriers: int
    barriers_left: int
    thief_moves_first: bool = True
    move_count: int = 0
    status: Status = Status.PLAYING
    turn: Role = Role.THIEF
    history: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.turn = Role.THIEF if self.thief_moves_first else Role.COP
        if self.cop == self.thief:
            self.status = Status.COP_WIN

    # --- queries -----------------------------------------------------------
    def position(self, role: Role) -> Cell:
        return self.cop if role is Role.COP else self.thief

    def legal_moves(self, role: Role) -> list[Move]:
        """All legal actions for ``role`` from the current state."""
        moves: list[Move] = []
        pos = self.position(role)
        for name in self.board.direction_names():
            nxt = self.board.step(pos, name)
            if self.board.is_free(nxt):
                moves.append(Move("move", nxt, name))
        if role is Role.COP and self.barriers_left > 0:
            # Barriers go on an adjacent free cell that is not occupied.
            for name in self.board.direction_names():
                nxt = self.board.step(pos, name)
                if (
                    self.board.in_bounds(nxt)
                    and not self.board.is_barrier(nxt)
                    and nxt != self.thief
                    and nxt != self.cop
                ):
                    moves.append(Move("barrier", nxt, name))
        return moves

    def is_legal(self, role: Role, move: Move) -> bool:
        return any(m.kind == move.kind and m.cell == move.cell for m in self.legal_moves(role))

    # --- transitions -------------------------------------------------------
    def clone(self) -> SubGame:
        """A cheap copy for look-ahead search (no history carried over)."""
        board = Board(
            self.board.rows,
            self.board.cols,
            origin=self.board.origin,
            diagonal=self.board.diagonal,
            barriers=set(self.board.barriers),
        )
        c = SubGame(
            board=board,
            cop=self.cop,
            thief=self.thief,
            max_moves=self.max_moves,
            max_barriers=self.max_barriers,
            barriers_left=self.barriers_left,
            thief_moves_first=self.thief_moves_first,
        )
        c.move_count = self.move_count
        c.status = self.status
        c.turn = self.turn
        return c

    def apply(self, role: Role, move: Move, *, validate: bool = True) -> None:
        """Apply ``role``'s action, advance the turn, and update terminal status.

        ``validate=False`` skips the legality re-check — used by search, which only
        ever applies moves it generated from :meth:`legal_moves`.
        """
        if self.status is not Status.PLAYING:
            raise RuntimeError(f"sub-game already finished: {self.status}")
        if role is not self.turn:
            raise RuntimeError(f"not {role}'s turn (turn={self.turn})")
        if validate and not self.is_legal(role, move):
            raise ValueError(f"illegal {role} action: {move.describe()}")

        if move.kind == "move":
            if role is Role.COP:
                self.cop = move.cell
            else:
                self.thief = move.cell
        elif move.kind == "barrier":
            self.board.barriers.add(move.cell)
            self.barriers_left -= 1

        self._record(role, move)

        # Capture check after every action.
        if self.cop == self.thief:
            self.status = Status.COP_WIN
            return

        # Advance turn; a round completes after the cop acts.
        self.turn = role.other
        round_done = (role is Role.COP) if self.thief_moves_first else (role is Role.THIEF)
        if round_done:
            self.move_count += 1
            if self.move_count >= self.max_moves:
                self.status = Status.THIEF_WIN
                return

        # A thief with no legal move is trapped → caught.
        if self.turn is Role.THIEF and not self.legal_moves(Role.THIEF):
            self.status = Status.COP_WIN

    def _record(self, role: Role, move: Move) -> None:
        self.history.append(
            {
                "round": self.move_count,
                "turn": role.value,
                "action": move.kind,
                "cell": list(move.cell),
                "direction": move.direction,
                "cop": list(self.cop),
                "thief": list(self.thief),
                "barriers": [list(b) for b in sorted(self.board.barriers)],
                "barriers_left": self.barriers_left,
                "status": self.status.value,
            }
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "cop": list(self.cop),
            "thief": list(self.thief),
            "barriers": [list(b) for b in sorted(self.board.barriers)],
            "barriers_left": self.barriers_left,
            "move_count": self.move_count,
            "max_moves": self.max_moves,
            "turn": self.turn.value,
            "status": self.status.value,
            "distance": chebyshev(self.cop, self.thief),
        }


def new_sub_game(
    *,
    rows: int,
    cols: int,
    origin: int = 1,
    diagonal: bool = True,
    max_moves: int = 25,
    max_barriers: int = 5,
    thief_moves_first: bool = True,
    cop: Cell | None = None,
    thief: Cell | None = None,
    rng: random.Random | None = None,
) -> SubGame:
    """Factory placing cop & thief on distinct free cells (random unless given)."""
    rng = rng or random.Random()
    board = Board(rows=rows, cols=cols, origin=origin, diagonal=diagonal)
    cells = board.all_cells()
    if cop is None:
        cop = rng.choice(cells)
    if thief is None:
        choices = [c for c in cells if c != cop]
        thief = rng.choice(choices)
    return SubGame(
        board=board,
        cop=cop,
        thief=thief,
        max_moves=max_moves,
        max_barriers=max_barriers,
        barriers_left=max_barriers,
        thief_moves_first=thief_moves_first,
    )


# Re-exported for callers that want the geometry helper without importing board.
__all__ = ["Role", "Status", "Move", "SubGame", "new_sub_game", "delta_to_direction"]

"""The grid board and movement geometry.

A :class:`Cell` is a ``(row, col)`` tuple in board coordinates. By convention the
origin is ``1`` (configurable), so a 5x5 board spans ``(1, 1)`` .. ``(5, 5)``.
Movement is one step in any of the 8 compass directions (diagonals optional).
"""

from __future__ import annotations

from dataclasses import dataclass, field

Cell = tuple[int, int]

# name -> (d_row, d_col). The four cardinal directions first, then diagonals.
DIRECTIONS: dict[str, tuple[int, int]] = {
    "N": (-1, 0),
    "S": (1, 0),
    "E": (0, 1),
    "W": (0, -1),
    "NE": (-1, 1),
    "NW": (-1, -1),
    "SE": (1, 1),
    "SW": (1, -1),
}
CARDINAL = ("N", "S", "E", "W")
DIAGONAL = ("NE", "NW", "SE", "SW")


def delta_to_direction(d_row: int, d_col: int) -> str | None:
    """Map a one-step ``(d_row, d_col)`` delta back to its direction name."""
    for name, delta in DIRECTIONS.items():
        if delta == (d_row, d_col):
            return name
    return None


@dataclass
class Board:
    """A rectangular grid with a set of impassable barrier cells."""

    rows: int
    cols: int
    origin: int = 1
    diagonal: bool = True
    barriers: set[Cell] = field(default_factory=set)

    @property
    def min_coord(self) -> int:
        return self.origin

    @property
    def max_row(self) -> int:
        return self.origin + self.rows - 1

    @property
    def max_col(self) -> int:
        return self.origin + self.cols - 1

    def in_bounds(self, cell: Cell) -> bool:
        r, c = cell
        return self.origin <= r <= self.max_row and self.origin <= c <= self.max_col

    def is_barrier(self, cell: Cell) -> bool:
        return cell in self.barriers

    def is_free(self, cell: Cell) -> bool:
        """In bounds and not a barrier."""
        return self.in_bounds(cell) and not self.is_barrier(cell)

    def direction_names(self) -> tuple[str, ...]:
        return (*CARDINAL, *DIAGONAL) if self.diagonal else CARDINAL

    def step(self, cell: Cell, direction: str) -> Cell:
        """Return the cell reached by moving one step in ``direction``."""
        if direction not in DIRECTIONS:
            raise ValueError(f"unknown direction: {direction!r}")
        if not self.diagonal and direction in DIAGONAL:
            raise ValueError(f"diagonal moves disabled: {direction!r}")
        d_row, d_col = DIRECTIONS[direction]
        return (cell[0] + d_row, cell[1] + d_col)

    def neighbors(self, cell: Cell, *, free_only: bool = True) -> list[Cell]:
        """Adjacent cells one step away. By default only in-bounds, non-barrier ones."""
        out: list[Cell] = []
        for name in self.direction_names():
            nxt = self.step(cell, name)
            if free_only:
                if self.is_free(nxt):
                    out.append(nxt)
            elif self.in_bounds(nxt):
                out.append(nxt)
        return out

    def all_cells(self) -> list[Cell]:
        return [
            (r, c)
            for r in range(self.origin, self.max_row + 1)
            for c in range(self.origin, self.max_col + 1)
        ]


def chebyshev(a: Cell, b: Cell) -> int:
    """Chebyshev distance — the minimum number of 8-direction steps between cells."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

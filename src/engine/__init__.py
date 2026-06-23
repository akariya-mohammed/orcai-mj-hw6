"""Pure-Python game engine: board, rules, state machine, scoring.

No LLM, no network, no I/O — deterministic and fully unit-testable.
"""

from .board import DIRECTIONS, Board, Cell
from .game import Move, Role, Status, SubGame, new_sub_game
from .scoring import Match, SubGameResult, run_sub_game, score_sub_game, summarize_match

__all__ = [
    "Board",
    "Cell",
    "DIRECTIONS",
    "Match",
    "Move",
    "Role",
    "Status",
    "SubGame",
    "SubGameResult",
    "new_sub_game",
    "run_sub_game",
    "score_sub_game",
    "summarize_match",
]

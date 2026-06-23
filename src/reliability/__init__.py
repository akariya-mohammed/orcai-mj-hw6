"""Reliability primitives: a token budget gatekeeper and a hang watchdog.

Ported and adapted from the HW2 multi-agent-debate project. Both are required by
the course rubric and matter doubly here because the game runs autonomously.
"""

from .gatekeeper import BudgetExceeded, TokenGatekeeper
from .watchdog import Watchdog

__all__ = ["BudgetExceeded", "TokenGatekeeper", "Watchdog"]

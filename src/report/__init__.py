"""Result reporting: structured JSON bodies + a JSONL match logbook."""

from .bonus import build_bonus_report
from .internal import build_internal_report
from .logbook import LogBook

__all__ = ["build_internal_report", "build_bonus_report", "LogBook"]

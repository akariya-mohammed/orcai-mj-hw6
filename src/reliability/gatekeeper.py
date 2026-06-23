"""Hard token-budget cap shared across all LLM calls in a run.

Call :meth:`check` before each model call and :meth:`record` after it. Once the
running total reaches the cap, :meth:`check` raises :class:`BudgetExceeded` — the
caller must NOT retry an over-budget call. Thread-safe.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)


class BudgetExceeded(RuntimeError):
    """Raised when the token budget is exhausted."""


class TokenGatekeeper:
    def __init__(self, max_tokens: int, name: str = "game") -> None:
        self.max_tokens = max_tokens
        self.name = name
        self._total = 0
        self._calls = 0
        self._lock = threading.Lock()

    @property
    def total(self) -> int:
        with self._lock:
            return self._total

    def check(self, caller: str = "") -> None:
        with self._lock:
            if self._total >= self.max_tokens:
                raise BudgetExceeded(
                    f"token budget exhausted: {self._total}/{self.max_tokens} "
                    f"(blocked call by {caller or '?'})"
                )

    def record(self, input_tokens: int, output_tokens: int, caller: str = "") -> None:
        with self._lock:
            self._calls += 1
            self._total += int(input_tokens) + int(output_tokens)
            pct = 100.0 * self._total / self.max_tokens if self.max_tokens else 0.0
            logger.info(
                "GATEKEEPER[%s] call#%d by %s: in=%d out=%d total=%d/%d (%.1f%%)",
                self.name,
                self._calls,
                caller or "?",
                input_tokens,
                output_tokens,
                self._total,
                self.max_tokens,
                pct,
            )

    def summary(self) -> dict[str, int]:
        with self._lock:
            return {
                "calls": self._calls,
                "total_tokens": self._total,
                "max_tokens": self.max_tokens,
            }

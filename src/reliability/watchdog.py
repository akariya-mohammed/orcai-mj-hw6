"""A ``threading.Timer`` watchdog that kills a stuck autonomous run.

Windows-friendly (no ``signal.SIGALRM``). ``pet()`` resets the countdown; if the
timer ever fires, the run is considered hung and the process exits non-zero.
Usable as a context manager.
"""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


class Watchdog:
    def __init__(
        self, timeout: float, name: str = "game", on_timeout: Callable[[], None] | None = None
    ) -> None:
        self.timeout = timeout
        self.name = name
        self._on_timeout = on_timeout or self._default_timeout
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def _default_timeout(self) -> None:  # pragma: no cover - process kill
        logger.error("WATCHDOG[%s] timed out after %.0fs — killing run.", self.name, self.timeout)
        os._exit(1)

    def start(self) -> None:
        self.pet()

    def pet(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.timeout, self._on_timeout)
            self._timer.daemon = True
            self._timer.start()

    def stop(self) -> None:
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

    def __enter__(self) -> Watchdog:
        self.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.stop()

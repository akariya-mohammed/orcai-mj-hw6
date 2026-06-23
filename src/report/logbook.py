"""Append-only JSONL match log.

Every game event (setup agreement, each move, each capture/escape, final score)
is written as one JSON line. The log proves the 6 sub-games ran autonomously and
is what we'd show in a dispute. One object per line keeps it greppable and
re-playable without re-running the agents.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class LogBook:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w", encoding="utf-8")
        self.entries: list[dict[str, Any]] = []

    def write(self, kind: str, **fields: Any) -> None:
        entry = {"event": kind, **fields}
        self.entries.append(entry)
        self._fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> LogBook:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

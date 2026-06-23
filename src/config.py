"""Central configuration loader.

Everything that tunes the game lives in ``config.yaml`` — there are no magic
numbers in the source. This module loads that file, loads ``.env`` for secrets,
and exposes a small typed accessor so the rest of the code never reaches for
``os.environ`` or re-parses YAML.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:  # python-dotenv is optional at import time (e.g. minimal CI)
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover

    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(RuntimeError):
    """Raised when the configuration is missing or internally inconsistent."""


@dataclass(frozen=True)
class AppConfig:
    """Parsed view over ``config.yaml`` plus a couple of convenience helpers."""

    raw: dict[str, Any] = field(default_factory=dict)

    # --- section accessors -------------------------------------------------
    @property
    def game(self) -> dict[str, Any]:
        return self.raw["game"]

    @property
    def scoring(self) -> dict[str, int]:
        return self.raw["scoring"]

    @property
    def strategy(self) -> dict[str, Any]:
        return self.raw["strategy"]

    @property
    def llm(self) -> dict[str, Any]:
        return self.raw["llm"]

    @property
    def servers(self) -> dict[str, Any]:
        return self.raw["servers"]

    @property
    def email(self) -> dict[str, Any]:
        return self.raw["email"]

    @property
    def identity(self) -> dict[str, Any]:
        return self.raw["identity"]

    @property
    def bonus(self) -> dict[str, Any]:
        return self.raw["bonus"]

    # --- helpers -----------------------------------------------------------
    def provider(self, name: str | None = None) -> dict[str, Any]:
        """Return the config block for the active (or named) LLM provider."""
        name = name or self.llm["provider"]
        providers = self.raw.get("providers", {})
        if name not in providers:
            raise ConfigError(f"Unknown LLM provider '{name}'. Known: {list(providers)}")
        return {**providers[name], "name": name}

    def api_key(self, provider_name: str | None = None) -> str | None:
        """Resolve the API key for a provider from the environment, if any."""
        block = self.provider(provider_name)
        env_name = block.get("api_key_env")
        return os.environ.get(env_name) if env_name else None

    def path(self, key: str) -> Path:
        """Project-root-anchored path from the ``paths`` section."""
        return PROJECT_ROOT / self.raw.get("paths", {}).get(key, key)


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load ``.env`` (for secrets) then ``config.yaml`` into an :class:`AppConfig`."""
    load_dotenv(PROJECT_ROOT / ".env")
    cfg_path = Path(path) if path else PROJECT_ROOT / "config.yaml"
    if not cfg_path.exists():
        raise ConfigError(f"config file not found: {cfg_path}")
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    for section in ("game", "scoring", "strategy", "llm"):
        if section not in raw:
            raise ConfigError(f"config.yaml missing required section: [{section}]")
    return AppConfig(raw=raw)

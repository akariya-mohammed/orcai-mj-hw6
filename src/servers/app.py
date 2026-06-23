"""FastMCP server factory shared by the cop and thief entrypoints.

Each server exposes one :class:`AgentBody` as MCP tools. Access is gated by a
bearer **token** (value from the env var named in ``config.yaml`` ->
``servers.<role>.token_env``), so a public URL can't be driven by a stranger —
the assignment's cyber requirement for the cloud level.

FastMCP is imported lazily here, so importing the rest of the project never
requires the dependency.
"""

from __future__ import annotations

import os

from ..config import AppConfig, load_config
from ..engine.game import Role
from .common import AgentBody


class AuthError(PermissionError):
    pass


def build_mcp_server(role: Role, cfg: AppConfig | None = None):
    """Create a FastMCP server exposing one agent's body, token-gated."""
    from fastmcp import FastMCP  # lazy

    cfg = cfg or load_config()
    body = AgentBody(role, cfg)
    expected = os.environ.get(cfg.servers[role.value]["token_env"], "")

    def _auth(token: str) -> None:
        if expected and token != expected:
            raise AuthError("invalid or missing MCP token")

    mcp = FastMCP(name=f"hw6-{role.value}")

    @mcp.tool
    def setup(cop: list[int], thief: list[int], token: str = "") -> dict:
        """Initialise this agent's world with both start cells."""
        _auth(token)
        return body.setup(cop=cop, thief=thief)

    @mcp.tool
    def my_move(token: str = "") -> dict:
        """Decide, announce (natural language) and apply this agent's own move."""
        _auth(token)
        return body.my_move()

    @mcp.tool
    def observe(message: str, mover: str, token: str = "") -> dict:
        """Interpret the opponent's natural-language message and sync this world."""
        _auth(token)
        return body.observe(message=message, mover=mover)

    @mcp.tool
    def state(token: str = "") -> dict:
        """Return this agent's current world snapshot."""
        _auth(token)
        return body.state()

    return mcp, cfg


def run_server(role: Role) -> None:  # pragma: no cover - long-running process
    mcp, cfg = build_mcp_server(role)
    s = cfg.servers[role.value]
    mcp.run(transport="http", host=s["host"], port=s["port"])

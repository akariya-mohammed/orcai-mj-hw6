"""Entrypoint: run the COP MCP server.

python -m src.servers.cop_server
"""

from __future__ import annotations

from ..engine.game import Role
from .app import run_server

if __name__ == "__main__":  # pragma: no cover
    run_server(Role.COP)

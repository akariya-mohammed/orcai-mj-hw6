"""MCP server side: the shared agent "body" and the two FastMCP servers.

Kept import-light on purpose — importing this package does NOT import FastMCP, so
the rest of the project (and the tests) load without the server dependency.
"""

from .common import AgentBody, run_loopback_match

__all__ = ["AgentBody", "run_loopback_match"]

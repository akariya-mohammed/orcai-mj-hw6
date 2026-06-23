"""MCP client side: LLM factory, agent personas, and the game orchestrator."""

from .llm import LLMResult, build_llm
from .personas import Persona

__all__ = ["build_llm", "LLMResult", "Persona"]

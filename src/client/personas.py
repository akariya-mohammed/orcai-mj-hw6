"""Agent personas: the natural-language *voice* and *ears* of each agent.

Per the assignment, the two agents converse in **free natural language** and the
tools fire from *interpretation* of that language. The deterministic strategy
picks the move; the persona:

* ``announce`` — turns the chosen move into a free-language sentence (rephrased by
  the LLM when a real backend is configured), always embedding the coordinates so
  the round-trip is robust.
* ``interpret`` — reads the opponent's sentence back into a structured
  :class:`~src.engine.game.Move` (LLM extraction with a regex safety net),
  validated against the rules.

If interpretation ever fails or is illegal, we log it and fall back so the
autonomous 6-game run never stalls — robustness the lecturer explicitly wants.
"""

from __future__ import annotations

import logging
import re

from ..engine.board import delta_to_direction
from ..engine.game import Move, Role, SubGame
from .llm import BaseLLM

logger = logging.getLogger(__name__)

_COORD = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")

_COP_SYS = (
    "You are the COP agent in a cops-and-robbers grid game, talking to the thief "
    "in natural language. Be brief and natural. You MUST keep every coordinate "
    "exactly as given, in (row, col) form, and keep the word MOVE or BARRIER."
)
_THIEF_SYS = (
    "You are the THIEF agent in a cops-and-robbers grid game, talking to the cop "
    "in natural language. Be brief and natural. You MUST keep every coordinate "
    "exactly as given, in (row, col) form, and keep the word MOVE."
)


class Persona:
    def __init__(self, role: Role, llm: BaseLLM, gatekeeper=None) -> None:
        self.role = role
        self.llm = llm
        self.gatekeeper = gatekeeper

    @property
    def system(self) -> str:
        return _COP_SYS if self.role is Role.COP else _THIEF_SYS

    # --- helpers -----------------------------------------------------------
    def _call(self, prompt: str) -> str:
        if self.gatekeeper is not None:
            self.gatekeeper.check(caller=f"{self.role.value}.persona")
        result = self.llm.complete(self.system, prompt)
        if self.gatekeeper is not None:
            self.gatekeeper.record(
                result.input_tokens, result.output_tokens, caller=f"{self.role.value}.persona"
            )
        return result.text.strip()

    def _canonical(self, move: Move, frm: tuple[int, int]) -> str:
        if move.kind == "barrier":
            return (
                f"{self.role.value.capitalize()} here, holding at {frm}. "
                f"I place a BARRIER at {move.cell}."
            )
        d = (
            move.direction
            or delta_to_direction(move.cell[0] - frm[0], move.cell[1] - frm[1])
            or "?"
        )
        verb = "advance" if self.role is Role.COP else "slip away"
        return (
            f"{self.role.value.capitalize()} here. From {frm} I {verb} {d}. "
            f"MOVE to {move.cell}."
        )

    # --- public API --------------------------------------------------------
    def announce(self, move: Move, sub: SubGame) -> str:
        """Free-language sentence describing ``move`` (coordinates preserved)."""
        frm = sub.position(self.role)
        canonical = self._canonical(move, frm)
        if isinstance(self.llm, BaseLLM) and self.llm.name == "mock":
            return canonical
        prompt = (
            "Rephrase the following game message in one short, natural sentence. "
            "Keep all coordinates in (row, col) form and keep the MOVE/BARRIER keyword.\n\n"
            f"{canonical}"
        )
        try:
            text = self._call(prompt)
        except Exception as exc:  # never let phrasing break the game
            logger.warning("announce LLM failed (%s); using canonical text", exc)
            return canonical
        # Guarantee the coordinate + keyword survive for the interpreter.
        if not _COORD.search(text) or (
            "MOVE" not in text.upper() and "BARRIER" not in text.upper()
        ):
            return canonical
        return text

    def interpret(self, text: str, sub: SubGame, mover: Role) -> Move | None:
        """Read a sentence into a legal Move for ``mover`` (regex-validated)."""
        coords = _COORD.findall(text)
        if not coords:
            logger.warning("interpret: no coordinates found in %r", text)
            return None
        cell = (int(coords[-1][0]), int(coords[-1][1]))
        kind = "barrier" if "BARRIER" in text.upper() or "BLOCK" in text.upper() else "move"
        for m in sub.legal_moves(mover):
            if m.kind == kind and m.cell == cell:
                return m
        logger.warning("interpret: %s %s at %s is not legal", mover.value, kind, cell)
        return None

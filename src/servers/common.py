"""The shared agent "body".

Each MCP server (cop, thief) wraps one :class:`AgentBody`. A body owns *its own*
view of the world (its :class:`SubGame`), its strategy, and its persona. The two
bodies stay in sync purely through natural-language messages:

* ``my_move``  — decide (strategy) → announce (NL) → apply to my own world.
* ``observe``  — read the opponent's NL message → interpret → apply to my world.

Because the announced sentence always carries the coordinates, both worlds track
each other exactly. This is the networked design; :func:`run_loopback_match`
exercises the exact same flow in-process (two bodies, no transport) so it is unit
testable without a running server.
"""

from __future__ import annotations

import logging
import random
from typing import Any

from ..client.llm import build_llm
from ..client.personas import Persona
from ..config import AppConfig
from ..engine.game import Move, Role, Status, new_sub_game
from ..engine.scoring import Match, SubGameResult, score_sub_game, summarize_match
from ..strategy import make_decider

logger = logging.getLogger(__name__)


class AgentBody:
    """One agent's world view + strategy + voice, exposed to the network as tools."""

    def __init__(self, role: Role, cfg: AppConfig, *, rng: random.Random | None = None) -> None:
        self.role = role
        self.cfg = cfg
        self.rng = rng or random.Random(cfg.strategy.get("seed", 7))
        self.persona = Persona(role, build_llm(cfg))
        self.decide_self = make_decider(role, cfg, rng=self.rng)
        self.decide_opp = make_decider(role.other, cfg, rng=self.rng)  # parse-failure fallback
        self.sub = None  # type: ignore[assignment]

    # --- tool: setup -------------------------------------------------------
    def setup(self, *, cop: list[int], thief: list[int]) -> dict[str, Any]:
        g = self.cfg.game
        from ..engine.board import Board
        from ..engine.game import SubGame

        board = Board(
            g["grid_size"][0], g["grid_size"][1], origin=g["origin"], diagonal=g["diagonal_moves"]
        )
        self.sub = SubGame(
            board=board,
            cop=tuple(cop),
            thief=tuple(thief),
            max_moves=g["max_moves"],
            max_barriers=g["max_barriers"],
            barriers_left=g["max_barriers"],
            thief_moves_first=g["thief_moves_first"],
        )
        return {"role": self.role.value, "snapshot": self.sub.snapshot()}

    # --- tool: my_move -----------------------------------------------------
    def my_move(self) -> dict[str, Any]:
        if self.sub.turn is not self.role:
            raise RuntimeError(f"not {self.role.value}'s turn")
        move: Move = self.decide_self(self.sub, self.role)
        sentence = self.persona.announce(move, self.sub)
        self.sub.apply(self.role, move)
        return {
            "message": sentence,
            "snapshot": self.sub.snapshot(),
            "status": self.sub.status.value,
        }

    # --- tool: observe -----------------------------------------------------
    def observe(self, *, message: str, mover: str) -> dict[str, Any]:
        mover_role = Role(mover)
        move = self.persona.interpret(message, self.sub, mover_role)
        if move is None:  # parse failed — best-effort resync so the game proceeds
            move = self.decide_opp(self.sub, mover_role)
            logger.warning(
                "%s body: could not parse %r; resync via heuristic", self.role.value, message
            )
        self.sub.apply(mover_role, move)
        return {"snapshot": self.sub.snapshot(), "status": self.sub.status.value}

    # --- tool: state / result ---------------------------------------------
    def state(self) -> dict[str, Any]:
        return self.sub.snapshot()

    def status(self) -> str:
        return self.sub.status.value


def run_loopback_match(cfg: AppConfig) -> dict[str, Any]:
    """Drive two AgentBody instances against each other in-process.

    This is the *distributed* flow (each body keeps its own world, synced only by
    natural language) — minus the network. It proves the MCP server logic without
    needing FastMCP or a daemon, and is what the unit test runs.
    """
    rng = random.Random(cfg.strategy.get("seed", 7))
    n = cfg.game["num_sub_games"]
    half = n // 2
    schedule = [Role.COP] * half + [Role.THIEF] * (n - half)
    match = Match()

    cop_body = AgentBody(Role.COP, cfg, rng=rng)
    thief_body = AgentBody(Role.THIEF, cfg, rng=rng)
    bodies = {Role.COP: cop_body, Role.THIEF: thief_body}

    for i, our_role in enumerate(schedule, start=1):
        g = cfg.game
        sub = new_sub_game(
            rows=g["grid_size"][0],
            cols=g["grid_size"][1],
            origin=g["origin"],
            diagonal=g["diagonal_moves"],
            max_moves=g["max_moves"],
            max_barriers=g["max_barriers"],
            thief_moves_first=g["thief_moves_first"],
            rng=rng,
        )
        cop_body.setup(cop=list(sub.cop), thief=list(sub.thief))
        thief_body.setup(cop=list(sub.cop), thief=list(sub.thief))

        while cop_body.sub.status is Status.PLAYING:
            mover = cop_body.sub.turn
            out = bodies[mover].my_move()  # mover acts in its own world
            bodies[mover.other].observe(message=out["message"], mover=mover.value)  # opponent syncs
            if out["status"] != Status.PLAYING.value:
                break

        status = cop_body.sub.status
        # Both worlds must agree (sanity check on the NL sync).
        assert cop_body.sub.status == thief_body.sub.status, "world desync between bodies"
        cop_pts, thief_pts = score_sub_game(status, cfg.scoring)
        match.add(SubGameResult(i, our_role, status, cop_pts, thief_pts, cop_body.sub.move_count))

    return summarize_match(match)

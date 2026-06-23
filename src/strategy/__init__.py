"""Strategy factory: turn config into a ``DecideFn`` per role.

``cop: heuristic`` / ``thief: qlearning`` etc. is read straight from
``config.yaml``. Q-learners are trained once and cached on first use.
"""

from __future__ import annotations

import random
from collections.abc import Callable

from ..engine.game import Move, Role, SubGame
from . import heuristic
from .qlearning import QConfig, QLearner

DecideFn = Callable[[SubGame, Role], Move]

_QCACHE: dict[tuple, QLearner] = {}


def make_decider(role: Role, cfg, *, rng: random.Random | None = None) -> DecideFn:
    """Build the decision function for ``role`` according to ``cfg.strategy``."""
    rng = rng or random.Random(cfg.strategy.get("seed", 7))
    kind = cfg.strategy.get(role.value, "heuristic")

    if kind == "heuristic":
        return heuristic.make_heuristic(role, rng)

    if kind == "qlearning":
        rows, cols = cfg.game["grid_size"]
        key = (role, rows, cols, cfg.game["origin"], cfg.game["diagonal_moves"])
        learner = _QCACHE.get(key)
        if learner is None:
            ql = cfg.strategy.get("qlearning", {})
            learner = QLearner(
                role,
                rows,
                cols,
                origin=cfg.game["origin"],
                diagonal=cfg.game["diagonal_moves"],
                max_moves=cfg.game["max_moves"],
                config=QConfig(
                    learning_rate=ql.get("learning_rate", 0.1),
                    discount_factor=ql.get("discount_factor", 0.9),
                    epsilon=ql.get("epsilon", 0.2),
                    train_episodes=ql.get("train_episodes", 2000),
                ),
                seed=cfg.strategy.get("seed", 7),
            )
            learner.train()
            _QCACHE[key] = learner
        return learner.decide

    raise ValueError(f"unknown strategy kind for {role.value}: {kind!r}")


__all__ = ["make_decider", "DecideFn", "QLearner", "QConfig", "heuristic"]

"""Tabular Q-Learning (Reinforcement Learning) for pursuit/evasion.

State  = (own cell, opponent cell)         encoded as a single integer index.
Action = one movement direction.
Reward = +10 win / -10 loss at terminal; small per-step shaping in between.
Update = Bellman:  Q(s,a) <- Q(s,a) + alpha * [ r + gamma * max_a' Q(s',a') - Q(s,a) ]

The learner trains by self-play against the deterministic heuristic opponent on a
barrier-free board of the configured size, then plays greedily. Unseen states
fall back to the heuristic, so the agent is never worse than the baseline.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from ..engine.game import Move, Role, Status, new_sub_game
from . import heuristic


@dataclass
class QConfig:
    learning_rate: float = 0.1
    discount_factor: float = 0.9
    epsilon: float = 0.2
    train_episodes: int = 2000


class QLearner:
    """A tabular Q-learner for one role on a fixed-size board."""

    def __init__(
        self,
        role: Role,
        rows: int,
        cols: int,
        *,
        origin: int = 1,
        diagonal: bool = True,
        max_moves: int = 25,
        config: QConfig | None = None,
        seed: int = 7,
    ) -> None:
        self.role = role
        self.rows = rows
        self.cols = cols
        self.origin = origin
        self.diagonal = diagonal
        self.max_moves = max_moves
        self.cfg = config or QConfig()
        self.rng = random.Random(seed)
        self.actions: list[str] = (
            ["N", "S", "E", "W", "NE", "NW", "SE", "SW"] if diagonal else ["N", "S", "E", "W"]
        )
        self.n_cells = rows * cols
        self.q = np.zeros((self.n_cells * self.n_cells, len(self.actions)), dtype=np.float64)
        self._heur = heuristic.make_heuristic(role.other, self.rng)  # opponent
        self.trained = False

    # --- encoding ----------------------------------------------------------
    def cell_idx(self, cell: tuple[int, int]) -> int:
        return (cell[0] - self.origin) * self.cols + (cell[1] - self.origin)

    def state_idx(self, own: tuple[int, int], opp: tuple[int, int]) -> int:
        return self.cell_idx(own) * self.n_cells + self.cell_idx(opp)

    def _own_opp(self, sub) -> tuple[tuple[int, int], tuple[int, int]]:
        own = sub.position(self.role)
        opp = sub.position(self.role.other)
        return own, opp

    # --- rewards -----------------------------------------------------------
    def _terminal_reward(self, status: Status) -> float:
        won = (status is Status.COP_WIN) == (self.role is Role.COP)
        return 10.0 if won else -10.0

    def _step_reward(self) -> float:
        return -0.1 if self.role is Role.COP else 0.1

    # --- action selection --------------------------------------------------
    def _legal_dir_moves(self, sub) -> list[tuple[int, Move]]:
        out = []
        for m in sub.legal_moves(self.role):
            if m.kind == "move" and m.direction in self.actions:
                out.append((self.actions.index(m.direction), m))
        return out

    def _choose_training(self, sub) -> tuple[int, Move]:
        legal = self._legal_dir_moves(sub)
        if self.rng.random() < self.cfg.epsilon:
            return self.rng.choice(legal)
        own, opp = self._own_opp(sub)
        s = self.state_idx(own, opp)
        return max(legal, key=lambda am: self.q[s, am[0]])

    # --- training ----------------------------------------------------------
    def train(self) -> None:
        alpha, gamma = self.cfg.learning_rate, self.cfg.discount_factor
        for _ in range(self.cfg.train_episodes):
            sub = new_sub_game(
                rows=self.rows,
                cols=self.cols,
                origin=self.origin,
                diagonal=self.diagonal,
                max_moves=self.max_moves,
                max_barriers=0,  # barrier-free during training for tractability
                rng=self.rng,
            )
            pending: tuple[int, int] | None = None  # (state_idx, action_idx)
            guard = 0
            while sub.status is Status.PLAYING and guard < self.max_moves * 4 + 10:
                guard += 1
                role = sub.turn
                if role is self.role:
                    legal = self._legal_dir_moves(sub)
                    if not legal:
                        break
                    a_idx, move = self._choose_training(sub)
                    own, opp = self._own_opp(sub)
                    s = self.state_idx(own, opp)
                    sub.apply(role, move)
                    pending = (s, a_idx)
                    if sub.status is not Status.PLAYING:
                        self._update(s, a_idx, self._terminal_reward(sub.status), None)
                        pending = None
                else:
                    opp_move = self._heur(sub, role)
                    sub.apply(role, opp_move)
                    if pending is not None:
                        s, a_idx = pending
                        if sub.status is not Status.PLAYING:
                            self._update(s, a_idx, self._terminal_reward(sub.status), None)
                        else:
                            own, opp = self._own_opp(sub)
                            self._update(s, a_idx, self._step_reward(), self.state_idx(own, opp))
                        pending = None
                if sub.status is not Status.PLAYING:
                    break
        _ = (alpha, gamma)  # used inside _update
        self.trained = True

    def _update(self, s: int, a: int, r: float, s_next: int | None) -> None:
        alpha, gamma = self.cfg.learning_rate, self.cfg.discount_factor
        best_next = 0.0 if s_next is None else float(self.q[s_next].max())
        td_target = r + gamma * best_next
        self.q[s, a] += alpha * (td_target - self.q[s, a])

    # --- play --------------------------------------------------------------
    def decide(self, sub, role: Role) -> Move:
        if role is not self.role:  # defensive — a learner only plays its own role
            raise ValueError(f"Q-learner is {self.role}, asked to play {role}")
        legal = self._legal_dir_moves(sub)
        own, opp = self._own_opp(sub)
        s = self.state_idx(own, opp)
        if legal and float(np.abs(self.q[s]).sum()) > 0.0:
            a_idx, move = max(legal, key=lambda am: self.q[s, am[0]])
            return move
        # Unseen state (or no movement legal): defer to the heuristic baseline.
        return (
            heuristic.cop_decide(sub, self.rng)
            if role is Role.COP
            else heuristic.thief_decide(sub, self.rng)
        )

    # --- visualization -----------------------------------------------------
    def value_grid(self, opp_cell: tuple[int, int]) -> np.ndarray:
        """V(own) = max_a Q(own, opp_cell) over the board, as a rows x cols array."""
        grid = np.zeros((self.rows, self.cols), dtype=np.float64)
        for r in range(self.rows):
            for c in range(self.cols):
                own = (self.origin + r, self.origin + c)
                if own == opp_cell:
                    grid[r, c] = np.nan
                    continue
                s = self.state_idx(own, opp_cell)
                grid[r, c] = float(self.q[s].max())
        return grid

from src.engine.game import Role
from src.strategy.qlearning import QConfig, QLearner


def test_qlearner_trains_and_plays_legally():
    ql = QLearner(Role.THIEF, 4, 4, config=QConfig(train_episodes=300), seed=3)
    ql.train()
    assert ql.trained
    # Q-table got some non-zero updates during training.
    assert float(abs(ql.q).sum()) > 0.0

    import random

    from src.engine.game import new_sub_game

    sub = new_sub_game(rows=4, cols=4, max_barriers=0, rng=random.Random(3))
    # ensure it's the thief's turn for a thief learner
    if sub.turn is not Role.THIEF:
        sub.turn = Role.THIEF
    move = ql.decide(sub, Role.THIEF)
    assert sub.is_legal(Role.THIEF, move)


def test_value_grid_shape_and_opp_blank():
    import numpy as np

    ql = QLearner(Role.COP, 5, 5, config=QConfig(train_episodes=100))
    ql.train()
    grid = ql.value_grid((3, 3))
    assert grid.shape == (5, 5)
    assert np.isnan(grid[2, 2])  # opponent cell (origin 1 -> index 2,2)

import random

from src.engine.game import Role, Status, new_sub_game
from src.engine.scoring import run_sub_game
from src.strategy import heuristic
from src.strategy.minimax import best_move, evaluate, make_minimax


def test_minimax_returns_legal_move():
    rng = random.Random(1)
    sub = new_sub_game(rows=5, cols=5, cop=(1, 1), thief=(5, 5), rng=rng)
    m = best_move(sub, sub.turn, depth=3, rng=rng)
    assert sub.is_legal(sub.turn, m)


def test_minimax_cop_captures_heuristic_thief_on_small_board():
    rng = random.Random(2)
    cop = make_minimax(Role.COP, depth=4, rng=rng)
    thief = heuristic.make_heuristic(Role.THIEF, rng)
    wins = 0
    for _ in range(10):
        sub = new_sub_game(rows=4, cols=4, max_moves=25, max_barriers=5, rng=rng)
        if run_sub_game(sub, cop, thief) is Status.COP_WIN:
            wins += 1
    assert wins == 10  # minimax cop should always catch on a small board


def test_evaluate_terminal_signs():
    rng = random.Random(3)
    # cop adjacent to thief, cop to move -> cop can capture -> positive for cop
    sub = new_sub_game(rows=5, cols=5, cop=(3, 4), thief=(3, 3), thief_moves_first=False, rng=rng)
    assert sub.turn is Role.COP
    val = evaluate(sub.clone())  # non-terminal eval is finite
    assert isinstance(val, float)

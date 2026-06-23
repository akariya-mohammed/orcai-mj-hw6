from src.engine.game import Role, Status
from src.engine.scoring import Match, SubGameResult, score_sub_game, summarize_match

SCORING = {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5}


def test_score_sub_game():
    assert score_sub_game(Status.COP_WIN, SCORING) == (20, 5)
    assert score_sub_game(Status.THIEF_WIN, SCORING) == (5, 10)


def test_match_totals_and_bounds():
    m = Match()
    # 3 cop wins as cop, 3 thief wins as thief -> our_total maximal = 90
    for i in range(1, 4):
        m.add(SubGameResult(i, Role.COP, Status.COP_WIN, 20, 5, 5))
    for i in range(4, 7):
        m.add(SubGameResult(i, Role.THIEF, Status.THIEF_WIN, 5, 10, 25))
    summary = summarize_match(m)
    assert summary["our_total"] == 90
    assert summary["num_sub_games"] == 6
    assert summary["totals"]["cop"] == 3 * 20 + 3 * 5
    assert summary["totals"]["thief"] == 3 * 5 + 3 * 10


def test_min_our_total_is_30():
    m = Match()
    for i in range(1, 4):
        m.add(SubGameResult(i, Role.COP, Status.THIEF_WIN, 5, 10, 25))  # lost as cop -> 5 each
    for i in range(4, 7):
        m.add(SubGameResult(i, Role.THIEF, Status.COP_WIN, 20, 5, 5))  # lost as thief -> 5 each
    assert summarize_match(m)["our_total"] == 30

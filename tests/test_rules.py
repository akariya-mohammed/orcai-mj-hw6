from src.engine.board import Board
from src.engine.game import Move, Role, Status, SubGame, new_sub_game


def make(cop, thief, **kw):
    rows = kw.pop("rows", 5)
    cols = kw.pop("cols", 5)
    barriers = kw.pop("barriers", set())
    board = Board(rows, cols, origin=1, diagonal=kw.pop("diagonal", True), barriers=set(barriers))
    return SubGame(
        board=board,
        cop=cop,
        thief=thief,
        max_moves=kw.pop("max_moves", 25),
        max_barriers=kw.pop("max_barriers", 5),
        barriers_left=kw.pop("barriers_left", 5),
        thief_moves_first=kw.pop("thief_moves_first", True),
    )


def test_capture_when_cop_steps_on_thief():
    sub = make((3, 4), (3, 3), thief_moves_first=False)  # cop first
    sub.apply(Role.COP, Move("move", (3, 3), "W"))
    assert sub.status is Status.COP_WIN


def test_thief_cannot_enter_barrier():
    sub = make((1, 1), (3, 3), barriers={(3, 4)})
    legal = sub.legal_moves(Role.THIEF)
    assert all(m.cell != (3, 4) for m in legal)


def test_thief_must_move_no_stay_action():
    sub = make((1, 1), (3, 3))
    assert all(m.kind == "move" for m in sub.legal_moves(Role.THIEF))


def test_barrier_cap_and_cop_stays():
    sub = make((3, 3), (1, 1), barriers_left=1)
    barriers = [m for m in sub.legal_moves(Role.COP) if m.kind == "barrier"]
    assert barriers, "cop should have barrier options"
    pos = sub.cop
    # place a barrier: cop position unchanged, budget decremented
    sub.turn = Role.COP
    b = [m for m in sub.legal_moves(Role.COP) if m.kind == "barrier"][0]
    sub.apply(Role.COP, b)
    assert sub.cop == pos
    assert sub.barriers_left == 0
    # no more barrier options once budget is exhausted
    assert all(m.kind != "barrier" for m in sub.legal_moves(Role.COP))


def test_thief_wins_after_max_moves():
    # Put them far apart on a big board so the cop can't reach in 2 rounds.
    sub = make((1, 1), (5, 5), max_moves=2)
    # thief just oscillates; cop chases but can't catch in 2 rounds
    for _ in range(20):
        if sub.status is not Status.PLAYING:
            break
        role = sub.turn
        moves = [m for m in sub.legal_moves(role) if m.kind == "move"]
        sub.apply(role, moves[0])
    assert sub.status is Status.THIEF_WIN


def test_factory_places_distinct_cells():
    import random

    sub = new_sub_game(rows=5, cols=5, rng=random.Random(1))
    assert sub.cop != sub.thief
    assert sub.board.in_bounds(sub.cop) and sub.board.in_bounds(sub.thief)

from src.engine.board import Board, chebyshev, delta_to_direction, manhattan


def test_bounds_and_step():
    b = Board(5, 5, origin=1)
    assert b.in_bounds((1, 1))
    assert b.in_bounds((5, 5))
    assert not b.in_bounds((0, 1))
    assert not b.in_bounds((6, 5))
    assert b.step((3, 3), "N") == (2, 3)
    assert b.step((3, 3), "SE") == (4, 4)


def test_neighbors_excludes_barriers_and_edges():
    b = Board(3, 3, origin=1, barriers={(1, 2)})
    n = b.neighbors((1, 1))  # corner
    assert (1, 2) not in n  # barrier excluded
    assert all(b.in_bounds(c) for c in n)
    assert (2, 2) in n  # diagonal allowed


def test_no_diagonal():
    b = Board(3, 3, diagonal=False)
    names = b.direction_names()
    assert set(names) == {"N", "S", "E", "W"}


def test_distances_and_delta_name():
    assert chebyshev((1, 1), (3, 4)) == 3
    assert manhattan((1, 1), (3, 4)) == 5
    assert delta_to_direction(-1, 1) == "NE"
    assert delta_to_direction(2, 0) is None

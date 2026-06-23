from src.client.llm import MockLLM
from src.client.personas import Persona
from src.engine.game import Role, new_sub_game


def test_announce_contains_coords_and_keyword():
    p = Persona(Role.THIEF, MockLLM())
    sub = new_sub_game(rows=5, cols=5, cop=(1, 1), thief=(3, 3))
    move = [m for m in sub.legal_moves(Role.THIEF) if m.kind == "move"][0]
    text = p.announce(move, sub)
    assert str(move.cell) in text.replace(" ", "") or f"({move.cell[0]}, {move.cell[1]})" in text
    assert "MOVE" in text.upper()


def test_interpret_round_trips():
    cop_p = Persona(Role.COP, MockLLM())
    thief_p = Persona(Role.THIEF, MockLLM())
    sub = new_sub_game(rows=5, cols=5, cop=(1, 1), thief=(3, 3), thief_moves_first=True)
    move = [m for m in sub.legal_moves(Role.THIEF) if m.kind == "move"][0]
    sentence = thief_p.announce(move, sub)
    parsed = cop_p.interpret(sentence, sub, Role.THIEF)
    assert parsed is not None
    assert (parsed.kind, parsed.cell) == (move.kind, move.cell)


def test_interpret_barrier_keyword():
    cop_p = Persona(Role.COP, MockLLM())
    thief_p = Persona(Role.THIEF, MockLLM())
    sub = new_sub_game(rows=5, cols=5, cop=(3, 3), thief=(1, 1), thief_moves_first=False)
    barrier = [m for m in sub.legal_moves(Role.COP) if m.kind == "barrier"][0]
    sentence = cop_p.announce(barrier, sub)
    parsed = thief_p.interpret(sentence, sub, Role.COP)
    assert parsed is not None and parsed.kind == "barrier" and parsed.cell == barrier.cell


# --- interop robustness: the other group may phrase things differently ---


def test_interpret_bare_direction_relative_to_position():
    """'I move north' with no coordinates -> resolve from the mover's cell."""
    p = Persona(Role.COP, MockLLM())
    sub = new_sub_game(rows=5, cols=5, cop=(1, 1), thief=(3, 3), thief_moves_first=True)
    # thief at (3,3); "south-east" => (4,4)
    parsed = p.interpret("Thief here, I slip south-east to keep my distance.", sub, Role.THIEF)
    assert parsed is not None and parsed.cell == (4, 4)


def test_interpret_row_col_format():
    p = Persona(Role.COP, MockLLM())
    sub = new_sub_game(rows=5, cols=5, cop=(1, 1), thief=(3, 3), thief_moves_first=True)
    parsed = p.interpret("Thief moving to row 2 col 4.", sub, Role.THIEF)
    assert parsed is not None and parsed.cell == (2, 4)


def test_interpret_wall_synonym_for_barrier():
    p = Persona(Role.THIEF, MockLLM())
    sub = new_sub_game(rows=5, cols=5, cop=(3, 3), thief=(1, 1), thief_moves_first=False)
    barrier = [m for m in sub.legal_moves(Role.COP) if m.kind == "barrier"][0]
    parsed = p.interpret(f"I drop a wall at {barrier.cell}.", sub, Role.COP)
    assert parsed is not None and parsed.kind == "barrier" and parsed.cell == barrier.cell


def test_interpret_destination_is_last_coordinate():
    """'from (3,3) to (2,4)' must pick the destination, not the origin."""
    p = Persona(Role.COP, MockLLM())
    sub = new_sub_game(rows=5, cols=5, cop=(1, 1), thief=(3, 3), thief_moves_first=True)
    parsed = p.interpret("Thief: from (3,3) I move to (2,4).", sub, Role.THIEF)
    assert parsed is not None and parsed.cell == (2, 4)

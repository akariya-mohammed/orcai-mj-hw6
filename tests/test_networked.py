import asyncio

import pytest

# The networked path needs FastMCP; skip cleanly where it isn't installed (e.g. CI).
pytest.importorskip("fastmcp")

from src.client.networked import run_networked_match  # noqa: E402
from src.engine.game import Role  # noqa: E402
from src.servers.app import build_mcp_server  # noqa: E402


def test_networked_selftest_over_inmemory(cfg):
    import os

    cop_srv, _ = build_mcp_server(Role.COP, cfg)
    thief_srv, _ = build_mcp_server(Role.THIEF, cfg)
    # Use whatever tokens the servers expect (empty in CI; real if .env sets them).
    cop_tok = os.environ.get(cfg.servers["cop"]["token_env"], "")
    thief_tok = os.environ.get(cfg.servers["thief"]["token_env"], "")
    out = asyncio.run(
        run_networked_match(
            cfg,
            our_cop=cop_srv,
            our_thief=thief_srv,
            opp_cop=cop_srv,
            opp_thief=thief_srv,
            tokens={
                "our_cop": cop_tok,
                "our_thief": thief_tok,
                "opp_cop": cop_tok,
                "opp_thief": thief_tok,
            },
            opponent_meta={"group_code": "selftest"},
        )
    )
    assert out["summary"]["num_sub_games"] == 6
    assert out["report"]["report_type"] == "bonus_game"
    assert set(out["totals_by_group"]) == {"group_1", "group_2"}
    assert out["bonus_claim"] in ("group_1", "group_2", "tie")
    # every sub-game finished with a valid outcome
    for sg in out["summary"]["sub_games"]:
        assert sg["outcome"] in ("cop_win", "thief_win")

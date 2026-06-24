import json
from pathlib import Path

from src.mailer import send_report
from src.report import build_bonus_report, build_internal_report
from src.servers.common import run_loopback_match


def test_internal_report_shape(cfg):
    summary = run_loopback_match(cfg)
    report = build_internal_report(
        cfg,
        summary,
        cop_mcp_url="http://x/cop",
        thief_mcp_url="http://x/thief",
        generated_at="2026-06-23T00:00:00",
    )
    assert report["report_type"] == "internal_self_play"
    assert report["cop_mcp_url"] == "http://x/cop"
    assert report["totals"] == summary["totals"]
    assert len(report["sub_games"]) == cfg.game["num_sub_games"]
    assert isinstance(report["students"], list)


def test_bonus_report_shape(cfg):
    summary = run_loopback_match(cfg)
    report = build_bonus_report(
        cfg,
        summary,
        our_role_schedule=["cop", "cop", "cop", "thief", "thief", "thief"],
        opponent={"group_code": "other", "cop_url": "u1", "thief_url": "u2"},
        totals_by_group={"group_1": 75, "group_2": 60},
        bonus_claim="group_1",
        mutual_agreement=True,
        generated_at="2026-06-23T00:00:00",
    )
    assert report["report_type"] == "bonus_game"
    assert report["mutual_agreement"] is True
    assert report["totals_by_group"]["group_1"] == 75
    assert report["groups"]["group_2"] == "other"


def test_setup_accepts_board_override(cfg):
    """Referee can switch board size per game (5x5 / 8x8 / official) without restart."""
    from src.engine.game import Role
    from src.servers.common import AgentBody

    body = AgentBody(Role.COP, cfg)  # cfg default grid may be 10x10
    out = body.setup(cop=[0, 0], thief=[4, 4], rows=5, cols=5, origin=0, max_barriers=3)
    snap = out["snapshot"]
    assert snap["thief"] == [4, 4]
    assert body.sub.board.rows == 5 and body.sub.board.cols == 5
    assert body.sub.board.origin == 0
    assert body.sub.barriers_left == 3


def test_loopback_match_is_complete_and_consistent(cfg):
    summary = run_loopback_match(cfg)
    assert summary["num_sub_games"] == cfg.game["num_sub_games"]
    for sg in summary["sub_games"]:
        assert sg["outcome"] in ("cop_win", "thief_win")
        assert sg["cop_points"] + sg["thief_points"] in (25, 15)  # 20+5 or 5+10


def test_email_dry_run_writes_json(cfg, tmp_path):
    summary = run_loopback_match(cfg)
    report = build_internal_report(
        cfg, summary, cop_mcp_url="u", thief_mcp_url="u", generated_at="t"
    )
    status = send_report(cfg, report, subject_suffix="test", dry_run=True)
    assert status["sent"] is False and status["dry_run"] is True
    saved = json.loads(Path(status["saved"]).read_text(encoding="utf-8"))
    assert saved["report_type"] == "internal_self_play"

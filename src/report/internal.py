"""Internal Game JSON — the self-play report emailed to the lecturer.

Pure JSON body (no free text), per the assignment spec §9. Built from the config
identity block and the match summary produced by the engine.
"""

from __future__ import annotations

from typing import Any


def build_internal_report(
    cfg,
    match_summary: dict[str, Any],
    *,
    cop_mcp_url: str,
    thief_mcp_url: str,
    generated_at: str,
) -> dict[str, Any]:
    ident = cfg.identity
    return {
        "report_type": "internal_self_play",
        "group_code": ident.get("group_code", ""),
        "group_name": ident.get("group_name", ""),
        "github_repo": ident.get("github_repo", ""),
        "students": [
            {"name": m.get("name", ""), "id": str(m.get("id", ""))}
            for m in ident.get("members", [])
        ],
        "cop_mcp_url": cop_mcp_url,
        "thief_mcp_url": thief_mcp_url,
        "timezone": cfg.email.get("timezone", "UTC"),
        "generated_at": generated_at,
        "grid_size": cfg.game["grid_size"],
        "strategy": {
            "cop": cfg.strategy.get("cop"),
            "thief": cfg.strategy.get("thief"),
        },
        "sub_games": match_summary["sub_games"],
        "totals": match_summary["totals"],
    }

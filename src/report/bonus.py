"""Inter-Group Bonus Game JSON.

Both groups must email *agreeing* results or both are disqualified, so this body
is symmetric and carries an explicit ``mutual_agreement`` flag plus per-group
totals and the four MCP URLs that played.
"""

from __future__ import annotations

from typing import Any


def build_bonus_report(
    cfg,
    match_summary: dict[str, Any],
    *,
    our_role_schedule: list[str],
    opponent: dict[str, Any],
    totals_by_group: dict[str, int],
    bonus_claim: str,
    mutual_agreement: bool,
    generated_at: str,
) -> dict[str, Any]:
    ident = cfg.identity
    return {
        "report_type": "bonus_game",
        "timezone": cfg.email.get("timezone", "UTC"),
        "generated_at": generated_at,
        "grid_size": cfg.game["grid_size"],
        "groups": {
            "group_1": ident.get("group_code", ""),
            "group_2": opponent.get("group_code", ""),
        },
        "group_names": {
            "group_1": ident.get("group_name", ""),
            "group_2": opponent.get("group_name", ""),
        },
        "github_repo_group_1": ident.get("github_repo", ""),
        "github_repo_group_2": opponent.get("github_repo", ""),
        "students_group_1": [
            {"name": m.get("name", ""), "id": str(m.get("id", ""))}
            for m in ident.get("members", [])
        ],
        "students_group_2": opponent.get("members", []),
        "mcp_url_group_1_cop": opponent.get("our_cop_url", ""),
        "mcp_url_group_1_thief": opponent.get("our_thief_url", ""),
        "mcp_url_group_2_cop": opponent.get("cop_url", ""),
        "mcp_url_group_2_thief": opponent.get("thief_url", ""),
        "our_role_schedule": our_role_schedule,
        "sub_games": match_summary["sub_games"],
        "totals_by_group": totals_by_group,
        "bonus_claim": bonus_claim,
        "mutual_agreement": mutual_agreement,
    }

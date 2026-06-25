"""Compare two ``bonus_game`` JSON reports for mutual agreement.

Before both groups email the lecturer, the results must be identical (conflicting
emails disqualify both). This checks the parts that must match — board size, the
per-sub-game outcomes, and each group's total (matched by group code, not by
group_1/group_2 position) — and ignores cosmetic differences (timestamps, URLs).

    python -m src.report.compare ours.json theirs.json
    python -m src.report.compare theirs.json        # ours defaults to artefacts/bonus_report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ..config import PROJECT_ROOT


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _totals_by_code(report: dict[str, Any]) -> dict[str, int]:
    """Map group CODE -> total, so labeling (group_1/2) doesn't matter."""
    groups = report.get("groups", {})
    totals = report.get("totals_by_group", {})
    out: dict[str, int] = {}
    for slot, code in groups.items():  # slot = "group_1"/"group_2"
        if code:
            out[code] = totals.get(slot)
    return out


def _outcomes(report: dict[str, Any]) -> list[tuple[int, str, int]]:
    """The referee facts each report must agree on: (index, outcome, rounds)."""
    return sorted(
        (sg.get("index"), sg.get("outcome"), sg.get("rounds")) for sg in report.get("sub_games", [])
    )


def compare(ours: dict[str, Any], theirs: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []

    if ours.get("grid_size") != theirs.get("grid_size"):
        issues.append(f"grid_size differs: {ours.get('grid_size')} vs {theirs.get('grid_size')}")

    o_out, t_out = _outcomes(ours), _outcomes(theirs)
    if o_out != t_out:
        issues.append("sub-game outcomes differ:")
        issues.append(f"    ours:   {o_out}")
        issues.append(f"    theirs: {t_out}")

    o_tot, t_tot = _totals_by_code(ours), _totals_by_code(theirs)
    if o_tot != t_tot:
        issues.append(f"totals-by-group-code differ: {o_tot} vs {t_tot}")
    # NB: bonus_claim is stored by slot (group_1/group_2), which differs between
    # the two groups' reports, so it's NOT compared — the winner is derived from
    # the per-code totals above (which must already agree).

    return (not issues), issues


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compare two bonus_game reports for agreement.")
    p.add_argument("first", help="first report (or the partner's, if only one given)")
    p.add_argument("second", nargs="?", help="second report")
    args = p.parse_args(argv)

    if args.second is None:
        ours_path = PROJECT_ROOT / "artefacts" / "bonus_report.json"
        theirs_path = args.first
    else:
        ours_path, theirs_path = args.first, args.second

    try:
        ours, theirs = _load(ours_path), _load(theirs_path)
    except (OSError, ValueError) as exc:
        print(f"ERROR loading reports: {exc}", file=sys.stderr)
        return 2

    ok, issues = compare(ours, theirs)
    print(f"ours:   {ours_path}")
    print(f"theirs: {theirs_path}")
    if ok:
        print("\n[MATCH] results agree. Safe for BOTH groups to email (mutual_agreement=true).")
        tot = _totals_by_code(ours)
        print(f"   totals by group: {tot}")
        if tot:
            top = max(tot.values())
            leaders = [code for code, v in tot.items() if v == top]
            result = "TIE" if len(leaders) > 1 else f"WINNER: {leaders[0]}"
            print(f"   result: {result}")
        return 0
    print("\n[MISMATCH] DO NOT email until resolved (conflicting results disqualify both):")
    for line in issues:
        print(f"   {line}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

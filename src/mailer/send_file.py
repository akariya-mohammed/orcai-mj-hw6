"""Email a JSON file's contents (the agreed canonical bonus result) via Gmail.

After the official match, the referee group sends you the canonical
``bonus_game`` JSON. Once you've confirmed it matches (``src.report.compare``),
each group emails the **same** result from its own system. This sends that JSON
verbatim as the e-mail body.

    # safe: goes to YOUR inbox while email.send_to_lecturer is false
    python -m src.mailer.send_file path\\to\\canonical_bonus.json

    # the real submission (only after you set email.send_to_lecturer: true):
    python -m src.mailer.send_file path\\to\\canonical_bonus.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..config import load_config
from .gmail import send_report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Email a JSON file's contents via Gmail.")
    p.add_argument("path", help="path to the JSON file to send as the email body")
    p.add_argument("--to-self", action="store_true", help="force send to your own inbox")
    p.add_argument("--to", help="send to an explicit address")
    p.add_argument("--subject", default="bonus cross-group result", help="subject suffix")
    args = p.parse_args(argv)

    try:
        body = json.loads(Path(args.path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"ERROR reading {args.path}: {exc}", file=sys.stderr)
        return 2

    cfg = load_config()
    status = send_report(
        cfg, body, subject_suffix=args.subject, to_override=args.to, to_self=args.to_self
    )
    print(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

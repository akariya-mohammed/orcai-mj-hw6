"""One-command Gmail OAuth authorizer + verifier.

This replaces the Google guide's throwaway ``uv`` test program (שלב 15-16): it runs
the OAuth browser flow, caches ``secrets/token.json``, and then proves it works by
creating a Gmail **draft** (safe — nothing is sent to the lecturer).

    python -m src.mailer.authorize            # create a test draft (default)
    python -m src.mailer.authorize --send     # actually send a test mail to yourself

Prereqs: ``secrets/credentials.json`` (your downloaded Desktop OAuth client) and
``pip install -r requirements.txt`` (Google libraries).
"""

from __future__ import annotations

import argparse
import sys

from ..config import load_config
from .gmail import GmailSender


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Authorize Gmail and verify with a draft.")
    parser.add_argument("--send", action="store_true", help="send a real test email to yourself")
    args = parser.parse_args(argv)

    cfg = load_config()
    email = cfg.email
    creds_path = cfg.path("artefacts").parent / email["credentials_path"]
    token_path = cfg.path("artefacts").parent / email["token_path"]

    if not creds_path.exists():
        print(f"ERROR: {creds_path} not found.", file=sys.stderr)
        print("Put your downloaded Desktop OAuth client there (rename to credentials.json).", file=sys.stderr)
        return 2

    sender = GmailSender(creds_path, token_path)
    body = "HW6 Cops & Robbers — OAuth verification. If you can read this, Gmail auth works."

    try:
        if args.send:
            # Self-test: send to the authorized account itself, not the lecturer.
            me = _self_address(sender)
            mid = sender.send(me, f"{email['subject_prefix']} OAuth self-test", {"hello": body})
            print(f"OK: sent test email id={mid} to {me}")
        else:
            did = sender.create_draft(_self_address(sender), f"{email['subject_prefix']} OAuth test", body)
            print(f"OK: created Gmail draft id={did} (nothing sent).")
        print(f"token cached at: {token_path}")
        print("You can now set email.enabled: true in config.yaml.")
        return 0
    except Exception as exc:  # noqa: BLE001 - surface any OAuth/API error plainly
        print(f"ERROR during Gmail auth/verify: {exc}", file=sys.stderr)
        return 1


def _self_address(sender: GmailSender) -> str:
    """Resolve the authorized account's own email address."""
    if sender._service is None:  # noqa: SLF001 - intentional: trigger auth
        sender._service = sender._build_service()
    profile = sender._service.users().getProfile(userId="me").execute()
    return profile.get("emailAddress", "me")


if __name__ == "__main__":
    raise SystemExit(main())

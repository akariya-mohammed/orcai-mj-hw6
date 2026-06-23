"""Send the result report by e-mail via the Gmail API.

Auth follows Dr. Segal's guide: a Desktop OAuth client (``credentials.json``)
plus a cached ``token.json`` (scope ``gmail.modify``). Both live under
``secrets/`` and are gitignored — secrets never reach the repo.

The message *body is the report JSON itself* (no free text), per the spec, so the
lecturer's agent can parse and compare both groups' results automatically.

Imports of the Google libraries are lazy so the module loads (and the rest of the
project runs / tests) even when those packages aren't installed.
"""

from __future__ import annotations

import base64
import json
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailSender:
    def __init__(self, credentials_path: str | Path, token_path: str | Path) -> None:
        self.credentials_path = Path(credentials_path)
        self.token_path = Path(token_path)
        self._service = None

    def _build_service(self):  # pragma: no cover - requires Google libs + OAuth
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        if self.token_path.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_path.exists():
                    raise FileNotFoundError(
                        f"OAuth client not found: {self.credentials_path}. "
                        "Create a Desktop OAuth client per the Google API guide."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(creds.to_json(), encoding="utf-8")
        return build("gmail", "v1", credentials=creds)

    def _raw(self, to: str, subject: str, body_text: str) -> str:
        message = MIMEText(body_text, "plain", "utf-8")
        message["to"] = to
        message["subject"] = subject
        return base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    def send(self, to: str, subject: str, json_body: dict[str, Any]) -> str:  # pragma: no cover
        if self._service is None:
            self._service = self._build_service()
        body_text = json.dumps(json_body, ensure_ascii=False, indent=2)
        raw = self._raw(to, subject, body_text)
        sent = self._service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return sent.get("id", "")

    def self_address(self) -> str:  # pragma: no cover - needs OAuth
        """The authorized account's own email address (for safe self-tests)."""
        if self._service is None:
            self._service = self._build_service()
        return self._service.users().getProfile(userId="me").execute().get("emailAddress", "me")

    def create_draft(self, to: str, subject: str, body_text: str) -> str:  # pragma: no cover
        """Create a Gmail *draft* (does not send) — used to verify OAuth safely."""
        if self._service is None:
            self._service = self._build_service()
        raw = self._raw(to, subject, body_text)
        draft = (
            self._service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        return draft.get("id", "")


def send_report(
    cfg,
    json_body: dict[str, Any],
    *,
    subject_suffix: str = "",
    dry_run: bool | None = None,
    to_override: str | None = None,
    to_self: bool = False,
) -> dict[str, Any]:
    """Send (or, in dry-run, just render) the JSON report.

    Returns a small status dict. Dry-run writes the body to ``artefacts/`` and is
    the default whenever ``email.enabled`` is false, so CI and tests never send.
    ``to_self`` sends to the authorized account itself (safe end-to-end test);
    ``to_override`` sends to an explicit address. Otherwise the configured
    recipient (the lecturer) is used.
    """
    email = cfg.email
    if dry_run is None:
        dry_run = not email.get("enabled", False)

    subject = f"{email.get('subject_prefix', '[HW6]')} {subject_suffix}".strip()
    body_text = json.dumps(json_body, ensure_ascii=False, indent=2)

    if dry_run:
        out = cfg.path("artefacts") / "email_dry_run.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(body_text, encoding="utf-8")
        to = to_override or ("<self>" if to_self else email["to"])
        return {"sent": False, "dry_run": True, "to": to, "subject": subject, "saved": str(out)}

    sender = GmailSender(email["credentials_path"], email["token_path"])
    # SAFETY GATE: never reach the lecturer unless explicitly allowed.
    # Order: explicit --to override > --to-self > (lecturer only if send_to_lecturer) > self.
    if to_override:
        to = to_override
    elif to_self or not email.get("send_to_lecturer", False):
        to = sender.self_address()
    else:
        to = email["to"]
    msg_id = sender.send(to, subject, json_body)
    return {"sent": True, "dry_run": False, "to": to, "subject": subject, "message_id": msg_id}

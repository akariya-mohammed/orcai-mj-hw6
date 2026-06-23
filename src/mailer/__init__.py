"""Gmail-API e-mail delivery of the JSON result report."""

from .gmail import GmailSender, send_report

__all__ = ["GmailSender", "send_report"]

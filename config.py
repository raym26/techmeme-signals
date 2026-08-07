import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")

GOOGLE_SERVICE_ACCOUNT_FILE = _require("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_SHEET_ID = _require("GOOGLE_SHEET_ID")
SIGNALS_SHEET_NAME = os.environ.get("SIGNALS_SHEET_NAME", "Sheet3")
REPORTS_SHEET_NAME = os.environ.get("REPORTS_SHEET_NAME", "WeeklyReports")

# Sheet3 is a rolling window, not cleared weekly: signals older than
# ROLLING_WINDOW_DAYS are pruned after each weekly run, and only the most
# recent CURRENT_WEEK_DAYS get sent to Claude in full detail (older signals
# within the window are summarized as aggregate counts) to bound prompt size.
ROLLING_WINDOW_DAYS = int(os.environ.get("ROLLING_WINDOW_DAYS", "28"))
CURRENT_WEEK_DAYS = int(os.environ.get("CURRENT_WEEK_DAYS", "7"))

GMAIL_ADDRESS = _require("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = _require("GMAIL_APP_PASSWORD")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", GMAIL_ADDRESS)

# Same Gmail App Password also authenticates IMAP for reading the daily digest.
IMAP_HOST = os.environ.get("IMAP_HOST", "imap.gmail.com")
TECHMEME_SENDER = os.environ.get("TECHMEME_SENDER", "newsletter@techmeme.com")

# Gmail label used to track which digests have already been ingested. Deliberately
# independent of the \Seen flag, since the user may read a digest in Gmail before
# the daily job runs -- relying on unread/read state would silently skip it.
TECHMEME_PROCESSED_LABEL = os.environ.get("TECHMEME_PROCESSED_LABEL", "techmeme-processed")

CLAUDE_MODEL = "claude-haiku-4-5"

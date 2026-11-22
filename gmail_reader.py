import email
import email.message
import imaplib
from dataclasses import dataclass
from datetime import date, timedelta
from email.header import decode_header
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

import config

BLOCK_TAGS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "table"}
SKIP_TAGS = {"script", "style"}


class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML-to-text stripper: keeps text content, inserts newlines at
    block boundaries so headline items stay on separate lines for the LLM."""

    def __init__(self):
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip_depth += 1
        elif tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in BLOCK_TAGS:
            self._chunks.append("\n")

    def handle_data(self, data):
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


def _html_to_text(html: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    lines = [line.strip() for line in parser.text().splitlines()]
    return "\n".join(line for line in lines if line)


def _decode_subject(raw_subject: str) -> str:
    parts = decode_header(raw_subject or "")
    decoded = []
    for text, encoding in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded.append(text)
    return "".join(decoded)


def _extract_body(msg: email.message.Message) -> str:
    plain_text = None
    html_text = None

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")
            if "attachment" in disposition:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if content_type == "text/plain" and plain_text is None:
                plain_text = text
            elif content_type == "text/html" and html_text is None:
                html_text = text
    else:
        payload = msg.get_payload(decode=True)
        if payload is not None:
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                html_text = text
            else:
                plain_text = text

    if plain_text:
        return plain_text
    if html_text:
        return _html_to_text(html_text)
    return ""


@dataclass
class DigestEmail:
    uid: bytes
    received_date: str  # ISO date, e.g. "2026-08-03"
    subject: str
    body: str


def fetch_unprocessed_digests() -> list[DigestEmail]:
    """Gmail-search for Techmeme digest emails not yet tagged with the
    processed label, oldest first.

    Deliberately ignores the \\Seen flag: the user often reads the digest in
    Gmail before the daily job runs, which would otherwise make it invisible
    to an UNSEEN-based search. The processed label is the only dedup state,
    set by mark_as_processed() once a digest's signals are written to
    Sheet3, so a job that missed a day or two (script was down, or the user
    read several digests before catching up) still processes everything on
    the next run.

    Bounded to the last config.ROLLING_WINDOW_DAYS (matches the weekly pipeline's
    pruning window) so a long-stale inbox doesn't trigger ingesting -- and
    burning Claude calls on -- months of backlog that would just get pruned
    from Sheet3 on the next weekly run anyway. Older unprocessed digests are
    left untouched in the inbox, not labeled or deleted.
    """
    conn = imaplib.IMAP4_SSL(config.IMAP_HOST, timeout=60)
    try:
        conn.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        conn.select("INBOX")

        cutoff = date.today() - timedelta(days=config.ROLLING_WINDOW_DAYS)
        raw_query = (
            f"from:({config.TECHMEME_SENDER}) -label:{config.TECHMEME_PROCESSED_LABEL} "
            f"after:{cutoff:%Y/%m/%d}"
        )
        status, data = conn.uid("SEARCH", None, "X-GM-RAW", f'"{raw_query}"')
        if status != "OK":
            return []

        uids = data[0].split()
        digests = []
        for uid in uids:
            status, msg_data = conn.uid("FETCH", uid, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            received_at = parsedate_to_datetime(msg.get("Date"))
            digests.append(
                DigestEmail(
                    uid=uid,
                    received_date=received_at.date().isoformat(),
                    subject=_decode_subject(msg.get("Subject")),
                    body=_extract_body(msg),
                )
            )

        digests.sort(key=lambda d: d.received_date)
        return digests
    finally:
        try:
            conn.logout()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass


def mark_as_processed(uid: bytes) -> None:
    conn = imaplib.IMAP4_SSL(config.IMAP_HOST, timeout=60)
    try:
        conn.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        conn.select("INBOX")
        conn.uid("STORE", uid, "+X-GM-LABELS", f"({config.TECHMEME_PROCESSED_LABEL})")
    finally:
        try:
            conn.logout()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass

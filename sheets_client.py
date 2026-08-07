from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

import config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

REPORT_COLUMNS = [
    "date",
    "action",
    "ticker",
    "conviction",
    "reasoning",
    "signal_quality",
    "overall_sentiment",
]

# Matches Sheet3's actual header row exactly, including the trailing space on
# "industry " — column order matters for values().append, header text does not.
SIGNAL_COLUMNS = [
    "date",
    "headline",
    "company",
    "category",
    "industry",
    "sentiment",
    "stock_ticker",
    "signal_strength",
    "financial_value",
    "is_sponsored",
]


def _get_service():
    credentials = service_account.Credentials.from_service_account_file(
        config.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=credentials)


def get_signal_rows() -> list[dict[str, Any]]:
    """Port of the "Get row(s) in sheet" node: read all signal rows as dicts keyed by header."""
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=config.GOOGLE_SHEET_ID, range=config.SIGNALS_SHEET_NAME)
        .execute()
    )
    values = result.get("values", [])
    if not values:
        return []

    header, *rows = values
    signals = []
    for row in rows:
        padded = row + [""] * (len(header) - len(row))
        signals.append(dict(zip(header, padded)))
    return signals


def append_recommendations(recommendations: list[dict[str, Any]]) -> None:
    """Port of the "Append row" node: append recommendation rows to the WeeklyReports sheet."""
    if not recommendations:
        return

    service = _get_service()
    rows = [[rec.get(col, "") for col in REPORT_COLUMNS] for rec in recommendations]
    service.spreadsheets().values().append(
        spreadsheetId=config.GOOGLE_SHEET_ID,
        range=config.REPORTS_SHEET_NAME,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()


def append_signal_rows(signals: list[dict[str, Any]]) -> None:
    """Companion-workflow write: append daily-digest signal rows to Sheet3."""
    if not signals:
        return

    service = _get_service()
    rows = [[signal.get(col, "") for col in SIGNAL_COLUMNS] for signal in signals]
    service.spreadsheets().values().append(
        spreadsheetId=config.GOOGLE_SHEET_ID,
        range=config.SIGNALS_SHEET_NAME,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()


def prune_signal_rows(keep_after: str) -> None:
    """Enforces the rolling window: drops signal rows older than `keep_after`
    (an ISO date string, "YYYY-MM-DD") and rewrites Sheet3 with only the rows
    still within the window. Replaces the original n8n node's full weekly
    clear now that Sheet3 is a rolling multi-week buffer rather than a
    once-a-week snapshot.
    """
    signals = get_signal_rows()
    kept = [s for s in signals if s.get("date", "") >= keep_after]

    service = _get_service()
    service.spreadsheets().values().clear(
        spreadsheetId=config.GOOGLE_SHEET_ID,
        range=f"{config.SIGNALS_SHEET_NAME}!A2:ZZ5000",
        body={},
    ).execute()

    if kept:
        rows = [[s.get(col, "") for col in SIGNAL_COLUMNS] for s in kept]
        service.spreadsheets().values().update(
            spreadsheetId=config.GOOGLE_SHEET_ID,
            range=f"{config.SIGNALS_SHEET_NAME}!A2",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()


def clear_signal_rows() -> None:
    """Manual/administrative full reset of Sheet3 (not used by the weekly
    pipeline, which now calls prune_signal_rows to maintain a rolling window
    instead of clearing everything each week).
    """
    service = _get_service()
    service.spreadsheets().values().clear(
        spreadsheetId=config.GOOGLE_SHEET_ID,
        range=f"{config.SIGNALS_SHEET_NAME}!A2:ZZ5000",
        body={},
    ).execute()

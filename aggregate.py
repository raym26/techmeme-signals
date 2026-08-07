from datetime import date, datetime, timedelta
from typing import Any

import config


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _tally(signals: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for signal in signals:
        key = signal.get(field)
        counts[key] = counts.get(key, 0) + 1
    return counts


def build_summary(signals: list[dict[str, Any]], as_of: date | None = None) -> dict[str, Any]:
    """Builds a tiered summary for the weekly analysis prompt.

    Sheet3 is a rolling window (see sheets_client.prune_signal_rows), so it can
    hold up to config.ROLLING_WINDOW_DAYS of accumulated signals rather than
    just one week. To keep the prompt bounded regardless of how much has
    accumulated, only the most recent config.CURRENT_WEEK_DAYS of signals are
    sent in full detail; everything older (but still within the rolling
    window) is reduced to aggregate counts plus high-value signals only, so
    multi-week momentum stays visible without re-sending every headline.
    """
    as_of = as_of or date.today()
    current_week_start = as_of - timedelta(days=config.CURRENT_WEEK_DAYS - 1)

    current_week: list[dict[str, Any]] = []
    prior_weeks: list[dict[str, Any]] = []

    for signal in signals:
        signal_date = _parse_date(signal.get("date", ""))
        if signal_date is not None and signal_date >= current_week_start:
            current_week.append(signal)
        else:
            prior_weeks.append(signal)

    all_dates = [d for d in (_parse_date(s.get("date", "")) for s in signals) if d is not None]

    return {
        "total_signals": len(signals),
        "date_range": {
            "start": min(all_dates).isoformat() if all_dates else "Unknown",
            "end": max(all_dates).isoformat() if all_dates else "Unknown",
        },
        "current_week": {
            "date_range": {
                "start": current_week_start.isoformat(),
                "end": as_of.isoformat(),
            },
            "total_signals": len(current_week),
            "signals_by_category": _tally(current_week, "category"),
            "signals_by_sentiment": _tally(current_week, "sentiment"),
            "all_signals": current_week,
        },
        "prior_weeks_summary": {
            "total_signals": len(prior_weeks),
            "signals_by_category": _tally(prior_weeks, "category"),
            "signals_by_sentiment": _tally(prior_weeks, "sentiment"),
            "signals_by_signal_strength": _tally(prior_weeks, "signal_strength"),
            "high_value_signals": [s for s in prior_weeks if s.get("signal_strength") == "High"],
        },
    }

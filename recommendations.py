from datetime import date
from typing import Any


def build_recommendation_rows(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Maps Claude's structured recommendations + market_summary onto WeeklyReports
    rows. Replaces the original n8n "Code" node's markdown regex-parsing — Claude
    now returns clean structured data directly (see analyzer.py's output_config
    schema), so there's no section-boundary/ticker-regex guessing involved.
    """
    today = date.today().isoformat()
    market_summary = analysis.get("market_summary", {})
    signal_quality = market_summary.get("signal_quality", "N/A")
    overall_sentiment = market_summary.get("sentiment_shift", "Unknown")

    rows = [
        {
            "date": today,
            "action": rec.get("action", ""),
            "ticker": rec.get("ticker", ""),
            "conviction": f"{rec.get('conviction', '')} Conviction".strip(),
            "reasoning": rec.get("reasoning", ""),
            "signal_quality": signal_quality,
            "overall_sentiment": overall_sentiment,
        }
        for rec in analysis.get("recommendations", [])
    ]

    if not rows:
        rows.append(
            {
                "date": today,
                "action": "NO_RECS",
                "ticker": "NONE",
                "conviction": "N/A",
                "reasoning": "No recommendations found",
                "signal_quality": signal_quality,
                "overall_sentiment": overall_sentiment,
            }
        )

    return rows

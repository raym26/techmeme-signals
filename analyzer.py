import json
from typing import Any

import anthropic

import config

PROMPT_TEMPLATE = """Analyze these tech market signals for investment decisions. Your goal is to help the user beat market benchmarks in a 1-2 year timeframe.

The data below is tiered: "current_week" contains full detail for every signal from the most \
recent week, since that's most actionable right now. "prior_weeks_summary" covers the prior \
weeks within the rolling window as aggregate counts (by category, sentiment, signal strength) \
plus the individual high-value signals from that period — use it to spot signals that have been \
building momentum over multiple weeks, not just this week's snapshot.

{signals_json}

Return your analysis as the structured object described by the response schema:

- narrative_markdown: the write-up, in markdown, covering exactly these five sections — no \
more, no less. Do NOT write a "top stock recommendations" section here: the specific ticker \
calls belong only in the `recommendations` field below and are rendered as a table separately, \
so writing them out again in prose here would just duplicate that table and burn space needed \
for the sections below.
  **BUY SIGNALS:** which sectors are accelerating and why, at the sector/theme level — not a \
repeat of the per-ticker reasoning that belongs in `recommendations`.
  **SELL/AVOID SIGNALS:** which sectors show concerning developments, regulatory risk, or \
competitive threats — again at the sector/theme level, not per-ticker detail.
  **CRYPTO IMPLICATIONS:** how these signals affect crypto/blockchain markets, AI + crypto \
intersection opportunities.
  **SECOND-ORDER EFFECTS:** unusual, surprising, non-obvious companies worth investigating as a \
result of the above trends — this section is required and must not be dropped or shortened to \
make room for the earlier sections.
  **AI WATCH:** exactly 2-3 interesting AI developments from this week's signals, picked purely \
for being notable or worth knowing about — NOT filtered through an investment/trading lens. This \
is a "what's new in AI" pulse check, separate from the market-signal sections above; a genuinely \
interesting development belongs here even if it has no clear stock angle. One or two sentences \
per item. Keep this section short — it must not crowd out SECOND-ORDER EFFECTS above.
  This text is emailed to the user as-is. Keep each section focused and avoid restating the \
same point in multiple sections — thoroughness means covering more distinct ideas, not writing \
more words about the same idea.

- recommendations: one entry per concrete ticker-level BUY or SELL call, covering both the \
sector trends above and any second-order-effects picks — ticker, action, conviction \
(High/Medium/Low), and a one-to-two sentence reasoning specific to that ticker. This is the only \
place ticker-level reasoning should appear.

- market_summary: overall market sentiment shift (a short phrase), a signal quality score from \
1 to 10, and a risk level assessment (Low/Medium/High).

Focus on actionable trading insights based on the signal patterns.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "narrative_markdown": {"type": "string"},
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "action": {"type": "string", "enum": ["BUY", "SELL"]},
                    "conviction": {"type": "string", "enum": ["High", "Medium", "Low"]},
                    "reasoning": {"type": "string"},
                },
                "required": ["ticker", "action", "conviction", "reasoning"],
                "additionalProperties": False,
            },
        },
        "market_summary": {
            "type": "object",
            "properties": {
                "sentiment_shift": {"type": "string"},
                "signal_quality": {"type": "integer"},
                "risk_level": {"type": "string"},
            },
            "required": ["sentiment_shift", "signal_quality", "risk_level"],
            "additionalProperties": False,
        },
    },
    "required": ["narrative_markdown", "recommendations", "market_summary"],
    "additionalProperties": False,
}


def analyze(summary: dict[str, Any]) -> dict[str, Any]:
    """Port of the "AI Agent" node, using Claude Sonnet 5.5 with structured outputs
    instead of freeform markdown + regex parsing (see recommendations.py)."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    prompt = PROMPT_TEMPLATE.format(signals_json=json.dumps(summary, indent=2))

    response = client.messages.create(
        model=config.ANALYZER_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )

    text = next((block.text for block in response.content if block.type == "text"), "{}")
    return json.loads(text)

import json
from typing import Any

import anthropic

import config

SYSTEM_PROMPT = """You extract structured tech/market signal rows from a raw Techmeme daily \
digest email. The email lists news headlines grouped under section labels like "top news", \
"artificial intelligence", "data centers", "cryptocurrency", "funding deals", and "more news". \
Each real headline is a single summary sentence, usually ending in "(Author Name / Publication)".

Extract ONE row per genuine headline. Skip:
- SPONSOR / advertisement blocks (they have no "(Author / Publication)" citation and are not news)
- The "tomorrow's events" / calendar line at the top of the email
- Embedded tweet-reaction quotes (lines starting with "@handle:") — these are commentary on a \
headline, not a headline themselves

For each headline, infer:
- headline: the summary sentence only, with the "(Author / Publication)" citation stripped off
- company: the primary company the headline is about (best single company name; use "Unknown" \
if no specific company is the subject)
- category: a short freeform label for what kind of news this is (e.g. "Product Launch", \
"Regulatory", "Funding", "M&A", "Earnings", "Security", "AI/ML", "Business")
- industry: a short freeform label for the broader industry/sector (e.g. "Technology", \
"Artificial Intelligence", "Cryptocurrency", "Data Centers")
- sentiment: "positive", "neutral", or "negative" from the perspective of the company/companies \
most central to the headline
- stock_ticker: the uppercase ticker symbol if the central company is publicly traded, else \
"private"
- signal_strength: "Low", "Medium", or "High" — how market-moving or significant this headline \
is likely to be
- financial_value: a dollar figure explicitly mentioned in the headline if any (e.g. "$1.94B"), \
else "none"
- is_sponsored: true only for genuine sponsored/advertisement content, false otherwise
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "company": {"type": "string"},
                    "category": {"type": "string"},
                    "industry": {"type": "string"},
                    "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
                    "stock_ticker": {"type": "string"},
                    "signal_strength": {"type": "string", "enum": ["Low", "Medium", "High"]},
                    "financial_value": {"type": "string"},
                    "is_sponsored": {"type": "boolean"},
                },
                "required": [
                    "headline",
                    "company",
                    "category",
                    "industry",
                    "sentiment",
                    "stock_ticker",
                    "signal_strength",
                    "financial_value",
                    "is_sponsored",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["signals"],
    "additionalProperties": False,
}


def extract_signals(digest_text: str, digest_date: str) -> list[dict[str, Any]]:
    """Calls Claude (Haiku 5.5) with structured outputs to turn a raw digest
    email body into rows matching Sheet3's schema."""
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=config.EXTRACTOR_MODEL,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": digest_text}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )

    text = next((block.text for block in response.content if block.type == "text"), "{}")
    parsed = json.loads(text)
    signals = parsed.get("signals", [])

    for signal in signals:
        signal["date"] = digest_date
        signal["is_sponsored"] = "TRUE" if signal.get("is_sponsored") else "FALSE"

    return signals

from typing import Any

import markdown

ACTION_COLORS = {"BUY": "#1a7f37", "SELL": "#cf222e"}

BASE_STYLE = """
<div style="font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
            max-width: 720px; color: #1f2328; line-height: 1.5;">
{body}
</div>
"""


def to_html(markdown_text: str) -> str:
    """Converts Claude's markdown narrative to HTML using the standard `markdown`
    library (headers, bold, lists, and tables all handled correctly) instead of
    the original n8n node's narrow regex converter, which only understood
    **bold**-wrapped headers and simple lists — it silently passed through plain
    `#` headers, `---` rules, and markdown tables as raw text.
    """
    if not markdown_text:
        return "<p>No analysis available.</p>"
    return markdown.markdown(markdown_text, extensions=["tables", "fenced_code", "nl2br"])


def _market_summary_html(market_summary: dict[str, Any]) -> str:
    sentiment = market_summary.get("sentiment_shift", "Unknown")
    quality = market_summary.get("signal_quality", "N/A")
    risk = market_summary.get("risk_level", "Unknown")

    return f"""
<div style="background: #f6f8fa; border-radius: 6px; padding: 12px 16px; margin: 16px 0;">
  <strong>Market Summary</strong><br>
  Sentiment shift: {sentiment}<br>
  Signal quality: {quality}/10<br>
  Risk level: {risk}
</div>
"""


def _recommendations_table_html(recommendations: list[dict[str, Any]]) -> str:
    """Builds the ticker recommendations table deterministically from Claude's
    structured `recommendations` array, rather than asking Claude to write this
    out a second time as prose (which is what caused truncation and duplication
    in the old freeform-narrative design)."""
    if not recommendations:
        return "<p><em>No specific ticker recommendations this week.</em></p>"

    rows = []
    for rec in recommendations:
        action = rec.get("action", "")
        color = ACTION_COLORS.get(action, "#57606a")
        pct_off_high = rec.get("pct_off_52wk_high")
        pct_off_high_display = f"{pct_off_high:.1f}%" if pct_off_high is not None else "—"
        rows.append(
            f"""<tr>
  <td style="padding: 6px 10px; border-bottom: 1px solid #d0d7de; color: {color}; font-weight: 600;">{action}</td>
  <td style="padding: 6px 10px; border-bottom: 1px solid #d0d7de; font-weight: 600;">{rec.get("ticker", "")}</td>
  <td style="padding: 6px 10px; border-bottom: 1px solid #d0d7de;">{rec.get("conviction", "")}</td>
  <td style="padding: 6px 10px; border-bottom: 1px solid #d0d7de;">{pct_off_high_display}</td>
  <td style="padding: 6px 10px; border-bottom: 1px solid #d0d7de;">{rec.get("reasoning", "")}</td>
</tr>"""
        )

    return f"""
<table style="border-collapse: collapse; width: 100%; margin: 12px 0;">
  <thead>
    <tr style="text-align: left; border-bottom: 2px solid #1f2328;">
      <th style="padding: 6px 10px;">Action</th>
      <th style="padding: 6px 10px;">Ticker</th>
      <th style="padding: 6px 10px;">Conviction</th>
      <th style="padding: 6px 10px;">vs 52wk High</th>
      <th style="padding: 6px 10px;">Reasoning</th>
    </tr>
  </thead>
  <tbody>
    {"".join(rows)}
  </tbody>
</table>
"""


def render_email_html(analysis: dict[str, Any]) -> str:
    """Builds the full report email: Claude's narrative (BUY/SELL sector
    analysis, crypto implications, second-order-effects picks) followed by a
    deterministic market-summary block and recommendations table built from
    the structured data, not re-generated prose."""
    narrative_html = to_html(analysis.get("narrative_markdown", ""))
    summary_html = _market_summary_html(analysis.get("market_summary", {}))
    table_html = _recommendations_table_html(analysis.get("recommendations", []))

    body = f"""{narrative_html}
<h2>Top Recommendations</h2>
{table_html}
{summary_html}"""

    return BASE_STYLE.format(body=body)

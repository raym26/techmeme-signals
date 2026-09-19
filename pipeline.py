import logging
from datetime import date, timedelta

import aggregate
import analyzer
import config
import emailer
import html_report
import market_data
import recommendations
import sheets_client

logger = logging.getLogger(__name__)


def run() -> None:
    """Runs the full pipeline once, mirroring the n8n node graph end-to-end.

    Sheet3 is a rolling window (config.ROLLING_WINDOW_DAYS), not cleared each
    run: signals older than the window are pruned after analysis, and the
    current week's signals stay in the sheet for next week's momentum context.
    """
    today = date.today()

    logger.info("Reading signal rows from sheet")
    signals = sheets_client.get_signal_rows()

    if not signals:
        logger.info("No signals found; skipping run")
        return

    logger.info("Aggregating %d signals (tiered: current week + prior weeks)", len(signals))
    summary = aggregate.build_summary(signals, as_of=today)

    logger.info("Requesting structured analysis from Claude")
    analysis = analyzer.analyze(summary)

    logger.info("Fetching 52-week-high context for recommended tickers")
    market_data.attach_pct_off_high(analysis.get("recommendations", []))

    logger.info("Building recommendation rows and email content")
    recs = recommendations.build_recommendation_rows(analysis)
    html_content = html_report.render_email_html(analysis)

    logger.info("Appending %d recommendations to %s", len(recs), config.REPORTS_SHEET_NAME)
    sheets_client.append_recommendations(recs)

    logger.info("Sending report email")
    emailer.send_report(html_content)

    cutoff = (today - timedelta(days=config.ROLLING_WINDOW_DAYS - 1)).isoformat()
    logger.info("Pruning signal rows older than %s (rolling %d-day window)", cutoff, config.ROLLING_WINDOW_DAYS)
    sheets_client.prune_signal_rows(keep_after=cutoff)

    logger.info("Pipeline run complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

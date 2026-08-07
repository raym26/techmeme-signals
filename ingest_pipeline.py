import logging

import extractor
import gmail_reader
import sheets_client

logger = logging.getLogger(__name__)


def run() -> None:
    """Daily companion pipeline: pulls the Techmeme digest email, extracts
    structured signal rows via Claude, appends them to Sheet3, and tags the
    email as processed. Processes every unprocessed digest found, oldest
    first, so a missed day or two is caught up automatically."""
    logger.info("Checking for unprocessed Techmeme digest emails")
    digests = gmail_reader.fetch_unprocessed_digests()

    if not digests:
        logger.info("No unprocessed Techmeme digests found")
        return

    for digest in digests:
        logger.info("Processing digest from %s (%s)", digest.received_date, digest.subject)

        if not digest.body.strip():
            logger.warning("Digest from %s had an empty body; skipping", digest.received_date)
            continue

        signals = extractor.extract_signals(digest.body, digest.received_date)
        logger.info("Extracted %d signal rows", len(signals))

        if signals:
            sheets_client.append_signal_rows(signals)

        gmail_reader.mark_as_processed(digest.uid)
        logger.info("Marked digest from %s as processed", digest.received_date)

    logger.info("Ingest run complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()

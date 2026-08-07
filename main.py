import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import ingest_pipeline
import pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    scheduler = BlockingScheduler()

    # Daily companion job: pulls the Techmeme digest email and populates Sheet3.
    daily_trigger = CronTrigger(hour=21, minute=0)
    scheduler.add_job(ingest_pipeline.run, daily_trigger, name="techmeme-daily-ingest")

    # Mirrors the n8n Schedule Trigger node: weekly, Friday, 17:45.
    weekly_trigger = CronTrigger(day_of_week="fri", hour=17, minute=45)
    scheduler.add_job(pipeline.run, weekly_trigger, name="techmeme-weekly-report")

    logger.info("Scheduler starting. Daily ingest fires at 21:00; weekly report fires Friday at 17:45.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    main()

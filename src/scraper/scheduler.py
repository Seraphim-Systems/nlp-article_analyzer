"""
Daily scraper scheduler.

Runs once a day at midnight (configurable via settings.SCRAPE_HOUR).
On each run it fetches today's articles from all configured RSS feeds
and bulk-inserts them into the raw MongoDB collection.

Usage
-----
    python -m scraper.scheduler
    python scripts/run_daily.py
"""

from __future__ import annotations

import logging
import time
from datetime import date

import schedule

from config.settings import settings
from database.repositories import insert_raw_articles
from scraper.scraper import build_rss_scrapers

logger = logging.getLogger(__name__)


def run_scrape_job(for_date: date | None = None) -> None:
    """
    Execute one full scrape cycle.

    Parameters
    ----------
    for_date : date, optional
        Override the target date (useful for back-filling). Defaults to today.
    """
    target = for_date or date.today()
    logger.info("=== Scrape job started for %s ===", target)

    all_articles: list[dict] = []
    for scraper in build_rss_scrapers():
        try:
            articles = scraper.scrape_today(target)
            all_articles.extend(articles)
        except Exception:
            logger.exception("Scraper '%s' raised an unhandled exception.", scraper.name)

    inserted = insert_raw_articles(all_articles)
    logger.info(
        "=== Scrape job finished: %d articles collected, %d newly inserted ===",
        len(all_articles),
        inserted,
    )


def start_scheduler() -> None:
    """
    Block forever, running the scrape job daily at settings.SCRAPE_HOUR:00 UTC.
    """
    hour = settings.SCRAPE_HOUR
    logger.info("Scheduler started — daily scrape at %02d:00 UTC.", hour)
    schedule.every().day.at(f"{hour:02d}:00").do(run_scrape_job)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    start_scheduler()

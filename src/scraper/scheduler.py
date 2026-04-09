"""
Daily scraper scheduler.

Runs once a day at midnight (configurable via settings.SCRAPE_HOUR).
On each run it:
  1. Calls every registered scraper to collect today's articles.
  2. Bulk-inserts the results into the raw MongoDB collection.

This module can be run directly:
    python -m scraper.scheduler

Or invoked from scripts/run_daily.py by an OS-level cron / Task Scheduler job.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date

import schedule  # pip install schedule

from config.settings import settings
from database.repositories import insert_raw_articles
from scraper.scrapers.rss_scraper import build_rss_scrapers

logger = logging.getLogger(__name__)


def _collect_all_scrapers():
    """Return all active scraper instances."""
    scrapers = []
    scrapers.extend(build_rss_scrapers())
    # Add additional scraper types here as the project grows:
    # scrapers.extend(build_web_scrapers())
    return scrapers


def run_scrape_job(
    for_date: date | None = None,
    run_cleaning: bool | None = None,
    log_fn=None,
    stop_event: threading.Event | None = None,
) -> None:
    """
    Execute one full scrape cycle.

    Parameters
    ----------
    for_date : date, optional
        Override the target date (useful for back-filling). Defaults to today.
    log_fn : callable, optional
        Called with a progress string after each feed completes.
    """
    log = log_fn or (lambda _: None)
    _stop = stop_event or threading.Event()
    target = for_date or date.today()
    logger.info("=== Scrape job started for %s ===", target)

    scrapers = _collect_all_scrapers()
    all_articles: list[dict] = []
    log(f"Found {len(scrapers)} feeds to scrape")

    for scraper in scrapers:
        if _stop.is_set():
            log("Scrape cancelled.")
            break
        log(f"Fetching: {scraper.name}...")
        try:
            articles = scraper.scrape_today(target)
            all_articles.extend(articles)
            log(f"  {scraper.name}: {len(articles)} articles collected")
        except Exception:
            log(f"  {scraper.name}: failed")
            logger.exception("Scraper '%s' raised an unhandled exception.", scraper.name)

    log(f"Inserting {len(all_articles)} articles into raw_articles...")
    inserted = insert_raw_articles(all_articles)
    log(f"Inserted {inserted} new articles")
    logger.info(
        "=== Scrape job finished: %d articles collected, %d newly inserted ===",
        len(all_articles),
        inserted,
    )

    should_run_cleaning = settings.RUN_CLEAN_AFTER_SCRAPE if run_cleaning is None else run_cleaning
    if should_run_cleaning:
        log("Running cleaning pipeline after scrape...")
        from cleaning.cleaner import run_cleaning_pipeline

        summary = run_cleaning_pipeline()
        log(f"Cleaning done: promoted={summary.get('promoted',0)}, discarded={summary.get('discarded',0)}")
        logger.info("=== Cleaning finished after scrape: %s ===", summary)


def start_scheduler() -> None:
    """
    Block forever, running the scrape job daily at settings.SCRAPE_HOUR:00 UTC.
    Designed to be called from the main process or a long-running service.
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

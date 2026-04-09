"""
Scrape job - collects articles from RSS feeds and ingests into raw collection.

Entry point: run()
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


def run(for_date: date | None = None, dry_run: bool = False, log_fn=None, stop_event: threading.Event | None = None) -> dict[str, Any]:
    """
    Execute a scrape job.

    Collects articles from all configured RSS feeds and inserts them into the
    raw articles collection.

    Parameters
    ----------
    for_date : date, optional
        Target date for scraping. Defaults to today.
    dry_run : bool
        If True, scrape but don't insert into DB.

    Returns
    -------
    dict
        Result with keys:
        - status: 'success' or 'failed'
        - collected: number of articles collected
        - inserted: number of articles newly inserted
        - errors: list of error messages
        - duration_seconds: execution time
    """
    log = log_fn or (lambda _: None)
    _stop = stop_event or threading.Event()
    start_time = time.time()
    result: dict[str, Any] = {
        "status": "success",
        "collected": 0,
        "inserted": 0,
        "errors": [],
        "duration_seconds": 0,
    }

    try:
        from database.init_db import init_databases

        init_databases()

        target = for_date or date.today()
        logger.info("=== Scrape job started for %s ===", target)
        log(f"Initializing for date: {target}")

        from scraper.scheduler import run_scrape_job

        if dry_run:
            log("Dry run — skipping feed collection")
            logger.info("DRY RUN: Would scrape for date %s", target)
        else:
            log("Fetching RSS feeds and collecting articles...")
            run_scrape_job(for_date=target, log_fn=log, stop_event=_stop)
            log("Feed collection complete")
            logger.info("Scrape job completed for %s", target)

        result["status"] = "success"

    except Exception as e:
        logger.exception("Scrape job failed")
        log(f"Error: {e}")
        result["status"] = "failed"
        result["errors"].append(str(e))

    finally:
        result["duration_seconds"] = time.time() - start_time
        log(f"Finished in {result['duration_seconds']:.1f}s — status: {result['status']}")
        logger.info(
            "=== Scrape job finished (status=%s, duration=%.2fs) ===",
            result["status"],
            result["duration_seconds"],
        )

    return result


__all__ = ["run"]

"""
Scrape job - collects articles from RSS feeds and ingests into raw collection.

Entry point: run()
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


def run(for_date: date | None = None, dry_run: bool = False) -> dict[str, Any]:
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
    start_time = time.time()
    result: dict[str, Any] = {
        "status": "success",
        "collected": 0,
        "inserted": 0,
        "errors": [],
        "duration_seconds": 0,
    }

    try:
        # Initialize databases on first run
        from database.init_db import init_databases

        init_databases()

        target = for_date or date.today()
        logger.info("=== Scrape job started for %s ===", target)

        # Import scraper logic
        from scraper.scheduler import run_scrape_job

        if dry_run:
            logger.info("DRY RUN: Would scrape for date %s", target)
        else:
            run_scrape_job(for_date=target)
            logger.info("Scrape job completed for %s", target)

        result["status"] = "success"

    except Exception as e:
        logger.exception("Scrape job failed")
        result["status"] = "failed"
        result["errors"].append(str(e))

    finally:
        result["duration_seconds"] = time.time() - start_time
        logger.info(
            "=== Scrape job finished (status=%s, duration=%.2fs) ===",
            result["status"],
            result["duration_seconds"],
        )

    return result


__all__ = ["run"]

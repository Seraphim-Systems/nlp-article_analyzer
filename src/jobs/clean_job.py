"""
Clean job - runs the data quality cleaning pipeline on raw articles.

Entry point: run()
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


def run(limit: int = 0, dry_run: bool = False, log_fn=None) -> dict[str, Any]:
    """
    Execute the cleaning job.

    Runs the full cleaning pipeline on raw articles:
    1. Rank unranked articles
    2. Attempt to recover Rank-1 (incomplete) articles via URL re-fetch
    3. Promote Rank-0 articles to clean collection
    4. Delete Rank-2 articles (discarded)

    Parameters
    ----------
    limit : int
        Maximum number of articles to process in recovery and promotion steps.
    dry_run : bool
        If True, analyze but don't update collections.

    Returns
    -------
    dict
        Result with keys:
        - status: 'success' or 'failed'
        - promoted: articles moved to clean collection
        - discarded: articles deleted
        - errors: list of error messages
        - duration_seconds: execution time
    """
    log = log_fn or (lambda _: None)
    _stop = threading.Event()
    start_time = time.time()
    result: dict[str, Any] = {
        "status": "success",
        "promoted": 0,
        "discarded": 0,
        "errors": [],
        "duration_seconds": 0,
    }

    try:
        from database.init_db import init_databases

        init_databases()

        logger.info("=== Clean job started ===")
        log("Ranking raw articles...")

        if _stop.is_set():
            result["status"] = "cancelled"
            return result

        if dry_run:
            log("Dry run — no changes committed")
            logger.info("DRY RUN: Cleaning pipeline would run")
        else:
            from cleaning.cleaner import run_cleaning_pipeline

            log("Running cleaning pipeline: rank, recover, promote...")
            summary = run_cleaning_pipeline(limit=limit)
            result["promoted"] = summary.get("promoted", 0)
            result["discarded"] = summary.get("discarded", 0)
            log(f"Promoted {result['promoted']:,} articles to clean collection")
            log(f"Discarded {result['discarded']:,} rank-2 articles")
            logger.info("Clean job completed: %s", summary)

        result["status"] = "success"

    except Exception as e:
        logger.exception("Clean job failed")
        log(f"Error: {e}")
        result["status"] = "failed"
        result["errors"].append(str(e))

    finally:
        result["duration_seconds"] = time.time() - start_time
        log(f"Finished in {result['duration_seconds']:.1f}s — status: {result['status']}")
        logger.info(
            "=== Clean job finished (status=%s, duration=%.2fs) ===",
            result["status"],
            result["duration_seconds"],
        )

    return result


__all__ = ["run"]

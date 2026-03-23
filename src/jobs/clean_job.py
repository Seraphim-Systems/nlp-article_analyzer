"""
Clean job - runs the data quality cleaning pipeline on raw articles.

Entry point: run()
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def run(dry_run: bool = False) -> dict[str, Any]:
    """
    Execute the cleaning job.

    Runs the full cleaning pipeline on raw articles:
    1. Rank unranked articles
    2. Attempt to recover Rank-1 (incomplete) articles via URL re-fetch
    3. Promote Rank-0 articles to clean collection
    4. Delete Rank-2 articles (discarded)

    Parameters
    ----------
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
    start_time = time.time()
    result: dict[str, Any] = {
        "status": "success",
        "promoted": 0,
        "discarded": 0,
        "errors": [],
        "duration_seconds": 0,
    }

    try:
        # Initialize databases on first run
        from database.init_db import init_databases

        init_databases()

        logger.info("=== Clean job started ===")

        if dry_run:
            logger.info("DRY RUN: Cleaning pipeline would run")
        else:
            from cleaning.cleaner import run_cleaning_pipeline

            summary = run_cleaning_pipeline()
            result["promoted"] = summary.get("promoted", 0)
            result["discarded"] = summary.get("discarded", 0)
            logger.info("Clean job completed: %s", summary)

        result["status"] = "success"

    except Exception as e:
        logger.exception("Clean job failed")
        result["status"] = "failed"
        result["errors"].append(str(e))

    finally:
        result["duration_seconds"] = time.time() - start_time
        logger.info(
            "=== Clean job finished (status=%s, duration=%.2fs) ===",
            result["status"],
            result["duration_seconds"],
        )

    return result


__all__ = ["run"]

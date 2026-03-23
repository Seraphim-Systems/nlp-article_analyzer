"""
Classify job - tags cleaned articles with NLP classifications (category, entities, sentiment).

Entry point: run()

NOTE: This is a stub for Phase 3 implementation.
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


def run(for_date: date | None = None, dry_run: bool = False) -> dict[str, Any]:
    """
    Execute the classification job.

    Fetches all Rank-0 (clean) articles and applies NLP models:
    - Text classification (category/subcategory)
    - Named entity recognition
    - Sentiment analysis
    - Keyword extraction

    Upserts results into the classified collection.

    Parameters
    ----------
    for_date : date, optional
        Filter articles by publication date (optional).
    dry_run : bool
        If True, analyze but don't update collections.

    Returns
    -------
    dict
        Result with keys:
        - status: 'success' or 'failed'
        - classified_count: articles classified
        - errors: list of error messages
        - duration_seconds: execution time
    """
    start_time = time.time()
    result: dict[str, Any] = {
        "status": "success",
        "classified_count": 0,
        "errors": [],
        "duration_seconds": 0,
    }

    try:
        # Initialize databases on first run
        from database.init_db import init_databases

        init_databases()

        logger.info("=== Classify job started ===")

        if dry_run:
            logger.info("DRY RUN: Classification would run")
        else:
            logger.warning("Classify job not yet implemented (Phase 3)")
            logger.info("Would classify articles here")

        result["status"] = "success"

    except Exception as e:
        logger.exception("Classify job failed")
        result["status"] = "failed"
        result["errors"].append(str(e))

    finally:
        result["duration_seconds"] = time.time() - start_time
        logger.info(
            "=== Classify job finished (status=%s, duration=%.2fs) ===",
            result["status"],
            result["duration_seconds"],
        )

    return result


__all__ = ["run"]

"""
Classify job — extracts named entities from clean articles and writes results to ner_articles.

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
    Execute the NER classification job.

    Fetches all clean articles not yet in ner_articles, runs NER extraction
    via dslim/bert-base-NER, and upserts enriched documents into ner_articles.

    Parameters
    ----------
    for_date : date, optional
        Not used — kept for interface compatibility with other jobs.
    dry_run : bool
        If True, run extraction but skip DB writes.

    Returns
    -------
    dict
        Result with keys: status, classified_count, errors, duration_seconds
    """
    start_time = time.time()
    result: dict[str, Any] = {
        "status": "success",
        "classified_count": 0,
        "errors": [],
        "duration_seconds": 0,
    }

    try:
        from database.init_db import init_databases
        from database.repositories import get_unprocessed_clean_articles, insert_ner_articles
        from features.ner_extractor import batch_extract

        init_databases()

        logger.info("=== Classify (NER) job started ===")

        articles = get_unprocessed_clean_articles()
        logger.info("Found %d unprocessed clean articles", len(articles))

        if not articles:
            logger.info("No unprocessed articles — nothing to do.")
            return result

        from tqdm import tqdm

        BATCH = 64
        enriched: list[dict[str, Any]] = []
        total_written = 0

        for i in tqdm(range(0, len(articles), BATCH), desc="  NER", unit="batch", ncols=80):
            chunk = articles[i : i + BATCH]
            enriched_chunk = batch_extract(chunk)
            enriched.extend(enriched_chunk)

            if not dry_run and len(enriched) >= BATCH * 4:
                total_written += insert_ner_articles(enriched)
                enriched = []

        if not dry_run:
            if enriched:
                total_written += insert_ner_articles(enriched)
            result["classified_count"] = total_written
            logger.info("Wrote %d NER articles to ner_articles", total_written)
        else:
            result["classified_count"] = len(articles)
            logger.info("DRY RUN: would write %d articles to ner_articles", len(articles))

        logger.info("NER extraction complete: %d articles enriched", len(articles))

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

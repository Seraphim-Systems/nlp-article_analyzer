"""
Data cleaning pipeline.

Orchestrates the full cleaning flow on raw articles:

  Step 1 — Rank all unranked raw articles (assign rank 0 / 1 / 2).
  Step 2 — For Rank-1 articles: attempt to fill missing fields via URL re-fetch,
            then re-rank; articles that reach Rank 0 are promoted.
    Step 3 — Rank-0 articles are normalized/enriched and upserted to clean.
    Step 4 — Rank-2 articles are quarantined for auditing/recovery.

The raw collection retains original scraped data as a safety net. The clean
collection holds quality-verified and enriched
articles ready for downstream NLP processing.
"""

from __future__ import annotations

import logging
from typing import Any

from utils.progress import make_pbar_simple

from database.repositories import (
    bulk_update_raw_ranks,
    count_raw_articles_by_rank,
    get_raw_articles_by_rank,
    get_raw_collection,
    upsert_quarantine_articles,
    update_raw_article_fields,
    update_raw_rank,
    upsert_clean_articles,
)
from cleaning.normalizer import enrich_article_for_cleaning
from cleaning.ranker import rank_article_with_reasons
from cleaning.url_fetcher import fill_missing_fields

logger = logging.getLogger(__name__)


def _rank_unranked_articles() -> None:
    """
    Find all raw articles without a rank (rank=None) and assign one.
    This covers newly inserted articles from the scraper.
    """
    col_iter = __import__(
        "database.repositories", fromlist=["get_raw_collection"]
    ).get_raw_collection()
    unranked = list(col_iter.find({"rank": None}))
    if not unranked:
        logger.info("No unranked articles found.")
        return

    logger.info("Ranking %d unranked articles…", len(unranked))
    updates = []
    for article in make_pbar_simple(
        unranked, total=len(unranked), desc="Ranking", unit="art"
    ):
        rank, reasons = rank_article_with_reasons(article)
        updates.append((article["url"], rank, reasons))
    bulk_update_raw_ranks(updates)
    logger.info("Ranking complete.")


def _process_rank1(limit: int = 0, batch_size: int = 1000) -> None:
    """
    Attempt to recover Rank-1 articles by re-fetching their URLs.
    Updates the DB fields and re-assigns rank.

    Processes articles in batches to avoid memory bloat and timeouts.

    Parameters
    ----------
    limit : int
        Maximum total articles to process (0 = all)
    batch_size : int
        Number of articles per batch (default 1000)
    """
    total_rank1 = get_raw_collection().count_documents({"rank": 1})
    if total_rank1 == 0:
        logger.info("No Rank-1 articles to process.")
        return

    effective_limit = limit if limit > 0 else total_rank1
    logger.info(
        "Attempting to recover Rank-1 articles in batches of %d (total to process: %d)…",
        batch_size,
        min(effective_limit, total_rank1),
    )

    total_promoted = 0
    processed = 0
    batch_num = 0

    while processed < effective_limit:
        batch_num += 1
        remaining = effective_limit - processed
        current_batch_size = min(batch_size, remaining)

        rank1_articles = list(get_raw_articles_by_rank(1, limit=current_batch_size))
        if not rank1_articles:
            logger.info("No more Rank-1 articles found.")
            break

        logger.info(
            "Processing batch %d: %d articles (%d / %d total)…",
            batch_num,
            len(rank1_articles),
            processed + len(rank1_articles),
            effective_limit,
        )

        promoted = 0
        rank_updates = []

        for article in make_pbar_simple(
            rank1_articles,
            total=len(rank1_articles),
            desc=f"Batch {batch_num}",
            unit="art",
        ):
            patched = fill_missing_fields(article)
            new_rank, reasons = rank_article_with_reasons(patched)

            changed_fields = {
                k: patched[k]
                for k in patched
                if k not in ("_id", "rank") and patched[k] != article.get(k)
            }
            if changed_fields:
                update_raw_article_fields(article["url"], changed_fields)

            rank_updates.append((article["url"], new_rank, reasons))

            if new_rank == 0:
                promoted += 1

        bulk_update_raw_ranks(rank_updates)
        total_promoted += promoted
        processed += len(rank1_articles)

        logger.info(
            "Batch %d done: %d promoted to Rank 0. Total progress: %d / %d",
            batch_num,
            promoted,
            processed,
            effective_limit,
        )

    logger.info(
        "Rank-1 processing complete: %d articles promoted to Rank 0 (%d batches).",
        total_promoted,
        batch_num,
    )


def _promote_rank0_to_clean(limit: int = 0, batch_size: int = 500) -> int:
    """Copy all Rank-0 raw articles to the clean collection in batches."""
    total_rank0 = get_raw_collection().count_documents({"rank": 0})
    if total_rank0 == 0:
        logger.info("No Rank-0 articles to promote.")
        return 0

    effective_limit = limit if limit > 0 else total_rank0
    logger.info(
        "Promoting %d Rank-0 articles to clean collection (batch_size=%d)…",
        min(effective_limit, total_rank0),
        batch_size,
    )

    total_upserted = 0
    processed = 0
    batch_num = 0

    try:
        while processed < effective_limit:
            batch_num += 1
            remaining = effective_limit - processed
            current_batch_size = min(batch_size, remaining)

            rank0_articles = list(get_raw_articles_by_rank(0, limit=current_batch_size))
            if not rank0_articles:
                logger.info("No more Rank-0 articles found.")
                break

            logger.info(
                "Enriching batch %d: %d articles (processed %d / %d total)…",
                batch_num,
                len(rank0_articles),
                processed,
                effective_limit,
            )

            try:
                enriched = []
                for i, article in enumerate(
                    make_pbar_simple(
                        rank0_articles,
                        total=len(rank0_articles),
                        desc=f"Enrich B{batch_num}",
                        unit="art",
                    )
                ):
                    try:
                        enriched.append(enrich_article_for_cleaning(article))
                    except Exception as e:
                        logger.warning(
                            "Failed to enrich article %s: %s", article.get("url"), e
                        )
                        continue

                logger.info(
                    "Upserting %d enriched articles to clean collection…", len(enriched)
                )
                upserted = upsert_clean_articles(enriched)
                total_upserted += upserted
                processed += len(rank0_articles)

                logger.info(
                    "Batch %d complete: upserted %d articles. Total progress: %d / %d",
                    batch_num,
                    upserted,
                    processed,
                    effective_limit,
                )
            except Exception as e:
                logger.error(
                    "Error during batch %d enrichment: %s", batch_num, e, exc_info=True
                )
                raise

        logger.info(
            "Promotion complete: %d Rank-0 articles upserted to clean collection (%d batches).",
            total_upserted,
            batch_num,
        )
        return total_upserted
    except Exception as e:
        logger.error("Rank-0 promotion FAILED: %s", e, exc_info=True)
        raise


def _quarantine_rank2() -> int:
    """Store Rank-2 articles in quarantine for audit/recovery."""
    rank2_count = get_raw_collection().count_documents({"rank": 2})
    if rank2_count == 0:
        logger.info("No Rank-2 articles to quarantine.")
        return 0

    logger.info("Quarantining %d Rank-2 articles…", rank2_count)
    try:
        rank2_articles = list(get_raw_articles_by_rank(2))
        quarantined = upsert_quarantine_articles(rank2_articles)
        logger.info("Quarantined %d Rank-2 articles.", quarantined)
        return quarantined
    except Exception as e:
        logger.error("Quarantine FAILED: %s", e, exc_info=True)
        raise


def run_cleaning_pipeline(
    skip_rank1_recovery: bool = False, limit: int = 0, rank1_limit: int = 1000
) -> dict[str, int]:
    """
    Execute the full cleaning pipeline.

    Parameters
    ----------
    skip_rank1_recovery : bool
        If True, skip the URL re-fetch step for Rank-1 articles.
        Useful for large historical datasets where most URLs are dead.
    limit : int
        Maximum number of articles to process in recovery and promotion steps.
    rank1_limit : int
        Maximum number of Rank-1 articles to attempt URL recovery on (default 1000).
        Set to 0 to recover all Rank-1 articles (may be very slow).

    Returns a summary dict:
    {
        "ranked":   <articles newly ranked>,
        "promoted": <rank-0 articles moved to clean>,
        "discarded":<rank-2 articles deleted>,
    }
    """
    logger.info("=== Cleaning pipeline started ===")

    try:
        # Step 1: rank new articles
        logger.info("Step 1: Ranking unranked articles…")
        _rank_unranked_articles()
        logger.info("✓ Step 1 complete")

        # Step 2: try to recover rank-1 (skippable)
        logger.info("Step 2: Processing Rank-1 articles…")
        if skip_rank1_recovery:
            logger.info("Skipping Rank-1 URL recovery (skip_rank1_recovery=True)")
        else:
            effective_rank1_limit = rank1_limit if rank1_limit > 0 else limit
            _process_rank1(limit=effective_rank1_limit)
        logger.info("✓ Step 2 complete")

        # Step 3: promote rank-0 to clean DB
        logger.info("Step 3: Promoting Rank-0 articles to clean collection…")
        promoted = _promote_rank0_to_clean(limit=limit)
        logger.info("✓ Step 3 complete: %d articles promoted", promoted)

        # Step 4: quarantine rank-2 for auditing / future recovery
        logger.info("Step 4: Quarantining Rank-2 articles…")
        discarded = _quarantine_rank2()
        logger.info("✓ Step 4 complete: %d articles quarantined", discarded)

        # Summary
        rank_counts = count_raw_articles_by_rank()
        logger.info(
            "=== Cleaning pipeline FINISHED | Distribution after clean: %s ===",
            rank_counts,
        )

        return {
            "promoted": promoted,
            "discarded": discarded,
            "rank_distribution": rank_counts,
        }
    except Exception as e:
        logger.error("=== Cleaning pipeline FAILED: %s ===", e, exc_info=True)
        rank_counts = count_raw_articles_by_rank()
        logger.error(
            "Pipeline failed at unknown step. Current rank distribution: %s",
            rank_counts,
        )
        raise

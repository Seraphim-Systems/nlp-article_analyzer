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

from tqdm import tqdm

from database.repositories import (
    bulk_update_raw_ranks,
    count_raw_articles_by_rank,
    get_raw_articles_by_rank,
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
    col_iter = __import__("database.repositories", fromlist=["get_raw_collection"]).get_raw_collection()
    unranked = list(col_iter.find({"rank": None}))
    if not unranked:
        logger.info("No unranked articles found.")
        return

    logger.info("Ranking %d unranked articles…", len(unranked))
    updates = []
    for article in tqdm(unranked, desc="  Ranking", unit="art", ncols=80):
        rank, reasons = rank_article_with_reasons(article)
        updates.append((article["url"], rank, reasons))
    bulk_update_raw_ranks(updates)
    logger.info("Ranking complete.")


def _process_rank1() -> None:
    """
    Attempt to recover Rank-1 articles by re-fetching their URLs.
    Updates the DB fields and re-assigns rank.
    """
    rank1_articles = list(get_raw_articles_by_rank(1))
    if not rank1_articles:
        logger.info("No Rank-1 articles to process.")
        return

    logger.info("Attempting to recover %d Rank-1 articles…", len(rank1_articles))
    promoted = 0

    rank_updates = []
    for article in tqdm(rank1_articles, desc="  Recovering rank-1", unit="art", ncols=80):
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

    logger.info("Rank-1 processing done: %d articles promoted to Rank 0.", promoted)


def _promote_rank0_to_clean() -> int:
    """Copy all Rank-0 raw articles to the clean collection."""
    rank0_articles = list(get_raw_articles_by_rank(0))
    if not rank0_articles:
        logger.info("No Rank-0 articles to promote.")
        return 0

    enriched = [enrich_article_for_cleaning(a) for a in rank0_articles]
    upserted = upsert_clean_articles(enriched)
    logger.info("Promoted %d Rank-0 articles to clean collection.", upserted)
    return upserted


def _quarantine_rank2() -> int:
    """Store Rank-2 articles in quarantine for audit/recovery."""
    rank2_articles = list(get_raw_articles_by_rank(2))
    if not rank2_articles:
        logger.info("No Rank-2 articles to quarantine.")
        return 0

    quarantined = upsert_quarantine_articles(rank2_articles)
    logger.info("Quarantined %d Rank-2 articles.", quarantined)
    return quarantined


def run_cleaning_pipeline(skip_rank1_recovery: bool = False) -> dict[str, int]:
    """
    Execute the full cleaning pipeline.

    Parameters
    ----------
    skip_rank1_recovery : bool
        If True, skip the URL re-fetch step for Rank-1 articles.
        Useful for large historical datasets where most URLs are dead.

    Returns a summary dict:
    {
        "ranked":   <articles newly ranked>,
        "promoted": <rank-0 articles moved to clean>,
        "discarded":<rank-2 articles deleted>,
    }
    """
    logger.info("=== Cleaning pipeline started ===")

    # Step 1: rank new articles
    _rank_unranked_articles()

    # Step 2: try to recover rank-1 (skippable)
    if skip_rank1_recovery:
        logger.info("Skipping Rank-1 URL recovery (skip_rank1_recovery=True)")
    else:
        _process_rank1()

    # Step 3: promote rank-0 to clean DB
    promoted = _promote_rank0_to_clean()

    # Step 4: quarantine rank-2 for auditing / future recovery
    discarded = _quarantine_rank2()

    # Summary
    rank_counts = count_raw_articles_by_rank()
    logger.info(
        "=== Cleaning pipeline finished | Distribution after clean: %s ===",
        rank_counts,
    )

    return {"promoted": promoted, "discarded": discarded, "rank_distribution": rank_counts}

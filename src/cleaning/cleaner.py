"""
Data cleaning pipeline.

Orchestrates the full cleaning flow on raw articles:

  Step 1 — Rank all unranked raw articles (assign rank 0 / 1 / 2).
  Step 2 — For Rank-1 articles: attempt to fill missing fields via URL re-fetch,
            then re-rank; articles that reach Rank 0 are promoted.
  Step 3 — Rank-2 articles are deleted from the raw collection.
  Step 4 — Rank-0 articles are upserted into the clean collection.

The raw collection always retains the original scraped data (minus rank-2
documents) as a safety net.  The clean collection holds only quality-verified
articles ready for downstream NLP processing.
"""

from __future__ import annotations

import logging
from typing import Any

from database.repositories import (
    count_raw_articles_by_rank,
    delete_raw_by_rank,
    get_raw_articles_by_rank,
    update_raw_article_fields,
    update_raw_rank,
    upsert_clean_articles,
)
from cleaning.ranker import rank_article, rank_articles, summarise_ranks
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
    for article in unranked:
        rank = rank_article(article)
        update_raw_rank(article["url"], rank)

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

    for article in rank1_articles:
        patched = fill_missing_fields(article)
        new_rank = rank_article(patched)

        # Persist any newly filled fields back to raw
        changed_fields = {
            k: patched[k]
            for k in patched
            if k not in ("_id", "rank") and patched[k] != article.get(k)
        }
        if changed_fields:
            update_raw_article_fields(article["url"], changed_fields)

        update_raw_rank(article["url"], new_rank)

        if new_rank == 0:
            promoted += 1
        elif new_rank == 2:
            logger.warning("Article demoted to Rank 2 after re-fetch: %s", article["url"])

    logger.info("Rank-1 processing done: %d articles promoted to Rank 0.", promoted)


def _promote_rank0_to_clean() -> int:
    """Copy all Rank-0 raw articles to the clean collection."""
    rank0_articles = list(get_raw_articles_by_rank(0))
    if not rank0_articles:
        logger.info("No Rank-0 articles to promote.")
        return 0

    upserted = upsert_clean_articles(rank0_articles)
    logger.info("Promoted %d Rank-0 articles to clean collection.", upserted)
    return upserted


def _discard_rank2() -> int:
    """Delete Rank-2 articles from the raw collection."""
    deleted = delete_raw_by_rank(2)
    logger.info("Discarded %d Rank-2 articles.", deleted)
    return deleted


def run_cleaning_pipeline() -> dict[str, int]:
    """
    Execute the full cleaning pipeline.

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

    # Step 2: try to recover rank-1
    _process_rank1()

    # Step 3: promote rank-0 to clean DB
    promoted = _promote_rank0_to_clean()

    # Step 4: delete rank-2 from raw
    discarded = _discard_rank2()

    # Summary
    rank_counts = count_raw_articles_by_rank()
    logger.info(
        "=== Cleaning pipeline finished | Distribution after clean: %s ===",
        rank_counts,
    )

    return {"promoted": promoted, "discarded": discarded, "rank_distribution": rank_counts}

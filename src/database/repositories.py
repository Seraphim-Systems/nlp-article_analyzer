"""
Repository layer — all MongoDB read/write operations for articles.

Uses two separate collections:
  - raw_articles  (in RAW_DB)  : articles as scraped, never mutated after insert
  - clean_articles (in CLEAN_DB): articles that survived the cleaning pipeline
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterator

from pymongo import UpdateOne
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError, DuplicateKeyError

from config.settings import settings
from database.connection import get_clean_db, get_raw_db, get_ner_db
from database.models import (
    ARTICLE_VALIDATOR,
    CLEAN_INDEXES,
    RAW_INDEXES,
    NER_ARTICLE_VALIDATOR,
    NER_INDEXES,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Collection accessors (lazy — only touch DB when first called)
# ---------------------------------------------------------------------------

def _ensure_collection(db, name: str, validator, indexes) -> Collection:
    """Create collection with schema validation + indexes if it doesn't exist."""
    existing = db.list_collection_names()
    if name not in existing:
        logger.info("Creating collection '%s'", name)
        db.create_collection(
            name,
            validator=validator,
            validationLevel="moderate",   # warn but don't hard-reject on update
            validationAction="warn",
        )
    col = db[name]
    # Ensure indexes exist (idempotent)
    for idx in indexes:
        col.create_index(idx["keys"], **idx["options"])
    return col


def get_raw_collection() -> Collection:
    return _ensure_collection(
        get_raw_db(),
        settings.RAW_COLLECTION,
        ARTICLE_VALIDATOR,
        RAW_INDEXES,
    )


def get_clean_collection() -> Collection:
    return _ensure_collection(
        get_clean_db(),
        settings.CLEAN_COLLECTION,
        ARTICLE_VALIDATOR,
        CLEAN_INDEXES,
    )


def get_ner_collection() -> Collection:
    return _ensure_collection(
        get_ner_db(),
        settings.NER_COLLECTION,
        NER_ARTICLE_VALIDATOR,
        NER_INDEXES,
    )


# ---------------------------------------------------------------------------
# Raw-collection operations
# ---------------------------------------------------------------------------

def insert_raw_articles(articles: list[dict[str, Any]]) -> int:
    """
    Bulk-insert scraped articles into the raw collection.
    Duplicate URLs (already in DB) are silently skipped.
    Returns number of newly inserted documents.
    """
    if not articles:
        return 0

    col = get_raw_collection()
    now_iso = datetime.now(timezone.utc).isoformat()
    for a in articles:
        a.setdefault("ret", now_iso)

    ops = [
        UpdateOne({"url": a["url"]}, {"$setOnInsert": a}, upsert=True)
        for a in articles
    ]
    try:
        result = col.bulk_write(ops, ordered=False)
        inserted = result.upserted_count
    except BulkWriteError as exc:
        inserted = exc.details.get("nUpserted", 0)
        logger.warning("Bulk write partial error: %s", exc.details)

    logger.info("Inserted %d new raw articles (skipped duplicates).", inserted)
    return inserted


def get_raw_articles_by_rank(rank: int) -> Iterator[dict[str, Any]]:
    """Iterate over raw articles matching a cleaning rank."""
    return get_raw_collection().find({"rank": rank})


def update_raw_rank(url: str, rank: int) -> None:
    get_raw_collection().update_one({"url": url}, {"$set": {"rank": rank}})


def update_raw_article_fields(url: str, fields: dict[str, Any]) -> None:
    """Patch missing fields on a rank-1 article after URL re-fetch."""
    get_raw_collection().update_one({"url": url}, {"$set": fields})


def delete_raw_by_rank(rank: int) -> int:
    """Remove all raw articles with the given rank. Returns deleted count."""
    result = get_raw_collection().delete_many({"rank": rank})
    logger.info("Deleted %d raw articles with rank=%d.", result.deleted_count, rank)
    return result.deleted_count


# ---------------------------------------------------------------------------
# Clean-collection operations
# ---------------------------------------------------------------------------

def upsert_clean_articles(articles: list[dict[str, Any]]) -> int:
    """
    Insert or update articles in the clean collection.
    Strips the `rank` field before storing (not needed post-cleaning).
    Returns number of upserted documents.
    """
    if not articles:
        return 0

    col = get_clean_collection()
    ops = []
    for a in articles:
        doc = {k: v for k, v in a.items() if k != "rank"}
        ops.append(UpdateOne({"url": doc["url"]}, {"$set": doc}, upsert=True))

    try:
        result = col.bulk_write(ops, ordered=False)
        upserted = result.upserted_count + result.modified_count
    except BulkWriteError as exc:
        upserted = exc.details.get("nUpserted", 0)
        logger.warning("Clean bulk write partial error: %s", exc.details)

    logger.info("Upserted %d clean articles.", upserted)
    return upserted


def get_unprocessed_clean_articles() -> list[dict]:
    """Return clean articles not yet processed by the NER job."""
    processed_urls = set(get_ner_collection().distinct("url"))
    return list(get_clean_collection().find({"url": {"$nin": list(processed_urls)}}))


def insert_ner_articles(articles: list[dict]) -> int:
    """Upsert NER-enriched articles. Returns upserted + modified count."""
    if not articles:
        return 0
    col = get_ner_collection()
    ops = [UpdateOne({"url": a["url"]}, {"$set": a}, upsert=True) for a in articles]
    try:
        result = col.bulk_write(ops, ordered=False)
        upserted = result.upserted_count + result.modified_count
    except BulkWriteError as exc:
        upserted = exc.details.get("nUpserted", 0)
        logger.warning("NER bulk write partial error: %s", exc.details)
    logger.info("Upserted %d NER articles.", upserted)
    return upserted


def count_clean_articles() -> int:
    return get_clean_collection().count_documents({})


def count_raw_articles_by_rank() -> dict[int, int]:
    pipeline = [{"$group": {"_id": "$rank", "count": {"$sum": 1}}}]
    return {
        doc["_id"]: doc["count"]
        for doc in get_raw_collection().aggregate(pipeline)
    }

"""
Repository layer - all MongoDB read/write operations for articles, entities, and sentences.

Uses multiple collections:
  - raw_articles      (in RAW_DB)  : articles as scraped, never mutated after insert
  - clean_articles    (in CLEAN_DB): articles that survived the cleaning pipeline
  - entities          (in RAW_DB)  : named entities extracted from articles
  - sentences         (in RAW_DB)  : sentences extracted from articles
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterator

from pymongo import UpdateOne
from pymongo.collection import Collection
from pymongo.errors import BulkWriteError, DuplicateKeyError

from config.settings import settings
from database.connection import get_clean_db, get_models_db, get_ner_db, get_raw_db
from database.models import (
    ARTICLE_VALIDATOR,
    CLEAN_INDEXES,
    ENTITY_INDEXES,
    ENTITY_VALIDATOR,
    NER_ARTICLE_VALIDATOR,
    NER_INDEXES,
    RAW_INDEXES,
    SENTENCE_INDEXES,
    SENTENCE_VALIDATOR,
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
            validationLevel="moderate",  # warn but don't hard-reject on update
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


def get_quarantine_collection() -> Collection:
    return get_raw_db()["quarantine"]


def get_entities_collection() -> Collection:
    """Get or create the entities collection in RAW_DB."""
    return _ensure_collection(
        get_raw_db(),
        "entities",
        ENTITY_VALIDATOR,
        ENTITY_INDEXES,
    )


def get_sentences_collection() -> Collection:
    """Get or create the sentences collection in RAW_DB."""
    return _ensure_collection(
        get_raw_db(),
        "sentences",
        SENTENCE_VALIDATOR,
        SENTENCE_INDEXES,
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

    ops = [UpdateOne({"url": a["url"]}, {"$setOnInsert": a}, upsert=True) for a in articles]
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


def update_raw_rank(url: str, rank: int, reasons: list[str] | None = None) -> None:
    payload: dict[str, Any] = {"rank": rank}
    if reasons is not None:
        payload["rank_reasons"] = reasons
    get_raw_collection().update_one({"url": url}, {"$set": payload})


def bulk_update_raw_ranks(updates: list[tuple[str, int, list[str] | None]]) -> None:
    """Batch-update ranks for multiple articles in a single bulk_write call.

    Parameters
    ----------
    updates : list of (url, rank, reasons)
    """
    if not updates:
        return
    ops = []
    for url, rank, reasons in updates:
        payload: dict[str, Any] = {"rank": rank}
        if reasons is not None:
            payload["rank_reasons"] = reasons
        ops.append(UpdateOne({"url": url}, {"$set": payload}))
    try:
        get_raw_collection().bulk_write(ops, ordered=False)
    except BulkWriteError as exc:
        logger.warning("Bulk rank update partial error: %s", exc.details)


def update_raw_article_fields(url: str, fields: dict[str, Any]) -> None:
    """Patch missing fields on a rank-1 article after URL re-fetch."""
    get_raw_collection().update_one({"url": url}, {"$set": fields})


def delete_raw_by_rank(rank: int) -> int:
    """Remove all raw articles with the given rank. Returns deleted count."""
    result = get_raw_collection().delete_many({"rank": rank})
    logger.info("Deleted %d raw articles with rank=%d.", result.deleted_count, rank)
    return result.deleted_count


def upsert_quarantine_articles(articles: list[dict[str, Any]]) -> int:
    """Store low-quality documents for audit/recovery instead of hard deleting."""
    if not articles:
        return 0

    col = get_quarantine_collection()
    now_iso = datetime.now(timezone.utc).isoformat()
    ops = []
    for a in articles:
        doc = dict(a)
        doc["quarantined_at"] = now_iso
        ops.append(UpdateOne({"url": doc["url"]}, {"$set": doc}, upsert=True))

    try:
        result = col.bulk_write(ops, ordered=False)
        upserted = result.upserted_count + result.modified_count
    except BulkWriteError as exc:
        upserted = exc.details.get("nUpserted", 0)
        logger.warning("Quarantine bulk write partial error: %s", exc.details)

    logger.info("Quarantined %d raw articles.", upserted)
    return upserted


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
        upserted = exc.details.get("nUpserted", 0) + exc.details.get("nModified", 0)
        errors = exc.details.get("writeErrors", [])
        logger.warning(
            "Clean bulk write partial error: %d write error(s), codes=%s",
            len(errors),
            [e.get("code") for e in errors[:5]],
        )

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
    return {doc["_id"]: doc["count"] for doc in get_raw_collection().aggregate(pipeline)}


def get_unprocessed_topic_articles(limit: int = 1000) -> list[dict]:
    """Fetch clean articles that don't have a topic_label yet."""
    return list(get_clean_collection().find({"topic_label": {"$exists": False}}, limit=limit))


def update_article_topics(updates: list[dict]) -> int:
    """Bulk update articles with topics and keywords."""
    if not updates:
        return 0
    col = get_clean_collection()
    ops = [
        UpdateOne(
            {"url": u["url"]},
            {
                "$set": {
                    "topic_label": u["topic_label"],
                    "topic_score": u["topic_score"],
                    "keywords": u["keywords"],
                }
            },
        )
        for u in updates
    ]
    result = col.bulk_write(ops, ordered=False)
    return result.modified_count


# ---------------------------------------------------------------------------
# Model run operations
# ---------------------------------------------------------------------------


def insert_model_run(doc: dict[str, Any]) -> str:
    """Insert one evaluation run document into nlp_models.model_runs.

    Returns the inserted document's ``_id`` as a string.
    """
    col = get_models_db()["model_runs"]
    result = col.insert_one(doc)
    logger.info("Inserted model run with _id=%s", result.inserted_id)
    return str(result.inserted_id)


def get_latest_model_run() -> dict[str, Any] | None:
    """Return the most recent model run document, or None if no runs exist."""
    col = get_models_db()["model_runs"]
    return col.find_one({}, sort=[("created_at", -1)])


# ---------------------------------------------------------------------------
# Entity operations
# ---------------------------------------------------------------------------


def insert_entities(entities: list[dict[str, Any]]) -> int:
    """
    Bulk-insert named entities into the entities collection.
    Skips duplicate (docID, senDocID, NE) combinations.
    Returns number of newly inserted documents.
    """
    if not entities:
        return 0

    col = get_entities_collection()
    ops = [
        UpdateOne(
            {
                "docID": e["docID"],
                "senDocID": e["senDocID"],
                "NE": e["NE"],
            },
            {"$setOnInsert": e},
            upsert=True,
        )
        for e in entities
    ]
    try:
        result = col.bulk_write(ops, ordered=False)
        inserted = result.upserted_count
    except BulkWriteError as exc:
        inserted = exc.details.get("nUpserted", 0)
        # Only log warnings for real errors, not just skipped duplicates
        # logger.warning("Entity bulk write partial error: %s", exc.details)

    # logger.info("Inserted %d new entities (skipped duplicates).", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Sentence operations
# ---------------------------------------------------------------------------


def insert_sentences(sentences: list[dict[str, Any]]) -> int:
    """
    Bulk-insert sentences into the sentences collection.
    Uses (docID, senDocID) as unique constraint per the schema.
    Returns number of newly inserted documents.
    """
    if not sentences:
        return 0

    col = get_sentences_collection()
    ops = [
        UpdateOne(
            {"docID": s["docID"], "senDocID": s["senDocID"]},
            {"$setOnInsert": s},
            upsert=True,
        )
        for s in sentences
    ]
    try:
        result = col.bulk_write(ops, ordered=False)
        inserted = result.upserted_count
    except BulkWriteError as exc:
        inserted = exc.details.get("nUpserted", 0)
        # Only log warnings for real errors, not just skipped duplicates
        # logger.warning("Sentence bulk write partial error: %s", exc.details)

    # logger.info("Inserted %d new sentences (skipped duplicates).", inserted)
    return inserted

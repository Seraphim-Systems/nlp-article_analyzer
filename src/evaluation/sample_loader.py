"""
MongoDB adapter for the evaluation pipeline.

Keeps all database access out of the pure metrics module so that
``ner_metrics.py`` remains fully unit-testable without a live database.
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings
from database.connection import get_models_db, get_ner_db

logger = logging.getLogger(__name__)


def load_ner_sample(n: int = 500) -> list[dict[str, Any]]:
    """
    Return a random sample of up to ``n`` NER articles from ``nlp_ner.ner_articles``.

    Each document is projected to ``{url, body, entities}`` only — the
    evaluate job does not need the full article payload.

    Returns fewer documents than ``n`` when the collection has less than ``n``
    documents; returns an empty list when the collection is empty.
    """
    col = get_ner_db()[settings.NER_COLLECTION]
    pipeline = [
        {"$sample": {"size": n}},
        {"$project": {"_id": 0, "url": 1, "body": 1, "entities": 1}},
    ]
    docs = list(col.aggregate(pipeline))
    logger.info("Loaded %d NER articles for evaluation (requested %d)", len(docs), n)
    return docs


def load_latest_run_metrics() -> dict[str, Any] | None:
    """
    Return the metrics dict from the most recent model run, or ``None`` if no
    runs have been stored yet.
    """
    col = get_models_db()["model_runs"]
    doc = col.find_one({}, sort=[("created_at", -1)])
    if doc is None:
        return None
    return doc

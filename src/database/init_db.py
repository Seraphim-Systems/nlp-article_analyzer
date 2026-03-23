"""
Database initialization and schema setup.

Call this at application startup to ensure all databases and collections
exist with proper schemas, validators, and indexes.
"""

from __future__ import annotations

import logging
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database

from config.settings import settings
from database.connection import get_client, get_raw_db, get_clean_db, get_ner_db
from database.models import ARTICLE_VALIDATOR, RAW_INDEXES, CLEAN_INDEXES, NER_ARTICLE_VALIDATOR, NER_INDEXES

logger = logging.getLogger(__name__)


def _ensure_collection(
    db: Database, name: str, validator: dict[str, Any], indexes: list[dict]
) -> None:
    """
    Create collection with schema validation + indexes if it doesn't exist.
    Idempotent: safe to call multiple times.
    """
    existing = db.list_collection_names()
    if name not in existing:
        logger.info("Creating collection '%s' in database '%s'", name, db.name)
        db.create_collection(
            name,
            validator=validator,
            validationLevel="moderate",  # warn but don't hard-reject on update
            validationAction="warn",
        )
    else:
        logger.debug("Collection '%s' already exists", name)

    col = db[name]
    # Ensure indexes exist (idempotent)
    for idx in indexes:
        try:
            col.create_index(idx["keys"], **idx["options"])
            logger.debug(
                "Index '%s' ensured on collection '%s'",
                idx["options"].get("name", "unnamed"),
                name,
            )
        except Exception as e:
            logger.warning("Failed to create index: %s", e)


def init_databases() -> None:
    """
    Initialize all application databases.

    Creates:
    - raw_articles collection (in RAW_DB)
    - clean_articles collection (in CLEAN_DB)
    - classified_articles collection (in CLASSIFIED_DB)
    - model_runs collection (in MODELS_DB)

    This function is idempotent and safe to call on every application startup.
    """
    logger.info("Initializing application databases…")

    # Raw articles database
    raw_db = get_raw_db()
    _ensure_collection(
        raw_db,
        settings.RAW_COLLECTION,
        ARTICLE_VALIDATOR,
        RAW_INDEXES,
    )

    # Clean articles database
    clean_db = get_clean_db()
    _ensure_collection(
        clean_db,
        settings.CLEAN_COLLECTION,
        ARTICLE_VALIDATOR,
        CLEAN_INDEXES,
    )

    # Classified articles database
    classified_db = get_client()[settings.CLASSIFIED_DB_NAME]
    _ensure_collection(
        classified_db,
        settings.CLASSIFIED_COLLECTION,
        ARTICLE_VALIDATOR,
        CLEAN_INDEXES,  # reuse clean indexes for classified
    )

    # Model runs / metrics database
    models_db = get_client()[settings.MODELS_DB_NAME]
    model_run_schema: dict[str, Any] = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["model_version", "metrics", "created_at"],
            "properties": {
                "model_version": {"bsonType": "string"},
                "metrics": {"bsonType": "object"},
                "created_at": {"bsonType": "string"},
                "hyperparams": {"bsonType": ["object", "null"]},
                "training_set_size": {"bsonType": ["int", "null"]},
            },
        }
    }
    _ensure_collection(
        models_db,
        "model_runs",
        model_run_schema,
        [
            {
                "keys": [("model_version", -1)],
                "options": {"name": "version_idx"},
            },
            {
                "keys": [("created_at", -1)],
                "options": {"name": "created_at_idx"},
            },
        ],
    )

    # NER articles database
    ner_db = get_ner_db()
    _ensure_collection(
        ner_db,
        settings.NER_COLLECTION,
        NER_ARTICLE_VALIDATOR,
        NER_INDEXES,
    )

    logger.info("Database initialization complete.")

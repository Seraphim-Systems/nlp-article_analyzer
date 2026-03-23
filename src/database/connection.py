"""
MongoDB connection manager.

Five MongoDB databases are maintained:
  - RAW_DB        : articles as scraped, never modified
  - CLEAN_DB      : articles that passed the cleaning pipeline
  - CLASSIFIED_DB : articles with classification labels (future)
  - MODELS_DB     : model run metadata and metrics
  - NER_DB        : articles enriched with named entities

All databases share the same MongoDB instance but are logically isolated.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

from config.settings import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    """Return a singleton MongoClient with connection pooling."""
    logger.info("Connecting to MongoDB at %s", settings.MONGO_URI)
    client: MongoClient = MongoClient(
        settings.MONGO_URI,
        maxPoolSize=10,
        minPoolSize=1,
        connectTimeoutMS=5_000,
        serverSelectionTimeoutMS=5_000,
        socketTimeoutMS=30_000,
        retryWrites=True,
    )
    client.admin.command("ping")
    logger.info("MongoDB connection established.")
    return client


def get_raw_db() -> Database:
    """Return the raw (uncleaned) articles database."""
    return get_client()[settings.RAW_DB_NAME]


def get_clean_db() -> Database:
    """Return the cleaned articles database."""
    return get_client()[settings.CLEAN_DB_NAME]


def get_ner_db() -> Database:
    """Return the NER-enriched articles database."""
    return get_client()[settings.NER_DB_NAME]


def close_connection() -> None:
    """Close the MongoDB client (call on application shutdown)."""
    client = get_client()
    client.close()
    get_client.cache_clear()
    logger.info("MongoDB connection closed.")

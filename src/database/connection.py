"""
MongoDB connection manager.

Two separate MongoDB databases are maintained:
  - RAW_DB   : stores articles exactly as scraped, never modified
  - CLEAN_DB : stores articles that have passed the cleaning pipeline (rank 0 or 1)

Both databases share the same MongoDB instance (or cluster) but are logically
isolated so that the raw data is always preserved as a safety net.
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
    """Return a singleton MongoClient instance."""
    logger.info("Connecting to MongoDB at %s", settings.MONGO_URI)
    client: MongoClient = MongoClient(
        settings.MONGO_URI,
        serverSelectionTimeoutMS=5_000,
    )
    # Ping to surface connection errors early
    client.admin.command("ping")
    logger.info("MongoDB connection established.")
    return client


def get_raw_db() -> Database:
    """Return the raw (uncleaned) articles database."""
    return get_client()[settings.RAW_DB_NAME]


def get_clean_db() -> Database:
    """Return the cleaned articles database."""
    return get_client()[settings.CLEAN_DB_NAME]


def close_connection() -> None:
    """Close the MongoDB client (call on application shutdown)."""
    client = get_client()
    client.close()
    get_client.cache_clear()
    logger.info("MongoDB connection closed.")

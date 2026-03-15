"""
Central configuration.

All tuneable values are read from environment variables (with sensible defaults)
so that the same codebase runs locally, in Docker, or in CI without code changes.

Copy .env.example → .env and fill in your own values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


@dataclass
class Settings:
    # ------------------------------------------------------------------
    # MongoDB
    # ------------------------------------------------------------------

    #: Full MongoDB connection URI.
    #: For local dev: mongodb://localhost:27017
    #: For Atlas:     mongodb+srv://<user>:<pass>@<cluster>.mongodb.net/
    MONGO_URI: str = field(
        default_factory=lambda: _env("MONGO_URI", "mongodb://localhost:27017")
    )

    #: Name of the raw (uncleaned) database
    RAW_DB_NAME: str = field(
        default_factory=lambda: _env("RAW_DB_NAME", "nlp_raw")
    )

    #: Name of the clean database
    CLEAN_DB_NAME: str = field(
        default_factory=lambda: _env("CLEAN_DB_NAME", "nlp_clean")
    )

    #: Collection name within each database
    RAW_COLLECTION: str = field(
        default_factory=lambda: _env("RAW_COLLECTION", "articles")
    )
    CLEAN_COLLECTION: str = field(
        default_factory=lambda: _env("CLEAN_COLLECTION", "articles")
    )

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    #: UTC hour at which the daily scrape job runs (0–23)
    SCRAPE_HOUR: int = field(
        default_factory=lambda: _env_int("SCRAPE_HOUR", 0)   # midnight
    )

    # ------------------------------------------------------------------
    # RSS Feeds
    # ------------------------------------------------------------------
    #
    # Each entry is a dict:
    #   name (str)  — display name / value for the `feed` field
    #   url  (str)  — RSS / Atom feed URL
    #   lang (str)  — BCP-47 language code (default "en")
    #
    # Add, remove, or swap feeds here without touching scraper code.
    # ------------------------------------------------------------------

    RSS_FEEDS: list[dict[str, Any]] = field(default_factory=lambda: [
        {
            "name": "BBC News - World",
            "url":  "http://feeds.bbci.co.uk/news/world/rss.xml",
            "lang": "en",
        },
        {
            "name": "BBC News - Politics",
            "url":  "http://feeds.bbci.co.uk/news/politics/rss.xml",
            "lang": "en",
        },
        {
            "name": "Reuters - World",
            "url":  "https://feeds.reuters.com/reuters/worldNews",
            "lang": "en",
        },
        {
            "name": "The Hindu",
            "url":  "https://www.thehindu.com/feeder/default.rss",
            "lang": "en",
        },
        {
            "name": "NDTV",
            "url":  "https://feeds.feedburner.com/ndtvnews-top-stories",
            "lang": "en",
        },
        {
            "name": "Al Jazeera English",
            "url":  "https://www.aljazeera.com/xml/rss/all.xml",
            "lang": "en",
        },
        {
            "name": "Times of India",
            "url":  "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
            "lang": "en",
        },
    ])


# Singleton instance used throughout the project
settings = Settings()

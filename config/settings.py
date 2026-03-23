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


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    #: Runtime environment (development, staging, production)
    ENVIRONMENT: str = field(
        default_factory=lambda: _env("ENVIRONMENT", "development")
    )

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
    RAW_DB_NAME: str = field(default_factory=lambda: _env("RAW_DB_NAME", "nlp_raw"))

    #: Name of the clean database
    CLEAN_DB_NAME: str = field(
        default_factory=lambda: _env("CLEAN_DB_NAME", "nlp_clean")
    )

    #: Name of the classified articles database
    CLASSIFIED_DB_NAME: str = field(
        default_factory=lambda: _env("CLASSIFIED_DB_NAME", "nlp_classified")
    )

    #: Name of the models and metrics database
    MODELS_DB_NAME: str = field(
        default_factory=lambda: _env("MODELS_DB_NAME", "nlp_models")
    )

    #: Collection name within each database
    RAW_COLLECTION: str = field(
        default_factory=lambda: _env("RAW_COLLECTION", "articles")
    )
    CLEAN_COLLECTION: str = field(
        default_factory=lambda: _env("CLEAN_COLLECTION", "articles")
    )
    CLASSIFIED_COLLECTION: str = field(
        default_factory=lambda: _env("CLASSIFIED_COLLECTION", "articles")
    )

    #: Name of the NER articles database
    NER_DB_NAME: str = field(
        default_factory=lambda: _env("NER_DB_NAME", "nlp_ner")
    )

    #: Collection name for NER-enriched articles
    NER_COLLECTION: str = field(
        default_factory=lambda: _env("NER_COLLECTION", "ner_articles")
    )

    # ------------------------------------------------------------------
    # Scheduler
    # ------------------------------------------------------------------

    #: UTC hour at which the daily scrape job runs (0–23)
    SCRAPE_HOUR: int = field(
        default_factory=lambda: _env_int("SCRAPE_HOUR", 0)  # midnight
    )

    #: If true, run cleaning automatically right after each scrape cycle.
    RUN_CLEAN_AFTER_SCRAPE: bool = field(
        default_factory=lambda: _env_bool("RUN_CLEAN_AFTER_SCRAPE", True)
    )

    #: If true, skip articles whose detected language is not English.
    ENGLISH_ONLY: bool = field(
        default_factory=lambda: _env_bool("ENGLISH_ONLY", True)
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

    RSS_FEEDS: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {
                "name": "BBC News - World",
                "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
                "lang": "en",
            },
            {
                "name": "BBC News - Politics",
                "url": "http://feeds.bbci.co.uk/news/politics/rss.xml",
                "lang": "en",
            },
            {
                "name": "Reuters - World",
                "url": "https://feeds.reuters.com/reuters/worldNews",
                "lang": "en",
            },
            {
                "name": "The Hindu",
                "url": "https://www.thehindu.com/feeder/default.rss",
                "lang": "en",
            },
            {
                "name": "NDTV",
                "url": "https://feeds.feedburner.com/ndtvnews-top-stories",
                "lang": "en",
            },
            {
                "name": "Al Jazeera English",
                "url": "https://www.aljazeera.com/xml/rss/all.xml",
                "lang": "en",
            },
            {
                "name": "Times of India",
                "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
                "lang": "en",
            },
        ]
    )

    # ------------------------------------------------------------------
    # Kaggle Dataset (for initial bootstrap)
    # ------------------------------------------------------------------

    #: Enable Kaggle dataset download on container init
    KAGGLE_ENABLED: bool = field(
        default_factory=lambda: _env("KAGGLE_ENABLED", "false").lower() == "true"
    )

    #: Kaggle dataset identifier (e.g., "julianschelb/newsdata")
    KAGGLE_DATASET: str = field(
        default_factory=lambda: _env("KAGGLE_DATASET", "julianschelb/newsdata")
    )

    #: Kaggle API username (optional, legacy format only; modern tokens don't need username)
    KAGGLE_USERNAME: str = field(default_factory=lambda: _env("KAGGLE_USERNAME", ""))

    #: Kaggle API key/token (set via .env). Modern tokens include the full token here.
    KAGGLE_KEY: str = field(default_factory=lambda: _env("KAGGLE_KEY", ""))

    #: Local path to store Kaggle dataset downloads
    KAGGLE_DOWNLOAD_PATH: str = field(
        default_factory=lambda: _env("KAGGLE_DOWNLOAD_PATH", "/tmp/kaggle_datasets")
    )

    #: Skip bootstrap on container init (useful for production after initial run)
    SKIP_BOOTSTRAP: bool = field(
        default_factory=lambda: _env("SKIP_BOOTSTRAP", "false").lower() == "true"
    )

    #: Skip Rank-1 URL re-fetch during cleaning (useful for historical datasets with dead links)
    SKIP_RANK1_RECOVERY: bool = field(
        default_factory=lambda: _env("SKIP_RANK1_RECOVERY", "false").lower() == "true"
    )


# Singleton instance used throughout the project
settings = Settings()

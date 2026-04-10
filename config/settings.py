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
        default_factory=lambda: _env_bool("RUN_CLEAN_AFTER_SCRAPE", False)
    )

    #: If true, skip articles whose detected language is not English.
    ENGLISH_ONLY: bool = field(
        default_factory=lambda: _env_bool("ENGLISH_ONLY", True)
    )

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    #: Number of NER documents sampled for separability evaluation.
    EVAL_SEPARABILITY_SAMPLE: int = field(
        default_factory=lambda: _env_int("EVAL_SEPARABILITY_SAMPLE", 200)
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
            # ── BBC ───────────────────────────────────────────────────────────
            {"name": "BBC - World",       "url": "http://feeds.bbci.co.uk/news/world/rss.xml",                      "lang": "en"},
            {"name": "BBC - UK",          "url": "http://feeds.bbci.co.uk/news/uk/rss.xml",                         "lang": "en"},
            {"name": "BBC - Politics",    "url": "http://feeds.bbci.co.uk/news/politics/rss.xml",                   "lang": "en"},
            {"name": "BBC - Business",    "url": "http://feeds.bbci.co.uk/news/business/rss.xml",                   "lang": "en"},
            {"name": "BBC - Technology",  "url": "http://feeds.bbci.co.uk/news/technology/rss.xml",                 "lang": "en"},
            {"name": "BBC - Science",     "url": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml",    "lang": "en"},
            {"name": "BBC - Health",      "url": "http://feeds.bbci.co.uk/news/health/rss.xml",                     "lang": "en"},
            # ── The Guardian ─────────────────────────────────────────────────
            {"name": "Guardian - World",       "url": "https://www.theguardian.com/world/rss",       "lang": "en"},
            {"name": "Guardian - UK",          "url": "https://www.theguardian.com/uk/rss",          "lang": "en"},
            {"name": "Guardian - Politics",    "url": "https://www.theguardian.com/politics/rss",    "lang": "en"},
            {"name": "Guardian - Business",    "url": "https://www.theguardian.com/business/rss",    "lang": "en"},
            {"name": "Guardian - Technology",  "url": "https://www.theguardian.com/technology/rss",  "lang": "en"},
            {"name": "Guardian - Science",     "url": "https://www.theguardian.com/science/rss",     "lang": "en"},
            {"name": "Guardian - Environment", "url": "https://www.theguardian.com/environment/rss", "lang": "en"},
            # ── NPR ───────────────────────────────────────────────────────────
            {"name": "NPR - Top Stories", "url": "https://feeds.npr.org/1001/rss.xml", "lang": "en"},
            {"name": "NPR - World",       "url": "https://feeds.npr.org/1004/rss.xml", "lang": "en"},
            {"name": "NPR - Politics",    "url": "https://feeds.npr.org/1014/rss.xml", "lang": "en"},
            # ── Sky News ─────────────────────────────────────────────────────
            {"name": "Sky News - World",  "url": "https://feeds.skynews.com/feeds/rss/world.xml",      "lang": "en"},
            {"name": "Sky News - UK",     "url": "https://feeds.skynews.com/feeds/rss/uk.xml",         "lang": "en"},
            {"name": "Sky News - US",     "url": "https://feeds.skynews.com/feeds/rss/us.xml",         "lang": "en"},
            {"name": "Sky News - Tech",   "url": "https://feeds.skynews.com/feeds/rss/technology.xml", "lang": "en"},
            # ── International broadcasters ────────────────────────────────────
            {"name": "Al Jazeera",  "url": "https://www.aljazeera.com/xml/rss/all.xml",          "lang": "en"},
            {"name": "DW - World",  "url": "https://rss.dw.com/rdf/rss-en-world",                "lang": "en"},
            {"name": "DW - Top",    "url": "https://rss.dw.com/rdf/rss-en-top",                  "lang": "en"},
            {"name": "France 24",   "url": "https://www.france24.com/en/rss",                    "lang": "en"},
            {"name": "Euronews",    "url": "https://www.euronews.com/rss?level=theme&name=news", "lang": "en"},
            # ── South / Southeast Asia ────────────────────────────────────────
            {"name": "The Hindu",        "url": "https://www.thehindu.com/feeder/default.rss",               "lang": "en"},
            {"name": "Times of India",   "url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms", "lang": "en"},
            {"name": "Economic Times",   "url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms","lang": "en"},
            {"name": "CNA - World",      "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511", "lang": "en"},
            {"name": "CNA - Asia",       "url": "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6513", "lang": "en"},
            # ── Technology ───────────────────────────────────────────────────
            {"name": "Ars Technica",    "url": "https://feeds.arstechnica.com/arstechnica/index", "lang": "en"},
            {"name": "The Verge",       "url": "https://www.theverge.com/rss/index.xml",          "lang": "en"},
            {"name": "TechCrunch",      "url": "https://techcrunch.com/feed/",                    "lang": "en"},
            # ── Science ──────────────────────────────────────────────────────
            {"name": "Science Daily",   "url": "https://www.sciencedaily.com/rss/all.xml", "lang": "en"},
        ]
    )

    # ------------------------------------------------------------------
    # Kaggle Dataset (for initial bootstrap)
    # ------------------------------------------------------------------

    #: Enable Kaggle dataset download on container init
    KAGGLE_ENABLED: bool = field(
        default_factory=lambda: _env_bool("KAGGLE_ENABLED", False)
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
        default_factory=lambda: _env_bool("SKIP_BOOTSTRAP", False)
    )

    #: Skip Rank-1 URL re-fetch during cleaning (useful for historical datasets with dead links)
    SKIP_RANK1_RECOVERY: bool = field(
        default_factory=lambda: _env_bool("SKIP_RANK1_RECOVERY", False)
    )

    def validate(self) -> None:
        """
        Raise EnvironmentError if required settings are missing.
        Called at container startup — surfaces misconfiguration immediately.
        """
        errors = []
        if not self.MONGO_URI:
            errors.append("MONGO_URI is required")
        if self.KAGGLE_ENABLED and not self.KAGGLE_KEY:
            errors.append("KAGGLE_KEY is required when KAGGLE_ENABLED=true")
        if errors:
            raise EnvironmentError(
                "Missing required configuration:\n  " + "\n  ".join(errors)
            )


# Singleton instance used throughout the project
settings = Settings()

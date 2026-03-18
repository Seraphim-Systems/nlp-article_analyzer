"""
Abstract base class that all concrete scrapers must implement.

A scraper is responsible for:
  1. Fetching a list of article URLs published TODAY from a specific source.
  2. Fetching and parsing the full content of each URL into a raw article dict.

Concrete scrapers live in scraper/scrapers/ and are registered in
scraper/registry.py so the scheduler can discover them automatically.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Base class for all news scrapers."""

    #: Human-readable name used in logs and the `feed` field
    name: str = "unnamed"

    #: BCP-47 language of this source (may be overridden per-article)
    default_lang: str = "en"

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"scraper.{self.name}")

    # ------------------------------------------------------------------
    # Mandatory interface
    # ------------------------------------------------------------------

    @abstractmethod
    def get_today_urls(self, for_date: date) -> list[str]:
        """
        Return a list of article URLs published on `for_date`.
        Implementations should NOT raise — return [] on failure and log.
        """

    @abstractmethod
    def parse_article(self, url: str) -> dict[str, Any] | None:
        """
        Fetch `url` and return an article dict matching the schema in
        database/models.py, or None if the page cannot be parsed.

        Minimum required keys: url, title, feed, body.
        """

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def scrape_today(self, for_date: date | None = None) -> list[dict[str, Any]]:
        """
        High-level method: get today's URLs then parse each one.
        Returns a list of successfully parsed article dicts.
        """
        target = for_date or date.today()
        self.logger.info("[%s] Fetching URLs for %s", self.name, target)
        urls = self.get_today_urls(target)
        self.logger.info("[%s] Found %d URLs", self.name, len(urls))

        articles: list[dict[str, Any]] = []
        for url in urls:
            try:
                article = self.parse_article(url)
                if article:
                    article.setdefault("feed", self.name)
                    article.setdefault("lang", self.default_lang)
                    articles.append(article)
            except Exception:
                self.logger.exception("[%s] Failed to parse %s", self.name, url)

        self.logger.info("[%s] Successfully parsed %d / %d articles", self.name, len(articles), len(urls))
        return articles

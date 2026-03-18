"""
RSS / Atom feed scraper.

Reads configured RSS/Atom feeds, filters for articles published today,
and fetches full article content via newspaper3k.

To add a new source, append an entry to RSS_FEEDS in config/settings.py:

    RSS_FEEDS = [
        {"name": "BBC News", "url": "http://feeds.bbci.co.uk/news/rss.xml", "lang": "en"},
        ...
    ]
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import feedparser
from newspaper import Article as NewspaperArticle

from config.settings import settings

logger = logging.getLogger(__name__)

_FETCH_TIMEOUT = 15


class RssScraper:
    """Scrapes a single RSS/Atom feed and parses full article content."""

    def __init__(self, feed_config: dict[str, Any]) -> None:
        self.name: str = feed_config["name"]
        self.default_lang: str = feed_config.get("lang", "en")
        self._feed_url: str = feed_config["url"]
        self.logger = logging.getLogger(f"scraper.{self.name}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape_today(self, for_date: date | None = None) -> list[dict[str, Any]]:
        """Fetch today's URLs then parse each one into an article dict."""
        target = for_date or date.today()
        self.logger.info("[%s] Fetching URLs for %s", self.name, target)
        urls = self._get_today_urls(target)
        self.logger.info("[%s] Found %d URLs", self.name, len(urls))

        articles: list[dict[str, Any]] = []
        for url in urls:
            try:
                article = self._parse_article(url)
                if article:
                    articles.append(article)
            except Exception:
                self.logger.exception("[%s] Failed to parse %s", self.name, url)

        self.logger.info(
            "[%s] Successfully parsed %d / %d articles",
            self.name, len(articles), len(urls),
        )
        return articles

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_today_urls(self, for_date: date) -> list[str]:
        parsed = feedparser.parse(self._feed_url)
        if parsed.bozo:
            self.logger.warning(
                "Feed parse warning (%s): %s", self._feed_url, parsed.bozo_exception
            )

        urls: list[str] = []
        for entry in parsed.entries:
            link = entry.get("link")
            if not link:
                continue
            pub_date = self._entry_date(entry)
            # Include if published today OR if date is unknown (let cleaner handle)
            if pub_date is None or pub_date.date() == for_date:
                urls.append(link)

        return urls

    def _parse_article(self, url: str) -> dict[str, Any] | None:
        try:
            art = NewspaperArticle(url, language=self.default_lang, fetch_images=False)
            art.download()
            art.parse()
            art.nlp()
        except Exception:
            self.logger.exception("newspaper3k failed for %s", url)
            return None

        if not art.title or not art.text:
            self.logger.debug("Skipping %s — no title or body extracted.", url)
            return None

        pub_str = None
        if art.publish_date:
            try:
                pub_str = art.publish_date.astimezone(timezone.utc).isoformat()
            except Exception:
                pub_str = str(art.publish_date)

        return {
            "url":   url,
            "title": art.title,
            "feed":  self.name,
            "type":  "news",
            "pub":   pub_str,
            "lang":  art.meta_lang or self.default_lang,
            "refs":  list(art.movies),
            "sum":   art.summary or None,
            "body":  art.text,
        }

    @staticmethod
    def _entry_date(entry) -> datetime | None:
        for key in ("published_parsed", "updated_parsed"):
            val = getattr(entry, key, None)
            if val:
                try:
                    return datetime(*val[:6], tzinfo=timezone.utc)
                except Exception:
                    pass
        return None


def build_rss_scrapers() -> list[RssScraper]:
    """Return one RssScraper per entry in settings.RSS_FEEDS."""
    scrapers = []
    for feed_cfg in settings.RSS_FEEDS:
        try:
            scrapers.append(RssScraper(feed_cfg))
        except Exception:
            logger.exception("Failed to build scraper for feed: %s", feed_cfg)
    return scrapers

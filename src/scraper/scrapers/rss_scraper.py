"""
Generic RSS / Atom feed scraper.

Reads one or more RSS/Atom feeds, filters for articles published today,
then fetches and parses the full article via newspaper3k.

To add a new RSS-based news source, simply add an entry to RSS_FEEDS in
config/settings.py. No new Python code is needed.

  RSS_FEEDS = [
      {"name": "BBC News",    "url": "http://feeds.bbci.co.uk/news/rss.xml",  "lang": "en"},
      {"name": "The Hindu",   "url": "https://www.thehindu.com/feeder/default.rss", "lang": "en"},
      ...
  ]
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import feedparser
import newspaper
from newspaper import Article as NewspaperArticle

from config.settings import settings
from scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Timeout for fetching a single article page (seconds)
_FETCH_TIMEOUT = 15


class RssScraper(BaseScraper):
    """
    Scraper for a single RSS/Atom feed.

    Parameters
    ----------
    feed_config : dict with keys `name`, `url`, `lang`
    """

    def __init__(self, feed_config: dict[str, Any]) -> None:
        self.name = feed_config["name"]
        self.default_lang = feed_config.get("lang", "en")
        self._feed_url: str = feed_config["url"]
        super().__init__()

    # ------------------------------------------------------------------
    # BaseScraper interface
    # ------------------------------------------------------------------

    def get_today_urls(self, for_date: date) -> list[str]:
        self.logger.info("Fetching RSS feed: %s", self._feed_url)
        parsed = feedparser.parse(self._feed_url)
        if parsed.bozo:
            self.logger.warning("Feed parse warning (%s): %s", self._feed_url, parsed.bozo_exception)

        urls: list[str] = []
        for entry in parsed.entries:
            pub_date = self._entry_date(entry)
            if pub_date and pub_date.date() == for_date:
                link = entry.get("link")
                if link:
                    urls.append(link)
            elif pub_date is None:
                # No date information — include optimistically (cleaner will handle)
                link = entry.get("link")
                if link:
                    urls.append(link)

        return urls

    def parse_article(self, url: str) -> dict[str, Any] | None:
        try:
            art = NewspaperArticle(url, language=self.default_lang, fetch_images=False)
            art.download()
            art.parse()
            art.nlp()  # populates keywords and summary
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
            "refs":  list(art.movies),           # external links in article
            "sum":   art.summary or None,
            "body":  art.text,
            "text":  art.text,   # newspaper doesn't give full raw HTML text
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _entry_date(entry) -> datetime | None:
        """Parse the published/updated time from a feedparser entry."""
        for key in ("published_parsed", "updated_parsed"):
            val = getattr(entry, key, None)
            if val:
                try:
                    return datetime(*val[:6], tzinfo=timezone.utc)
                except Exception:
                    pass
        return None


# ---------------------------------------------------------------------------
# Factory: build one RssScraper per configured feed
# ---------------------------------------------------------------------------

def build_rss_scrapers() -> list[RssScraper]:
    """Return one RssScraper instance per entry in settings.RSS_FEEDS."""
    scrapers = []
    for feed_cfg in settings.RSS_FEEDS:
        try:
            scrapers.append(RssScraper(feed_cfg))
        except Exception:
            logger.exception("Failed to build scraper for feed: %s", feed_cfg)
    return scrapers

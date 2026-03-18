"""
URL-based re-fetcher for Rank-1 articles.

When an article is Rank 1 (non-crucial fields missing) and its URL is
available, this module attempts to re-parse the page and fill in the
missing fields so the article can be promoted to Rank 0.

Uses newspaper3k (same as the RSS scraper) for consistency.
"""

from __future__ import annotations

import logging
from datetime import timezone
from typing import Any

from newspaper import Article as NewspaperArticle

from cleaning.ranker import NON_CRUCIAL_FIELDS, _is_empty

logger = logging.getLogger(__name__)


def _fetch_article_data(url: str, lang: str = "en") -> dict[str, Any]:
    """
    Re-fetch a URL with newspaper3k and return a dict of available fields.
    Returns an empty dict if the fetch/parse fails.
    """
    try:
        art = NewspaperArticle(url, language=lang, fetch_images=False)
        art.download()
        art.parse()
        art.nlp()
    except Exception:
        logger.exception("Re-fetch failed for %s", url)
        return {}

    pub_str = None
    if art.publish_date:
        try:
            pub_str = art.publish_date.astimezone(timezone.utc).isoformat()
        except Exception:
            pub_str = str(art.publish_date)

    return {
        "title": art.title or None,
        "type":  "news",
        "pub":   pub_str,
        "lang":  art.meta_lang or None,
        "refs":  list(art.movies) or None,
        "sum":   art.summary or None,
        "body":  art.text or None,
    }


def fill_missing_fields(article: dict[str, Any]) -> dict[str, Any]:
    """
    Attempt to fill missing non-crucial fields by re-fetching the article URL.

    Returns a new dict with as many fields filled as possible.
    The `rank` key is NOT updated here — call ranker.rank_article() afterwards.
    """
    url = article.get("url")
    if not url:
        return article

    missing = [f for f in NON_CRUCIAL_FIELDS if _is_empty(article.get(f))]
    if not missing:
        return article  # Nothing to fix

    logger.info("Re-fetching %s to fill: %s", url, missing)
    fetched = _fetch_article_data(url, lang=article.get("lang") or "en")
    if not fetched:
        return article

    patched = dict(article)
    for field in missing:
        if field in fetched and not _is_empty(fetched[field]):
            patched[field] = fetched[field]

    return patched


def batch_fill_rank1(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Run fill_missing_fields on every Rank-1 article in the list.
    Returns a new list with updated dicts.
    """
    result = []
    for article in articles:
        if article.get("rank") == 1:
            result.append(fill_missing_fields(article))
        else:
            result.append(article)
    return result

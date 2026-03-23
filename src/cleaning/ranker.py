"""
Article data-quality ranker.

Assigns a cleaning rank to each raw article:

  Rank 0 — All fields present and non-empty.
  Rank 1 — Non-crucial fields are missing (pub date, summary, refs, lang, type).
            Article may be recoverable by re-fetching the URL.
  Rank 2 — Crucial fields are missing (url, title, body).
            Article should be discarded.

Crucial fields   : url, title, body  (without these the article is useless)
Non-crucial fields: type, pub, ret, lang, refs, sum, text
"""

from __future__ import annotations

from typing import Any

# Fields whose absence makes an article unrecoverable
CRUCIAL_FIELDS: tuple[str, ...] = ("url", "title", "body")

# Fields whose absence degrades quality but doesn't make the article useless
NON_CRUCIAL_FIELDS: tuple[str, ...] = ("type", "pub", "ret", "lang", "refs", "sum", "text")


def _is_empty(value: Any) -> bool:
    """Return True if a field value counts as 'missing'."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, list) and len(value) == 0:
        return True
    return False


def rank_article(article: dict[str, Any]) -> int:
    """
    Compute and return the cleaning rank for a single article dict.

    Returns
    -------
    0  — complete
    1  — non-crucial fields missing
    2  — crucial fields missing (discard)
    """
    # Check crucial fields first
    for field in CRUCIAL_FIELDS:
        if _is_empty(article.get(field)):
            return 2

    # Check non-crucial fields
    for field in NON_CRUCIAL_FIELDS:
        if _is_empty(article.get(field)):
            return 1

    return 0


def rank_article_with_reasons(article: dict[str, Any]) -> tuple[int, list[str]]:
    """Return rank and a human-readable list of missing-field reasons."""
    missing_crucial = [f for f in CRUCIAL_FIELDS if _is_empty(article.get(f))]
    if missing_crucial:
        return 2, [f"missing_crucial:{field}" for field in missing_crucial]

    missing_non_crucial = [f for f in NON_CRUCIAL_FIELDS if _is_empty(article.get(f))]
    if missing_non_crucial:
        return 1, [f"missing_optional:{field}" for field in missing_non_crucial]

    return 0, []


def rank_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Return the same list with a `rank` key added/updated on each article.
    Does NOT mutate the original dicts — returns new dicts.
    """
    result = []
    for article in articles:
        ranked = dict(article)
        ranked["rank"] = rank_article(article)
        result.append(ranked)
    return result


def summarise_ranks(articles: list[dict[str, Any]]) -> dict[int, int]:
    """Return a count breakdown of ranks in the list."""
    counts: dict[int, int] = {0: 0, 1: 0, 2: 0}
    for a in articles:
        rank = a.get("rank")
        if rank in counts:
            counts[rank] += 1
    return counts

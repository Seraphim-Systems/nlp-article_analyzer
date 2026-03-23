"""
Text normalization and lightweight signal extraction for cleaned articles.

This module intentionally preserves finance/time/location symbols and turns
those patterns into explicit fields for downstream feature engineering.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

_MONEY_RE = re.compile(
    r"(?:[$EURGBPJPYCHF]|USD|EUR|GBP|JPY|CHF)\s?\d{1,3}(?:[,\.]\d{3})*(?:\.\d+)?",
    flags=re.IGNORECASE,
)
_PERCENT_RE = re.compile(r"\b\d+(?:\.\d+)?%")
_DATETIME_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4})\b",
    flags=re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s)\]>'\"]+")
_WHITESPACE_RE = re.compile(r"\s+")
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]+")


@dataclass(frozen=True)
class DocumentStats:
    char_count: int
    token_count: int
    sentence_count: int
    paragraph_count: int


def normalize_text(text: str) -> str:
    """Normalize spacing only; preserve informative symbols such as %, $, and @."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def compute_document_stats(text: str) -> DocumentStats:
    paragraphs = [p for p in text.splitlines() if p.strip()]
    tokens = [t for t in text.split() if t.strip()]
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    return DocumentStats(
        char_count=len(text),
        token_count=len(tokens),
        sentence_count=len(sentences),
        paragraph_count=len(paragraphs) if paragraphs else (1 if text.strip() else 0),
    )


def extract_url_tags(urls: list[str]) -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    for u in urls:
        parsed = urlparse(u)
        if not parsed.netloc:
            continue
        host = parsed.netloc.lower()
        parts = host.split(".")
        tld = parts[-1] if len(parts) > 1 else ""
        tags.append(
            {
                "url": u,
                "domain": host,
                "tld": tld,
                "path": parsed.path or "/",
            }
        )
    return tags


def enrich_article_for_cleaning(article: dict[str, Any]) -> dict[str, Any]:
    """Return article enriched with normalized text and extracted signal tags."""
    body = article.get("body") or article.get("text") or ""
    clean_text = normalize_text(body)

    urls = [article.get("url")] if article.get("url") else []
    refs = article.get("refs") or []
    urls.extend([u for u in refs if isinstance(u, str)])
    urls.extend(_URL_RE.findall(clean_text))

    money_tags = sorted(set(_MONEY_RE.findall(clean_text)))
    percent_tags = sorted(set(_PERCENT_RE.findall(clean_text)))
    datetime_tags = sorted(set(_DATETIME_RE.findall(clean_text)))
    url_tags = extract_url_tags(sorted(set(urls)))

    stats = compute_document_stats(clean_text)
    quality_flags = {
        "short_text": stats.token_count < 80,
        "empty_summary": not bool(article.get("sum")),
        "has_money_signal": bool(money_tags),
        "has_percent_signal": bool(percent_tags),
        "has_datetime_signal": bool(datetime_tags),
    }

    enriched = dict(article)
    enriched.update(
        {
            "clean_text": clean_text,
            "money_tags": money_tags,
            "percent_tags": percent_tags,
            "datetime_tags": datetime_tags,
            "url_tags": url_tags,
            "doc_stats": {
                "char_count": stats.char_count,
                "token_count": stats.token_count,
                "sentence_count": stats.sentence_count,
                "paragraph_count": stats.paragraph_count,
            },
            "cleaning_flags": quality_flags,
        }
    )

    # Useful aggregate for quick analytics without scanning nested arrays.
    enriched["signal_counts"] = dict(
        Counter(
            {
                "money": len(money_tags),
                "percent": len(percent_tags),
                "datetime": len(datetime_tags),
                "url": len(url_tags),
            }
        )
    )
    return enriched

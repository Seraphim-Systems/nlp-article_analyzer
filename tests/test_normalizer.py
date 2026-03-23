"""Unit tests for cleaning normalizer signal extraction."""

from __future__ import annotations

from cleaning.normalizer import enrich_article_for_cleaning


def test_enrich_article_extracts_core_signals():
    article = {
        "url": "https://example.co.us/news/a",
        "body": "Revenue reached $195,000 and margins improved to 60% on Jan 10, 2024.",
        "refs": ["https://data.example.co.us/report?id=10"],
        "sum": "A short summary.",
    }

    enriched = enrich_article_for_cleaning(article)

    assert "$195,000" in enriched["money_tags"]
    assert "60%" in enriched["percent_tags"]
    assert "Jan 10, 2024" in enriched["datetime_tags"]
    assert enriched["doc_stats"]["token_count"] > 0
    assert any(tag["domain"].endswith("co.us") for tag in enriched["url_tags"])


def test_enrich_article_preserves_symbols_in_clean_text():
    article = {
        "url": "https://example.com/x",
        "body": "Email us @newsdesk. Inflation is at 4.2% and budget is $1000.",
    }
    enriched = enrich_article_for_cleaning(article)
    assert "@newsdesk" in enriched["clean_text"]
    assert "4.2%" in enriched["clean_text"]
    assert "$1000" in enriched["clean_text"]

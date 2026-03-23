"""Unit tests for ranking and quality-reason assignment."""

from __future__ import annotations

from cleaning.ranker import rank_article, rank_article_with_reasons, rank_articles, summarise_ranks


def _full_article(**overrides):
    base = {
        "url": "https://example.com/article-1",
        "title": "Test Article",
        "feed": "Test Feed",
        "type": "news",
        "pub": "2026-03-10T10:00:00Z",
        "ret": "2026-03-10T11:00:00Z",
        "lang": "en",
        "refs": ["https://example.com/ref"],
        "sum": "A short summary.",
        "body": "This is the full article body.",
        "text": "This is the full article body.",
    }
    base.update(overrides)
    return base


def test_rank0_complete_article():
    assert rank_article(_full_article()) == 0


def test_rank1_missing_summary():
    assert rank_article(_full_article(sum=None)) == 1


def test_rank2_missing_body():
    assert rank_article(_full_article(body=None)) == 2


def test_rank2_takes_priority_over_rank1():
    assert rank_article(_full_article(body=None, pub=None)) == 2


def test_rank_with_reasons_for_crucial_field():
    rank, reasons = rank_article_with_reasons(_full_article(body=None, pub=None))
    assert rank == 2
    assert "missing_crucial:body" in reasons


def test_rank_with_reasons_for_non_crucial_field():
    rank, reasons = rank_article_with_reasons(_full_article(sum=None))
    assert rank == 1
    assert "missing_optional:sum" in reasons


def test_rank_articles_adds_rank_key_without_mutating_original():
    original = _full_article()
    ranked = rank_articles([original])
    assert ranked[0]["rank"] == 0
    assert "rank" not in original


def test_summarise_ranks():
    counts = summarise_ranks([{"rank": 0}, {"rank": 0}, {"rank": 1}, {"rank": 2}])
    assert counts == {0: 2, 1: 1, 2: 1}

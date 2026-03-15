"""
Unit tests for the data cleaning ranker.
Run with:  pytest tests/
"""

import pytest
from cleaning.ranker import rank_article, rank_articles, summarise_ranks

# --------------- helpers ------------------------------------------------

def _full_article(**overrides):
    base = {
        "url":   "https://example.com/article-1",
        "title": "Test Article",
        "feed":  "Test Feed",
        "type":  "news",
        "pub":   "2026-03-10T10:00:00Z",
        "ret":   "2026-03-10T11:00:00Z",
        "lang":  "en",
        "refs":  ["https://example.com/ref"],
        "sum":   "A short summary.",
        "body":  "This is the full article body.",
        "text":  "This is the full article body.",
    }
    base.update(overrides)
    return base


# --------------- rank_article -------------------------------------------

def test_rank0_complete_article():
    assert rank_article(_full_article()) == 0


def test_rank1_missing_summary():
    assert rank_article(_full_article(sum=None)) == 1


def test_rank1_missing_pub_date():
    assert rank_article(_full_article(pub=None)) == 1


def test_rank1_missing_refs():
    assert rank_article(_full_article(refs=None)) == 1


def test_rank1_empty_refs_list():
    assert rank_article(_full_article(refs=[])) == 1


def test_rank2_missing_body():
    assert rank_article(_full_article(body=None)) == 2


def test_rank2_missing_title():
    assert rank_article(_full_article(title="")) == 2


def test_rank2_missing_url():
    assert rank_article(_full_article(url=None)) == 2


def test_rank2_takes_priority_over_rank1():
    # Missing both body (crucial) and pub (non-crucial) → still rank 2
    assert rank_article(_full_article(body=None, pub=None)) == 2


# --------------- rank_articles / summarise_ranks -----------------------

def test_rank_articles_adds_rank_key():
    articles = [_full_article(), _full_article(sum=None), _full_article(body=None)]
    ranked = rank_articles(articles)
    assert [a["rank"] for a in ranked] == [0, 1, 2]


def test_rank_articles_does_not_mutate_originals():
    original = _full_article()
    rank_articles([original])
    assert "rank" not in original


def test_summarise_ranks():
    articles = [
        {"rank": 0}, {"rank": 0}, {"rank": 1}, {"rank": 2},
    ]
    counts = summarise_ranks(articles)
    assert counts == {0: 2, 1: 1, 2: 1}

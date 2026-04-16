"""Unit tests for the cleaning layer: normalizer extras, url_fetcher, and cleaner."""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Stub heavy dependencies that are not installed in the test env
# ---------------------------------------------------------------------------

def _ensure_stub(name):
    if name not in sys.modules:
        sys.modules[name] = MagicMock()

for _mod in (
    "spacy", "spacy.cli", "spacy.tokens",
    "nltk", "nltk.corpus", "nltk.stem",
    "newspaper",
):
    _ensure_stub(_mod)

# Ensure preprocessing can be imported (it pulls spacy at module level)
import importlib
if "preprocessing" in sys.modules:
    importlib.reload(sys.modules["preprocessing"])
if "preprocessing.text_processor" in sys.modules:
    importlib.reload(sys.modules["preprocessing.text_processor"])

# ===========================================================================
# normalizer.py — cases NOT covered by test_normalizer.py
# ===========================================================================

from cleaning.normalizer import (
    normalize_text,
    compute_document_stats,
    extract_url_tags,
    enrich_article_for_cleaning,
)


# --- normalize_text --------------------------------------------------------

def test_normalize_text_collapses_multiple_spaces_and_tabs():
    assert normalize_text("hello   world\tbar") == "hello world bar"


def test_normalize_text_strips_leading_trailing_whitespace():
    assert normalize_text("  hello  ") == "hello"


# --- compute_document_stats ------------------------------------------------

def test_compute_document_stats_empty_string():
    stats = compute_document_stats("")
    assert stats.char_count == 0
    assert stats.token_count == 0
    assert stats.sentence_count == 0
    assert stats.paragraph_count == 0


def test_compute_document_stats_multiline_paragraph_count():
    text = "Para one.\n\nPara two.\n\nPara three."
    stats = compute_document_stats(text)
    assert stats.paragraph_count == 3


# --- extract_url_tags ------------------------------------------------------

def test_extract_url_tags_empty_list():
    assert extract_url_tags([]) == []


def test_extract_url_tags_malformed_url_skipped():
    # No netloc → skipped
    result = extract_url_tags(["not-a-url", "ftp://", ""])
    assert result == []


# --- enrich_article_for_cleaning -------------------------------------------

@pytest.fixture
def _patch_preprocess():
    """Patch preprocess_text to identity so we don't need spacy/nltk."""
    with patch("cleaning.normalizer.preprocess_text", side_effect=lambda t: t):
        yield


def test_enrich_uses_body_field(_patch_preprocess):
    article = {"body": "Hello world", "url": "https://x.com"}
    enriched = enrich_article_for_cleaning(article)
    assert "Hello world" in enriched["clean_text"]


def test_enrich_short_text_flag(_patch_preprocess):
    article = {"body": "short", "url": "https://x.com"}
    enriched = enrich_article_for_cleaning(article)
    assert enriched["cleaning_flags"]["short_text"] is True


def test_enrich_empty_summary_flag(_patch_preprocess):
    article = {"body": "Some body text here", "sum": None}
    enriched = enrich_article_for_cleaning(article)
    assert enriched["cleaning_flags"]["empty_summary"] is True


def test_enrich_does_not_mutate_original(_patch_preprocess):
    article = {"body": "test body", "url": "https://x.com"}
    original_keys = set(article.keys())
    enrich_article_for_cleaning(article)
    assert set(article.keys()) == original_keys


def test_enrich_signal_counts_keys(_patch_preprocess):
    article = {"body": "price $100 and 50% on Jan 1, 2024", "url": "https://x.com"}
    enriched = enrich_article_for_cleaning(article)
    assert set(enriched["signal_counts"].keys()) == {"money", "percent", "datetime", "url"}


# ===========================================================================
# url_fetcher.py
# ===========================================================================

@pytest.fixture
def mock_article():
    a = MagicMock()
    a.title = "Title"
    a.publish_date = None
    a.meta_lang = "en"
    a.movies = []
    a.summary = "Sum"
    a.text = "Body"
    return a


def _base_article(**overrides):
    base = {
        "url": "https://example.com/a",
        "title": "T",
        "feed": "F",
        "type": "news",
        "pub": "2026-01-01",
        "ret": "2026-01-01",
        "lang": "en",
        "refs": ["https://r.com"],
        "sum": "summary",
        "body": "body text",
        "text": "body text",
    }
    base.update(overrides)
    return base


def test_fill_missing_no_url():
    from cleaning.url_fetcher import fill_missing_fields
    article = {"title": "T"}
    result = fill_missing_fields(article)
    assert result is article  # returned unchanged


def test_fill_missing_all_present():
    from cleaning.url_fetcher import fill_missing_fields
    article = _base_article()
    with patch("cleaning.url_fetcher.NewspaperArticle") as mock_cls:
        result = fill_missing_fields(article)
    mock_cls.assert_not_called()
    assert result is article


def test_fill_missing_patches_summary(mock_article):
    from cleaning.url_fetcher import fill_missing_fields
    article = _base_article(sum=None)
    with patch("cleaning.url_fetcher.NewspaperArticle", return_value=mock_article):
        result = fill_missing_fields(article)
    assert result["sum"] == "Sum"


def test_fill_missing_fetch_raises():
    from cleaning.url_fetcher import fill_missing_fields
    article = _base_article(sum=None)
    bad_art = MagicMock()
    bad_art.download.side_effect = Exception("network error")
    with patch("cleaning.url_fetcher.NewspaperArticle", return_value=bad_art):
        result = fill_missing_fields(article)
    # Should return original unchanged on error
    assert result.get("sum") is None


def test_fill_missing_does_not_mutate_original(mock_article):
    from cleaning.url_fetcher import fill_missing_fields
    article = _base_article(sum=None)
    original = dict(article)
    with patch("cleaning.url_fetcher.NewspaperArticle", return_value=mock_article):
        fill_missing_fields(article)
    assert article == original


def test_batch_fill_rank1_only_rank1(mock_article):
    from cleaning.url_fetcher import batch_fill_rank1
    articles = [
        _base_article(rank=0, sum=None),
        _base_article(rank=1, sum=None),
        _base_article(rank=2, sum=None),
    ]
    with patch("cleaning.url_fetcher.NewspaperArticle", return_value=mock_article):
        result = batch_fill_rank1(articles)
    # Only rank=1 should have been patched
    assert result[0]["sum"] is None  # rank 0 untouched
    assert result[1]["sum"] == "Sum"  # rank 1 patched
    assert result[2]["sum"] is None  # rank 2 untouched


def test_batch_fill_rank1_empty_list():
    from cleaning.url_fetcher import batch_fill_rank1
    assert batch_fill_rank1([]) == []


def test_batch_fill_rank1_preserves_order(mock_article):
    from cleaning.url_fetcher import batch_fill_rank1
    articles = [
        _base_article(rank=1, sum=None, url="https://a.com"),
        _base_article(rank=0, url="https://b.com"),
        _base_article(rank=1, sum=None, url="https://c.com"),
    ]
    with patch("cleaning.url_fetcher.NewspaperArticle", return_value=mock_article):
        result = batch_fill_rank1(articles)
    assert [r["url"] for r in result] == ["https://a.com", "https://b.com", "https://c.com"]


# ===========================================================================
# cleaner.py — mock all database/cleaning dependencies
# ===========================================================================

# We need to mock heavy dependencies before importing cleaner
@pytest.fixture
def cleaner_mocks():
    """Set up all mocks needed by cleaner module functions."""
    fake_col = MagicMock()
    fake_col.find.return_value = []
    fake_col.count_documents.return_value = 0
    with patch("cleaning.cleaner.make_pbar_simple", side_effect=lambda x, **kw: x), \
         patch("cleaning.cleaner.rank_article_with_reasons") as mock_rank, \
         patch("cleaning.cleaner.fill_missing_fields", side_effect=lambda a: a) as mock_fill, \
         patch("cleaning.cleaner.enrich_article_for_cleaning", side_effect=lambda a: a) as mock_enrich, \
         patch("cleaning.cleaner.bulk_update_raw_ranks") as mock_bulk, \
         patch("cleaning.cleaner.count_raw_articles_by_rank", return_value={0: 0, 1: 0, 2: 0}) as mock_count, \
         patch("cleaning.cleaner.get_raw_articles_by_rank") as mock_get_by_rank, \
         patch("cleaning.cleaner.upsert_quarantine_articles", return_value=0) as mock_quarantine, \
         patch("cleaning.cleaner.update_raw_article_fields") as mock_update_fields, \
         patch("cleaning.cleaner.update_raw_rank") as mock_update_rank, \
         patch("cleaning.cleaner.upsert_clean_articles", return_value=0) as mock_upsert_clean, \
         patch("cleaning.cleaner.get_raw_collection", return_value=fake_col), \
         patch("database.repositories.get_raw_collection", return_value=fake_col):
        yield {
            "rank": mock_rank,
            "fill": mock_fill,
            "enrich": mock_enrich,
            "bulk_update": mock_bulk,
            "count": mock_count,
            "get_by_rank": mock_get_by_rank,
            "quarantine": mock_quarantine,
            "update_fields": mock_update_fields,
            "update_rank": mock_update_rank,
            "upsert_clean": mock_upsert_clean,
            "fake_col": fake_col,
        }


def test_cleaner_no_unranked_no_rank1(cleaner_mocks):
    from cleaning.cleaner import run_cleaning_pipeline
    cleaner_mocks["get_by_rank"].return_value = []
    result = run_cleaning_pipeline()
    assert result["promoted"] == 0
    assert result["discarded"] == 0


def test_cleaner_promotes_rank0(cleaner_mocks):
    from cleaning.cleaner import run_cleaning_pipeline
    rank0_art = [_base_article(rank=0)]

    def get_by_rank_side(rank, limit=0):
        if rank == 0:
            return rank0_art
        return []

    cleaner_mocks["get_by_rank"].side_effect = get_by_rank_side
    cleaner_mocks["upsert_clean"].return_value = 1
    cleaner_mocks["fake_col"].count_documents.return_value = 1

    result = run_cleaning_pipeline()
    cleaner_mocks["upsert_clean"].assert_called_once()
    assert result["promoted"] == 1


def test_cleaner_quarantines_rank2(cleaner_mocks):
    from cleaning.cleaner import run_cleaning_pipeline
    rank2_art = [_base_article(rank=2)]

    def get_by_rank_side(rank, limit=0):
        if rank == 2:
            return rank2_art
        return []

    cleaner_mocks["get_by_rank"].side_effect = get_by_rank_side
    cleaner_mocks["quarantine"].return_value = 1
    cleaner_mocks["fake_col"].count_documents.return_value = 1

    result = run_cleaning_pipeline()
    cleaner_mocks["quarantine"].assert_called_once()
    assert result["discarded"] == 1


def test_cleaner_skip_rank1_recovery(cleaner_mocks):
    from cleaning.cleaner import run_cleaning_pipeline
    cleaner_mocks["get_by_rank"].return_value = []

    run_cleaning_pipeline(skip_rank1_recovery=True)
    cleaner_mocks["fill"].assert_not_called()


def test_cleaner_rank1_recovery_promotes(cleaner_mocks):
    from cleaning.cleaner import _process_rank1
    rank1_art = [_base_article(rank=1, sum=None)]

    cleaner_mocks["get_by_rank"].return_value = rank1_art
    cleaner_mocks["rank"].return_value = (0, [])
    cleaner_mocks["fill"].side_effect = lambda a: {**a, "sum": "recovered"}
    cleaner_mocks["fake_col"].count_documents.return_value = 1

    _process_rank1()

    cleaner_mocks["bulk_update"].assert_called_once()
    # The url and new rank should be in the bulk update call
    update_args = cleaner_mocks["bulk_update"].call_args[0][0]
    assert update_args[0][1] == 0  # promoted to rank 0


def test_cleaner_rank1_no_change_no_field_update(cleaner_mocks):
    from cleaning.cleaner import _process_rank1
    rank1_art = [_base_article(rank=1, sum=None)]

    cleaner_mocks["get_by_rank"].return_value = rank1_art
    cleaner_mocks["rank"].return_value = (1, ["missing_optional:sum"])
    cleaner_mocks["fill"].side_effect = lambda a: a
    cleaner_mocks["fake_col"].count_documents.return_value = 1

    _process_rank1()

    cleaner_mocks["update_fields"].assert_not_called()

"""
Unit tests for the NER-related repository functions.

All MongoDB operations are mocked via pytest-mock.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import BulkWriteError


# ---------------------------------------------------------------------------
# get_unprocessed_clean_articles
# ---------------------------------------------------------------------------

def test_get_unprocessed_clean_articles_filters_existing(mocker):
    from database.repositories import get_unprocessed_clean_articles

    ner_col = MagicMock()
    ner_col.distinct.return_value = ["http://already.com"]

    clean_col = MagicMock()
    clean_col.find.return_value = [{"url": "http://new.com", "body": "text"}]

    mocker.patch("database.repositories.get_ner_collection", return_value=ner_col)
    mocker.patch("database.repositories.get_clean_collection", return_value=clean_col)

    result = get_unprocessed_clean_articles()

    clean_col.find.assert_called_once_with({"url": {"$nin": ["http://already.com"]}})
    assert result == [{"url": "http://new.com", "body": "text"}]


def test_get_unprocessed_clean_articles_all_new(mocker):
    from database.repositories import get_unprocessed_clean_articles

    ner_col = MagicMock()
    ner_col.distinct.return_value = []

    clean_col = MagicMock()
    clean_col.find.return_value = [{"url": "http://a.com"}, {"url": "http://b.com"}]

    mocker.patch("database.repositories.get_ner_collection", return_value=ner_col)
    mocker.patch("database.repositories.get_clean_collection", return_value=clean_col)

    result = get_unprocessed_clean_articles()
    assert len(result) == 2


# ---------------------------------------------------------------------------
# insert_ner_articles
# ---------------------------------------------------------------------------

def test_insert_ner_articles_empty_list(mocker):
    from database.repositories import insert_ner_articles

    col = MagicMock()
    mocker.patch("database.repositories.get_ner_collection", return_value=col)

    result = insert_ner_articles([])
    col.bulk_write.assert_not_called()
    assert result == 0


def test_insert_ner_articles_returns_upsert_count(mocker):
    from database.repositories import insert_ner_articles

    col = MagicMock()
    bulk_result = MagicMock()
    bulk_result.upserted_count = 2
    bulk_result.modified_count = 1
    col.bulk_write.return_value = bulk_result

    mocker.patch("database.repositories.get_ner_collection", return_value=col)

    articles = [
        {"url": "http://a.com", "entities": []},
        {"url": "http://b.com", "entities": []},
        {"url": "http://c.com", "entities": []},
    ]
    result = insert_ner_articles(articles)
    assert result == 3  # upserted_count + modified_count


def test_insert_ner_articles_handles_bulk_write_error(mocker):
    from database.repositories import insert_ner_articles

    col = MagicMock()
    error_details = {"nUpserted": 1, "writeErrors": []}
    col.bulk_write.side_effect = BulkWriteError(error_details)

    mocker.patch("database.repositories.get_ner_collection", return_value=col)

    articles = [{"url": "http://a.com", "entities": []}]
    result = insert_ner_articles(articles)
    assert result == 1

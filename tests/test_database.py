"""
Unit tests for config/settings, database/connection, database/models,
database/init_db, and database/repositories.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from pymongo.errors import BulkWriteError


# ===================================================================
# config/settings.py
# ===================================================================


def test_env_returns_default_when_absent():
    from config.settings import _env

    assert _env("__NONEXISTENT_KEY__", "fallback") == "fallback"


def test_env_returns_env_value(monkeypatch):
    from config.settings import _env

    monkeypatch.setenv("__TEST_KEY__", "hello")
    assert _env("__TEST_KEY__", "fallback") == "hello"


def test_env_int_returns_default_on_invalid():
    from config.settings import _env_int

    with patch.dict(os.environ, {"__BAD_INT__": "abc"}):
        assert _env_int("__BAD_INT__", 42) == 42


def test_env_int_parses_valid(monkeypatch):
    from config.settings import _env_int

    monkeypatch.setenv("__GOOD_INT__", "7")
    assert _env_int("__GOOD_INT__", 0) == 7


@pytest.mark.parametrize("val", ["1", "true", "yes", "on", "TRUE"])
def test_env_bool_truthy(monkeypatch, val):
    from config.settings import _env_bool

    monkeypatch.setenv("__BOOL_T__", val)
    assert _env_bool("__BOOL_T__", False) is True


@pytest.mark.parametrize("val", ["0", "false", "no", "off"])
def test_env_bool_falsy(monkeypatch, val):
    from config.settings import _env_bool

    monkeypatch.setenv("__BOOL_F__", val)
    assert _env_bool("__BOOL_F__", True) is False


def test_env_bool_returns_default_when_absent():
    from config.settings import _env_bool

    assert _env_bool("__NOKEY__", True) is True
    assert _env_bool("__NOKEY__", False) is False


def test_settings_reads_mongo_uri(monkeypatch):
    from config.settings import Settings

    monkeypatch.setenv("MONGO_URI", "mongodb://test:1234")
    s = Settings()
    assert s.MONGO_URI == "mongodb://test:1234"


def test_validate_passes_with_uri_set(monkeypatch):
    from config.settings import Settings

    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("KAGGLE_ENABLED", "false")
    s = Settings()
    s.validate()


def test_validate_raises_when_uri_empty(monkeypatch):
    from config.settings import Settings

    monkeypatch.setenv("MONGO_URI", "")
    s = Settings()
    with pytest.raises(EnvironmentError, match="MONGO_URI"):
        s.validate()


def test_validate_raises_when_kaggle_enabled_no_key(monkeypatch):
    from config.settings import Settings

    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("KAGGLE_ENABLED", "true")
    monkeypatch.setenv("KAGGLE_KEY", "")
    s = Settings()
    with pytest.raises(EnvironmentError, match="KAGGLE_KEY"):
        s.validate()


def test_validate_passes_kaggle_enabled_with_key(monkeypatch):
    from config.settings import Settings

    monkeypatch.setenv("MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setenv("KAGGLE_ENABLED", "true")
    monkeypatch.setenv("KAGGLE_KEY", "mykey")
    s = Settings()
    s.validate()


# ===================================================================
# database/connection.py
# ===================================================================


@pytest.fixture(autouse=False)
def clear_cache():
    from database.connection import get_client

    get_client.cache_clear()
    yield
    get_client.cache_clear()


def test_get_client_creates_mongo_client(clear_cache):
    with patch("database.connection.MongoClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        from database.connection import get_client

        client = get_client()
        MockClient.assert_called_once()
        assert client is mock_instance


def test_get_client_calls_ping(clear_cache):
    with patch("database.connection.MongoClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        from database.connection import get_client

        get_client()
        mock_instance.admin.command.assert_called_once_with("ping")


def test_get_client_singleton(clear_cache):
    with patch("database.connection.MongoClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        from database.connection import get_client

        c1 = get_client()
        c2 = get_client()
        assert c1 is c2
        MockClient.assert_called_once()


def test_get_raw_db_returns_correct_db(clear_cache):
    with patch("database.connection.MongoClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        from database.connection import get_raw_db
        from config.settings import settings

        get_raw_db()
        mock_instance.__getitem__.assert_called_with(settings.RAW_DB_NAME)


def test_get_clean_db_returns_correct_db(clear_cache):
    with patch("database.connection.MongoClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        from database.connection import get_clean_db
        from config.settings import settings

        get_clean_db()
        mock_instance.__getitem__.assert_called_with(settings.CLEAN_DB_NAME)


def test_get_ner_db_returns_correct_db(clear_cache):
    with patch("database.connection.MongoClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        from database.connection import get_ner_db
        from config.settings import settings

        get_ner_db()
        mock_instance.__getitem__.assert_called_with(settings.NER_DB_NAME)


def test_close_connection_calls_close(clear_cache):
    with patch("database.connection.MongoClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        from database.connection import get_client, close_connection

        get_client()
        close_connection()
        mock_instance.close.assert_called_once()


def test_close_connection_clears_cache(clear_cache):
    with patch("database.connection.MongoClient") as MockClient:
        mock_instance = MagicMock()
        MockClient.return_value = mock_instance

        from database.connection import get_client, close_connection

        get_client()
        close_connection()
        mock_instance2 = MagicMock()
        MockClient.return_value = mock_instance2
        c = get_client()
        assert c is mock_instance2
        assert MockClient.call_count == 2


# ===================================================================
# database/models.py
# ===================================================================


def test_article_validator_required_fields():
    from database.models import ARTICLE_VALIDATOR

    required = ARTICLE_VALIDATOR["$jsonSchema"]["required"]
    assert set(required) == {"url", "title", "feed", "body"}


def test_ner_article_validator_has_entities():
    from database.models import NER_ARTICLE_VALIDATOR

    required = NER_ARTICLE_VALIDATOR["$jsonSchema"]["required"]
    assert "entities" in required


def test_entity_validator_required_fields():
    from database.models import ENTITY_VALIDATOR

    required = ENTITY_VALIDATOR["$jsonSchema"]["required"]
    assert set(required) == {"docID", "senDocID", "NE", "sSen", "eSen"}


def test_raw_indexes_has_unique_url():
    from database.models import RAW_INDEXES

    url_idx = [i for i in RAW_INDEXES if ("url", 1) in i["keys"]]
    assert len(url_idx) == 1
    assert url_idx[0]["options"]["unique"] is True


def test_clean_indexes_has_topic_label():
    from database.models import CLEAN_INDEXES

    topic_idx = [i for i in CLEAN_INDEXES if ("topic_label", 1) in i["keys"]]
    assert len(topic_idx) == 1


def test_build_article_dict_minimal():
    from database.models import build_article_dict

    d = build_article_dict(url="http://x.com", title="T", feed="F", body="B")
    assert d["url"] == "http://x.com"
    assert d["title"] == "T"
    assert d["feed"] == "F"
    assert d["body"] == "B"


def test_build_article_dict_optional_defaults():
    from database.models import build_article_dict

    d = build_article_dict(url="u", title="t", feed="f", body="b")
    for key in [
        "type", "pub", "ret", "lang", "refs", "sum", "text",
        "clean_text", "preprocessed_text", "money_tags", "percent_tags",
        "datetime_tags", "url_tags", "doc_stats", "cleaning_flags",
        "signal_counts", "rank",
    ]:
        assert d.get(key) is None, f"{key} should default to None"


def test_build_article_dict_optional_fields_set():
    from database.models import build_article_dict

    d = build_article_dict(
        url="u", title="t", feed="f", body="b",
        type_="news", lang="en", preprocessed_text="clean text",
        rank=0,
    )
    assert d["type"] == "news"
    assert d["lang"] == "en"
    assert d["preprocessed_text"] == "clean text"
    assert d["rank"] == 0


# ===================================================================
# database/init_db.py
# ===================================================================


def test_ensure_collection_creates_when_absent():
    from database.init_db import _ensure_collection

    db = MagicMock()
    db.list_collection_names.return_value = []
    db.__getitem__ = MagicMock(return_value=MagicMock())

    _ensure_collection(db, "test_col", {"schema": True}, [])
    db.create_collection.assert_called_once_with(
        "test_col",
        validator={"schema": True},
        validationLevel="moderate",
        validationAction="warn",
    )


def test_ensure_collection_skips_create_when_exists():
    from database.init_db import _ensure_collection

    db = MagicMock()
    db.list_collection_names.return_value = ["test_col"]
    db.__getitem__ = MagicMock(return_value=MagicMock())

    _ensure_collection(db, "test_col", {"schema": True}, [])
    db.create_collection.assert_not_called()


def test_ensure_collection_always_creates_indexes():
    from database.init_db import _ensure_collection

    col = MagicMock()
    db = MagicMock()
    db.list_collection_names.return_value = ["test_col"]
    db.__getitem__ = MagicMock(return_value=col)

    indexes = [
        {"keys": [("url", 1)], "options": {"unique": True, "name": "url_unique"}},
    ]
    _ensure_collection(db, "test_col", {}, indexes)
    col.create_index.assert_called_once_with([("url", 1)], unique=True, name="url_unique")


def test_ensure_collection_swallows_index_exception():
    from database.init_db import _ensure_collection

    col = MagicMock()
    col.create_index.side_effect = Exception("index error")
    db = MagicMock()
    db.list_collection_names.return_value = []
    db.__getitem__ = MagicMock(return_value=col)

    _ensure_collection(db, "test_col", {}, [
        {"keys": [("x", 1)], "options": {"name": "x_idx"}},
    ])


def test_init_databases_calls_ensure_for_all_collections():
    from database.init_db import init_databases

    with patch("database.init_db._ensure_collection") as mock_ensure, \
         patch("database.init_db.get_raw_db", return_value=MagicMock()), \
         patch("database.init_db.get_clean_db", return_value=MagicMock()), \
         patch("database.init_db.get_ner_db", return_value=MagicMock()), \
         patch("database.init_db.get_client", return_value=MagicMock()):

        init_databases()
        assert mock_ensure.call_count == 7


# ===================================================================
# database/repositories.py
# ===================================================================


# --- insert_raw_articles ---


def test_insert_raw_articles_empty_list():
    from database.repositories import insert_raw_articles

    with patch("database.repositories.get_raw_collection") as mock_get:
        col = MagicMock()
        mock_get.return_value = col
        assert insert_raw_articles([]) == 0
        col.bulk_write.assert_not_called()


def test_insert_raw_articles_sets_ret_if_missing():
    from database.repositories import insert_raw_articles

    with patch("database.repositories.get_raw_collection") as mock_get:
        col = MagicMock()
        bulk_result = MagicMock()
        bulk_result.upserted_count = 1
        col.bulk_write.return_value = bulk_result
        mock_get.return_value = col

        articles = [{"url": "http://a.com", "title": "T", "feed": "F", "body": "B"}]
        insert_raw_articles(articles)
        assert "ret" in articles[0]


def test_insert_raw_articles_preserves_existing_ret():
    from database.repositories import insert_raw_articles

    with patch("database.repositories.get_raw_collection") as mock_get:
        col = MagicMock()
        bulk_result = MagicMock()
        bulk_result.upserted_count = 1
        col.bulk_write.return_value = bulk_result
        mock_get.return_value = col

        articles = [{"url": "http://a.com", "ret": "2020-01-01"}]
        insert_raw_articles(articles)
        assert articles[0]["ret"] == "2020-01-01"


def test_insert_raw_articles_returns_upserted_count():
    from database.repositories import insert_raw_articles

    with patch("database.repositories.get_raw_collection") as mock_get:
        col = MagicMock()
        bulk_result = MagicMock()
        bulk_result.upserted_count = 3
        col.bulk_write.return_value = bulk_result
        mock_get.return_value = col

        articles = [{"url": f"http://{i}.com"} for i in range(3)]
        assert insert_raw_articles(articles) == 3


def test_insert_raw_articles_handles_bulk_write_error():
    from database.repositories import insert_raw_articles

    with patch("database.repositories.get_raw_collection") as mock_get:
        col = MagicMock()
        col.bulk_write.side_effect = BulkWriteError({"nUpserted": 2, "writeErrors": []})
        mock_get.return_value = col

        articles = [{"url": "http://a.com"}]
        assert insert_raw_articles(articles) == 2


# --- update_raw_rank ---


def test_update_raw_rank_without_reasons():
    from database.repositories import update_raw_rank

    with patch("database.repositories.get_raw_collection") as mock_get:
        col = MagicMock()
        mock_get.return_value = col

        update_raw_rank("http://a.com", 1)
        args = col.update_one.call_args
        payload = args[0][1]["$set"]
        assert payload == {"rank": 1}
        assert "rank_reasons" not in payload


def test_update_raw_rank_with_reasons():
    from database.repositories import update_raw_rank

    with patch("database.repositories.get_raw_collection") as mock_get:
        col = MagicMock()
        mock_get.return_value = col

        update_raw_rank("http://a.com", 2, reasons=["missing body"])
        args = col.update_one.call_args
        payload = args[0][1]["$set"]
        assert payload["rank_reasons"] == ["missing body"]


# --- bulk_update_raw_ranks ---


def test_bulk_update_raw_ranks_empty():
    from database.repositories import bulk_update_raw_ranks

    with patch("database.repositories.get_raw_collection") as mock_get:
        col = MagicMock()
        mock_get.return_value = col

        bulk_update_raw_ranks([])
        col.bulk_write.assert_not_called()


def test_bulk_update_raw_ranks_builds_ops():
    from database.repositories import bulk_update_raw_ranks

    with patch("database.repositories.get_raw_collection") as mock_get:
        col = MagicMock()
        mock_get.return_value = col

        updates = [
            ("http://a.com", 0, None),
            ("http://b.com", 2, ["bad"]),
        ]
        bulk_update_raw_ranks(updates)
        col.bulk_write.assert_called_once()
        ops = col.bulk_write.call_args[0][0]
        assert len(ops) == 2


# --- upsert_quarantine_articles ---


def test_upsert_quarantine_empty():
    from database.repositories import upsert_quarantine_articles

    with patch("database.repositories.get_quarantine_collection") as mock_get:
        col = MagicMock()
        mock_get.return_value = col

        assert upsert_quarantine_articles([]) == 0
        col.bulk_write.assert_not_called()


def test_upsert_quarantine_adds_timestamp():
    from database.repositories import upsert_quarantine_articles

    with patch("database.repositories.get_quarantine_collection") as mock_get:
        col = MagicMock()
        bulk_result = MagicMock()
        bulk_result.upserted_count = 1
        bulk_result.modified_count = 0
        col.bulk_write.return_value = bulk_result
        mock_get.return_value = col

        upsert_quarantine_articles([{"url": "http://a.com"}])
        ops = col.bulk_write.call_args[0][0]
        set_doc = ops[0]._doc["$set"]
        assert "quarantined_at" in set_doc


def test_upsert_quarantine_handles_bulk_write_error():
    from database.repositories import upsert_quarantine_articles

    with patch("database.repositories.get_quarantine_collection") as mock_get:
        col = MagicMock()
        col.bulk_write.side_effect = BulkWriteError({"nUpserted": 1, "writeErrors": []})
        mock_get.return_value = col

        assert upsert_quarantine_articles([{"url": "http://a.com"}]) == 1


# --- upsert_clean_articles ---


def test_upsert_clean_empty():
    from database.repositories import upsert_clean_articles

    with patch("database.repositories.get_clean_collection") as mock_get:
        col = MagicMock()
        mock_get.return_value = col

        assert upsert_clean_articles([]) == 0


def test_upsert_clean_strips_rank():
    from database.repositories import upsert_clean_articles

    with patch("database.repositories.get_clean_collection") as mock_get:
        col = MagicMock()
        bulk_result = MagicMock()
        bulk_result.upserted_count = 1
        bulk_result.modified_count = 0
        col.bulk_write.return_value = bulk_result
        mock_get.return_value = col

        upsert_clean_articles([{"url": "http://a.com", "rank": 0, "title": "T"}])
        ops = col.bulk_write.call_args[0][0]
        set_doc = ops[0]._doc["$set"]
        assert "rank" not in set_doc


def test_upsert_clean_returns_count():
    from database.repositories import upsert_clean_articles

    with patch("database.repositories.get_clean_collection") as mock_get:
        col = MagicMock()
        bulk_result = MagicMock()
        bulk_result.upserted_count = 2
        bulk_result.modified_count = 1
        col.bulk_write.return_value = bulk_result
        mock_get.return_value = col

        result = upsert_clean_articles([{"url": "http://a.com"}, {"url": "http://b.com"}])
        assert result == 3


# --- count_clean_articles ---


def test_count_clean_articles():
    from database.repositories import count_clean_articles

    with patch("database.repositories.get_clean_collection") as mock_get:
        col = MagicMock()
        col.count_documents.return_value = 42
        mock_get.return_value = col

        assert count_clean_articles() == 42


# --- count_raw_articles_by_rank ---


def test_count_raw_articles_by_rank():
    from database.repositories import count_raw_articles_by_rank

    with patch("database.repositories.get_raw_collection") as mock_get:
        col = MagicMock()
        col.aggregate.return_value = [
            {"_id": 0, "count": 10},
            {"_id": 1, "count": 5},
            {"_id": 2, "count": 3},
        ]
        mock_get.return_value = col

        result = count_raw_articles_by_rank()
        assert result == {0: 10, 1: 5, 2: 3}


# --- get_unprocessed_topic_articles ---


def test_get_unprocessed_topic_articles_queries_missing_label():
    from database.repositories import get_unprocessed_topic_articles

    with patch("database.repositories.get_clean_collection") as mock_get:
        col = MagicMock()
        col.find.return_value = [{"url": "http://a.com"}]
        mock_get.return_value = col

        get_unprocessed_topic_articles()
        filter_arg = col.find.call_args[0][0]
        assert filter_arg == {"topic_label": {"$exists": False}}


def test_get_unprocessed_topic_articles_respects_limit():
    from database.repositories import get_unprocessed_topic_articles

    with patch("database.repositories.get_clean_collection") as mock_get:
        col = MagicMock()
        col.find.return_value = []
        mock_get.return_value = col

        get_unprocessed_topic_articles(limit=10)
        assert col.find.call_args[1]["limit"] == 10


# --- update_article_topics ---


def test_update_article_topics_empty():
    from database.repositories import update_article_topics

    with patch("database.repositories.get_clean_collection") as mock_get:
        col = MagicMock()
        mock_get.return_value = col

        assert update_article_topics([]) == 0
        col.bulk_write.assert_not_called()


def test_update_article_topics_builds_payload():
    from database.repositories import update_article_topics

    with patch("database.repositories.get_clean_collection") as mock_get:
        col = MagicMock()
        bulk_result = MagicMock()
        bulk_result.modified_count = 1
        col.bulk_write.return_value = bulk_result
        mock_get.return_value = col

        updates = [{
            "url": "http://a.com",
            "topic_label": "tech",
            "topic_score": 0.9,
            "keywords": ["ai"],
        }]
        update_article_topics(updates)
        ops = col.bulk_write.call_args[0][0]
        set_payload = ops[0]._doc["$set"]
        assert set_payload["topic_label"] == "tech"
        assert set_payload["topic_score"] == 0.9
        assert set_payload["keywords"] == ["ai"]


def test_update_article_topics_returns_modified_count():
    from database.repositories import update_article_topics

    with patch("database.repositories.get_clean_collection") as mock_get:
        col = MagicMock()
        bulk_result = MagicMock()
        bulk_result.modified_count = 5
        col.bulk_write.return_value = bulk_result
        mock_get.return_value = col

        result = update_article_topics([{
            "url": "u", "topic_label": "t", "topic_score": 0.1, "keywords": [],
        }])
        assert result == 5


# --- insert_model_run ---


def test_insert_model_run_returns_id_str():
    from database.repositories import insert_model_run

    with patch("database.repositories.get_models_db") as mock_get:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_result = MagicMock()
        mock_result.inserted_id = "abc123"
        mock_col.insert_one.return_value = mock_result
        mock_get.return_value = mock_db

        result = insert_model_run({"model_version": "v1"})
        assert result == "abc123"


# --- get_latest_model_run ---


def test_get_latest_model_run_none():
    from database.repositories import get_latest_model_run

    with patch("database.repositories.get_models_db") as mock_get:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.find_one.return_value = None
        mock_get.return_value = mock_db

        assert get_latest_model_run() is None


def test_get_latest_model_run_returns_doc():
    from database.repositories import get_latest_model_run

    doc = {"model_version": "v1", "created_at": "2026-01-01"}
    with patch("database.repositories.get_models_db") as mock_get:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.find_one.return_value = doc
        mock_get.return_value = mock_db

        result = get_latest_model_run()
        assert result == doc
        mock_col.find_one.assert_called_once_with({}, sort=[("created_at", -1)])

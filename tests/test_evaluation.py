"""
Unit tests for evaluation/sample_loader.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


# ===================================================================
# load_ner_sample
# ===================================================================


def test_load_ner_sample_returns_projected_docs():
    from evaluation.sample_loader import load_ner_sample

    with patch("evaluation.sample_loader.get_ner_db") as mock_get:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.aggregate.return_value = [
            {"url": "http://a.com", "body": "text", "entities": []},
        ]
        mock_get.return_value = mock_db

        docs = load_ner_sample()
        assert len(docs) == 1
        assert docs[0]["url"] == "http://a.com"


def test_load_ner_sample_default_n():
    from evaluation.sample_loader import load_ner_sample

    with patch("evaluation.sample_loader.get_ner_db") as mock_get:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.aggregate.return_value = []
        mock_get.return_value = mock_db

        load_ner_sample()
        pipeline = mock_col.aggregate.call_args[0][0]
        assert pipeline[0]["$sample"]["size"] == 500


def test_load_ner_sample_custom_n():
    from evaluation.sample_loader import load_ner_sample

    with patch("evaluation.sample_loader.get_ner_db") as mock_get:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.aggregate.return_value = []
        mock_get.return_value = mock_db

        load_ner_sample(n=10)
        pipeline = mock_col.aggregate.call_args[0][0]
        assert pipeline[0]["$sample"]["size"] == 10


def test_load_ner_sample_empty_collection():
    from evaluation.sample_loader import load_ner_sample

    with patch("evaluation.sample_loader.get_ner_db") as mock_get:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.aggregate.return_value = []
        mock_get.return_value = mock_db

        assert load_ner_sample() == []


def test_load_ner_sample_projection():
    from evaluation.sample_loader import load_ner_sample

    with patch("evaluation.sample_loader.get_ner_db") as mock_get:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.aggregate.return_value = []
        mock_get.return_value = mock_db

        load_ner_sample()
        pipeline = mock_col.aggregate.call_args[0][0]
        proj = pipeline[1]["$project"]
        assert proj == {"_id": 0, "url": 1, "body": 1, "entities": 1}


# ===================================================================
# load_latest_run_metrics
# ===================================================================


def test_load_latest_run_metrics_none():
    from evaluation.sample_loader import load_latest_run_metrics

    with patch("evaluation.sample_loader.get_models_db") as mock_get:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.find_one.return_value = None
        mock_get.return_value = mock_db

        assert load_latest_run_metrics() is None


def test_load_latest_run_metrics_returns_doc():
    from evaluation.sample_loader import load_latest_run_metrics

    doc = {"model_version": "v1", "metrics": {"f1": 0.9}, "created_at": "2026-01-01"}
    with patch("evaluation.sample_loader.get_models_db") as mock_get:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.find_one.return_value = doc
        mock_get.return_value = mock_db

        result = load_latest_run_metrics()
        assert result == doc


def test_load_latest_run_metrics_sorts_by_created_at():
    from evaluation.sample_loader import load_latest_run_metrics

    with patch("evaluation.sample_loader.get_models_db") as mock_get:
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_col)
        mock_col.find_one.return_value = {"x": 1}
        mock_get.return_value = mock_db

        load_latest_run_metrics()
        mock_col.find_one.assert_called_once_with({}, sort=[("created_at", -1)])

"""Tests for jobs layer: __init__, scrape_job, clean_job, classify_job, evaluate_job."""
from __future__ import annotations

import sys
import threading
from datetime import date
from unittest.mock import MagicMock, patch

import pytest


class _FakePbar:
    """Minimal tqdm-like wrapper so pbar.set_postfix() works."""
    def __init__(self, iterable):
        self._it = iterable
    def __iter__(self):
        return iter(self._it)
    def set_postfix(self, **kw):
        pass


def _fake_make_pbar(it, **kw):
    return _FakePbar(it)


# ── Stub heavy external deps so job modules can be imported without them ─────
for _m in [
    "schedule", "feedparser", "newspaper", "newspaper.article",
    "pymongo", "pymongo.collection", "pymongo.database", "pymongo.errors",
    "pymongo.operations", "pymongo.mongo_client",
    "motor", "motor.motor_asyncio",
    "bs4", "requests", "spacy", "spacy.tokens", "transformers", "torch",
    "prometheus_client",
    "nltk", "nltk.corpus", "nltk.tokenize", "nltk.stem",
]:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

import jobs
import jobs.scrape_job
import jobs.clean_job
import jobs.classify_job
import jobs.evaluate_job


# ── jobs/__init__.py — run_job dispatcher ────────────────────────────────────

class TestRunJobDispatcher:

    @patch("jobs.scrape_job.run", return_value={"status": "success"})
    def test_scrape_routes(self, mock_run):
        result = jobs.run_job("scrape")
        mock_run.assert_called_once()
        assert result["status"] == "success"

    @patch("jobs.clean_job.run", return_value={"status": "success"})
    def test_clean_routes(self, mock_run):
        result = jobs.run_job("clean")
        mock_run.assert_called_once()
        assert result["status"] == "success"

    @patch("jobs.classify_job.run", return_value={"status": "success"})
    def test_classify_routes(self, mock_run):
        result = jobs.run_job("classify")
        mock_run.assert_called_once()
        assert result["status"] == "success"

    @patch("jobs.classify_job.run", return_value={"status": "success"})
    def test_ner_alias_routes_to_classify(self, mock_run):
        result = jobs.run_job("ner")
        mock_run.assert_called_once()
        assert result["status"] == "success"

    @patch("jobs.evaluate_job.run", return_value={"status": "success"})
    def test_evaluate_routes(self, mock_run):
        result = jobs.run_job("evaluate")
        mock_run.assert_called_once()
        assert result["status"] == "success"

    @patch("jobs.analyze_job.run", return_value={"status": "success"})
    def test_analyze_routes(self, mock_run):
        result = jobs.run_job("analyze")
        mock_run.assert_called_once()
        assert result["status"] == "success"

    @patch("jobs.scrape_job.run", return_value={"status": "success"})
    def test_case_and_whitespace_normalisation(self, mock_run):
        result = jobs.run_job("  SCRAPE  ")
        mock_run.assert_called_once()
        assert result["status"] == "success"

    def test_unknown_job_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown job"):
            jobs.run_job("nonexistent")

    @patch("jobs.scrape_job.run", return_value={"status": "success"})
    def test_log_fn_defaults_to_noop(self, mock_run):
        jobs.run_job("scrape")
        mock_run.assert_called_once()

    @patch("jobs.scrape_job.run", return_value={"status": "success"})
    def test_stop_event_defaults_to_new_event(self, mock_run):
        jobs.run_job("scrape")
        call_kwargs = mock_run.call_args[1]
        assert isinstance(call_kwargs["stop_event"], threading.Event)

    @patch("jobs.scrape_job.run", return_value={"status": "success"})
    def test_for_date_forwarded(self, mock_run):
        d = date(2025, 1, 15)
        jobs.run_job("scrape", for_date=d)
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["for_date"] == d


# ── scrape_job.run() ─────────────────────────────────────────────────────────

@patch("scraper.scheduler.run_scrape_job")
@patch("database.init_db.init_databases")
def test_scrape_job_happy_path(mock_init, mock_scrape):
    result = jobs.scrape_job.run(for_date=date(2025, 1, 1))
    assert result["status"] == "success"
    assert result["duration_seconds"] >= 0
    mock_init.assert_called_once()
    mock_scrape.assert_called_once()


@patch("scraper.scheduler.run_scrape_job")
@patch("database.init_db.init_databases")
def test_scrape_job_dry_run(mock_init, mock_scrape):
    result = jobs.scrape_job.run(dry_run=True)
    assert result["status"] == "success"
    mock_scrape.assert_not_called()


@patch("scraper.scheduler.run_scrape_job", side_effect=RuntimeError("boom"))
@patch("database.init_db.init_databases")
def test_scrape_job_run_scrape_raises(mock_init, mock_scrape):
    result = jobs.scrape_job.run()
    assert result["status"] == "failed"
    assert "boom" in result["errors"][0]


@patch("database.init_db.init_databases", side_effect=RuntimeError("db fail"))
def test_scrape_job_init_databases_raises(mock_init):
    result = jobs.scrape_job.run()
    assert result["status"] == "failed"
    assert "db fail" in result["errors"][0]


@patch("scraper.scheduler.run_scrape_job")
@patch("database.init_db.init_databases")
def test_scrape_job_log_fn_called(mock_init, mock_scrape):
    log = MagicMock()
    jobs.scrape_job.run(log_fn=log)
    assert log.call_count >= 1


@patch("scraper.scheduler.run_scrape_job")
@patch("database.init_db.init_databases")
def test_scrape_job_for_date_forwarded(mock_init, mock_scrape):
    d = date(2025, 6, 1)
    jobs.scrape_job.run(for_date=d)
    call_kwargs = mock_scrape.call_args[1]
    assert call_kwargs["for_date"] == d


@patch("scraper.scheduler.run_scrape_job")
@patch("database.init_db.init_databases")
def test_scrape_job_stop_event_propagated(mock_init, mock_scrape):
    ev = threading.Event()
    jobs.scrape_job.run(stop_event=ev)
    call_kwargs = mock_scrape.call_args[1]
    assert call_kwargs["stop_event"] is ev


# ── clean_job.run() ──────────────────────────────────────────────────────────

@patch("cleaning.cleaner.run_cleaning_pipeline", return_value={"promoted": 5, "discarded": 2})
@patch("database.init_db.init_databases")
def test_clean_job_happy_path(mock_init, mock_pipe):
    result = jobs.clean_job.run()
    assert result["status"] == "success"
    assert result["promoted"] == 5
    assert result["discarded"] == 2


@patch("database.init_db.init_databases")
def test_clean_job_dry_run(mock_init):
    result = jobs.clean_job.run(dry_run=True)
    assert result["status"] == "success"



@patch("cleaning.cleaner.run_cleaning_pipeline", side_effect=RuntimeError("pipe fail"))
@patch("database.init_db.init_databases")
def test_clean_job_pipeline_raises(mock_init, mock_pipe):
    result = jobs.clean_job.run()
    assert result["status"] == "failed"
    assert "pipe fail" in result["errors"][0]


@patch("database.init_db.init_databases", side_effect=RuntimeError("db fail"))
def test_clean_job_init_databases_raises(mock_init):
    result = jobs.clean_job.run()
    assert result["status"] == "failed"
    assert "db fail" in result["errors"][0]


@patch("cleaning.cleaner.run_cleaning_pipeline", return_value={})
@patch("database.init_db.init_databases")
def test_clean_job_empty_pipeline_defaults(mock_init, mock_pipe):
    result = jobs.clean_job.run()
    assert result["promoted"] == 0
    assert result["discarded"] == 0


# ── classify_job.run() ───────────────────────────────────────────────────────

def _make_article(i: int) -> dict:
    return {"_id": f"id{i}", "url": f"http://example.com/{i}", "body": f"body {i}", "entities": []}


# Patch _print_collection_sizes to avoid DB calls in all classify tests
_classify_patches = [
    patch.object(jobs.classify_job, "_print_collection_sizes"),
    patch("utils.progress.make_pbar_simple", side_effect=_fake_make_pbar),
]


@patch("database.repositories.get_ner_collection")
@patch("database.repositories.get_clean_collection")
@patch("database.repositories.insert_ner_articles", return_value=0)
@patch("database.repositories.get_unprocessed_clean_articles", return_value=[])
@patch("features.ner_extractor.get_device_label", return_value="cpu")
@patch("database.init_db.init_databases")
@patch("utils.progress.make_pbar_simple", side_effect=_fake_make_pbar)
@patch.object(jobs.classify_job, "_print_collection_sizes")
def test_classify_no_articles(mock_sizes, mock_pbar, mock_init, mock_device,
                               mock_get, mock_insert,
                               mock_clean_col, mock_ner_col):
    result = jobs.classify_job.run()
    assert result["status"] == "success"
    assert result["classified_count"] == 0
    mock_insert.assert_not_called()


@patch.object(jobs.classify_job, "_print_comparison")
@patch.object(jobs.classify_job, "_print_collection_sizes")
@patch("preprocessing.ner_text_builder.build_ner_preprocessed_text", return_value="preprocessed")
@patch("features.ner_extractor.batch_extract", side_effect=lambda chunk: chunk)
@patch("features.ner_extractor.get_device_label", return_value="cpu")
@patch("database.repositories.get_ner_collection")
@patch("database.repositories.get_clean_collection")
@patch("database.repositories.insert_ner_articles", return_value=2)
@patch("database.repositories.get_unprocessed_clean_articles", return_value=[_make_article(0), _make_article(1)])
@patch("database.init_db.init_databases")
@patch("utils.progress.make_pbar_simple", side_effect=_fake_make_pbar)
def test_classify_happy_path_small_batch(mock_pbar, mock_init, mock_get, mock_insert,
                                          mock_clean_col, mock_ner_col,
                                          mock_device, mock_extract, mock_build,
                                          mock_sizes, mock_comparison):
    mock_clean_col.return_value.find_one.return_value = None
    mock_ner_col.return_value.find_one.return_value = None
    result = jobs.classify_job.run()
    assert result["status"] == "success"
    assert result["classified_count"] == 2
    mock_insert.assert_called_once()
    inserted_articles = mock_insert.call_args[0][0]
    for art in inserted_articles:
        assert "ner_preprocessed_text" in art


@patch.object(jobs.classify_job, "_print_collection_sizes")
@patch("preprocessing.ner_text_builder.build_ner_preprocessed_text", return_value="preprocessed")
@patch("features.ner_extractor.batch_extract", side_effect=lambda chunk: chunk)
@patch("features.ner_extractor.get_device_label", return_value="cpu")
@patch("database.repositories.get_ner_collection")
@patch("database.repositories.get_clean_collection")
@patch("database.repositories.insert_ner_articles", return_value=0)
@patch("database.repositories.get_unprocessed_clean_articles", return_value=[_make_article(0), _make_article(1)])
@patch("database.init_db.init_databases")
@patch("utils.progress.make_pbar_simple", side_effect=_fake_make_pbar)
def test_classify_dry_run(mock_pbar, mock_init, mock_get, mock_insert,
                           mock_clean_col, mock_ner_col,
                           mock_device, mock_extract, mock_build, mock_sizes):
    mock_clean_col.return_value.find_one.return_value = None
    mock_ner_col.return_value.find_one.return_value = None
    result = jobs.classify_job.run(dry_run=True)
    assert result["classified_count"] == 2
    mock_insert.assert_not_called()


@patch.object(jobs.classify_job, "_print_collection_sizes")
@patch("preprocessing.ner_text_builder.build_ner_preprocessed_text", return_value="preprocessed")
@patch("features.ner_extractor.batch_extract", side_effect=RuntimeError("ner fail"))
@patch("features.ner_extractor.get_device_label", return_value="cpu")
@patch("database.repositories.get_ner_collection")
@patch("database.repositories.get_clean_collection")
@patch("database.repositories.insert_ner_articles", return_value=0)
@patch("database.repositories.get_unprocessed_clean_articles", return_value=[_make_article(0)])
@patch("database.init_db.init_databases")
@patch("utils.progress.make_pbar_simple", side_effect=_fake_make_pbar)
def test_classify_batch_extract_raises(mock_pbar, mock_init, mock_get, mock_insert,
                                        mock_clean_col, mock_ner_col,
                                        mock_device, mock_extract, mock_build, mock_sizes):
    result = jobs.classify_job.run()
    assert result["status"] == "failed"
    assert "ner fail" in result["errors"][0]


# ── evaluate_job.run() ───────────────────────────────────────────────────────

_SEP_RESULT = {
    "improvement_pct": 5.0,
    "verdict": "NER_BETTER",
    "sample_size": 10,
    "mean_sim_clean": 0.4,
    "mean_sim_ner": 0.35,
}

_CONLL_RESULT = {
    "precision": 0.9,
    "recall": 0.85,
    "f1": 0.87,
    "sample_size": 5,
    "benchmark": "conll2003",
    "per_entity": {"PER": {"precision": 0.9, "recall": 0.85, "f1": 0.87, "support": 5}},
}


@patch("evaluation.separability_eval.compute_separability", return_value=_SEP_RESULT)
@patch("database.init_db.init_databases")
def test_evaluate_no_articles(mock_init, mock_sep):
    result = jobs.evaluate_job.run(dry_run=True)
    assert result["status"] == "success"
    assert result["separability"] is not None


@patch("database.repositories.insert_model_run", return_value="abc123")
@patch("evaluation.conll_eval.run_conll_eval", return_value=_CONLL_RESULT)
@patch("evaluation.separability_eval.compute_separability", return_value=_SEP_RESULT)
@patch("database.init_db.init_databases")
def test_evaluate_happy_path(mock_init, mock_sep, mock_conll, mock_insert):
    result = jobs.evaluate_job.run()
    assert result["status"] == "success"
    assert result["separability"]["improvement_pct"] == 5.0
    assert result["conll_metrics"]["f1"] == 0.87
    mock_insert.assert_called_once()


@patch("evaluation.conll_eval.run_conll_eval", return_value=_CONLL_RESULT)
@patch("evaluation.separability_eval.compute_separability", return_value=_SEP_RESULT)
@patch("database.init_db.init_databases")
def test_evaluate_dry_run(mock_init, mock_sep, mock_conll):
    result = jobs.evaluate_job.run(dry_run=True)
    assert result["status"] == "success"
    assert result["separability"]["verdict"] == "NER_BETTER"


@patch("evaluation.separability_eval.compute_separability", side_effect=RuntimeError("sep fail"))
@patch("database.init_db.init_databases")
def test_evaluate_compute_raises(mock_init, mock_sep):
    result = jobs.evaluate_job.run()
    assert result["status"] == "failed"
    assert "sep fail" in result["errors"][0]


@patch("evaluation.conll_eval.run_conll_eval", return_value=_CONLL_RESULT)
@patch("evaluation.separability_eval.compute_separability", return_value=_SEP_RESULT)
@patch("database.init_db.init_databases")
def test_evaluate_metrics_has_required_keys(mock_init, mock_sep, mock_conll):
    result = jobs.evaluate_job.run(dry_run=True)
    for key in ("separability", "conll_metrics", "status", "errors", "duration_seconds"):
        assert key in result
    assert result["separability"]["sample_size"] == 10

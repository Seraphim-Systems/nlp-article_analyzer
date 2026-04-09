"""Tests for scraper.scheduler.run_scrape_job."""
from __future__ import annotations

import sys
import threading
from datetime import date
from unittest.mock import MagicMock, patch

# ── Stub heavy external deps so scheduler can be imported ────────────────────
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

import scraper.scheduler


def _make_scraper(name: str, articles: list[dict] | None = None, raises: bool = False):
    s = MagicMock()
    s.name = name
    if raises:
        s.scrape_today.side_effect = RuntimeError(f"{name} exploded")
    else:
        s.scrape_today.return_value = articles or []
    return s


@patch.object(scraper.scheduler, "insert_raw_articles", return_value=6)
@patch.object(scraper.scheduler, "build_rss_scrapers")
def test_happy_path_two_scrapers(mock_build, mock_insert):
    arts_a = [{"url": f"http://a/{i}"} for i in range(3)]
    arts_b = [{"url": f"http://b/{i}"} for i in range(3)]
    mock_build.return_value = [_make_scraper("feed-a", arts_a), _make_scraper("feed-b", arts_b)]
    scraper.scheduler.run_scrape_job(run_cleaning=False)
    mock_insert.assert_called_once()
    inserted = mock_insert.call_args[0][0]
    assert len(inserted) == 6


@patch.object(scraper.scheduler, "insert_raw_articles", return_value=3)
@patch.object(scraper.scheduler, "build_rss_scrapers")
def test_one_scraper_raises_other_continues(mock_build, mock_insert):
    good = _make_scraper("good", [{"url": "http://good/1"}] * 3)
    bad = _make_scraper("bad", raises=True)
    mock_build.return_value = [bad, good]
    scraper.scheduler.run_scrape_job(run_cleaning=False)
    mock_insert.assert_called_once()
    inserted = mock_insert.call_args[0][0]
    assert len(inserted) == 3


@patch.object(scraper.scheduler, "insert_raw_articles", return_value=0)
@patch.object(scraper.scheduler, "build_rss_scrapers")
def test_stop_event_before_loop(mock_build, mock_insert):
    s = _make_scraper("feed", [{"url": "http://x"}])
    mock_build.return_value = [s]
    ev = threading.Event()
    ev.set()
    scraper.scheduler.run_scrape_job(stop_event=ev, run_cleaning=False)
    s.scrape_today.assert_not_called()
    mock_insert.assert_called_once_with([])


@patch.object(scraper.scheduler, "insert_raw_articles", return_value=1)
@patch.object(scraper.scheduler, "build_rss_scrapers")
def test_stop_event_mid_loop(mock_build, mock_insert):
    s1 = _make_scraper("first", [{"url": "http://1"}])
    s2 = _make_scraper("second", [{"url": "http://2"}])
    ev = threading.Event()

    def scrape_and_stop(target):
        ev.set()
        return [{"url": "http://1"}]

    s1.scrape_today.side_effect = scrape_and_stop
    mock_build.return_value = [s1, s2]
    scraper.scheduler.run_scrape_job(stop_event=ev, run_cleaning=False)
    s2.scrape_today.assert_not_called()
    inserted = mock_insert.call_args[0][0]
    assert len(inserted) == 1


@patch("cleaning.cleaner.run_cleaning_pipeline", return_value={"promoted": 1, "discarded": 0})
@patch.object(scraper.scheduler, "insert_raw_articles", return_value=0)
@patch.object(scraper.scheduler, "build_rss_scrapers", return_value=[])
def test_run_cleaning_true_explicit(mock_build, mock_insert, mock_clean):
    scraper.scheduler.run_scrape_job(run_cleaning=True)
    mock_clean.assert_called_once()


@patch.object(scraper.scheduler, "insert_raw_articles", return_value=0)
@patch.object(scraper.scheduler, "build_rss_scrapers", return_value=[])
def test_run_cleaning_false_explicit(mock_build, mock_insert):
    scraper.scheduler.run_scrape_job(run_cleaning=False)


@patch("cleaning.cleaner.run_cleaning_pipeline", return_value={"promoted": 0, "discarded": 0})
@patch.object(scraper.scheduler, "insert_raw_articles", return_value=0)
@patch.object(scraper.scheduler, "build_rss_scrapers", return_value=[])
@patch.object(scraper.scheduler, "settings")
def test_run_cleaning_none_with_setting_true(mock_settings, mock_build, mock_insert, mock_clean):
    mock_settings.RUN_CLEAN_AFTER_SCRAPE = True
    scraper.scheduler.run_scrape_job(run_cleaning=None)
    mock_clean.assert_called_once()


@patch.object(scraper.scheduler, "insert_raw_articles", return_value=0)
@patch.object(scraper.scheduler, "build_rss_scrapers", return_value=[])
@patch.object(scraper.scheduler, "settings")
def test_run_cleaning_none_with_setting_false(mock_settings, mock_build, mock_insert):
    mock_settings.RUN_CLEAN_AFTER_SCRAPE = False
    scraper.scheduler.run_scrape_job(run_cleaning=None)


@patch.object(scraper.scheduler, "insert_raw_articles", return_value=0)
@patch.object(scraper.scheduler, "build_rss_scrapers", return_value=[])
def test_log_fn_called(mock_build, mock_insert):
    log = MagicMock()
    scraper.scheduler.run_scrape_job(log_fn=log, run_cleaning=False)
    assert log.call_count >= 3


@patch.object(scraper.scheduler, "insert_raw_articles", return_value=0)
@patch.object(scraper.scheduler, "build_rss_scrapers")
def test_for_date_forwarded_to_scrapers(mock_build, mock_insert):
    s = _make_scraper("feed", [])
    mock_build.return_value = [s]
    d = date(2025, 3, 15)
    scraper.scheduler.run_scrape_job(for_date=d, run_cleaning=False)
    s.scrape_today.assert_called_once_with(d)

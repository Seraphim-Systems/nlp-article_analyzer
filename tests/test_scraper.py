"""
Unit tests for the RSS scraper helpers (no network calls).
"""

import pytest
from unittest.mock import MagicMock, patch
from scraper.scrapers.rss_scraper import RssScraper


FEED_CONFIG = {"name": "Test Feed", "url": "https://example.com/rss", "lang": "en"}


def test_scraper_name_set_from_config():
    scraper = RssScraper(FEED_CONFIG)
    assert scraper.name == "Test Feed"


def test_scraper_default_lang():
    scraper = RssScraper(FEED_CONFIG)
    assert scraper.default_lang == "en"


def test_parse_article_returns_none_on_empty_body():
    scraper = RssScraper(FEED_CONFIG)

    mock_art = MagicMock()
    mock_art.title = ""
    mock_art.text = ""

    with patch("scraper.scrapers.rss_scraper.NewspaperArticle", return_value=mock_art):
        result = scraper.parse_article("https://example.com/article")

    assert result is None


def test_parse_article_returns_dict_on_success():
    scraper = RssScraper(FEED_CONFIG)

    mock_art = MagicMock()
    mock_art.title = "Test Title"
    mock_art.text = "Full article body here."
    mock_art.publish_date = None
    mock_art.meta_lang = "en"
    mock_art.movies = []
    mock_art.summary = "A summary."

    with patch("scraper.scrapers.rss_scraper.NewspaperArticle", return_value=mock_art):
        result = scraper.parse_article("https://example.com/article")

    assert result is not None
    assert result["title"] == "Test Title"
    assert result["body"] == "Full article body here."
    assert result["feed"] == "Test Feed"

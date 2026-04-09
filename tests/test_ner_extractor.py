"""
Unit tests for features.ner_extractor.

The HuggingFace pipeline is mocked so these tests run without a GPU or model weights.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from features.ner_extractor import batch_extract, extract_entities


@pytest.fixture(autouse=True)
def reset_pipeline():
    """Reset the singleton pipeline between tests."""
    import features.ner_extractor as mod
    original = mod._pipeline
    mod._pipeline = None
    yield
    mod._pipeline = original


def _make_pipeline_mock(entities):
    """Return a mock that behaves like the HuggingFace NER pipeline callable."""
    mock = MagicMock(return_value=entities)
    return mock


# ---------------------------------------------------------------------------
# extract_entities
# ---------------------------------------------------------------------------

def test_extract_entities_empty_string():
    assert extract_entities("") == []


def test_extract_entities_whitespace_only():
    assert extract_entities("   ") == []


def test_extract_entities_returns_mapped_fields():
    raw = [
        {"word": "Apple", "entity_group": "ORG", "start": 0, "end": 5, "score": 0.99},
    ]
    with patch("features.ner_extractor._get_pipeline", return_value=_make_pipeline_mock(raw)):
        result = extract_entities("Apple is a company.")

    assert result == [{"text": "Apple", "label": "ORG", "start": 0, "end": 5}]


def test_extract_entities_multiple_entities():
    raw = [
        {"word": "Google", "entity_group": "ORG", "start": 0, "end": 6, "score": 0.99},
        {"word": "Mountain View", "entity_group": "LOC", "start": 10, "end": 23, "score": 0.97},
    ]
    with patch("features.ner_extractor._get_pipeline", return_value=_make_pipeline_mock(raw)):
        result = extract_entities("Google in Mountain View.")

    assert len(result) == 2
    assert result[0]["label"] == "ORG"
    assert result[1]["label"] == "LOC"


def test_extract_entities_long_text_uses_chunking():
    """Text exceeding _CHUNK_WORDS is split into overlapping chunks, not truncated."""
    from features.ner_extractor import _CHUNK_WORDS
    long_text = " ".join(["word"] * (_CHUNK_WORDS + 50))
    captured = []

    def mock_pipeline(text):
        captured.append(text)
        return []

    with patch("features.ner_extractor._get_pipeline", return_value=mock_pipeline):
        extract_entities(long_text)

    # Multiple chunks should have been processed
    assert len(captured) > 1
    # No single chunk exceeds _CHUNK_WORDS
    for chunk in captured:
        assert len(chunk.split()) <= _CHUNK_WORDS


def test_extract_entities_short_text_single_call():
    """Text under _CHUNK_WORDS is passed to the pipeline as-is in one call."""
    from features.ner_extractor import _CHUNK_WORDS
    text = " ".join(["word"] * (_CHUNK_WORDS - 10))
    captured = []

    def mock_pipeline(t):
        captured.append(t)
        return []

    with patch("features.ner_extractor._get_pipeline", return_value=mock_pipeline):
        extract_entities(text)

    assert len(captured) == 1
    assert captured[0] == text


# ---------------------------------------------------------------------------
# batch_extract
# ---------------------------------------------------------------------------

def test_batch_extract_empty_list():
    assert batch_extract([]) == []


def test_batch_extract_adds_entities_key():
    articles = [{"url": "http://a.com", "body": "Tim Cook leads Apple."}]
    raw = [{"word": "Tim Cook", "entity_group": "PER", "start": 0, "end": 8, "score": 0.98}]

    with patch("features.ner_extractor._get_pipeline", return_value=_make_pipeline_mock(raw)):
        result = batch_extract(articles)

    assert "entities" in result[0]
    assert result[0]["entities"][0]["text"] == "Tim Cook"


def test_batch_extract_preserves_original_fields():
    articles = [{"url": "http://b.com", "title": "Test", "body": "Some text."}]

    with patch("features.ner_extractor._get_pipeline", return_value=_make_pipeline_mock([])):
        result = batch_extract(articles)

    assert result[0]["url"] == "http://b.com"
    assert result[0]["title"] == "Test"


def test_batch_extract_missing_body_yields_empty_entities():
    articles = [{"url": "http://c.com", "title": "No body"}]

    with patch("features.ner_extractor._get_pipeline", return_value=_make_pipeline_mock([])):
        result = batch_extract(articles)

    assert result[0]["entities"] == []


def test_batch_extract_multiple_articles():
    articles = [
        {"url": "http://d.com", "body": "Article one."},
        {"url": "http://e.com", "body": "Article two."},
    ]

    with patch("features.ner_extractor._get_pipeline", return_value=_make_pipeline_mock([])):
        result = batch_extract(articles)

    assert len(result) == 2
    assert all("entities" in a for a in result)


# ---------------------------------------------------------------------------
# _snap_to_word — word-boundary alignment
# ---------------------------------------------------------------------------

def test_snap_to_word_already_at_boundaries():
    from features.ner_extractor import _snap_to_word
    text = "Hello World"
    s, e = _snap_to_word(text, 0, 5)   # "Hello"
    assert text[s:e] == "Hello"


def test_snap_to_word_mid_word_end():
    """Entity end pointing mid-word should be extended to end of word."""
    from features.ner_extractor import _snap_to_word
    text = "Barack Obama visited Paris"
    # Pipeline returned end=4 (mid "Obama" → "Obam")
    s, e = _snap_to_word(text, 7, 11)  # "Obam" → should snap to "Obama"
    assert text[s:e] == "Obama"


def test_snap_to_word_mid_word_start():
    """Entity start pointing mid-word should be pulled back to word start."""
    from features.ner_extractor import _snap_to_word
    text = "Sanders spoke today"
    # start at 2 (mid "Sanders" → "nders")
    s, e = _snap_to_word(text, 2, 7)
    assert text[s:e] == "Sanders"


def test_snap_to_word_at_end_of_string():
    from features.ner_extractor import _snap_to_word
    text = "visited London"
    s, e = _snap_to_word(text, 8, 12)  # "Lond" → should snap to "London"
    assert text[s:e] == "London"


def test_snap_to_word_full_word_no_change():
    from features.ner_extractor import _snap_to_word
    text = "New York is great"
    s, e = _snap_to_word(text, 0, 3)   # "New" — already word-aligned
    assert text[s:e] == "New"


# ---------------------------------------------------------------------------
# Mid-word entity regression — pipeline returns truncated offsets
# ---------------------------------------------------------------------------

def test_extract_entities_snaps_mid_word_end_to_full_word():
    """Regression: pipeline returning end mid-word should produce full-word entity."""
    text = "Barack Obama visited Paris"
    # Simulate pipeline returning "Obam" (end=11 instead of 12)
    raw = [{"word": "Obam", "entity_group": "PER", "start": 7, "end": 11, "score": 0.98}]
    with patch("features.ner_extractor._get_pipeline", return_value=_make_pipeline_mock(raw)):
        result = extract_entities(text)

    assert result[0]["text"] == "Obama"
    assert result[0]["end"] == 12


def test_extract_entities_snaps_mid_word_start_to_full_word():
    """Regression: pipeline returning start mid-word should pull back to word start."""
    text = "Senator Sanders spoke"
    # "Sanders" = positions 8-15; simulate start at 10 (mid-word), end at 15 (word boundary)
    raw = [{"word": "nders", "entity_group": "PER", "start": 10, "end": 15, "score": 0.97}]
    with patch("features.ner_extractor._get_pipeline", return_value=_make_pipeline_mock(raw)):
        result = extract_entities(text)

    assert result[0]["text"] == "Sanders"
    assert result[0]["start"] == 8


def test_extract_entities_text_field_matches_snapped_span():
    """Entity text must always equal body[start:end] after snapping."""
    text = "Netanyahu leads Israel"
    # Simulate "Netanyah" (missing last char 'u')
    raw = [{"word": "Netanyah", "entity_group": "PER", "start": 0, "end": 8, "score": 0.95}]
    with patch("features.ner_extractor._get_pipeline", return_value=_make_pipeline_mock(raw)):
        result = extract_entities(text)

    ent = result[0]
    normalized = " ".join(text.split())
    assert ent["text"] == normalized[ent["start"]:ent["end"]]


def test_batch_extract_entity_text_always_matches_body_span():
    """Regression: entity text must always be a complete word from the body."""
    body = "Obama visited New York and met Netanyahu"
    # Simulate truncated entities for Obama ("Obam") and Netanyahu ("Netanyah")
    raw = [
        {"word": "Obam",     "entity_group": "PER", "start": 0,  "end": 4,  "score": 0.98},
        {"word": "Netanyah", "entity_group": "PER", "start": 31, "end": 39, "score": 0.96},
    ]
    articles = [{"url": "http://x.com", "body": body}]
    with patch("features.ner_extractor._get_pipeline", return_value=_make_pipeline_mock(raw)):
        result = batch_extract(articles)

    normalized = " ".join(body.split())
    for ent in result[0]["entities"]:
        assert ent["text"] == normalized[ent["start"]:ent["end"]], (
            f"Entity text {ent['text']!r} doesn't match span "
            f"[{ent['start']}:{ent['end']}] = {normalized[ent['start']:ent['end']]!r}"
        )

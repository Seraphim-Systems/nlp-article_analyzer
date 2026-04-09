"""
Tests for preprocessing.ner_text_builder.build_ner_preprocessed_text.

Covers the core offset-alignment contract: entity offsets come from NER run on
normalized text (" ".join(body.split())), so the builder must apply them to the
same normalized form — not the raw body with its original newlines/spaces.

Spacy and nltk are stubbed at sys.modules level so these tests run locally
without the full ML stack.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest

# ── stub heavy ML deps before any project import triggers them ────────────────
_spacy_stub = types.ModuleType("spacy")
_spacy_stub.load = MagicMock(return_value=MagicMock())  # type: ignore[attr-defined]
sys.modules.setdefault("spacy", _spacy_stub)

_nltk_stub        = types.ModuleType("nltk")
_nltk_corpus_stub = types.ModuleType("nltk.corpus")
_sw_mock          = MagicMock()
_sw_mock.words    = MagicMock(return_value=set())
_nltk_corpus_stub.stopwords = _sw_mock  # type: ignore[attr-defined]
sys.modules.setdefault("nltk",        _nltk_stub)
sys.modules.setdefault("nltk.corpus", _nltk_corpus_stub)
# ─────────────────────────────────────────────────────────────────────────────

from preprocessing.ner_text_builder import build_ner_preprocessed_text  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────

def _ent(label: str, text: str, start: int, end: int) -> dict:
    return {"label": label, "text": text, "start": start, "end": end}


def _mock_processor(passthrough: bool = True):
    proc = MagicMock()
    proc.clean_text.side_effect = lambda t: t.lower() if not passthrough else t
    return proc


# ── empty / degenerate inputs ─────────────────────────────────────────────────

def test_empty_body_returns_empty():
    assert build_ner_preprocessed_text("", []) == ""


def test_none_body_returns_empty():
    assert build_ner_preprocessed_text(None, []) == ""  # type: ignore[arg-type]


def test_no_entities_returns_preprocessed_body():
    body = "Nothing special here."
    with patch("preprocessing.ner_text_builder._preprocess_preserving_ner", side_effect=lambda t: t):
        result = build_ner_preprocessed_text(body, [])
    assert result == "Nothing special here."


# ── offset alignment: raw body with newlines ──────────────────────────────────

def test_newline_body_offsets_land_on_word_boundaries():
    """
    Body has \n\n between sentences.  NER offsets are computed on the normalized
    form ("Iran is a country. The US attacked.").  Tags must wrap whole words.
    """
    raw_body = "Iran is a country.\n\nThe US attacked."
    normalized = " ".join(raw_body.split())
    # "Iran is a country.  The US attacked."
    #  0123456789...
    # In normalized: "Iran" → 0:4,  "US" → 24:26
    iran_start = normalized.index("Iran")
    iran_end   = iran_start + len("Iran")
    us_start   = normalized.index("US")
    us_end     = us_start + len("US")

    entities = [
        _ent("LOC", "Iran", iran_start, iran_end),
        _ent("LOC", "US",   us_start,   us_end),
    ]

    with patch("preprocessing.ner_text_builder._preprocess_preserving_ner", side_effect=lambda t: t):
        result = build_ner_preprocessed_text(raw_body, entities)

    assert "LOC_Iran" in result
    assert "LOC_US"   in result
    # make sure no label bled into surrounding characters
    assert "LOC_Ira" not in result or result.count("LOC_Iran") == 1
    for ch in result:
        pass  # just ensure no exception


def test_multiple_spaces_in_body_offsets_still_correct():
    raw_body = "Donald  Trump  spoke."
    normalized = " ".join(raw_body.split())  # "Donald Trump spoke."
    dt_start = normalized.index("Donald Trump")
    dt_end   = dt_start + len("Donald Trump")

    entities = [_ent("PER", "Donald Trump", dt_start, dt_end)]

    with patch("preprocessing.ner_text_builder._preprocess_preserving_ner", side_effect=lambda t: t):
        result = build_ner_preprocessed_text(raw_body, entities)

    assert "PER_Donald_Trump" in result


def test_leading_trailing_whitespace_offsets_correct():
    raw_body = "  Paris is beautiful.  "
    normalized = " ".join(raw_body.split())
    p_start = normalized.index("Paris")
    p_end   = p_start + len("Paris")

    entities = [_ent("LOC", "Paris", p_start, p_end)]

    with patch("preprocessing.ner_text_builder._preprocess_preserving_ner", side_effect=lambda t: t):
        result = build_ner_preprocessed_text(raw_body, entities)

    assert "LOC_Paris" in result


def test_multi_paragraph_article_no_mid_word_tags():
    """
    Regression: simulates the slopaganda article pattern that caused mid-word tags.
    Two paragraphs separated by \n\n; entities from the second paragraph must not
    land inside words.
    """
    para1 = "In early March the White House posted a video."
    para2 = "Iran and its allies responded to the strikes."
    raw_body = f"{para1}\n\n{para2}"
    normalized = " ".join(raw_body.split())

    iran_start = normalized.index("Iran")
    iran_end   = iran_start + len("Iran")

    entities = [_ent("LOC", "Iran", iran_start, iran_end)]

    with patch("preprocessing.ner_text_builder._preprocess_preserving_ner", side_effect=lambda t: t):
        result = build_ner_preprocessed_text(raw_body, entities)

    assert "LOC_Iran" in result
    # tag must not be embedded mid-word
    for token in result.split():
        if "LOC_" in token:
            assert token.startswith("LOC_"), f"tag embedded mid-token: {token!r}"


# ── multi-entity substitution order ──────────────────────────────────────────

def test_multiple_entities_all_substituted():
    body = "Barack Obama visited Berlin last year."
    normalized = " ".join(body.split())
    obama_s = normalized.index("Barack Obama")
    obama_e = obama_s + len("Barack Obama")
    berlin_s = normalized.index("Berlin")
    berlin_e = berlin_s + len("Berlin")

    entities = [
        _ent("PER", "Barack Obama", obama_s, obama_e),
        _ent("LOC", "Berlin",       berlin_s, berlin_e),
    ]

    with patch("preprocessing.ner_text_builder._preprocess_preserving_ner", side_effect=lambda t: t):
        result = build_ner_preprocessed_text(body, entities)

    assert "PER_Barack_Obama" in result
    assert "LOC_Berlin" in result


def test_overlapping_offset_guard_does_not_crash():
    body = "Apple Inc. is a company."
    normalized = " ".join(body.split())
    entities = [
        _ent("ORG", "Apple Inc.", 0, 10),
        _ent("ORG", "Apple",      0, 5),   # subset — one must be skipped
    ]
    with patch("preprocessing.ner_text_builder._preprocess_preserving_ner", side_effect=lambda t: t):
        result = build_ner_preprocessed_text(body, entities)
    assert isinstance(result, str)


# ── out-of-bounds entities are silently skipped ───────────────────────────────

def test_out_of_bounds_entity_skipped():
    body = "Short text."
    entities = [_ent("LOC", "Nowhere", 9999, 10005)]
    with patch("preprocessing.ner_text_builder._preprocess_preserving_ner", side_effect=lambda t: t):
        result = build_ner_preprocessed_text(body, entities)
    assert "Nowhere" not in result
    assert "LOC_" not in result


def test_zero_length_span_skipped():
    body = "Some text."
    entities = [_ent("PER", "", 3, 3)]
    with patch("preprocessing.ner_text_builder._preprocess_preserving_ner", side_effect=lambda t: t):
        result = build_ner_preprocessed_text(body, entities)
    assert "PER_" not in result


# ── multi-word entity text formatting ────────────────────────────────────────

def test_multi_word_entity_uses_underscore():
    body = "New York City is large."
    normalized = " ".join(body.split())
    nyc_s = normalized.index("New York City")
    nyc_e = nyc_s + len("New York City")

    entities = [_ent("LOC", "New York City", nyc_s, nyc_e)]

    with patch("preprocessing.ner_text_builder._preprocess_preserving_ner", side_effect=lambda t: t):
        result = build_ner_preprocessed_text(body, entities)

    assert "LOC_New_York_City" in result


# ── NER tokens survive preprocessing ─────────────────────────────────────────

def test_ner_tokens_preserved_through_preprocessing():
    """NER tokens must survive the clean_text step intact."""
    body = "Angela Merkel led Germany for years."
    normalized = " ".join(body.split())
    am_s = normalized.index("Angela Merkel")
    am_e = am_s + len("Angela Merkel")
    g_s  = normalized.index("Germany")
    g_e  = g_s + len("Germany")

    entities = [
        _ent("PER", "Angela Merkel", am_s, am_e),
        _ent("LOC", "Germany",       g_s,  g_e),
    ]

    # Use real _preprocess_preserving_ner but mock the text processor
    mock_proc = MagicMock()
    mock_proc.clean_text.side_effect = lambda t: t.lower()

    with patch("preprocessing.text_processor.get_default_processor", return_value=mock_proc):
        result = build_ner_preprocessed_text(body, entities)

    # Tokens must survive even after lowercasing
    assert "PER_Angela_Merkel" in result
    assert "LOC_Germany" in result

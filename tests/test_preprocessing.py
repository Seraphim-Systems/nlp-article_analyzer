"""Tests for preprocessing.text_processor."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, call, patch

# ── Stub heavy deps before any project import ────────────────────────────────
for _m in ["spacy", "nltk", "nltk.corpus"]:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()

# Configure nltk.corpus.stopwords to return a sensible stub
_nltk_corpus = sys.modules["nltk.corpus"]
_nltk_corpus.stopwords = type(
    "sw", (), {"words": staticmethod(lambda lang: ["the", "are", "to", "be", "or", "not"])}
)()

import src.preprocessing.text_processor as _tp_module
from src.preprocessing.text_processor import TextProcessor, get_default_processor, preprocess_text


# ── Token / doc helpers ───────────────────────────────────────────────────────

def _make_token(lemma: str, is_punct: bool = False, is_space: bool = False) -> MagicMock:
    t = MagicMock()
    t.lemma_ = lemma
    t.text = lemma
    t.is_punct = is_punct
    t.is_space = is_space
    return t


def _make_nlp(token_lists: list[list[MagicMock]]):
    """Return a mock nlp callable. Each call pops from token_lists."""
    call_count = [0]

    def nlp_call(text):
        idx = call_count[0]
        call_count[0] += 1
        tokens = token_lists[min(idx, len(token_lists) - 1)]
        doc = MagicMock()
        doc.__iter__ = lambda s: iter(tokens)
        return doc

    def nlp_pipe(texts, batch_size=50):
        for text in texts:
            yield nlp_call(text)

    m = MagicMock()
    m.side_effect = nlp_call
    m.pipe = nlp_pipe
    return m


# ── TextProcessor.__init__ ───────────────────────────────────────────────────

def test_init_sets_lang():
    mock_nlp = _make_nlp([[]])
    with patch.object(sys.modules["spacy"], "load", return_value=mock_nlp):
        tp = TextProcessor(lang="en")
    assert tp.lang == "en"


def test_init_loads_spacy_model():
    mock_nlp = _make_nlp([[]])
    with patch.object(sys.modules["spacy"], "load", return_value=mock_nlp) as mock_load:
        TextProcessor(lang="en")
    mock_load.assert_called()


def test_init_falls_back_on_os_error():
    mock_nlp = _make_nlp([[]])
    calls = [OSError("not found"), mock_nlp]

    def load_side_effect(*a, **kw):
        val = calls.pop(0)
        if isinstance(val, Exception):
            raise val
        return val

    with patch.object(sys.modules["spacy"], "load", side_effect=load_side_effect) as mock_load:
        tp = TextProcessor(lang="es")
    assert mock_load.call_count == 2


# ── clean_text ───────────────────────────────────────────────────────────────

def test_clean_text_empty_returns_empty():
    mock_nlp = _make_nlp([[]])
    with patch.object(sys.modules["spacy"], "load", return_value=mock_nlp):
        tp = TextProcessor()
    assert tp.clean_text("") == ""


def test_clean_text_removes_stopwords():
    tokens = [
        _make_token("the", is_punct=False),   # stopword → removed
        _make_token("quick"),
        _make_token("fox"),
    ]
    mock_nlp = _make_nlp([tokens])
    with patch.object(sys.modules["spacy"], "load", return_value=mock_nlp):
        tp = TextProcessor()
        tp.stop_words = {"the"}
    result = tp.clean_text("the quick fox")
    assert "quick" in result
    assert "fox" in result
    assert "the" not in result.split()


def test_clean_text_removes_punctuation():
    tokens = [
        _make_token(".", is_punct=True),
        _make_token("hello"),
    ]
    mock_nlp = _make_nlp([tokens])
    with patch.object(sys.modules["spacy"], "load", return_value=mock_nlp):
        tp = TextProcessor()
        tp.stop_words = set()
    result = tp.clean_text("hello.")
    assert result == "hello"


def test_clean_text_no_lowercase():
    tokens = [_make_token("Hello")]
    mock_nlp = _make_nlp([tokens])
    with patch.object(sys.modules["spacy"], "load", return_value=mock_nlp):
        tp = TextProcessor()
        tp.stop_words = set()
    result = tp.clean_text("Hello", lowercase=False)
    assert "Hello" in result


def test_clean_text_no_remove_stopwords():
    tokens = [_make_token("the"), _make_token("quick")]
    mock_nlp = _make_nlp([tokens])
    with patch.object(sys.modules["spacy"], "load", return_value=mock_nlp):
        tp = TextProcessor()
        tp.stop_words = {"the"}
    result = tp.clean_text("the quick", remove_stopwords=False)
    assert "the" in result


def test_clean_text_drops_short_tokens():
    tokens = [_make_token("i"), _make_token("fox")]  # "i" is len 1, not a digit
    mock_nlp = _make_nlp([tokens])
    with patch.object(sys.modules["spacy"], "load", return_value=mock_nlp):
        tp = TextProcessor()
        tp.stop_words = set()
    result = tp.clean_text("i fox")
    assert "fox" in result
    assert "i" not in result.split()


# ── batch_process ─────────────────────────────────────────────────────────────

def test_batch_process_returns_same_length():
    token_lists = [
        [_make_token("run")],
        [_make_token("jump")],
    ]
    mock_nlp = _make_nlp(token_lists)
    with patch.object(sys.modules["spacy"], "load", return_value=mock_nlp):
        tp = TextProcessor()
        tp.stop_words = set()
    results = tp.batch_process(["running fast", "jumping high"])
    assert len(results) == 2


def test_batch_process_empty_list():
    mock_nlp = _make_nlp([[]])
    with patch.object(sys.modules["spacy"], "load", return_value=mock_nlp):
        tp = TextProcessor()
    assert tp.batch_process([]) == []


# ── preprocess_text / get_default_processor ──────────────────────────────────

def test_preprocess_text_returns_string():
    tokens = [_make_token("simple"), _make_token("test")]
    mock_nlp = _make_nlp([tokens])
    with patch.object(sys.modules["spacy"], "load", return_value=mock_nlp):
        with patch.object(_tp_module, "get_default_processor") as mock_getter:
            mock_processor = MagicMock()
            mock_processor.clean_text.return_value = "simple test"
            mock_getter.return_value = mock_processor
            result = preprocess_text("Simple TEST")
    assert result == "simple test"

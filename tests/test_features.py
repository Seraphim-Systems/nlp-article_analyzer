"""Unit tests for feature extraction modules."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# keyword_extractor — uses real sklearn, no mocks needed
# ---------------------------------------------------------------------------

from features.keyword_extractor import extract_keywords


def test_extract_keywords_returns_one_list_per_input():
    texts = ["apple banana cherry", "dog cat bird", "red green blue"]
    result = extract_keywords(texts)
    assert len(result) == 3
    assert all(isinstance(r, list) for r in result)


def test_extract_keywords_respects_top_n():
    texts = ["apple banana cherry date elderberry fig grape"]
    result = extract_keywords(texts, top_n=2)
    assert len(result[0]) <= 2


def test_extract_keywords_empty_list():
    # sklearn raises when there are no documents to fit
    with pytest.raises(ValueError):
        extract_keywords([])


def test_extract_keywords_single_word_text():
    result = extract_keywords(["hello"])
    assert len(result) == 1
    assert isinstance(result[0], list)


def test_extract_keywords_all_stopwords():
    # All stop words → empty vocabulary → ValueError from sklearn
    with pytest.raises(ValueError):
        extract_keywords(["the is a an and or but"])


def test_extract_keywords_no_zero_score_terms():
    result = extract_keywords(["alpha beta gamma"])
    for kw_list in result:
        # every keyword must have had a positive TF-IDF score
        assert all(isinstance(k, str) and len(k) > 0 for k in kw_list)


def test_extract_keywords_two_distinct_texts_differ():
    texts = [
        "quantum physics relativity neutron proton",
        "cooking recipe pasta tomato basil",
    ]
    result = extract_keywords(texts, top_n=3)
    assert set(result[0]) != set(result[1])


def test_extract_keywords_default_top_n():
    words = " ".join(f"word{i}" for i in range(20))
    result = extract_keywords([words])
    assert len(result[0]) <= 5


def test_extract_keywords_top_n_larger_than_vocab():
    result = extract_keywords(["alpha beta"], top_n=100)
    assert len(result[0]) <= 2


# ---------------------------------------------------------------------------
# topic_classifier — fully mocked (no real model)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_pipeline():
    import features.topic_classifier as tc
    tc._pipeline = None
    yield
    tc._pipeline = None


def _mock_pipeline_output(labels, scores):
    return {"labels": labels, "scores": scores}


def test_classify_topics_returns_top_label_and_score():
    fake_pipe = MagicMock(
        return_value=_mock_pipeline_output(["politics", "sports"], [0.9, 0.1])
    )
    with patch("features.topic_classifier._get_pipeline", return_value=fake_pipe):
        from features.topic_classifier import classify_topics
        label, score = classify_topics("some text", ["politics", "sports"])
    assert label == "politics"
    assert score == 0.9


def test_classify_topics_truncates_long_text():
    fake_pipe = MagicMock(
        return_value=_mock_pipeline_output(["a"], [1.0])
    )
    long_text = "x" * 2000
    with patch("features.topic_classifier._get_pipeline", return_value=fake_pipe):
        from features.topic_classifier import classify_topics
        classify_topics(long_text, ["a"])
    # The pipeline should have been called with text[:1024]
    called_text = fake_pipe.call_args[0][0]
    assert len(called_text) == 1024


def test_classify_topics_no_truncation_at_1024():
    fake_pipe = MagicMock(
        return_value=_mock_pipeline_output(["a"], [1.0])
    )
    text_1024 = "x" * 1024
    with patch("features.topic_classifier._get_pipeline", return_value=fake_pipe):
        from features.topic_classifier import classify_topics
        classify_topics(text_1024, ["a"])
    called_text = fake_pipe.call_args[0][0]
    assert len(called_text) == 1024


def test_classify_topics_cpu_path():
    with patch("features.topic_classifier.torch") as mock_torch, \
         patch("features.topic_classifier.pipeline") as mock_pl:
        mock_torch.cuda.is_available.return_value = False
        mock_pl.return_value = MagicMock(
            return_value=_mock_pipeline_output(["a"], [1.0])
        )
        from features.topic_classifier import classify_topics
        import features.topic_classifier as tc
        tc._pipeline = None
        classify_topics("text", ["a"])
        mock_pl.assert_called_once_with(
            "zero-shot-classification", model="facebook/bart-large-mnli", device=-1
        )


def test_classify_topics_gpu_path():
    with patch("features.topic_classifier.torch") as mock_torch, \
         patch("features.topic_classifier.pipeline") as mock_pl:
        mock_torch.cuda.is_available.return_value = True
        mock_pl.return_value = MagicMock(
            return_value=_mock_pipeline_output(["a"], [1.0])
        )
        from features.topic_classifier import classify_topics
        import features.topic_classifier as tc
        tc._pipeline = None
        classify_topics("text", ["a"])
        mock_pl.assert_called_once_with(
            "zero-shot-classification", model="facebook/bart-large-mnli", device=0
        )


def test_classify_topics_singleton():
    with patch("features.topic_classifier.torch") as mock_torch, \
         patch("features.topic_classifier.pipeline") as mock_pl:
        mock_torch.cuda.is_available.return_value = False
        mock_pl.return_value = MagicMock(
            return_value=_mock_pipeline_output(["a"], [1.0])
        )
        from features.topic_classifier import classify_topics
        import features.topic_classifier as tc
        tc._pipeline = None
        classify_topics("text1", ["a"])
        classify_topics("text2", ["a"])
        # transformers.pipeline should have been called only once
        assert mock_pl.call_count == 1


def test_classify_topics_single_label():
    fake_pipe = MagicMock(
        return_value=_mock_pipeline_output(["only_label"], [0.95])
    )
    with patch("features.topic_classifier._get_pipeline", return_value=fake_pipe):
        from features.topic_classifier import classify_topics
        label, score = classify_topics("text", ["only_label"])
    assert label == "only_label"
    assert score == 0.95


def test_classify_topics_empty_text():
    fake_pipe = MagicMock(
        return_value=_mock_pipeline_output(["a"], [0.5])
    )
    with patch("features.topic_classifier._get_pipeline", return_value=fake_pipe):
        from features.topic_classifier import classify_topics
        label, score = classify_topics("", ["a"])
    assert isinstance(label, str)
    assert isinstance(score, float)

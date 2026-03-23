"""
Tests for NLP Text Preprocessing.
"""

import pytest
from src.preprocessing.text_processor import TextProcessor, preprocess_text


def test_text_processor_basic():
    processor = TextProcessor(lang="en")
    text = "The quick brown foxes are jumping over the lazy dogs."
    cleaned = processor.clean_text(text)

    # Check for lowercase
    assert cleaned.islower()
    # Check for lemmatization (foxes -> fox)
    assert "fox" in cleaned
    # Check for stopword removal (the, are)
    assert "the" not in cleaned.split()
    assert "are" not in cleaned.split()


def test_preprocess_text_helper():
    text = "Simple TEST for the helper function!"
    cleaned = preprocess_text(text)

    # Basic verification
    assert cleaned == "simple test helper function"


def test_batch_process():
    processor = TextProcessor(lang="en")
    texts = ["Running in the 90s.", "To be or not to be."]
    results = processor.batch_process(texts)

    assert len(results) == 2
    assert "run" in results[0]  # lemmatization of running
    assert results[1] == ""  # "to be or not to be" is all stopwords

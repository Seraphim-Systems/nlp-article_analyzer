"""
Named Entity Recognition extractor using dslim/bert-base-NER.

Model: dslim/bert-base-NER (HuggingFace)
Input: article body text (string)
Output: list of {text, label, start, end} dicts

The NER pipeline is a lazy-loaded singleton — it loads once on first call
and is reused for all subsequent calls in the same process.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_MODEL_NAME    = "dslim/bert-base-NER"
_CHUNK_WORDS   = 400   # well under BERT's 512-subtoken limit after wordpiece splitting
_OVERLAP_WORDS = 40    # overlap so entities spanning a chunk boundary aren't missed
_pipeline = None
_device_label: str = "cpu"


def _get_pipeline():
    """Return the NER pipeline, loading it on first call."""
    global _pipeline, _device_label
    if _pipeline is None:
        try:
            import torch
            from transformers import pipeline as hf_pipeline
            logger.info("Loading NER model: %s", _MODEL_NAME)
            if torch.cuda.is_available():
                device = 0
                _device_label = f"cuda ({torch.cuda.get_device_name(0)})"
            elif torch.backends.mps.is_available():
                device = "mps"
                _device_label = "mps (Apple Metal)"
            else:
                device = -1
                _device_label = "cpu"
            _pipeline = hf_pipeline(
                "ner",
                model=_MODEL_NAME,
                aggregation_strategy="simple",
                device=device,
            )
            logger.info("NER model loaded on %s.", _device_label)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to load NER model '{_MODEL_NAME}': {exc}"
            ) from exc
    return _pipeline


def get_device_label() -> str:
    """Load the pipeline if needed and return a human-readable device string."""
    _get_pipeline()
    return _device_label


def _char_offset_of_word(words: list[str], word_idx: int) -> int:
    """Return the character position where words[word_idx] starts in ' '.join(words)."""
    return sum(len(w) + 1 for w in words[:word_idx])


def _extract_chunked(normalized: str, nlp) -> list[dict[str, Any]]:
    """
    Run NER over arbitrarily long text by splitting into overlapping word-chunks.

    Each chunk is at most _CHUNK_WORDS words. Adjacent chunks overlap by
    _OVERLAP_WORDS words so entities that fall on a boundary are not missed.
    Entity positions are adjusted to be absolute in `normalized`.
    Duplicate detections from the overlap region are deduplicated.
    """
    words = normalized.split()
    if not words:
        return []

    if len(words) <= _CHUNK_WORDS:
        raw = nlp(normalized)
        return [
            {"text": e["word"], "label": e["entity_group"], "start": e["start"], "end": e["end"]}
            for e in raw
        ]

    seen: set[tuple[int, int, str]] = set()
    entities: list[dict[str, Any]] = []

    start_w = 0
    while start_w < len(words):
        end_w      = min(start_w + _CHUNK_WORDS, len(words))
        chunk_text = " ".join(words[start_w:end_w])
        offset     = _char_offset_of_word(words, start_w)

        for e in nlp(chunk_text):
            abs_start = e["start"] + offset
            abs_end   = e["end"]   + offset
            key = (abs_start, abs_end, e["entity_group"])
            if key not in seen:
                seen.add(key)
                entities.append({
                    "text":  e["word"],
                    "label": e["entity_group"],
                    "start": abs_start,
                    "end":   abs_end,
                })

        if end_w == len(words):
            break
        start_w += _CHUNK_WORDS - _OVERLAP_WORDS

    return entities


def extract_entities(text: str) -> list[dict[str, Any]]:
    """
    Extract named entities from a text string.

    Long texts are processed in overlapping chunks so no part of the article
    is silently dropped due to BERT's 512-subtoken limit.

    Parameters
    ----------
    text : str
        Article body text.

    Returns
    -------
    list[dict]
        Each dict has keys: text (str), label (str), start (int), end (int).
    """
    if not text or not text.strip():
        return []
    normalized = " ".join(text.split())
    return _extract_chunked(normalized, _get_pipeline())


def batch_extract(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Run NER extraction on a list of article dicts.

    Each article must have a `body` field. Returns a new list of dicts
    with an `entities` key added. Long articles are processed in overlapping
    chunks so entities are extracted from the full text.

    Parameters
    ----------
    articles : list[dict]
        Article documents from the clean collection.

    Returns
    -------
    list[dict]
        Same articles with `entities: list[dict]` added.
    """
    if not articles:
        return []

    nlp = _get_pipeline()
    enriched = []
    for article in articles:
        body       = article.get("body") or ""
        normalized = " ".join(body.split())
        entities   = _extract_chunked(normalized, nlp)
        enriched.append({**article, "entities": entities})

    return enriched


__all__ = ["extract_entities", "batch_extract"]

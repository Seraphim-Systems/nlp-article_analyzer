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

_MODEL_NAME = "dslim/bert-base-NER"
_CHUNK_WORDS = 400  # well under BERT's 512-subtoken limit after wordpiece splitting
_OVERLAP_WORDS = 40  # overlap so entities spanning a chunk boundary aren't missed
_CHUNK_WORDS_CPU = (
    280  # smaller chunks on CPU for faster processing, stay under 512 subtoken limit
)
_OVERLAP_WORDS_CPU = 28  # proportional overlap for CPU
_pipeline = None
_device_label: str = "cpu"
_is_cpu: bool | None = None


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


def is_cpu_device() -> bool:
    """Check if running on CPU device."""
    global _is_cpu
    if _is_cpu is None:
        _get_pipeline()
        _is_cpu = "cpu" in _device_label.lower()
    return _is_cpu


def get_batch_size_recommendation() -> int:
    """Return recommended batch size based on device."""
    if is_cpu_device():
        return 16  # Smaller batches on CPU for faster throughput
    else:
        return 32  # GPU can handle larger batches


def _char_offset_of_word(words: list[str], word_idx: int) -> int:
    """Return the character position where words[word_idx] starts in ' '.join(words)."""
    return sum(len(w) + 1 for w in words[:word_idx])


def _snap_to_word(text: str, start: int, end: int) -> tuple[int, int]:
    """Extend start/end to cover the full word, preventing mid-word entity splits."""
    while start > 0 and text[start - 1] not in (" ", "\t", "\n"):
        start -= 1
    while end < len(text) and text[end] not in (" ", "\t", "\n"):
        end += 1
    return start, end


def _extract_chunked(normalized: str, nlp) -> list[dict[str, Any]]:
    """
    Run NER over arbitrarily long text by splitting into overlapping word-chunks.

    Each chunk is at most _CHUNK_WORDS words (or _CHUNK_WORDS_CPU on CPU).
    Adjacent chunks overlap by _OVERLAP_WORDS words so entities that fall on a
    boundary are not missed. Entity positions are adjusted to be absolute in
    `normalized`. Duplicate detections from the overlap region are deduplicated.
    """
    words = normalized.split()
    if not words:
        return []

    # Use smaller chunks on CPU for faster processing
    chunk_words = _CHUNK_WORDS_CPU if is_cpu_device() else _CHUNK_WORDS
    overlap_words = _OVERLAP_WORDS_CPU if is_cpu_device() else _OVERLAP_WORDS

    if len(words) <= chunk_words:
        raw = nlp(normalized)
        result = []
        for e in raw:
            s, en = _snap_to_word(normalized, e["start"], e["end"])
            result.append(
                {
                    "text": normalized[s:en],
                    "label": e["entity_group"],
                    "start": s,
                    "end": en,
                }
            )
        return result

    seen: set[tuple[int, int, str]] = set()
    entities: list[dict[str, Any]] = []

    start_w = 0
    while start_w < len(words):
        end_w = min(start_w + chunk_words, len(words))
        chunk_text = " ".join(words[start_w:end_w])
        offset = _char_offset_of_word(words, start_w)

        for e in nlp(chunk_text):
            cs, ce = _snap_to_word(chunk_text, e["start"], e["end"])
            abs_start = cs + offset
            abs_end = ce + offset
            key = (abs_start, abs_end, e["entity_group"])
            if key not in seen:
                seen.add(key)
                entities.append(
                    {
                        "text": chunk_text[cs:ce],
                        "label": e["entity_group"],
                        "start": abs_start,
                        "end": abs_end,
                    }
                )

        if end_w == len(words):
            break
        start_w += chunk_words - overlap_words

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
        body = article.get("body") or ""
        normalized = " ".join(body.split())
        entities = _extract_chunked(normalized, nlp)
        enriched.append({**article, "entities": entities})

    return enriched


__all__ = [
    "extract_entities",
    "batch_extract",
    "get_batch_size_recommendation",
    "is_cpu_device",
]

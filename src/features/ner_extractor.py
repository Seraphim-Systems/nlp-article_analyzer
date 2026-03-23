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
_MAX_TOKENS = 512
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


def extract_entities(text: str) -> list[dict[str, Any]]:
    """
    Extract named entities from a text string.

    Truncates to _MAX_TOKENS words before inference to respect BERT's limit.

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

    words = text.split()
    if len(words) > _MAX_TOKENS:
        text = " ".join(words[:_MAX_TOKENS])

    nlp = _get_pipeline()
    raw_entities = nlp(text)

    return [
        {
            "text":  ent["word"],
            "label": ent["entity_group"],
            "start": ent["start"],
            "end":   ent["end"],
        }
        for ent in raw_entities
    ]


def batch_extract(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Run NER extraction on a list of article dicts using BERT batching.

    Each article must have a `body` field. Returns a new list of dicts
    with an `entities` key added to each article.

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

    # Truncate each body to _MAX_TOKENS words
    texts = []
    for article in articles:
        body = article.get("body") or ""
        words = body.split()
        if len(words) > _MAX_TOKENS:
            body = " ".join(words[:_MAX_TOKENS])
        texts.append(body)

    # Run BERT inference in one batched call
    all_raw = nlp(texts, batch_size=len(texts))

    enriched = []
    for article, raw_entities in zip(articles, all_raw):
        # nlp() on a list returns a list of lists
        if isinstance(raw_entities, dict):
            raw_entities = [raw_entities]
        entities = [
            {
                "text":  ent["word"],
                "label": ent["entity_group"],
                "start": ent["start"],
                "end":   ent["end"],
            }
            for ent in raw_entities
        ]
        enriched.append({**article, "entities": entities})

    return enriched


__all__ = ["extract_entities", "batch_extract"]

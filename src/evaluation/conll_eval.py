"""
CoNLL-2003 benchmark evaluation for dslim/bert-base-NER.

Loads the CoNLL-2003 English test split via HuggingFace datasets, runs BERT NER
inference, and computes strict entity-level P/R/F1 via seqeval.

CoNLL-2003 covers PER, ORG, LOC, MISC entity types and is the dataset this model
was fine-tuned on, making it the correct benchmark for evaluating dslim/bert-base-NER.

This produces academically defensible NER quality metrics (model vs human-annotated
ground truth) rather than a silver-label BERT-vs-BERT consistency check.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

MODEL_NAME     = "dslim/bert-base-NER"
BENCHMARK      = "conll2003"
DEFAULT_SAMPLE = 3684   # full CoNLL-2003 English test set


def _build_char_offsets(tokens: list[str]) -> list[tuple[int, int]]:
    """Return (start, end) char offsets assuming tokens are space-joined."""
    offsets: list[tuple[int, int]] = []
    pos = 0
    for tok in tokens:
        offsets.append((pos, pos + len(tok)))
        pos += len(tok) + 1  # +1 for the joining space
    return offsets


def _spans_to_bio(tokens: list[str], predictions: list[dict]) -> list[str]:
    """
    Convert HuggingFace NER span predictions to word-level BIO labels.

    predictions: list of dicts with keys entity_group, start, end
    Each token that overlaps with a predicted span is assigned B-<type> (first)
    or I-<type> (subsequent).
    """
    char_offsets = _build_char_offsets(tokens)
    bio = ["O"] * len(tokens)

    for pred in sorted(predictions, key=lambda p: p["start"]):
        entity  = pred["entity_group"]
        p_start = pred["start"]
        p_end   = pred["end"]
        first   = True
        for i, (t_start, t_end) in enumerate(char_offsets):
            if t_start < p_end and t_end > p_start:  # overlap
                bio[i] = f"{'B' if first else 'I'}-{entity}"
                first  = False
    return bio


def run_conll_eval(sample_size: int = DEFAULT_SAMPLE) -> dict[str, Any]:
    """
    Evaluate dslim/bert-base-NER on the CoNLL-2003 English test split.

    Parameters
    ----------
    sample_size : int
        Number of sentences to evaluate (default 3684; full CoNLL-2003 test set).

    Returns
    -------
    dict with keys: precision, recall, f1, per_entity, sample_size, benchmark.

    Raises
    ------
    RuntimeError
        If seqeval/datasets are not installed, or the dataset cannot be loaded.
    """
    try:
        from datasets import load_dataset
        from seqeval.metrics import (
            classification_report,
            f1_score,
            precision_score,
            recall_score,
        )
        from transformers import pipeline as hf_pipeline
    except ImportError as exc:
        raise RuntimeError(f"Missing dependency for CoNLL eval: {exc}") from exc

    logger.info("Loading CoNLL-2003 English test split (sample=%d)...", sample_size)
    dataset = load_dataset(BENCHMARK, split="test", trust_remote_code=True)
    tag_names: list[str] = dataset.features["ner_tags"].feature.names

    n        = min(sample_size, len(dataset))
    examples = dataset.select(range(n))

    device = -1
    device_label = "cpu"
    try:
        import torch

        if torch.cuda.is_available():
            device = 0
            device_label = f"cuda ({torch.cuda.get_device_name(0)})"
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            device = "mps"
            device_label = "mps (Apple Metal)"
    except Exception:
        # Fallback to CPU if torch probing fails for any reason.
        device = -1
        device_label = "cpu"

    logger.info("Loading NER pipeline (%s) on %s...", MODEL_NAME, device_label)
    ner = hf_pipeline(
        "ner",
        model=MODEL_NAME,
        aggregation_strategy="simple",
        device=device,
    )

    true_seqs: list[list[str]] = []
    pred_seqs: list[list[str]] = []

    logger.info("Running inference on %d sentences...", n)
    for example in examples:
        tokens: list[str] = example["tokens"]
        true_bio = [tag_names[t] for t in example["ner_tags"]]

        text     = " ".join(tokens)
        raw_preds = ner(text)
        pred_bio  = _spans_to_bio(tokens, raw_preds)

        true_seqs.append(true_bio)
        pred_seqs.append(pred_bio)

    report = classification_report(true_seqs, pred_seqs, output_dict=True)

    per_entity: dict[str, dict] = {
        label: {
            "precision": round(v["precision"], 4),
            "recall":    round(v["recall"], 4),
            "f1":        round(v["f1-score"], 4),
            "support":   int(v["support"]),
        }
        for label, v in report.items()
        if isinstance(v, dict)
        and label not in ("micro avg", "macro avg", "weighted avg", "accuracy")
    }

    return {
        "precision":   round(precision_score(true_seqs, pred_seqs), 4),
        "recall":      round(recall_score(true_seqs, pred_seqs), 4),
        "f1":          round(f1_score(true_seqs, pred_seqs), 4),
        "per_entity":  per_entity,
        "sample_size": n,
        "benchmark":   BENCHMARK,
    }

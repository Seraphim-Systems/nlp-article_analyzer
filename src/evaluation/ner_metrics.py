"""
NER evaluation metrics module.

Computes precision, recall, and F1 per entity type (PER, ORG, LOC, MISC)
by comparing predicted entity spans against reference (silver-label) spans.

Strategy
--------
Since no human-annotated ground truth exists, we use a silver-label approach:
the stored ``entities`` arrays in ``nlp_ner.ner_articles`` are treated as the
reference.  The evaluate job re-runs inference on the same sampled articles to
produce predictions, then calls ``compute_ner_metrics`` to compare them.

On the first eval run this will yield near-perfect scores (the model is being
compared against its own previous output).  This is intentional — it sets the
performance baseline and surfaces regressions if the model or pipeline changes.

Span matching
-------------
An entity pair (predicted, reference) is a true positive when:
  1. Both have the same ``label`` (entity type).
  2. Their character spans overlap with IoU >= ``IOU_THRESHOLD`` (default 0.5).

Using IoU rather than exact character equality accounts for minor tokenizer
offset drift that can occur between BERT inference runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

IOU_THRESHOLD = 0.5

ENTITY_LABELS = ("PER", "ORG", "LOC", "MISC")


@dataclass
class EvalResult:
    """Precision / recall / F1 for a single entity type."""

    entity_type: str
    precision: float
    recall: float
    f1: float
    support: int  # total reference entities of this type


def score_span_pair(pred_start: int, pred_end: int, ref_start: int, ref_end: int) -> bool:
    """Return True if the two character spans overlap with IoU >= IOU_THRESHOLD."""
    intersection = max(0, min(pred_end, ref_end) - max(pred_start, ref_start))
    if intersection == 0:
        return False
    union = max(pred_end, ref_end) - min(pred_start, ref_start)
    return (intersection / union) >= IOU_THRESHOLD


def _metrics_for_label(
    predicted_by_url: dict[str, list[dict]],
    reference_by_url: dict[str, list[dict]],
    label: str,
) -> EvalResult:
    """Compute P/R/F1 for a single entity label across all articles."""
    tp = 0
    fp = 0
    fn = 0

    all_urls = set(predicted_by_url) | set(reference_by_url)
    for url in all_urls:
        preds = [e for e in predicted_by_url.get(url, []) if e.get("label") == label]
        refs  = [e for e in reference_by_url.get(url, [])  if e.get("label") == label]

        matched_refs: set[int] = set()
        for pred in preds:
            matched = False
            for i, ref in enumerate(refs):
                if i in matched_refs:
                    continue
                if score_span_pair(pred["start"], pred["end"], ref["start"], ref["end"]):
                    tp += 1
                    matched_refs.add(i)
                    matched = True
                    break
            if not matched:
                fp += 1
        fn += len(refs) - len(matched_refs)

    support = sum(
        len([e for e in entities if e.get("label") == label])
        for entities in reference_by_url.values()
    )

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return EvalResult(
        entity_type=label,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        support=support,
    )


def macro_average(results: dict[str, EvalResult]) -> EvalResult:
    """Return an unweighted macro-average across all entity types."""
    label_results = [r for k, r in results.items() if k != "overall"]
    if not label_results:
        return EvalResult(entity_type="overall", precision=0.0, recall=0.0, f1=0.0, support=0)
    n = len(label_results)
    return EvalResult(
        entity_type="overall",
        precision=round(sum(r.precision for r in label_results) / n, 4),
        recall=round(sum(r.recall    for r in label_results) / n, 4),
        f1=round(sum(r.f1           for r in label_results) / n, 4),
        support=sum(r.support for r in label_results),
    )


def compute_ner_metrics(
    predicted: list[dict],
    reference: list[dict],
) -> dict[str, EvalResult]:
    """
    Compare predicted entity annotations against reference annotations.

    Parameters
    ----------
    predicted:
        List of article dicts, each with a ``url`` key and an ``entities``
        list of ``{text, label, start, end}`` dicts (output of batch_extract).
    reference:
        List of article dicts in the same format, used as ground truth.

    Returns
    -------
    dict mapping entity label → EvalResult, plus an ``"overall"`` macro average.
    """
    predicted_by_url: dict[str, list[dict]] = {
        a["url"]: a.get("entities", []) for a in predicted
    }
    reference_by_url: dict[str, list[dict]] = {
        a["url"]: a.get("entities", []) for a in reference
    }

    results: dict[str, EvalResult] = {}
    for label in ENTITY_LABELS:
        results[label] = _metrics_for_label(predicted_by_url, reference_by_url, label)

    results["overall"] = macro_average(results)
    return results

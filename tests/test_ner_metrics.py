"""
Unit tests for evaluation.ner_metrics.

No MongoDB connection or model weights are required — all functions under test
are pure Python.
"""

from __future__ import annotations

import pytest

from evaluation.ner_metrics import (
    EvalResult,
    compute_ner_metrics,
    macro_average,
    score_span_pair,
)


# ---------------------------------------------------------------------------
# score_span_pair
# ---------------------------------------------------------------------------

def test_exact_match_is_true():
    assert score_span_pair(0, 10, 0, 10) is True


def test_no_overlap_is_false():
    assert score_span_pair(0, 5, 6, 11) is False


def test_adjacent_spans_no_overlap():
    # end of pred == start of ref → zero intersection
    assert score_span_pair(0, 5, 5, 10) is False


def test_partial_overlap_above_threshold():
    # intersection=6, union=10, IoU=0.6 → True
    assert score_span_pair(0, 8, 2, 10) is True


def test_partial_overlap_below_threshold():
    # intersection=1, union=9, IoU≈0.11 → False
    assert score_span_pair(0, 5, 4, 9) is False


def test_contained_span_high_iou():
    # pred fully inside ref: intersection=3, union=10, IoU=0.3 → False
    assert score_span_pair(4, 7, 0, 10) is False


def test_single_char_exact_match():
    assert score_span_pair(5, 6, 5, 6) is True


# ---------------------------------------------------------------------------
# compute_ner_metrics — basic correctness
# ---------------------------------------------------------------------------

def _article(url: str, entities: list[dict]) -> dict:
    return {"url": url, "body": "...", "entities": entities}


def test_exact_match_yields_perfect_scores():
    ents = [{"text": "London", "label": "LOC", "start": 0, "end": 6}]
    predicted = [_article("http://a.com", ents)]
    reference = [_article("http://a.com", ents)]

    results = compute_ner_metrics(predicted, reference)
    assert results["LOC"].precision == 1.0
    assert results["LOC"].recall    == 1.0
    assert results["LOC"].f1        == 1.0
    assert results["LOC"].support   == 1


def test_no_predictions_yields_zero_precision_and_recall():
    ents = [{"text": "London", "label": "LOC", "start": 0, "end": 6}]
    predicted = [_article("http://a.com", [])]
    reference = [_article("http://a.com", ents)]

    results = compute_ner_metrics(predicted, reference)
    assert results["LOC"].precision == 0.0
    assert results["LOC"].recall    == 0.0
    assert results["LOC"].f1        == 0.0
    assert results["LOC"].support   == 1


def test_no_reference_entities_yields_zero():
    ents = [{"text": "London", "label": "LOC", "start": 0, "end": 6}]
    predicted = [_article("http://a.com", ents)]
    reference = [_article("http://a.com", [])]

    results = compute_ner_metrics(predicted, reference)
    assert results["LOC"].precision == 0.0
    assert results["LOC"].recall    == 0.0
    assert results["LOC"].f1        == 0.0


def test_non_overlapping_spans_counted_as_fp_and_fn():
    pred_ents = [{"text": "Paris", "label": "LOC", "start": 0, "end": 5}]
    ref_ents  = [{"text": "London", "label": "LOC", "start": 20, "end": 26}]
    predicted = [_article("http://a.com", pred_ents)]
    reference = [_article("http://a.com", ref_ents)]

    results = compute_ner_metrics(predicted, reference)
    # 1 FP, 1 FN → P=0, R=0, F1=0
    assert results["LOC"].precision == 0.0
    assert results["LOC"].recall    == 0.0
    assert results["LOC"].f1        == 0.0


def test_different_label_not_matched():
    pred_ents = [{"text": "Apple", "label": "ORG", "start": 0, "end": 5}]
    ref_ents  = [{"text": "Apple", "label": "LOC", "start": 0, "end": 5}]
    predicted = [_article("http://a.com", pred_ents)]
    reference = [_article("http://a.com", ref_ents)]

    results = compute_ner_metrics(predicted, reference)
    assert results["ORG"].precision == 0.0  # FP — no matching ref ORG
    assert results["LOC"].recall    == 0.0  # FN — no matching pred LOC


def test_multiple_articles_aggregated():
    predicted = [
        _article("http://a.com", [{"text": "Tim", "label": "PER", "start": 0, "end": 3}]),
        _article("http://b.com", [{"text": "Ada", "label": "PER", "start": 0, "end": 3}]),
    ]
    reference = [
        _article("http://a.com", [{"text": "Tim", "label": "PER", "start": 0, "end": 3}]),
        _article("http://b.com", [{"text": "Ada", "label": "PER", "start": 0, "end": 3}]),
    ]
    results = compute_ner_metrics(predicted, reference)
    assert results["PER"].f1      == 1.0
    assert results["PER"].support == 2


def test_empty_inputs_all_zeros():
    results = compute_ner_metrics([], [])
    for label in ("PER", "ORG", "LOC", "MISC"):
        assert results[label].f1 == 0.0
    assert results["overall"].f1 == 0.0


def test_overall_key_present():
    results = compute_ner_metrics([], [])
    assert "overall" in results
    assert isinstance(results["overall"], EvalResult)


# ---------------------------------------------------------------------------
# macro_average
# ---------------------------------------------------------------------------

def test_macro_average_known_values():
    results = {
        "PER":  EvalResult("PER",  precision=1.0, recall=1.0, f1=1.0, support=10),
        "ORG":  EvalResult("ORG",  precision=0.5, recall=0.5, f1=0.5, support=5),
        "LOC":  EvalResult("LOC",  precision=0.0, recall=0.0, f1=0.0, support=0),
        "MISC": EvalResult("MISC", precision=1.0, recall=1.0, f1=1.0, support=2),
    }
    avg = macro_average(results)
    assert avg.entity_type == "overall"
    assert avg.f1 == round((1.0 + 0.5 + 0.0 + 1.0) / 4, 4)
    assert avg.support == 17


def test_macro_average_empty_dict():
    avg = macro_average({})
    assert avg.f1 == 0.0
    assert avg.support == 0


def test_macro_average_skips_overall_key():
    results = {
        "PER":     EvalResult("PER",     precision=1.0, recall=1.0, f1=1.0, support=5),
        "overall": EvalResult("overall", precision=0.0, recall=0.0, f1=0.0, support=0),
    }
    avg = macro_average(results)
    # Only PER should be averaged, not the existing "overall" entry
    assert avg.f1 == 1.0

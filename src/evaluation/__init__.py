"""
Evaluation package.

Provides NER precision / recall / F1 metrics computed via span-level IoU
matching against silver-label annotations stored in ``nlp_ner.ner_articles``.
"""

from evaluation.ner_metrics import EvalResult, compute_ner_metrics

__all__ = ["EvalResult", "compute_ner_metrics"]

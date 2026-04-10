"""
Separability evaluation — reusable function that computes TF-IDF separability
metrics for the evaluate job to persist.

Mirrors the logic in web/app.py::separability_analysis but runs synchronously
so it can be called from a background job.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def compute_separability(sample_size: int = 4000) -> dict[str, Any]:
    """
    Compute TF-IDF separability metrics for clean vs NER-enhanced text.

    Returns the same dict shape as GET /compare/separability.
    Raises RuntimeError if no NER articles are available.
    """
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as _cos_sim

    from database.repositories import get_ner_collection
    from preprocessing.ner_text_builder import build_ner_preprocessed_text

    articles = list(
        get_ner_collection().find(
            {
                "preprocessed_text": {"$exists": True, "$ne": ""},
                "entities": {"$exists": True},
            },
            {"preprocessed_text": 1, "ner_preprocessed_text": 1, "body": 1, "entities": 1},
        ).limit(sample_size)
    )

    if not articles:
        raise RuntimeError("No NER-enriched articles available — run the NER job first.")

    clean_texts = [a.get("preprocessed_text") or "" for a in articles]
    ner_texts = [
        a.get("ner_preprocessed_text")
        or build_ner_preprocessed_text(a.get("body") or "", a.get("entities", []))
        for a in articles
    ]

    vect_clean = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True)
    vect_ner   = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, lowercase=False)

    mat_clean = vect_clean.fit_transform(clean_texts)
    mat_ner   = vect_ner.fit_transform(ner_texts)

    def _pairwise_stats(mat) -> tuple[float, float]:
        n = mat.shape[0]
        if n < 2:
            return 0.0, 0.0
        sims = _cos_sim(mat)
        upper = sims[np.triu_indices(n, k=1)]
        return float(upper.mean()), float(upper.std())

    clean_mean, clean_std = _pairwise_stats(mat_clean)
    ner_mean,   ner_std   = _pairwise_stats(mat_ner)

    mean_c = np.asarray(mat_clean.mean(axis=0)).flatten()
    mean_n = np.asarray(mat_ner.mean(axis=0)).flatten()
    top_c  = set(vect_clean.get_feature_names_out()[mean_c.argsort()[-25:][::-1]])
    top_n  = set(vect_ner.get_feature_names_out()[mean_n.argsort()[-25:][::-1]])
    top_c_l = {t.lower() for t in top_c}
    top_n_l = {t.lower() for t in top_n}
    intersection = len(top_c_l & top_n_l)
    union        = len(top_c_l | top_n_l)

    ner_prefixes = {"PER_", "ORG_", "LOC_", "MISC_"}
    ner_specific = sum(1 for t in top_n if any(t.startswith(p) for p in ner_prefixes))

    improvement = (clean_mean - ner_mean) / max(clean_mean, 0.001)

    return {
        "sample_size":          len(articles),
        "clean_avg_similarity": round(clean_mean, 4),
        "ner_avg_similarity":   round(ner_mean,   4),
        "clean_std":            round(clean_std,  4),
        "ner_std":              round(ner_std,    4),
        "top25_jaccard":        round(intersection / union if union > 0 else 0.0, 3),
        "top25_overlap_count":  intersection,
        "ner_specific_terms":   ner_specific,
        "improvement_pct":      round(improvement * 100, 1),
        "verdict":              (
            "improved"     if improvement >  0.03 else
            "degraded"     if improvement < -0.03 else
            "inconclusive"
        ),
    }

"""
Evaluate job — computes NER model performance metrics and persists results.

Entry point: run()

Strategy
--------
Uses a silver-label approach: a random sample of articles is drawn from
``nlp_ner.ner_articles`` (whose stored ``entities`` arrays become the reference).
The NER model is then re-run on the same articles to produce fresh predictions,
which are compared against the reference via span-level IoU matching.

The first run will yield near-perfect scores because the model is being compared
against its own previous output.  This is intentional — it establishes a
performance baseline and will surface regressions if the model or pipeline ever
changes.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

SAMPLE_SIZE = 500
MODEL_VERSION = "dslim/bert-base-NER"


def run(dry_run: bool = False) -> dict[str, Any]:
    """
    Execute the evaluation job.

    Loads a random sample of NER articles, re-runs inference, computes
    per-entity-type precision/recall/F1, and persists the run to
    ``nlp_models.model_runs`` (unless ``dry_run=True``).

    Parameters
    ----------
    dry_run : bool
        If True, compute metrics but do not write to MongoDB.

    Returns
    -------
    dict with keys: status, model_version, metrics, errors, duration_seconds,
    sample_size.
    """
    start_time = time.time()
    result: dict[str, Any] = {
        "status": "success",
        "model_version": MODEL_VERSION,
        "metrics": {},
        "errors": [],
        "duration_seconds": 0,
        "sample_size": 0,
    }

    try:
        from database.init_db import init_databases
        from evaluation import compute_ner_metrics
        from evaluation.sample_loader import load_ner_sample
        from features.ner_extractor import batch_extract

        init_databases()

        logger.info("=== Evaluate job started ===")

        # ── 1. Load reference sample ──────────────────────────────────────────
        reference = load_ner_sample(n=SAMPLE_SIZE)
        if not reference:
            logger.warning(
                "No NER articles found — run the classify job first. "
                "Evaluate job returning early."
            )
            result["status"] = "success"
            return result

        logger.info("Loaded %d reference articles for evaluation.", len(reference))

        # ── 2. Re-run inference to produce predictions ─────────────────────────
        logger.info("Running NER inference on sample…")
        predicted = batch_extract(reference)
        logger.info("Inference complete.")

        # ── 3. Compute metrics ────────────────────────────────────────────────
        eval_results = compute_ner_metrics(predicted=predicted, reference=reference)

        metrics_dict: dict[str, Any] = {
            label: {
                "precision": r.precision,
                "recall":    r.recall,
                "f1":        r.f1,
                "support":   r.support,
            }
            for label, r in eval_results.items()
        }

        result["metrics"]     = metrics_dict
        result["sample_size"] = len(reference)

        overall = eval_results.get("overall")
        if overall:
            logger.info(
                "Evaluation complete — overall P=%.4f  R=%.4f  F1=%.4f  (n=%d)",
                overall.precision,
                overall.recall,
                overall.f1,
                len(reference),
            )

        for label, r in eval_results.items():
            logger.info(
                "  %-8s  P=%.4f  R=%.4f  F1=%.4f  support=%d",
                label, r.precision, r.recall, r.f1, r.support,
            )

        # ── 4. Persist run ────────────────────────────────────────────────────
        if not dry_run:
            from database.repositories import insert_model_run

            run_doc: dict[str, Any] = {
                "model_version":    MODEL_VERSION,
                "metrics":          metrics_dict,
                "created_at":       datetime.now(timezone.utc).isoformat(),
                "hyperparams":      {"model": MODEL_VERSION, "sample_size": len(reference)},
                "training_set_size": len(reference),
            }
            inserted_id = insert_model_run(run_doc)
            logger.info("Eval run persisted to nlp_models.model_runs (id=%s)", inserted_id)
        else:
            logger.info("DRY RUN: metrics computed but not persisted.")


    except Exception as e:
        logger.exception("Evaluate job failed")
        result["status"] = "failed"
        result["errors"].append(str(e))

    finally:
        result["duration_seconds"] = round(time.time() - start_time, 2)
        logger.info(
            "=== Evaluate job finished (status=%s, duration=%.2fs) ===",
            result["status"],
            result["duration_seconds"],
        )

    return result


__all__ = ["run"]

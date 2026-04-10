"""
Evaluate job — computes evaluation metrics and persists results.

Two evaluations are run:

1. Separability (primary — answers the research question)
   Computes mean pairwise cosine similarity for clean TF-IDF vs NER-enhanced
   TF-IDF.  A lower NER similarity indicates more discriminative document
   vectors, supporting the hypothesis that NER enrichment benefits classification.

2. NER quality on CoNLL-2003 (secondary — validates the NER component)
   Runs dslim/bert-base-NER on a sample of the CoNLL-2003 test split and
   computes strict entity-level P/R/F1 via seqeval.  This is a real benchmark
   against human-annotated ground truth, not a silver-label self-comparison.
   Skipped gracefully if the dataset cannot be downloaded.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)

MODEL_VERSION       = "dslim/bert-base-NER"
SEPARABILITY_SAMPLE = settings.EVAL_SEPARABILITY_SAMPLE
CONLL_SAMPLE        = 500


def run(dry_run: bool = False, log_fn=None) -> dict[str, Any]:
    """
    Execute the evaluation job.

    Parameters
    ----------
    dry_run : bool
        Compute metrics but do not write to MongoDB.

    Returns
    -------
    dict with keys: status, separability, conll_metrics, errors, duration_seconds.
    """
    log = log_fn or (lambda _: None)
    start_time = time.time()
    result: dict[str, Any] = {
        "status":           "success",
        "model_version":    MODEL_VERSION,
        "separability":     None,
        "conll_metrics":    None,
        "errors":           [],
        "duration_seconds": 0,
    }

    try:
        from database.init_db import init_databases
        init_databases()

        # ── 1. Separability evaluation ─────────────────────────────────────
        log("Running separability evaluation (TF-IDF clean vs NER-enhanced)...")
        logger.info("=== Evaluate job started — separability ===")

        try:
            from evaluation.separability_eval import compute_separability
            sep = compute_separability(sample_size=SEPARABILITY_SAMPLE)
            result["separability"] = sep
            log(
                f"Separability: improvement={sep['improvement_pct']:+.1f}%  "
                f"verdict={sep['verdict']}  "
                f"(n={sep['sample_size']})"
            )
            logger.info(
                "Separability: improvement=%.1f%%  verdict=%s  n=%d",
                sep["improvement_pct"], sep["verdict"], sep["sample_size"],
            )
        except Exception as exc:
            msg = f"Separability eval failed: {exc}"
            log(msg)
            logger.exception("Separability evaluation failed")
            result["errors"].append(msg)
            result["status"] = "failed"
            result["duration_seconds"] = round(time.time() - start_time, 2)
            return result

        # ── 2. CoNLL-2003 NER quality evaluation ──────────────────────────
        log(f"Running CoNLL-2003 NER evaluation (sample={CONLL_SAMPLE} sentences)...")
        logger.info("=== Evaluate job — CoNLL-2003 NER quality ===")

        try:
            from evaluation.conll_eval import run_conll_eval
            conll = run_conll_eval(sample_size=CONLL_SAMPLE)
            result["conll_metrics"] = conll
            log(
                f"CoNLL-2003: P={conll['precision']:.3f}  "
                f"R={conll['recall']:.3f}  "
                f"F1={conll['f1']:.3f}  "
                f"(n={conll['sample_size']} sentences)"
            )
            logger.info(
                "CoNLL-2003: P=%.4f  R=%.4f  F1=%.4f  n=%d",
                conll["precision"], conll["recall"], conll["f1"], conll["sample_size"],
            )
            for label, m in conll.get("per_entity", {}).items():
                log(f"  {label:<8} P={m['precision']:.3f}  R={m['recall']:.3f}  F1={m['f1']:.3f}  n={m['support']}")
        except Exception as exc:
            msg = f"CoNLL eval skipped: {exc}"
            log(msg)
            logger.warning("CoNLL-2003 evaluation skipped: %s", exc)
            result["errors"].append(msg)
            # Non-fatal — separability result is still valid

        # ── 3. Persist ─────────────────────────────────────────────────────
        if not dry_run:
            from database.repositories import insert_model_run

            conll = result["conll_metrics"] or {}
            per_entity = conll.get("per_entity", {})
            overall = {
                "precision": conll.get("precision", 0.0),
                "recall":    conll.get("recall",    0.0),
                "f1":        conll.get("f1",        0.0),
                "support":   sum(m.get("support", 0) for m in per_entity.values()),
            }
            metrics_doc = {**per_entity, **({"overall": overall} if conll else {})}

            run_doc: dict[str, Any] = {
                "model_version":     MODEL_VERSION,
                "eval_type":         "separability+conll",
                "metrics":           metrics_doc,
                "separability":      result["separability"],
                "benchmark":         conll.get("benchmark", "conll2003"),
                "conll_sample_size": conll.get("sample_size"),
                "created_at":        datetime.now(timezone.utc).isoformat(),
                "hyperparams": {
                    "model":               MODEL_VERSION,
                    "separability_sample": SEPARABILITY_SAMPLE,
                    "conll_sample":        CONLL_SAMPLE,
                },
                "training_set_size": conll.get("sample_size") or SEPARABILITY_SAMPLE,
            }
            inserted_id = insert_model_run(run_doc)
            log("Results persisted to model_runs")
            logger.info("Eval run persisted (id=%s)", inserted_id)
        else:
            log("Dry run — metrics computed but not persisted")
            logger.info("DRY RUN: metrics computed but not persisted.")

    except Exception as exc:
        logger.exception("Evaluate job failed")
        log(f"Error: {exc}")
        result["status"] = "failed"
        result["errors"].append(str(exc))

    finally:
        result["duration_seconds"] = round(time.time() - start_time, 2)
        log(f"Finished in {result['duration_seconds']:.1f}s — status: {result['status']}")
        logger.info(
            "=== Evaluate job finished (status=%s, duration=%.2fs) ===",
            result["status"],
            result["duration_seconds"],
        )

    return result


__all__ = ["run"]

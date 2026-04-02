"""
Custom Prometheus collector that snapshots MongoDB collection sizes.

Uses the scrape-driven ``CustomCollector`` pattern rather than a background
thread so MongoDB is only queried when Prometheus actually pulls metrics.
A MongoDB outage will not break the ``/prometheus-metrics`` endpoint —
the collector catches all exceptions and yields nothing on failure.
"""

from __future__ import annotations

import logging

from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector

logger = logging.getLogger(__name__)

# Collections to monitor: (db_setting_attr, collection_name, label_db_name)
_COLLECTIONS = [
    ("RAW_DB_NAME",    "articles",     "nlp_raw"),
    ("RAW_DB_NAME",    "quarantine",   "nlp_raw"),
    ("CLEAN_DB_NAME",  "articles",     "nlp_clean"),
    ("NER_DB_NAME",    "ner_articles", "nlp_ner"),
    ("MODELS_DB_NAME", "model_runs",   "nlp_models"),
]


class MongoCollector(Collector):
    """Yields current document counts for all pipeline MongoDB collections."""

    def collect(self):
        gauge = GaugeMetricFamily(
            "mongo_collection_size",
            "Number of documents in a MongoDB collection",
            labels=["database", "collection"],
        )
        try:
            from database.connection import get_client
            from config.settings import settings

            client = get_client()
            for db_attr, col_name, db_label in _COLLECTIONS:
                db_name = getattr(settings, db_attr)
                try:
                    count = client[db_name][col_name].count_documents({})
                    gauge.add_metric([db_label, col_name], float(count))
                except Exception as e:
                    logger.debug("Could not count %s.%s: %s", db_label, col_name, e)
        except Exception as e:
            logger.debug("MongoCollector skipped (DB unavailable): %s", e)

        yield gauge

        # ── Latest evaluation run metrics ─────────────────────────────────────
        precision_g = GaugeMetricFamily(
            "eval_precision",
            "NER evaluation precision for the latest run",
            labels=["entity_type"],
        )
        recall_g = GaugeMetricFamily(
            "eval_recall",
            "NER evaluation recall for the latest run",
            labels=["entity_type"],
        )
        f1_g = GaugeMetricFamily(
            "eval_f1",
            "NER evaluation F1 score for the latest run",
            labels=["entity_type"],
        )
        timestamp_g = GaugeMetricFamily(
            "eval_last_run_timestamp",
            "Unix timestamp of the most recent evaluation run",
        )
        try:
            from database.repositories import get_latest_model_run
            from datetime import datetime, timezone

            run = get_latest_model_run()
            if run:
                for entity_type, scores in run.get("metrics", {}).items():
                    precision_g.add_metric([entity_type], float(scores.get("precision", 0)))
                    recall_g.add_metric([entity_type], float(scores.get("recall", 0)))
                    f1_g.add_metric([entity_type], float(scores.get("f1", 0)))
                created_at = run.get("created_at")
                if created_at:
                    ts = datetime.fromisoformat(created_at).replace(tzinfo=timezone.utc).timestamp()
                    timestamp_g.add_metric([], ts)
        except Exception as e:
            logger.debug("EvalCollector skipped: %s", e)

        yield precision_g
        yield recall_g
        yield f1_g
        yield timestamp_g

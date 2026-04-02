"""
Central Prometheus metric registry for the NLP Article Analyzer.

All application-level metrics are defined here so they can be imported
by both the FastAPI app (middleware, endpoints) and the job modules
(classify, evaluate) without circular imports.

Jobs use a guarded import pattern:
    try:
        from web.prometheus_metrics import SOME_METRIC
    except ImportError:
        pass

This ensures jobs remain runnable outside the API context (e.g. via
scripts/run_job.py) without requiring prometheus-client to be installed.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# API metrics
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)

# ---------------------------------------------------------------------------
# Job metrics
# ---------------------------------------------------------------------------

JOB_DURATION_SECONDS = Histogram(
    "job_duration_seconds",
    "Job execution duration in seconds",
    ["job_name", "status"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800],
)

JOB_RUNS_TOTAL = Counter(
    "job_runs_total",
    "Total job executions",
    ["job_name", "status"],
)

# ---------------------------------------------------------------------------
# NER pipeline metrics
# ---------------------------------------------------------------------------

NER_ARTICLES_PROCESSED_TOTAL = Counter(
    "ner_articles_processed_total",
    "Total articles processed by the NER pipeline",
)

NER_ENTITIES_EXTRACTED_TOTAL = Counter(
    "ner_entities_extracted_total",
    "Total named entities extracted",
    ["entity_type"],
)

NER_BATCH_DURATION_SECONDS = Histogram(
    "ner_batch_duration_seconds",
    "Duration of a single NER batch inference call",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
)

# ---------------------------------------------------------------------------
# Evaluation metrics  (Gauges — hold the most recent run's values)
# ---------------------------------------------------------------------------

EVAL_PRECISION = Gauge(
    "eval_precision",
    "NER evaluation precision for the latest run",
    ["entity_type"],
)

EVAL_RECALL = Gauge(
    "eval_recall",
    "NER evaluation recall for the latest run",
    ["entity_type"],
)

EVAL_F1 = Gauge(
    "eval_f1",
    "NER evaluation F1 score for the latest run",
    ["entity_type"],
)

EVAL_LAST_RUN_TIMESTAMP = Gauge(
    "eval_last_run_timestamp",
    "Unix timestamp of the most recent evaluation run",
)

# ---------------------------------------------------------------------------
# MongoDB collection sizes  (populated by MongoCollector on each scrape)
# ---------------------------------------------------------------------------

MONGO_COLLECTION_SIZE = Gauge(
    "mongo_collection_size",
    "Number of documents in a MongoDB collection",
    ["database", "collection"],
)

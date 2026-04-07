"""
Central Prometheus metric registry for the NLP Article Analyzer.

All application-level metrics are defined here so they can be imported
by both the FastAPI app (middleware, endpoints) and the job modules
(classify, evaluate) without circular imports.

This module includes a thread-safe helper to prevent 'Duplicated timeseries'
errors if the module is loaded via different paths (e.g., 'web' vs 'src.web').
"""

from __future__ import annotations

import logging
from prometheus_client import REGISTRY, Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper: Get or Create Metric
# ---------------------------------------------------------------------------

def _get_metric(cls, name, documentation, labelnames=(), **kwargs):
    """
    Safely get an existing metric from the global registry or create a new one.
    Prevents ValueError: Duplicated timeseries.
    """
    # Check if metric already exists in the global registry
    # Note: REGISTRY._names_to_collectors is private but the most reliable way 
    # to check for existing metrics in prometheus-client.
    if hasattr(REGISTRY, "_names_to_collectors") and name in REGISTRY._names_to_collectors:
        collector = REGISTRY._names_to_collectors[name]
        # Verify it's the same type (e.g. Counter vs Gauge)
        if isinstance(collector, cls):
            return collector
        # If it's a different type, we can't reuse it (this shouldn't happen)
        logger.warning("Metric %s exists but is of type %s, expected %s", name, type(collector), cls)

    # Otherwise create new one
    return cls(name, documentation, labelnames=labelnames, **kwargs)


# ---------------------------------------------------------------------------
# API metrics
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = _get_metric(
    Counter,
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = _get_metric(
    Histogram,
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)

# ---------------------------------------------------------------------------
# Job metrics
# ---------------------------------------------------------------------------

JOB_DURATION_SECONDS = _get_metric(
    Histogram,
    "job_duration_seconds",
    "Job execution duration in seconds",
    ["job_name", "status"],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800],
)

JOB_RUNS_TOTAL = _get_metric(
    Counter,
    "job_runs_total",
    "Total job executions",
    ["job_name", "status"],
)

# ---------------------------------------------------------------------------
# NER pipeline metrics
# ---------------------------------------------------------------------------

NER_ARTICLES_PROCESSED_TOTAL = _get_metric(
    Counter,
    "ner_articles_processed_total",
    "Total articles processed by the NER pipeline",
)

NER_ENTITIES_EXTRACTED_TOTAL = _get_metric(
    Counter,
    "ner_entities_extracted_total",
    "Total named entities extracted",
    ["entity_type"],
)

NER_BATCH_DURATION_SECONDS = _get_metric(
    Histogram,
    "ner_batch_duration_seconds",
    "Duration of a single NER batch inference call",
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30],
)

# ---------------------------------------------------------------------------
# MongoDB collection sizes
# ---------------------------------------------------------------------------

# Note: Handled dynamically by MongoCollector in web/mongo_collector.py

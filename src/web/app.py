"""
FastAPI web service for NLP article analyzer.

Provides REST endpoints for:
- Stack health and collection statistics
- Job management (trigger, status)
- Article queries (clean + NER)
- TF-IDF comparison (clean text vs NER-enhanced text)
"""

from __future__ import annotations

import base64
import logging
import re
import threading
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict

from web.middleware import PrometheusMiddleware

from config.settings import settings
from database.repositories import (
    get_clean_collection,
    count_clean_articles,
    count_raw_articles_by_rank,
    insert_job,
    get_job_by_id,
    list_jobs as repo_list_jobs,
    update_job,
    append_job_log,
    mark_job_cancelled,
)
from database.connection import get_client

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    database: str
    timestamp: str
    mongodb: str
    collections: dict[str, int]


class JobTriggerRequest(BaseModel):
    job_name: str
    date: str | None = None
    dry_run: bool = False


class JobTriggerResponse(BaseModel):
    job_id: str
    job_name: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    job_name: str
    status: str
    started_at: str
    finished_at: str | None
    result: dict | None
    logs: list[str] = []


class ArticleResponse(BaseModel):
    url: str
    title: str
    feed: str
    pub: str | None = None
    lang: str | None = None


class ArticleListResponse(BaseModel):
    items: list[ArticleResponse]
    total: int
    skip: int
    limit: int


class StatsResponse(BaseModel):
    clean_count: int
    raw_counts: dict[str, int]
    timestamp: str


class MetricsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    model_version: str | None = None
    last_updated: str | None = None
    # CoNLL-2003 NER quality (secondary — model validation)
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None
    per_entity: dict[str, dict] | None = None
    sample_size: int | None = None
    benchmark: str | None = None
    # Separability (primary — research evaluation)
    separability: dict | None = None


# ──────────────────────────────────────────────────────────────
# Lifespan
# ──────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        from database.init_db import init_databases
        init_databases()
        logger.info("Databases initialized on startup")
    except Exception as e:
        logger.error("Failed to initialize databases on startup: %s", e)
        raise

    try:
        from prometheus_client import REGISTRY
        from web.mongo_collector import MongoCollector
        REGISTRY.register(MongoCollector())
        logger.info("MongoCollector registered with Prometheus")
    except Exception as e:
        logger.warning("Could not register MongoCollector: %s", e)

    yield
    # Shutdown
    try:
        from database.connection import close_connection
        close_connection()
        logger.info("MongoDB connection closed on shutdown")
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
# App + CORS
# ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="NLP Article Analyzer API",
    description="REST API for the NLP article pipeline — scrape, clean, NER, compare",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(PrometheusMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://frontend:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc.body)},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ──────────────────────────────────────────────────────────────
# Health + Stats
# ──────────────────────────────────────────────────────────────

@app.get("/", tags=["root"])
def read_root() -> dict:
    return {"name": "NLP Article Analyzer API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health", tags=["health"], response_model=HealthResponse)
async def health() -> HealthResponse:
    """Full stack health check — MongoDB ping + collection counts."""
    from config.settings import settings
    from database.connection import get_client

    mongo_status = "healthy"
    counts: dict[str, int] = {}
    try:
        client = get_client()
        client.admin.command("ping")
        counts = {
            "raw":        client[settings.RAW_DB_NAME][settings.RAW_COLLECTION].count_documents({}),
            "clean":      client[settings.CLEAN_DB_NAME][settings.CLEAN_COLLECTION].count_documents({}),
            "ner":        client[settings.NER_DB_NAME][settings.NER_COLLECTION].count_documents({}),
            "quarantine": client[settings.RAW_DB_NAME].get_collection("quarantine").count_documents({}),
        }
    except Exception as e:
        mongo_status = f"unhealthy: {e}"

    return HealthResponse(
        status="healthy" if mongo_status == "healthy" else "degraded",
        database=mongo_status,
        timestamp=datetime.utcnow().isoformat() + "Z",
        mongodb=mongo_status,
        collections=counts,
    )


@app.get("/stats", tags=["stats"])
async def get_stats() -> dict:
    """Collection document counts — lightweight version of /health."""
    from config.settings import settings
    from database.connection import get_client

    client = get_client()

    raw_by_rank = {}
    try:
        pipeline = [{"$group": {"_id": "$rank", "count": {"$sum": 1}}}]
        for doc in client[settings.RAW_DB_NAME][settings.RAW_COLLECTION].aggregate(pipeline):
            raw_by_rank[str(doc["_id"])] = doc["count"]
    except Exception:
        pass

    return {
        "raw":        client[settings.RAW_DB_NAME][settings.RAW_COLLECTION].count_documents({}),
        "clean":      client[settings.CLEAN_DB_NAME][settings.CLEAN_COLLECTION].count_documents({}),
        "ner":        client[settings.NER_DB_NAME][settings.NER_COLLECTION].count_documents({}),
        "quarantine": client[settings.RAW_DB_NAME].get_collection("quarantine").count_documents({}),
        "raw_by_rank": raw_by_rank,
        "jobs_tracked": client[settings.MODELS_DB_NAME]["jobs"].count_documents({}),
    }


# ──────────────────────────────────────────────────────────────
# Jobs
# ──────────────────────────────────────────────────────────────

_stop_events: dict[str, threading.Event] = {}
_stop_events_lock = threading.Lock()


def _append_log(job_id: str, message: str) -> None:
    append_job_log(job_id, message)


def _run_job_thread(job_id: str, job_name: str, dry_run: bool, stop_event: threading.Event) -> None:
    """Execute a job in a background thread and record result."""
    import time as _time

    job = get_job_by_id(job_id)
    if not job or job.get("cancel_requested"):
        return

    update_job(job_id, {"status": "running"})
    _start = _time.perf_counter()
    _status = "failed"

    def _log(msg: str) -> None:
        _append_log(job_id, msg)

    try:
        from jobs import run_job

        result = run_job(job_name, dry_run=dry_run, log_fn=_log, stop_event=stop_event)

        latest_job = get_job_by_id(job_id)
        if latest_job and latest_job.get("cancel_requested"):
            _status = "cancelled"
        else:
            _status = "success" if result.get("status") == "success" else "failed"

        update_job(
            job_id,
            {
                "status": _status,
                "result": result,
                "finished_at": datetime.utcnow().isoformat() + "Z",
            },
        )
    except Exception as e:
        latest_job = get_job_by_id(job_id)
        if latest_job and not latest_job.get("cancel_requested"):
            _status = "failed"
            update_job(
                job_id,
                {
                    "status": "failed",
                    "result": {"error": str(e)},
                    "finished_at": datetime.utcnow().isoformat() + "Z",
                },
            )
        else:
            _status = "cancelled"
    finally:
        _duration = _time.perf_counter() - _start
        try:
            from web.prometheus_metrics import JOB_DURATION_SECONDS, JOB_RUNS_TOTAL

            JOB_DURATION_SECONDS.labels(job_name=job_name, status=_status).observe(_duration)
            JOB_RUNS_TOTAL.labels(job_name=job_name, status=_status).inc()
        except Exception:
            pass


@app.post("/jobs/trigger", tags=["jobs"], response_model=JobTriggerResponse)
async def trigger_job(request: JobTriggerRequest) -> JobTriggerResponse:
    """Trigger a pipeline job asynchronously."""
    valid = {"scrape", "clean", "ner", "evaluate"}
    if request.job_name not in valid:
        raise HTTPException(400, f"Invalid job. Must be one of: {', '.join(sorted(valid))}")

    job_id = str(uuid.uuid4())[:8]
    stop_event = threading.Event()
    with _stop_events_lock:
        _stop_events[job_id] = stop_event
    job_doc = {
        "job_id":      job_id,
        "job_name":    request.job_name,
        "status":      "queued",
        "started_at":  datetime.utcnow().isoformat() + "Z",
        "finished_at": None,
        "result":      None,
        "logs":        [],
    }
    insert_job(job_doc)

    t = threading.Thread(
        target=_run_job_thread,
        args=(job_id, request.job_name, request.dry_run, stop_event),
        daemon=True,
    )
    t.start()

    return JobTriggerResponse(
        job_id=job_id,
        job_name=request.job_name,
        status="queued",
        message=f"Job {request.job_name} queued with id={job_id}",
    )


@app.get("/jobs/{job_id}", tags=["jobs"], response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Poll job status by ID."""
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    return JobStatusResponse(**job)


@app.get("/jobs", tags=["jobs"])
async def list_jobs() -> dict:
    """List all tracked jobs (most recent first)."""
    jobs = repo_list_jobs(50)
    return {"jobs": jobs}


@app.post("/jobs/{job_id}/cancel", tags=["jobs"])
async def cancel_job(job_id: str) -> dict:
    """Cancel a queued or running job."""
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} not found")
    if job["status"] not in ("queued", "running"):
        raise HTTPException(400, f"Job {job_id} is already {job['status']}")

    with _stop_events_lock:
        ev = _stop_events.get(job_id)
    if ev:
        ev.set()
    mark_job_cancelled(job_id)
    return {"job_id": job_id, "status": "cancelled"}


# ──────────────────────────────────────────────────────────────
# Articles
# ──────────────────────────────────────────────────────────────


@app.get("/articles", tags=["articles"])
async def list_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    collection: str = Query("clean", pattern="^(clean|ner)$"),
    search: str | None = Query(None, max_length=100),
) -> dict:
    """Paginated article list from clean or ner collection."""
    from database.repositories import get_clean_collection, get_ner_collection

    col = get_ner_collection() if collection == "ner" else get_clean_collection()

    query: dict = {}
    if search:
        safe_search = re.escape(search)
        query["$or"] = [
            {"title": {"$regex": safe_search, "$options": "i"}},
            {"feed": {"$regex": safe_search, "$options": "i"}},
        ]

    total = col.count_documents(query)
    projection = {"url": 1, "title": 1, "feed": 1, "pub": 1, "lang": 1,
                  "doc_stats": 1, "cleaning_flags": 1, "signal_counts": 1}
    if collection == "ner":
        projection["entities"] = 1

    items = list(col.find(query, projection).sort("pub", -1).skip(skip).limit(limit))
    for item in items:
        item.pop("_id", None)
        if "entities" in item:
            item["entity_count"] = len(item["entities"])
            item.pop("entities", None)

    return {"items": items, "total": total, "skip": skip, "limit": limit}


@app.get("/articles/ner/{url_b64}", tags=["articles"])
async def get_ner_article(url_b64: str) -> dict:
    """Get NER-enriched article by base64-encoded URL."""
    try:
        url = base64.b64decode(url_b64 + "==").decode("utf-8")
    except Exception:
        raise HTTPException(400, "Invalid base64 URL encoding")

    from database.repositories import get_clean_collection, get_ner_collection

    clean = get_clean_collection().find_one({"url": url}, {"_id": 0})
    if not clean:
        raise HTTPException(404, "Article not found in clean collection")

    ner = get_ner_collection().find_one({"url": url}, {"_id": 0})

    return {"clean": clean, "ner": ner}


# ──────────────────────────────────────────────────────────────
# TF-IDF Comparison (thesis core feature)
# ──────────────────────────────────────────────────────────────


@app.get("/compare/tfidf", tags=["compare"])
async def tfidf_comparison(
    sample_size: int = Query(200, ge=10, le=5000),
) -> dict:
    """
    Compute TF-IDF comparison: clean preprocessed text vs NER-enhanced text.

    NER-enhanced text replaces entity spans with TYPE_word tokens
    (e.g. "New York" → "LOC_New_York"), making entity mentions single
    discriminative features for TF-IDF.

    Returns top-25 terms and scores for both versions, plus entity distribution.
    """
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

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
        raise HTTPException(
            503,
            "No NER-enriched articles available yet. Run the NER job first.",
        )

    clean_texts: list[str] = []
    ner_texts: list[str] = []
    entity_dist: dict[str, int] = defaultdict(int)

    for a in articles:
        clean_texts.append(a.get("preprocessed_text") or "")

        ner_pre = a.get("ner_preprocessed_text")
        if not ner_pre:
            ner_pre = build_ner_preprocessed_text(
                a.get("body") or "",
                a.get("entities", []),
            )
        ner_texts.append(ner_pre)

        for ent in a.get("entities", []):
            entity_dist[ent.get("label", "MISC")] += 1

    # Fit TF-IDF vectorizers
    top_n = 25
    vect_clean = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True)
    vect_ner   = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, lowercase=False)

    try:
        mat_clean = vect_clean.fit_transform(clean_texts)
        mat_ner   = vect_ner.fit_transform(ner_texts)
    except ValueError as e:
        raise HTTPException(500, f"TF-IDF computation failed: {e}")

    mean_clean = np.asarray(mat_clean.mean(axis=0)).flatten()
    mean_ner   = np.asarray(mat_ner.mean(axis=0)).flatten()

    terms_clean = vect_clean.get_feature_names_out()
    terms_ner   = vect_ner.get_feature_names_out()

    top_clean_idx = mean_clean.argsort()[-top_n:][::-1]
    top_ner_idx   = mean_ner.argsort()[-top_n:][::-1]

    ner_labels = {"PER_", "ORG_", "LOC_", "MISC_"}

    def is_ner_term(t: str) -> bool:
        return any(t.startswith(p) for p in ner_labels)

    return {
        "sample_size":    len(articles),
        "clean_top_terms": [
            {"term": terms_clean[i], "score": float(mean_clean[i]), "is_ner": False}
            for i in top_clean_idx
        ],
        "ner_top_terms": [
            {"term": terms_ner[i], "score": float(mean_ner[i]), "is_ner": is_ner_term(terms_ner[i])}
            for i in top_ner_idx
        ],
        "entity_distribution":  dict(entity_dist),
        "clean_vocab_size": int(mat_clean.shape[1]),
        "ner_vocab_size":   int(mat_ner.shape[1]),
        "ner_token_ratio":  round(
            sum(1 for t in terms_ner if is_ner_term(t)) / max(len(terms_ner), 1), 3
        ),
    }


# ──────────────────────────────────────────────────────────────
# Separability Analysis
# ──────────────────────────────────────────────────────────────


@app.get("/compare/separability", tags=["compare"])
async def separability_analysis(
    sample_size: int = Query(200, ge=10, le=1000),
) -> dict:
    """
    Compute document separability metrics for clean vs NER-enhanced TF-IDF.

    Mean pairwise cosine similarity across document pairs — lower values indicate
    more discriminative/separable document vectors, which should benefit classification.
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
        raise HTTPException(503, "No NER-enriched articles available yet.")

    clean_texts = [a.get("preprocessed_text") or "" for a in articles]
    ner_texts = [
        a.get("ner_preprocessed_text")
        or build_ner_preprocessed_text(a.get("body") or "", a.get("entities", []))
        for a in articles
    ]

    vect_clean = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True)
    vect_ner   = TfidfVectorizer(ngram_range=(1, 2), min_df=3, sublinear_tf=True, lowercase=False)

    try:
        mat_clean = vect_clean.fit_transform(clean_texts)
        mat_ner   = vect_ner.fit_transform(ner_texts)
    except ValueError as e:
        raise HTTPException(500, f"TF-IDF computation failed: {e}")

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


# ──────────────────────────────────────────────────────────────
# Metrics
# ──────────────────────────────────────────────────────────────


@app.get("/metrics", tags=["metrics"], response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Return the latest evaluation results (separability + CoNLL-2003 NER quality)."""
    from evaluation.sample_loader import load_latest_run_metrics

    run = load_latest_run_metrics()
    if run is None:
        return MetricsResponse()

    metrics = run.get("metrics", {})
    overall = metrics.get("overall", {})

    # Strip the overall key from per_entity so it only contains label-level data
    per_entity = {k: v for k, v in metrics.items() if k != "overall"} or None

    return MetricsResponse(
        model_version=run.get("model_version"),
        last_updated=run.get("created_at"),
        precision=overall.get("precision") or None,
        recall=overall.get("recall") or None,
        f1=overall.get("f1") or None,
        per_entity=per_entity or None,
        sample_size=run.get("conll_sample_size") or run.get("training_set_size"),
        benchmark=run.get("benchmark"),
        separability=run.get("separability"),
    )


# ──────────────────────────────────────────────────────────────
# Prometheus scrape endpoint
# ──────────────────────────────────────────────────────────────


@app.get("/prometheus-metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus text-format metrics endpoint — scraped by Prometheus every 15s."""
    from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)



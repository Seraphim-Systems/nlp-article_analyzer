"""
FastAPI web service for NLP article analyzer.

Provides REST endpoints for:
- Job management (trigger, status)
- Article queries
- Model metrics
- Health checks

This is expanded in Phase 5 with full implementations.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Pydantic response models
# ──────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    timestamp: str


class JobTriggerRequest(BaseModel):
    job_name: str
    date: str | None = None
    dry_run: bool = False


class JobTriggerResponse(BaseModel):
    job_id: str
    job_name: str
    status: str
    message: str


class ArticleResponse(BaseModel):
    url: str
    title: str
    feed: str
    rank: int | None = None


class MetricsResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_version: str | None = None
    last_updated: str | None = None
    precision: float | None = None
    recall: float | None = None
    f1: float | None = None


# ──────────────────────────────────────────────────────────────
# FastAPI app
# ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="NLP Article Analyzer API",
    description="REST API for article scraping, cleaning, classification, and evaluation",
    version="0.1.0",
)


@app.get("/", tags=["root"])
def read_root() -> dict:
    """Root endpoint."""
    return {
        "name": "NLP Article Analyzer API",
        "version": "0.1.0",
        "docs_url": "/docs",
        "health_url": "/health",
    }


@app.get("/health", tags=["health"], response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.post("/jobs/trigger", tags=["jobs"], response_model=JobTriggerResponse)
async def trigger_job(request: JobTriggerRequest) -> JobTriggerResponse:
    """
    Trigger a job (scrape, clean, classify, or evaluate).

    Currently synchronous; returns result immediately.

    Query parameters:
    - job_name: One of scrape, clean, classify, evaluate
    - date: (optional) ISO date for scrape/classify (YYYY-MM-DD)
    - dry_run: (optional) Boolean to preview changes without persisting

    Phase 5: To be implemented with full job orchestration.
    """
    return JobTriggerResponse(
        job_id="stub-001",
        job_name=request.job_name,
        status="not_implemented",
        message="Job triggering will be implemented in Phase 5",
    )


@app.get("/articles", tags=["articles"])
async def list_articles(
    skip: int = 0, limit: int = 20, rank: int | None = None
) -> dict:
    """
    List articles from the clean collection.

    Query parameters:
    - skip: Pagination offset (default: 0)
    - limit: Results per page (default: 20)
    - rank: Filter by rank (0=clean, 1=incomplete)

    Phase 5: To be implemented with MongoDB queries.
    """
    return {
        "items": [],
        "skip": skip,
        "limit": limit,
        "total": 0,
        "message": "Article querying will be implemented in Phase 5",
    }


@app.get("/metrics", tags=["metrics"], response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """
    Get current model performance metrics.

    Returns the latest model run results including precision, recall, F1.

    Phase 5: To be implemented with metrics retrieval from DB.
    """
    return MetricsResponse(
        model_version=None,
        last_updated=None,
        precision=None,
        recall=None,
        f1=None,
    )


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize databases on application startup."""
    try:
        from database.init_db import init_databases

        init_databases()
        logger.info("Databases initialized on startup")
    except Exception as e:
        logger.error("Failed to initialize databases: %s", e)
        raise

"""
FastAPI web service for NLP article analyzer.

Provides REST endpoints for:
- Job management (trigger, status)
- Article queries
- Model metrics
- Health checks
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from config.settings import settings
from database.repositories import (
    get_clean_collection,
    count_clean_articles,
    count_raw_articles_by_rank,
)
from database.connection import get_client

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Pydantic response models
# ──────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str
    database: str
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

# Enable CORS for React frontend
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

if settings.ENVIRONMENT == "development":
    origins.append("*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    """Health check endpoint with database ping."""
    db_status = "connected"
    try:
        get_client().admin.command("ping")
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        db_status = "disconnected"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/stats", tags=["stats"], response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Get aggregate article statistics."""
    try:
        clean_count = count_clean_articles()
        raw_counts_raw = count_raw_articles_by_rank()
        
        # Convert numeric keys to strings for JSON
        raw_counts = {str(k) if k is not None else "unranked": v for k, v in raw_counts_raw.items()}
        
        return StatsResponse(
            clean_count=clean_count,
            raw_counts=raw_counts,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
    except Exception as e:
        logger.exception("Failed to fetch stats")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/jobs/trigger", tags=["jobs"], response_model=JobTriggerResponse)
async def trigger_job(request: JobTriggerRequest) -> JobTriggerResponse:
    """Trigger a job (Phase 5 implementation placeholder)."""
    return JobTriggerResponse(
        job_id="stub-001",
        job_name=request.job_name,
        status="not_implemented",
        message="Job triggering will be implemented in Phase 5",
    )


@app.get("/articles", tags=["articles"], response_model=ArticleListResponse)
async def list_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> ArticleListResponse:
    """List articles from the clean collection with pagination."""
    try:
        col = get_clean_collection()
        total = col.count_documents({})
        
        cursor = col.find({}, {"url": 1, "title": 1, "feed": 1, "pub": 1, "lang": 1})
        cursor = cursor.sort("pub", -1).skip(skip).limit(limit)
        
        items = []
        for doc in cursor:
            items.append(ArticleResponse(
                url=doc["url"],
                title=doc.get("title", "Untitled"),
                feed=doc.get("feed", "Unknown"),
                pub=doc.get("pub"),
                lang=doc.get("lang")
            ))
            
        return ArticleListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit
        )
    except Exception as e:
        logger.exception("Failed to list articles")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics", tags=["metrics"], response_model=MetricsResponse)
async def get_metrics() -> MetricsResponse:
    """Get current model performance metrics (Phase 5 placeholder)."""
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

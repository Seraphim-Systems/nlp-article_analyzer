"""
Prometheus instrumentation middleware for FastAPI.

Records HTTP request count and latency for every request, labelled by
HTTP method, normalised path, and response status code.

Path normalisation
------------------
Raw paths like ``/jobs/abc12345`` or ``/articles/ner/aHR0cHM6...`` would
create unbounded label cardinality in Prometheus.  ``_normalize_path``
collapses dynamic segments into fixed placeholders before they reach the
label so the metric series stays manageable.
"""

from __future__ import annotations

import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Matches 8-char hex job IDs (e.g. "a3f2c891")
_JOB_ID_RE    = re.compile(r"^[0-9a-f]{8}$")
# Matches base64url segments used for article URL encoding
_BASE64_RE    = re.compile(r"^[A-Za-z0-9+/\-_]{20,}={0,2}$")


def _normalize_path(path: str) -> str:
    """
    Replace dynamic path segments with fixed placeholders.

    Examples
    --------
    /jobs/a3f2c891          → /jobs/{job_id}
    /articles/ner/aHR0cH…  → /articles/ner/{url_b64}
    /articles               → /articles
    """
    parts = path.strip("/").split("/")
    normalised = []
    for i, part in enumerate(parts):
        if _JOB_ID_RE.match(part):
            normalised.append("{job_id}")
        elif _BASE64_RE.match(part):
            normalised.append("{url_b64}")
        else:
            normalised.append(part)
    return "/" + "/".join(normalised)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record request count and duration for every HTTP request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        try:
            from web.prometheus_metrics import (
                HTTP_REQUEST_DURATION_SECONDS,
                HTTP_REQUESTS_TOTAL,
            )
            path   = _normalize_path(request.url.path)
            method = request.method
            status = str(response.status_code)

            HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=status).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)
        except Exception:
            pass  # never let metrics collection break a real request

        return response

"""Tests for the FastAPI web application endpoints."""

from __future__ import annotations

import base64
import sys
import types

import pytest
from unittest.mock import MagicMock, patch

# Stub heavy deps before any project import
for _mod in [
    "spacy", "nltk", "nltk.corpus", "torch", "transformers",
    "sklearn", "sklearn.feature_extraction", "sklearn.feature_extraction.text",
    "sklearn.metrics", "sklearn.metrics.pairwise",
    "numpy", "prometheus_client", "schedule",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

# nltk.corpus needs a stopwords stub so preprocessing/__init__.py can import
_nltk_corpus = sys.modules["nltk.corpus"]
_nltk_corpus.stopwords = type("sw", (), {"words": staticmethod(lambda lang: [])})()

# sklearn stubs for lazy imports inside endpoints
_sft = sys.modules["sklearn.feature_extraction.text"]
_sft.TfidfVectorizer = MagicMock  # will be overridden per-test

_smp = sys.modules["sklearn.metrics.pairwise"]
_smp.cosine_similarity = MagicMock

# numpy stubs — only patch if this is a fake stub module, not the real numpy
_np = sys.modules["numpy"]
if not hasattr(_np, "ndarray"):
    _np.asarray = lambda x, *args, **kwargs: x
    _np.triu_indices = lambda n, k=0: (list(range(n)), list(range(n)))

# Stub prometheus_client exports used by middleware/metrics
_prom = sys.modules["prometheus_client"]
_prom.Counter = lambda *a, **kw: type("C", (), {"labels": lambda s, **k: type("L", (), {"inc": lambda s: None})()})()
_prom.Histogram = lambda *a, **kw: type("H", (), {"labels": lambda s, **k: type("L", (), {"observe": lambda s, v: None})()})()
_prom.Gauge = lambda *a, **kw: type("G", (), {"labels": lambda s, **k: type("L", (), {"set": lambda s, v: None})()})()
_prom.CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
_prom.generate_latest = lambda: b"# HELP fake_metric\n"
_prom.REGISTRY = type("R", (), {"register": lambda s, c: None})()

from contextlib import asynccontextmanager

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------



@pytest.fixture()
def client():
    from web.app import app

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def noop(a):
        yield

    app.router.lifespan_context = noop
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.router.lifespan_context = original_lifespan


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------

class TestRoot:
    def test_returns_name_version_docs(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealth:
    def test_healthy(self, client):
        mock_client = MagicMock()
        mock_client.admin.command.return_value = {"ok": 1}
        mock_client.__getitem__.return_value.__getitem__.return_value.count_documents.return_value = 42
        mock_client.__getitem__.return_value.get_collection.return_value.count_documents.return_value = 5

        with patch("database.connection.get_client", return_value=mock_client):
            r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert "collections" in data
        assert len(data["collections"]) == 4

    def test_degraded_on_ping_failure(self, client):
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = Exception("connection refused")

        with patch("database.connection.get_client", return_value=mock_client):
            r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "degraded"
        assert "connection refused" in data["database"]


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_returns_expected_keys(self, client):
        mock_client = MagicMock()
        mock_client.__getitem__.return_value.__getitem__.return_value.count_documents.return_value = 10
        mock_client.__getitem__.return_value.get_collection.return_value.count_documents.return_value = 3
        mock_client.__getitem__.return_value.__getitem__.return_value.aggregate.return_value = [
            {"_id": "1", "count": 5},
            {"_id": "2", "count": 3},
        ]

        with patch("database.connection.get_client", return_value=mock_client):
            r = client.get("/stats")
        assert r.status_code == 200
        data = r.json()
        for key in ("raw", "clean", "ner", "quarantine", "raw_by_rank", "jobs_tracked"):
            assert key in data

    def test_aggregate_failure_returns_empty_raw_by_rank(self, client):
        mock_client = MagicMock()
        mock_client.__getitem__.return_value.__getitem__.return_value.count_documents.return_value = 0
        mock_client.__getitem__.return_value.get_collection.return_value.count_documents.return_value = 0
        mock_client.__getitem__.return_value.__getitem__.return_value.aggregate.side_effect = Exception("fail")

        with patch("database.connection.get_client", return_value=mock_client):
            r = client.get("/stats")
        assert r.status_code == 200
        assert r.json()["raw_by_rank"] == {}


# ---------------------------------------------------------------------------
# POST /jobs/trigger
# ---------------------------------------------------------------------------

class TestJobTrigger:
    def test_valid_job_name(self, client):
        with patch("web.app._run_job_thread"), patch("web.app.insert_job"):
            r = client.post("/jobs/trigger", json={"job_name": "scrape"})
        assert r.status_code == 200
        data = r.json()
        assert "job_id" in data
        assert data["status"] == "queued"

    def test_invalid_job_name(self, client):
        r = client.post("/jobs/trigger", json={"job_name": "invalid_job"})
        assert r.status_code == 400

    def test_jobs_dict_updated(self, client):
        with patch("web.app._run_job_thread"), \
             patch("web.app.insert_job") as mock_insert:
            r = client.post("/jobs/trigger", json={"job_name": "clean"})
        job_id = r.json()["job_id"]
        assert mock_insert.called
        inserted = mock_insert.call_args[0][0]
        assert inserted["job_id"] == job_id


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------

class TestJobStatus:
    def test_known_job(self, client):
        job_doc = {
            "job_id": "abc123",
            "job_name": "scrape",
            "status": "running",
            "started_at": "2024-01-01T00:00:00Z",
            "finished_at": None,
            "result": None,
            "logs": [],
        }
        with patch("web.app.get_job_by_id", return_value=job_doc):
            r = client.get("/jobs/abc123")
        assert r.status_code == 200
        data = r.json()
        assert data["job_id"] == "abc123"
        assert data["job_name"] == "scrape"
        assert data["status"] == "running"
        assert "started_at" in data
        assert "finished_at" in data
        assert "result" in data
        assert "logs" in data

    def test_unknown_job(self, client):
        with patch("web.app.get_job_by_id", return_value=None):
            r = client.get("/jobs/unknown")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /jobs
# ---------------------------------------------------------------------------

class TestListJobs:
    def test_returns_sorted_jobs(self, client):
        jobs_data = [
            {"job_id": f"j{i}", "job_name": "scrape", "status": "success",
             "started_at": f"2024-01-0{i + 1}T00:00:00Z", "finished_at": None,
             "result": None, "logs": []}
            for i in range(3)
        ]
        with patch("web.app.repo_list_jobs", return_value=jobs_data):
            r = client.get("/jobs")
        assert r.status_code == 200
        data = r.json()
        assert "jobs" in data
        assert len(data["jobs"]) == 3

    def test_max_50_jobs(self, client):
        jobs_data = [
            {"job_id": f"j{i:03d}", "job_name": "scrape", "status": "success",
             "started_at": f"2024-01-01T00:{i:02d}:00Z", "finished_at": None,
             "result": None, "logs": []}
            for i in range(50)
        ]
        with patch("web.app.repo_list_jobs", return_value=jobs_data):
            r = client.get("/jobs")
        assert len(r.json()["jobs"]) <= 50


# ---------------------------------------------------------------------------
# POST /jobs/{job_id}/cancel
# ---------------------------------------------------------------------------

class TestCancelJob:
    def test_cancel_queued(self, client):
        job_doc = {
            "job_id": "c1", "job_name": "scrape", "status": "queued",
            "started_at": "2024-01-01T00:00:00Z", "finished_at": None,
            "result": None, "logs": [],
        }
        with patch("web.app.get_job_by_id", return_value=job_doc), \
             patch("web.app.mark_job_cancelled") as mock_cancel:
            r = client.post("/jobs/c1/cancel")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"
        mock_cancel.assert_called_once_with("c1")

    def test_cancel_already_cancelled(self, client):
        job_doc = {
            "job_id": "c2", "job_name": "scrape", "status": "cancelled",
            "started_at": "2024-01-01T00:00:00Z", "finished_at": "2024-01-01T00:01:00Z",
            "result": None, "logs": [],
        }
        with patch("web.app.get_job_by_id", return_value=job_doc):
            r = client.post("/jobs/c2/cancel")
        assert r.status_code == 400

    def test_cancel_unknown(self, client):
        with patch("web.app.get_job_by_id", return_value=None):
            r = client.post("/jobs/nope/cancel")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /articles
# ---------------------------------------------------------------------------

class TestArticles:
    def _mock_collection(self, items, total=None):
        col = MagicMock()
        col.count_documents.return_value = total if total is not None else len(items)
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = list(items)
        col.find.return_value = cursor
        return col

    def test_default_clean_collection(self, client):
        items = [
            {"url": "http://a.com", "title": "A", "feed": "f", "pub": "2024-01-01"},
            {"url": "http://b.com", "title": "B", "feed": "f", "pub": "2024-01-02"},
        ]
        col = self._mock_collection(items)

        with patch("database.repositories.get_clean_collection", return_value=col):
            r = client.get("/articles")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data
        assert "skip" in data
        assert "limit" in data
        assert len(data["items"]) == 2

    def test_ner_collection_adds_entity_count(self, client):
        items = [
            {"url": "http://a.com", "title": "A", "feed": "f",
             "entities": [{"label": "PER"}, {"label": "ORG"}]},
        ]
        col = self._mock_collection(items)

        with patch("database.repositories.get_ner_collection", return_value=col), \
             patch("database.repositories.get_clean_collection"):
            r = client.get("/articles?collection=ner")
        assert r.status_code == 200
        item = r.json()["items"][0]
        assert item["entity_count"] == 2
        assert "entities" not in item

    def test_search_applies_filter(self, client):
        col = self._mock_collection([])

        with patch("database.repositories.get_clean_collection", return_value=col):
            client.get("/articles?search=test")
        query_arg = col.find.call_args[0][0]
        assert "$or" in query_arg

    def test_invalid_collection(self, client):
        r = client.get("/articles?collection=invalid")
        assert r.status_code == 422

    def test_limit_over_100(self, client):
        r = client.get("/articles?limit=101")
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /articles/ner/{url_b64}
# ---------------------------------------------------------------------------

class TestNerArticle:
    def test_valid_article(self, client):
        url = "http://example.com/article"
        url_b64 = base64.b64encode(url.encode()).decode().rstrip("=")

        mock_clean_col = MagicMock()
        mock_clean_col.find_one.return_value = {"url": url, "title": "Test"}

        mock_ner_col = MagicMock()
        mock_ner_col.find_one.return_value = {"url": url, "entities": []}

        with patch("database.repositories.get_clean_collection", return_value=mock_clean_col), \
             patch("database.repositories.get_ner_collection", return_value=mock_ner_col):
            r = client.get(f"/articles/ner/{url_b64}")
        assert r.status_code == 200
        data = r.json()
        assert "clean" in data
        assert "ner" in data

    def test_article_not_found(self, client):
        url = "http://example.com/missing"
        url_b64 = base64.b64encode(url.encode()).decode().rstrip("=")

        mock_clean_col = MagicMock()
        mock_clean_col.find_one.return_value = None

        with patch("database.repositories.get_clean_collection", return_value=mock_clean_col), \
             patch("database.repositories.get_ner_collection"):
            r = client.get(f"/articles/ner/{url_b64}")
        assert r.status_code == 404

    def test_invalid_base64(self, client):
        r = client.get("/articles/ner/!!!invalid!!!")
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /compare/tfidf
# ---------------------------------------------------------------------------

class _FakeArray:
    """Lightweight ndarray stand-in for TF-IDF tests."""

    def __init__(self, data):
        self._data = list(data)

    def flatten(self):
        return self

    def argsort(self):
        return _FakeArray(sorted(range(len(self._data)), key=lambda i: self._data[i]))

    def __getitem__(self, sl):
        if isinstance(sl, slice):
            return _FakeArray(self._data[sl])
        if isinstance(sl, tuple):
            # triu_indices-style indexing on a sim matrix
            return _FakeUpperTri([0.5, 0.6, 0.4])
        return self._data[sl]

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)


class _FakeUpperTri:
    def __init__(self, data):
        self._data = data

    def mean(self):
        return sum(self._data) / len(self._data)

    def std(self):
        m = self.mean()
        return (sum((x - m) ** 2 for x in self._data) / len(self._data)) ** 0.5


class _FakeMatrix:
    def __init__(self, n_docs, n_terms):
        self.shape = (n_docs, n_terms)

    def mean(self, axis=0):
        return _FakeArray([0.1 * (i + 1) for i in range(self.shape[1])])


class _FakeFeatureNames:
    def __init__(self, names):
        self._names = names

    def __getitem__(self, idx):
        if isinstance(idx, _FakeArray):
            return [self._names[i] for i in idx._data]
        return self._names[idx]

    def __iter__(self):
        return iter(self._names)

    def __len__(self):
        return len(self._names)


def _make_vectorizer_stub():
    cls = MagicMock()
    inst = MagicMock()
    inst.fit_transform.return_value = _FakeMatrix(10, 30)
    inst.get_feature_names_out.return_value = _FakeFeatureNames(
        [f"term_{i}" for i in range(30)]
    )
    cls.return_value = inst
    return cls


@pytest.fixture()
def _patch_ml_stubs():
    """Temporarily set sklearn/numpy stubs for compare endpoints."""
    sft = sys.modules["sklearn.feature_extraction.text"]
    smp = sys.modules["sklearn.metrics.pairwise"]
    np_mod = sys.modules["numpy"]

    prev = {
        "tfidf": getattr(sft, "TfidfVectorizer", None),
        "cos": getattr(smp, "cosine_similarity", None),
        "asarray": getattr(np_mod, "asarray", None),
        "triu": getattr(np_mod, "triu_indices", None),
    }

    vectorizer_cls = _make_vectorizer_stub()
    sft.TfidfVectorizer = vectorizer_cls
    smp.cosine_similarity = lambda mat: type("SM", (), {
        "__getitem__": lambda s, idx: _FakeUpperTri([0.5, 0.6, 0.4]),
    })()
    np_mod.asarray = lambda x: x
    np_mod.triu_indices = lambda n, k=0: ([0, 0, 1], [1, 2, 2])

    yield

    for attr, mod in [("TfidfVectorizer", sft), ("cosine_similarity", smp)]:
        if prev.get(attr.lower().replace("tfidfvectorizer", "tfidf").replace("cosine_similarity", "cos")):
            setattr(mod, attr, prev[attr.lower().replace("tfidfvectorizer", "tfidf").replace("cosine_similarity", "cos")])
    if prev["asarray"]:
        np_mod.asarray = prev["asarray"]
    if prev["triu"]:
        np_mod.triu_indices = prev["triu"]


class TestTfidfComparison:
    def test_no_articles_503(self, client, _patch_ml_stubs):
        mock_col = MagicMock()
        mock_col.find.return_value.limit.return_value = []

        with patch("database.repositories.get_ner_collection", return_value=mock_col):
            r = client.get("/compare/tfidf")
        assert r.status_code == 503

    def test_with_articles(self, client, _patch_ml_stubs):
        articles = [
            {"preprocessed_text": f"word{i} common text",
             "entities": [{"label": "PER"}],
             "body": f"word{i} body"}
            for i in range(10)
        ]
        mock_col = MagicMock()
        mock_col.find.return_value.limit.return_value = articles

        with patch("database.repositories.get_ner_collection", return_value=mock_col), \
             patch("preprocessing.ner_text_builder.build_ner_preprocessed_text", return_value="ner text"):
            r = client.get("/compare/tfidf?sample_size=10")

        assert r.status_code == 200
        data = r.json()
        for key in ("sample_size", "clean_top_terms", "ner_top_terms",
                    "entity_distribution", "clean_vocab_size", "ner_vocab_size", "ner_token_ratio"):
            assert key in data


# ---------------------------------------------------------------------------
# GET /compare/separability
# ---------------------------------------------------------------------------

class TestSeparability:
    def test_no_articles_503(self, client, _patch_ml_stubs):
        mock_col = MagicMock()
        mock_col.find.return_value.limit.return_value = []

        with patch("database.repositories.get_ner_collection", return_value=mock_col):
            r = client.get("/compare/separability")
        assert r.status_code == 503

    def test_with_articles(self, client, _patch_ml_stubs):
        articles = [
            {"preprocessed_text": f"word{i} common text",
             "entities": [{"label": "PER"}],
             "body": f"word{i} body"}
            for i in range(10)
        ]
        mock_col = MagicMock()
        mock_col.find.return_value.limit.return_value = articles

        with patch("database.repositories.get_ner_collection", return_value=mock_col), \
             patch("preprocessing.ner_text_builder.build_ner_preprocessed_text", return_value="ner text"):
            r = client.get("/compare/separability?sample_size=10")

        assert r.status_code == 200
        data = r.json()
        assert "verdict" in data
        assert "improvement_pct" in data
        assert "sample_size" in data


# ---------------------------------------------------------------------------
# GET /metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    def test_no_metrics(self, client):
        with patch("evaluation.sample_loader.load_latest_run_metrics", return_value=None):
            r = client.get("/metrics")
        assert r.status_code == 200
        data = r.json()
        assert data["precision"] is None
        assert data["recall"] is None
        assert data["f1"] is None

    def test_full_metrics(self, client):
        run = {
            "model_version": "v1.0",
            "created_at": "2024-01-01T00:00:00Z",
            "training_set_size": 500,
            "metrics": {
                "overall": {"precision": 0.9, "recall": 0.85, "f1": 0.87},
                "PER": {"precision": 0.95, "recall": 0.9, "f1": 0.92},
                "ORG": {"precision": 0.8, "recall": 0.75, "f1": 0.77},
            },
        }
        with patch("evaluation.sample_loader.load_latest_run_metrics", return_value=run):
            r = client.get("/metrics")
        assert r.status_code == 200
        data = r.json()
        assert data["precision"] == 0.9
        assert data["recall"] == 0.85
        assert data["f1"] == 0.87
        assert "overall" not in data["per_entity"]
        assert "PER" in data["per_entity"]


# ---------------------------------------------------------------------------
# GET /prometheus-metrics
# ---------------------------------------------------------------------------

class TestPrometheusMetrics:
    def test_returns_text_plain(self, client):
        r = client.get("/prometheus-metrics")
        assert r.status_code == 200
        assert "text/plain" in r.headers["content-type"]

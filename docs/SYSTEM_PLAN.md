# System Plan: NLP Article Analyzer

## Overview

The NLP Article Analyzer is a containerized pipeline that scrapes news articles from RSS feeds, cleans and quality-ranks them, and extracts named entities using a pretrained BERT model. All data is stored in MongoDB across logically isolated databases.

---

## Module Audit

| Module | File(s) | Status | Notes |
|--------|---------|--------|-------|
| Scraper | `src/scraper/base_scraper.py`, `scrapers/rss_scraper.py`, `scheduler.py` | done | RSS + newspaper3k, abstract base class, daily scheduler |
| Cleaning | `src/cleaning/cleaner.py`, `ranker.py`, `url_fetcher.py` | done | Rank 0/1/2 pipeline; rank-1 recovery via URL re-fetch |
| Database connection | `src/database/connection.py` | done | `lru_cache` singleton MongoClient; accessors per database |
| Database models | `src/database/models.py` | done | JSON Schema validators and index definitions |
| Database repositories | `src/database/repositories.py` | done | CRUD for raw and clean collections |
| Database init | `src/database/init_db.py` | done | Idempotent collection + index setup on startup |
| Kaggle ingestor | `src/database/kaggle_ingestor.py` | done | Bootstrap raw collection from Kaggle dataset |
| Settings | `config/settings.py` | done | All config via env vars with defaults |
| Job dispatcher | `src/jobs/__init__.py` | done | `run_job()` dispatcher for all job names |
| Scrape job | `src/jobs/scrape_job.py` | done | Fetches RSS feeds, inserts raw articles |
| Clean job | `src/jobs/clean_job.py` | done | Ranks raw articles, promotes rank-0/1 to clean collection |
| Classify job | `src/jobs/classify_job.py` | in-progress | Stub — full NER implementation this festival |
| Evaluate job | `src/jobs/evaluate_job.py` | stub | Phase 4 |
| NER extractor | `src/features/ner_extractor.py` | in-progress | Created this festival — dslim/bert-base-NER |
| Web API | `src/web/app.py` | stub | FastAPI skeleton — full implementation Phase 5 |
| Preprocessing | `src/preprocessing/` | out-of-scope | Empty — future phase |
| Modelling | `src/modelling/` | out-of-scope | Empty — future phase |
| Evaluation | `src/evaluation/` | out-of-scope | Empty — future phase |
| Deployment | `src/deployment/` | out-of-scope | Empty — future phase |
| Entrypoint | `scripts/entrypoint.py` | done | Container startup: wait for Mongo, init DBs, bootstrap, dispatch |
| Job CLI | `scripts/run_job.py` | done | `python scripts/run_job.py <job> [--dry-run]` |

---

## Data Flow

```
nlp_raw.articles
  populated by: run_job("scrape")
  source: RSS feeds (BBC, Reuters, Al Jazeera, etc.) via feedparser + newspaper3k
  stored as-is, never modified after insert
  fields: url, title, feed, type, pub, ret, lang, refs, sum, body, text, rank

      |
      v  run_job("clean")

nlp_clean.articles
  populated by: run_job("clean")
  rank-0 articles from raw (all required fields present)
  rank-1 articles recovered via URL re-fetch
  same schema as raw, minus rank field

      |
      v  run_job("classify")  /  run_job("ner")

nlp_ner.ner_articles                         <-- created this festival
  populated by: run_job("classify") / run_job("ner")
  clean article fields + entities array
  model: dslim/bert-base-NER (HuggingFace)
  entity fields: text (str), label (str), start (int), end (int)
  labels: PER (person), ORG (organisation), LOC (location), MISC (miscellaneous)
```

---

## MongoDB Databases

| Database | Default Name | Purpose |
|----------|-------------|---------|
| Raw | `nlp_raw` | Articles as scraped, immutable |
| Clean | `nlp_clean` | Articles that passed quality ranking |
| NER | `nlp_ner` | Clean articles enriched with named entities |
| Classified | `nlp_classified` | Reserved for Phase 4 topic classification |
| Models | `nlp_models` | Model run metadata and metrics |

All databases share the same MongoDB instance but are logically isolated.

---

## Article Schema

### Raw / Clean

```
_id     ObjectId   auto-generated
url     string     canonical URL (unique index)
title   string     article headline
feed    string     publisher / RSS feed name
type    string?    content type (news, opinion, etc.)
pub     string?    publication date (ISO-8601)
ret     string?    retrieval datetime (ISO-8601)
lang    string?    BCP-47 language tag
refs    string[]?  cited/referenced URLs
sum     string?    short summary
body    string     main article body text
text    string?    full raw page text
rank    int?       quality rank (raw only: 0=complete, 1=minor gaps, 2=discard)
```

### NER Articles (ner_articles)

Same as clean, plus:

```
entities  object[]  named entities extracted from body
  text    string    surface form of the entity
  label   string    entity type: PER, ORG, LOC, MISC
  start   int       character offset start in body
  end     int       character offset end in body
```

---

## Docker Infrastructure

### Dockerfile

- Base: `python:3.12-slim`
- System deps: libxml2, libxslt, libjpeg, zlib, curl (required by newspaper3k/lxml)
- Python deps: `pip install -r requirements.txt`
- NLTK data: `punkt_tab`, `stopwords` (required by newspaper3k)
- HuggingFace model: `dslim/bert-base-NER` pre-downloaded into image layer at build time
- `PYTHONPATH=/app/src:/app`
- Entrypoint: `python scripts/entrypoint.py`

### docker-compose.yml (dev)

| Service | Image | Purpose |
|---------|-------|---------|
| mongodb | mongo:7.0 | Local MongoDB on `nlp_network`, port 27017 |
| jobs | local build | Pipeline runner in `wait` mode; source dirs volume-mounted |
| api | local build | FastAPI on port 8000; source dirs volume-mounted |

Volumes: `mongo_data` (MongoDB data), `hf_cache` (HuggingFace model cache at `/root/.cache/huggingface`)

### docker-compose.prod.yml (prod)

| Service | Notes |
|---------|-------|
| mongodb | External `nlp_proxy_network`, `mongosh` healthcheck, 4G RAM limit |
| jobs | 4G RAM limit (BERT inference), `hf_cache` volume, `SKIP_BOOTSTRAP=true` |
| api | 2G RAM limit, Traefik routing labels, no direct port exposure |

### scripts/entrypoint.py

Startup sequence on every container start:
1. Wait for MongoDB to be ready (30 retries, 2s delay)
2. Initialize all database collections and indexes (`init_databases()`)
3. Check if databases are empty — if so, run Kaggle bootstrap (if enabled)
4. Dispatch to the requested service: `api`, `wait`, `job <name>`, or any job name directly

---

## Phase Roadmap

| Phase | Status | Scope |
|-------|--------|-------|
| 1 | done | Docker infrastructure, MongoDB, RSS scraper, cleaning pipeline, database layer |
| 2 | done | Job dispatcher, FastAPI skeleton, Kaggle ingestor, container entrypoint |
| 3 | in-progress | NER extraction — this festival (NE0001) |
| 4 | future | Model evaluation and metrics |
| 5 | future | Full REST API (article queries, entity search, job triggers) |
| 6 | future | Kubernetes, production orchestration |

---

## Running Jobs

```bash
# Inside the running jobs container
docker-compose exec jobs python scripts/run_job.py scrape
docker-compose exec jobs python scripts/run_job.py clean
docker-compose exec jobs python scripts/run_job.py classify   # NER extraction
docker-compose exec jobs python scripts/run_job.py ner        # alias for classify

# Dry-run (no DB writes)
docker-compose exec jobs python scripts/run_job.py classify --dry-run

# Local (with PYTHONPATH set)
PYTHONPATH=src:. python scripts/run_job.py classify --dry-run
```

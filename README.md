# NLP Article Analyzer

![Docker](https://img.shields.io/badge/Docker-Enabled-blue)
![Python](https://img.shields.io/badge/Python-3.11-yellow)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green)
![React](https://img.shields.io/badge/React-Vite-purple)
![MongoDB](https://img.shields.io/badge/MongoDB-7.0-darkgreen)
![HuggingFace](https://img.shields.io/badge/HuggingFace-Transformers-orange)

An **end-to-end NLP data pipeline and visualization stack** that scrapes news articles from RSS feeds, performs quality-filtering and cleaning, runs local **Named Entity Recognition (NER)** using BERT models, and provides analytical tools (like TF-IDF comparisons) to evaluate named-entity enhancement compared to a traditional approach.

---

## Features

- **Automated RSS Scraping**: Ingests breaking news from high-quality RSS feeds (BBC, Reuters, etc.) using `newspaper3k`.
- **Quality Cleaning & Ranking**: Ranks articles by data completeness (Rank 0: perfect, Rank 1: minor gaps, Rank 2: discard) and recovers incomplete articles via localized URL re-fetching.
- **Named Entity Recognition (NER)**: Applies `dslim/bert-base-NER` to detect Persons (PER), Organizations (ORG), Locations (LOC), and Misc (MISC) directly on hardware.
- **Extensible FastAPI Backend**: A RESTful, high-concurrency API acting as orchestrator to poll jobs, serve articles, provide metrics, and calculate TF-IDF comparison metrics.
- **React/Vite Frontend**: Real-time interface for data exploration, results visualization and administration (served on port 5173).
- **Robust Storage**: Uses logically isolated MongoDB databases for distinct pipeline stages (Raw, Clean, NER, Models).

---

## Architecture & Data Flow

The project processes data sequentially through structured stages, avoiding data corruption by maintaining the states isolated.

```mermaid
flowchart LR
    A[RSS Feeds] -->|Scrape| B[(nlp_raw)]
    B -->|Clean / Rank| C[(nlp_clean)]
    C -->|Classify (NER)| D[(nlp_ner)]
    D --> E[FastAPI & Metrics]
    E --> F[React Dashboard]
```

1. **Scrape**: Fetches raw data to `nlp_raw.articles`. Includes metadata (URL, publisher, language).
2. **Clean**: Filters high-quality articles and moves them to `nlp_clean.articles`.
3. **Classify (NER)**: Evaluates clean text, extracting character offsets for entities, saving to `nlp_ner.ner_articles`.
4. **Evaluate**: Computes ML metrics (against cached runs) and stores them for performance tracking.

---

## Prerequisites

- **Docker Desktop** (Engine 20.10+, Compose 2.0+)
- **System Memory**: Minimum 8 GB RAM, 4 CPU cores
- *(Optional)* **GPU**: For accelerated NER. By default, it runs on CPU in Docker. Configure `.env` (`NVIDIA_VISIBLE_DEVICES=all`) for GPU acceleration.

---

## Quickstart (Docker)

The fastest way to spin up the entire end-to-end stack is with Docker Compose.

```bash
# 1. Clone the repository
git clone <repo-url> nlp-article_analyzer
cd nlp-article_analyzer

# 2. Setup your environment
cp .env.example .env

# Optional: Add Kaggle API key to .env for bootstrapping historical data
# KAGGLE_KEY=your_key_here

# 3. Spin up all infrastructure and wait for data bootstrap
docker compose up --build -d
```

**Boot Sequence:**
`MongoDB` ➔ `Jobs Orchestrator` (creates DBs & auto-bootstraps) ➔ `API` ➔ `Frontend`

### Available Services

| Service | Address | Description |
|---------|---------|-------------|
| **Frontend UI** | [http://localhost:5173](http://localhost:5173) | Main application visual dashboard |
| **API Server** | [http://localhost:8000](http://localhost:8000) | Main FastAPI Router |
| **API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger Interactive Documentation |
| **MongoDB** | `localhost:27017` | Local DB Cluster (no auth locally) |

---

## Pipeline Execution

You can run individual pipeline stages manually but using Docker makes sure all dependencies and models are routed well.

```bash
# 1. scrape real-time articles
docker compose exec jobs python scripts/run_job.py scrape

# 2. clean and deduplicate raw articles
docker compose exec jobs python scripts/run_job.py clean

# 3. run NER on clean texts
docker compose exec jobs python scripts/run_job.py ner
# OR: docker compose exec jobs python scripts/run_job.py classify

# 4. generate system evaluations
docker compose exec jobs python scripts/run_job.py evaluate
```

> **Tip:** You can append `--dry-run` to preview operations without writing to MongoDB. Append `--json` to output CLI logs as JSON.

---

## Native Python Environment (For MPS / CUDA)

Docker on macOS cannot access Apple Metal as discussed in class as well. To use native GPU compute, run the jobs natively:

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (including ML packages)
pip install -r requirements.txt -r requirements-heavy.txt

# Start MongoDB only via docker
docker compose up -d mongodb

# Run your target jobs natively (auto-detects MPS / CUDA / CPU)
PYTHONPATH=src:. .venv/bin/python scripts/run_job.py ner
```

---

## Core API Endpoints

The FastAPI server provides granular interaction with the pipelines and analyzed data:

| Method | Endpoint | Use Case |
|--------|----------|----------|
| `GET` | `/health` | Validates MongoDB ping, collection status, and system health. |
| `POST` | `/jobs/trigger` | Triggers pipeline jobs (`scrape`, `clean`, `ner`). Executed asynchronously. |
| `GET` | `/articles` | Retrieve paginated articles (`?collection=clean&search=foo`). |
| `GET` | `/articles/ner/{url_b64}`| Fetch deep details of an NER-enriched article. |
| `GET` | `/compare/tfidf` | Perform computational TD-IDF analysis (Clean vs. NER outputs). |
| `GET` | `/metrics` | Retrieve the latest historical model metrics. |

---

## 🗄️ Database Management

Included bash scripts facilitate safe handling of database states:

```bash
# Dump the active database state to a tar.gz in ~/Downloads
bash scripts/db_dump.sh

# Restore the application from a known archive dump
bash scripts/db_restore.sh ~/Downloads/nlp_mongo_dump_YYYYMMDD_HHMMSS.tar.gz
```

_Note: `db_restore.sh` drops current collections and enforces an overwrite._

---

## Project Structure

```text
nlp-article_analyzer/
├── config/              # Centralized settings & environmental configs
├── docs/                # Extended system plans and architecture
├── frontend/            # React/Vite visualization application
├── scripts/             # Job runners, bootstrapping, & database migrations
└── src/                 # Main Python logic
    ├── cleaning/        # Text truncation, deduplication, and ranking rules
    ├── database/        # Pymongo adapters, models, schema enforcement
    ├── features/        # NLP routines (BERT NER setup)
    ├── jobs/            # Job orchestrations (scrape_job, clean_job...)
    ├── scraper/         # RSS parsing & newspaper3k extractors
    └── web/             # FastAPI backend (routers, metrics, dependency injection)
```

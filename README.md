# NLP Article Analyzer

End-to-end NLP pipeline that scrapes news articles from RSS feeds, cleans them, runs named-entity recognition, and produces TF-IDF comparisons of clean vs. NER-enhanced text.

---

## Pipeline Stages

| Stage | Job name | What it does |
|-------|----------|--------------|
| Scrape | `scrape` | Collects articles from RSS feeds via newspaper3k |
| Clean | `clean` | Quality-filters and ranks articles (0 = complete, 1 = incomplete, 2 = discard) |
| NER | `ner` | Runs `dslim/bert-base-NER` over clean articles; stores entity spans in `nlp_ner` |
| Evaluate | `evaluate` | Computes model metrics against stored runs |

**Stack:** Python 3.11 · FastAPI · React/Vite · MongoDB 7 · Docker Compose · HuggingFace Transformers

---

## Prerequisites

- Docker Desktop 4.x (Engine 20.10+, Compose 2.0+)
- 8 GB RAM, 4 CPU cores
- GPU optional — NER runs on CPU by default; set `NVIDIA_VISIBLE_DEVICES=all` in `.env` for GPU acceleration

---

## One-Shot Setup

```bash
git clone <repo-url> nlp-article_analyzer
cd nlp-article_analyzer
cp .env.example .env          # edit KAGGLE_KEY if you want dataset bootstrap
docker compose up --build -d
```

Services start in order: MongoDB → jobs (bootstrap) → API → frontend.

### With a team database dump

```bash
cp .env.example .env
docker compose up --build -d mongodb   # start only MongoDB first
bash scripts/db_restore.sh             # restore the dump (see Database Dump / Restore)
docker compose up -d                   # bring up the rest
```

---

## Services

| Service | URL | Notes |
|---------|-----|-------|
| API | http://localhost:8000 | FastAPI, port 8000 |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Frontend | http://localhost:5173 | React/Vite dev server |
| MongoDB | localhost:27017 | No auth in dev |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Version info |
| `GET` | `/health` | Stack health check — MongoDB ping + collection counts |
| `GET` | `/stats` | Lightweight collection document counts |
| `POST` | `/jobs/trigger` | Trigger a pipeline job asynchronously (`scrape`, `clean`, `ner`, `evaluate`) |
| `GET` | `/jobs` | List all tracked jobs |
| `GET` | `/jobs/{job_id}` | Poll job status by ID |
| `GET` | `/articles` | Paginated article list (`?collection=clean\|ner&search=...`) |
| `GET` | `/articles/ner/{url_b64}` | NER-enriched article by base64-encoded URL |
| `GET` | `/compare/tfidf` | TF-IDF comparison: clean text vs. NER-enhanced text |
| `GET` | `/metrics` | Latest model evaluation metrics |

---

## Running Jobs

### Via Docker (recommended)

```bash
# Scrape articles from RSS feeds
docker compose exec jobs python scripts/run_job.py scrape

# Clean and rank articles
docker compose exec jobs python scripts/run_job.py clean

# Run NER extraction
docker compose exec jobs python scripts/run_job.py ner

# Evaluate model
docker compose exec jobs python scripts/run_job.py evaluate

# Optional flags
docker compose exec jobs python scripts/run_job.py scrape --json     # JSON output
docker compose exec jobs python scripts/run_job.py clean --dry-run   # preview only
```

### Native NER (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-heavy.txt

PYTHONPATH=src:. .venv/bin/python scripts/run_job.py ner
```

---

## Database Dump / Restore

Scripts use `mongodump` / `mongorestore` against the running container.

```bash
# Dump all NLP databases to ./dump/
bash scripts/db_dump.sh

# Restore from ./dump/ into the running MongoDB container
bash scripts/db_restore.sh
```

`db_dump.sh` targets the `nlp_raw`, `nlp_clean`, and `nlp_ner` databases by default and writes BSON archives to `./dump/`. `db_restore.sh` reads from that same directory and replays them into the container — safe to run on an empty or populated instance.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `KAGGLE_ENABLED` | `true` | Download and ingest Kaggle dataset on first boot |
| `KAGGLE_KEY` | _(empty)_ | Kaggle API key (modern tokens only) |
| `SKIP_BOOTSTRAP` | `false` | Skip dataset bootstrap entirely (set `true` after first run) |
| `LOG_LEVEL` | `INFO` | Python log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

See `.env.example` for the full list including database names, collection names, and scheduler settings.

---

## Development

```bash
# Follow logs
docker compose logs -f api
docker compose logs -f jobs

# Rebuild after code changes
docker compose up --build -d

# Stop all services
docker compose down

# Stop and wipe volumes (full reset)
docker compose down --volumes
```

### Project structure

```
src/
  web/          FastAPI app and endpoints
  jobs/         Job orchestration (scrape, clean, ner, evaluate)
  scraper/      RSS feed collection
  cleaning/     Quality filtering and ranking
  database/     MongoDB connection, models, repositories
  modelling/    ML model wrappers
  evaluation/   Metric computation

config/         Environment-driven settings (settings.py)
scripts/        run_job.py, db_dump.sh, db_restore.sh
frontend/       React/Vite app
```

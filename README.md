# NLP Article Analyzer

An end-to-end NLP pipeline for scraping, cleaning, classifying, and evaluating news articles from multiple RSS feeds.

**Current Status**: Phases 1-2 complete. Phases 3-5 in progress.

## Features

- **Scraping** — Collect articles from RSS feeds with newspaper3k
- **Cleaning** — Quality filtering and ranking (0=complete, 1=incomplete, 2=discard)
- **Preprocessing** — NLP normalization (lowercasing, tokenization, lemmatization, stopword removal) using SpaCy
- **Classification** (Phase 3) — NLP categorization, entity extraction, sentiment analysis
- **Evaluation** (Phase 4) — Model performance metrics and baselines
- **REST API** (Phase 5) — Full query and job management interface
- **Containerized** — Docker + MongoDB for easy deployment
- **Production-Ready** — External network support, resource limits, logging

## Quick Start (Development)

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 8 GB RAM, 4 CPU cores

### Local Setup

```bash
# Clone and enter project directory
cd nlp-article_analyzer

# Start services (MongoDB, API, job runner)
docker-compose up -d

# Verify services
docker-compose ps

# View logs
docker-compose logs -f api
```

### Test the API

```bash
# Health check
curl http://localhost:8000/health

# API documentation (interactive)
open http://localhost:8000/docs
```

### Bootstrap with Kaggle Dataset (Optional)

On first startup, the container can automatically download and ingest the Kaggle newsdata dataset if the database is empty.

**Prerequisites:**
- Kaggle account (https://www.kaggle.com/settings/account)
- Download `kaggle.json` from Kaggle API settings

**Setup:**

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Kaggle API token:
   ```bash
   KAGGLE_ENABLED=true
   # Modern tokens: only paste the API key (no username needed)
   KAGGLE_KEY=your-api-key
   # Legacy tokens (optional): include username if using old format
   KAGGLE_USERNAME=
   ```

3. Restart the containers:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

4. Watch the initialization:
   ```bash
   docker-compose logs -f api  # or -f jobs
   ```

The seed will:
- Download the [newsdata dataset](https://www.kaggle.com/datasets/julianschelb/newsdata)
- Parse JSON files
- Ingest articles into the raw collection
- Run the cleaning pipeline automatically
- Start the service

After bootstrap completes, you can use the API normally without re-downloading:
```bash
# On subsequent restarts, bootstrap is skipped automatically
SKIP_BOOTSTRAP=true  # (optional, already skipped if data exists)
```

### Run Jobs Manually

```bash
# Scrape articles from RSS feeds
docker-compose exec jobs python scripts/run_job.py scrape

# Clean articles
docker-compose exec jobs python scripts/run_job.py clean

# Classify articles (Phase 3)
docker-compose exec jobs python scripts/run_job.py classify

# Evaluate model (Phase 4)
docker-compose exec jobs python scripts/run_job.py evaluate

# JSON output
docker-compose exec jobs python scripts/run_job.py scrape --json

# Dry-run (preview only)
docker-compose exec jobs python scripts/run_job.py clean --dry-run
```

### MongoDB Access

```bash
# Connect to database
docker-compose exec mongodb mongosh

# Query articles (from Python)
docker-compose exec jobs python3 << 'EOF'
from database.connection import get_raw_db
db = get_raw_db()
print(f"Articles: {db.articles.count_documents({})}")
EOF
```

## Architecture

### Local Development (docker-compose.yml)

```
┌────────────────────────────────────┐
│     Local Docker Network           │
├────────────────────────────────────┤
│ • MongoDB (port 27017)             │
│ • API Service (port 8000)          │
│ • Job Runner                       │
│ ← Volume mounts for hot reload     │
└────────────────────────────────────┘
```

### Production Deployment (docker-compose.prod.yml)

See [DEPLOYMENT.md](DEPLOYMENT.md) for full setup instructions.

```
┌─────────────────────────────────────────┐
│   External Docker Network               │
│   (Managed by Reverse Proxy)            │
├─────────────────────────────────────────┤
│ • Reverse Proxy (Traefik/nginx)         │
│ • MongoDB (persistent storage)          │
│ • API Service (no exposed ports)        │
│ • Job Runner (cron/K8s scheduled)       │
└─────────────────────────────────────────┘
```

## Project Structure

```
.
├── docker-compose.yml            # Local dev setup
├── docker-compose.prod.yml       # Production setup
├── Dockerfile                    # Container image
├── requirements.txt              # Python dependencies
│
├── src/
│   ├── pipeline.py              # Legacy entry point (use run_job.py)
│   │
│   ├── jobs/                    # Job orchestration (Phase 2)
│   │   ├── __init__.py          # Job dispatcher
│   │   ├── scrape_job.py        # Article collection
│   │   ├── clean_job.py         # Data quality filtering
│   │   ├── classify_job.py      # NLP classification (Phase 3)
│   │   └── evaluate_job.py      # Model evaluation (Phase 4)
│   │
│   ├── web/                     # FastAPI service (Phase 5)
│   │   ├── app.py               # REST endpoints
│   │   └── __init__.py
│   │
│   ├── scraper/                 # Article collection
│   │   ├── base_scraper.py
│   │   ├── scheduler.py
│   │   └── scrapers/
│   │       └── rss_scraper.py
│   │
│   ├── cleaning/                # Data quality pipeline
│   │   ├── cleaner.py
│   │   ├── ranker.py
│   │   └── url_fetcher.py
│   │
│   ├── database/                # MongoDB layer
│   │   ├── connection.py        # Connection pooling
│   │   ├── init_db.py           # Schema initialization (Phase 1)
│   │   ├── models.py            # Data schema & indexes
│   │   └── repositories.py      # CRUD operations
│   │
│   ├── modelling/               # ML models (Phase 3)
│   │   └── __init__.py          # Placeholder
│   │
│   ├── features/                # Feature extraction (Phase 3)
│   │   └── __init__.py          # Placeholder
│   │
│   ├── evaluation/              # Model evaluation (Phase 4)
│   │   └── __init__.py          # Placeholder
│   │
│   └── preprocessing/           # Placeholder
│
├── scripts/
│   ├── run_job.py               # CLI job runner (Phase 2)
│   └── orchestrate_jobs.sh      # Cron/scheduler helper (Phase 2)
│
├── config/
│   ├── settings.py              # Environment configuration
│   └── __init__.py
│
├── tests/                       # Unit/integration tests
│
├── DEPLOYMENT.md                # Deployment & ops guide
└── DEVELOPMENT.md               # Developer setup (TBD)
```

## Environment Variables

```bash
# Database
MONGO_URI=mongodb://mongodb:27017
RAW_DB_NAME=nlp_raw
CLEAN_DB_NAME=nlp_clean
CLASSIFIED_DB_NAME=nlp_classified
MODELS_DB_NAME=nlp_models

# Logging
LOG_LEVEL=INFO
PYTHONUNBUFFERED=1

# Scraper configuration (in config/settings.py)
SCRAPE_HOUR=0  # UTC hour for daily scrape (0-23)
```

## Database Schema

### Raw Collection (`nlp_raw.articles`)

Stores articles exactly as scraped from RSS feeds.

```javascript
{
  _id: ObjectId,
  url: String,           // Unique
  title: String,
  feed: String,
  type: String|null,     // e.g., "news", "opinion"
  pub: String|null,      // ISO-8601 publication date
  ret: String|null,      // ISO-8601 retrieval date
  lang: String|null,     // BCP-47 language code
  body: String,
  text: String|null,     // Full raw page text
  refs: [String]|null,   // Referenced URLs
  sum: String|null,      // Summary/lede
  rank: 0|1|2|null       // Quality rank (0=complete, 1=incomplete, 2=discard)
}
```

Indexes:
- `url` (unique)
- `rank` (fast filtering)
- `feed` (sector queries)
- `pub` (date-based sorting)

### Clean Collection (`nlp_clean.articles`)

Stores rank-0 articles ready for NLP processing.

Same schema as raw, no rank field (all are quality-verified).

### Classified Collection (`nlp_classified.articles`) — Phase 3

Extends clean schema with:
- `category: String` — Primary classification
- `subcategory: String|null`
- `confidence: Float` — Classification confidence (0-1)
- `entities: [Object]` — Named entities (NER)
- `keywords: [String]` — Extracted keywords
- `sentiment: Float|null` — Sentiment score (-1 to 1)

### Models Database (`nlp_models.model_runs`)

Stores evaluation results:

```javascript
{
  _id: ObjectId,
  model_version: String,         // e.g., "v0.1.0-20260323"
  metrics: {
    precision: Float,
    recall: Float,
    f1: Float,
    per_category: Object         // Breakdown by category
  },
  created_at: String,            // ISO-8601 timestamp
  hyperparams: Object|null,      // Model configuration
  training_set_size: Int|null    // Training examples
}
```

## Development Workflow

### Local Testing

```bash
# Run all services
docker-compose up -d

# Run a specific job
docker-compose exec jobs python scripts/run_job.py scrape

# Check logs
docker-compose logs -f jobs

# Stop all services
docker-compose down
```

### Data Inspection

```bash
# Count raw articles
docker-compose exec jobs python3 -c "
from database.repositories import get_raw_collection
col = get_raw_collection()
print(f'Raw: {col.count_documents({})}')
print(f'  Rank 0: {col.count_documents({\"rank\": 0})}')
print(f'  Rank 1: {col.count_documents({\"rank\": 1})}')
print(f'  Rank 2: {col.count_documents({\"rank\": 2})}')
"
```

### Adding New RSS Feeds

Edit `config/settings.py`:

```python
RSS_FEEDS: list[dict[str, Any]] = field(default_factory=lambda: [
    {
        "name": "Your Feed Name",
        "url": "https://example.com/feed.xml",
        "lang": "en",
    },
    # ... existing feeds
])
```

No Python code changes needed! Restart the jobs container.

## Phases

| Phase | Status | Components | Est. Effort |
|-------|--------|------------|------------|
| 1 | ✅ Done | Docker setup, MongoDB, DB init | - |
| 2 | ✅ Done | Job architecture, CLI runner | - |
| 3 | 🔄 In Progress | Classifier, feature extraction | 1-2 weeks |
| 4 | ⏳ Planned | Evaluation, model metrics | 1 week |
| 5 | ⏳ Planned | REST API implementation | 1-2 weeks |
| 6 | ⏳ Future | Kubernetes, orchestration | 2-3 weeks |

## Troubleshooting

### MongoDB won't start

```bash
# Check logs
docker-compose logs mongodb

# Verify health
docker-compose exec -T mongodb python3 -c "import socket; socket.create_connection(('localhost', 27017)); print('OK')"
```

### API not responding

```bash
# Check if running
docker-compose ps api

# Check logs
docker-compose logs api

# Test endpoint
curl http://localhost:8000/health
```

### Jobs fail silently

```bash
# Run with verbose output
docker-compose exec jobs python scripts/run_job.py scrape --json

# Check logs
docker-compose logs jobs | tail -50
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for production troubleshooting.

## Contributing

- Follow PEP 8 style guide
- Add unit tests for new features
- Document API endpoints
- Update this README for structural changes

## License

See [LICENSE](LICENSE)

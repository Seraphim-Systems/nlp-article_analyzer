# NLP Article Analyzer: Deployment & Operational Report

## 1. System Architecture
The application is a containerized microservices-based NLP pipeline and dashboard.
- **Frontend**: React (Vite, TypeScript, TailwindCSS)
- **Backend API**: FastAPI (Python)
- **Database**: MongoDB 7.0
- **NLP Engine**: Transformers (HuggingFace), BERT for NER, Scikit-learn for TF-IDF
- **Monitoring**: Prometheus & Grafana
- **Orchestration**: Docker Compose

## 2. Deployment Environments

### A. Local Development
- **File**: `docker-compose.yml`
- **Exposure**: API on `:8000`, Frontend on `:5173`, MongoDB on `:27017`
- **Volume Strategy**: Local named volumes for development ease.
- **Use Case**: Iterative development, debugging, and initial data exploration.

### B. Production (Current Implementation)
- **Target Platform**: Hetzner (Private Server)
- **File**: `docker-compose.prod.yml`
- **Network Architecture**: Services run on an external `proxy` network (e.g., Traefik/Nginx), with no ports exposed directly to the internet except via the proxy.
- **Volume Strategy**: Bind mounts to `./data/` for persistent storage of models and database.
- **Resource Management**: Strict CPU/Memory limits (e.g., MongoDB capped at 4GB, API at 2GB).

## 3. Deployment Instructions

### Local Execution
1. Ensure Docker and Docker Compose are installed.
2. Run `docker-compose up -d`.
3. Access the dashboard at `http://localhost:5173`.

### Production Deployment (Automated)
The project uses **GitHub Actions** for automated deployment.
- **Workflow**: `.github/workflows/deploy-prod.yml`
- **Trigger**: Manual trigger (`workflow_dispatch`).
- **Mechanism**: SSH-based deployment using `appleboy/ssh-action`.
- **Steps**:
    1. Prepare remote directories: `./data/{hf_cache,mongo,prometheus,grafana}`.
    2. Sync code via `git clone` or `git reset --hard`.
    3. Generate `.env` from GitHub Secrets.
    4. Build and start services using `docker-compose.prod.yml`.
    5. Clean up old images.

## 4. Operational Guide

### Job Management
Jobs are orchestrated via the `jobs` container.
- **Manual Trigger**: 
  ```bash
  docker compose exec jobs python scripts/run_job.py <job_name>
  ```
  *Available jobs: `scrape`, `clean`, `ner`, `evaluate`*
- **Scheduled Jobs**: Production uses `cron` or `systemd` timers on the host to run `scripts/orchestrate_jobs.sh`.

### Bootstrapping Data
The system can bootstrap using a Kaggle news dataset:
1. Set `KAGGLE_ENABLED=true` in `.env`.
2. Provide `KAGGLE_KEY`.
3. On startup, the `jobs` container entrypoint will ingest and clean the historical dataset.

### Monitoring
- **Prometheus**: Scrapes metrics from the API on `/prometheus-metrics`.
- **Grafana**: Pre-configured dashboards for pipeline throughput, NER entity distributions, and system health.
- **Logs**: Centralized via Docker's `json-file` driver with rotation (50MB/5 files).

## 5. Security & Maintenance
- **Secrets**: Managed via GitHub Secrets and injected into `.env` at deployment.
- **Database Security**: Configured for root password protection in production.
- **Backups**: Managed via `mongodump` commands on the host server.

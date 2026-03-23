# Deployment Guide

## Overview

The NLP Article Analyzer supports multiple deployment modes:

1. **Local Development** — `docker-compose.yml`
   - Single-machine setup with all services in local Docker network
   - MongoDB persists to local volumes
   - API exposed on `http://localhost:8000`
   - Ideal for development and testing

2. **Production with External Proxy** — `docker-compose.prod.yml`
   - Services connect to external Docker network (for reverse proxy)
   - No direct port mappings (all traffic through proxy)
   - Resource limits applied
   - Centralized logging
   - Suitable for staging/production

3. **Kubernetes** — Planned (Phase 6)
   - CronJob-based job scheduling
   - Horizontal scaling
   - Cloud-native deployment

## Local Development Setup

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 8 GB RAM, 4 CPU cores recommended

### Quick Start

```bash
# Clone and navigate to project
cd nlp-article_analyzer

# Start services
docker-compose up -d

# Verify services are running
docker-compose ps

# View logs
docker-compose logs -f api

# Check MongoDB
docker-compose exec mongodb python3 -c "import socket; socket.create_connection(('localhost', 27017), timeout=2); print('MongoDB OK')"
```

### Container Initialization & Bootstrap

On container startup, the entrypoint script executes an initialization sequence:

1. **Wait for MongoDB** — Connects with retries until MongoDB is healthy
2. **Initialize Schemas** — Creates databases, collections, and indexes
3. **Check if Bootstrap Needed** — Tests if databases are empty
4. **Kaggle Bootstrap** (optional) — Downloads and ingests dataset if enabled
5. **Start Service** — Runs API or job runner

#### Bootstrap Configuration

Control bootstrap behavior via environment variables in `.env`:

```bash
# Enable/disable Kaggle dataset download
KAGGLE_ENABLED=false|true

# Kaggle dataset identifier (owner/dataset)
KAGGLE_DATASET=julianschelb/newsdata

# Kaggle API credentials (from https://www.kaggle.com/settings/account)
# Modern tokens: leave KAGGLE_USERNAME empty, paste full token in KAGGLE_KEY
# Legacy format: provide both username and key
KAGGLE_USERNAME=
KAGGLE_KEY=your-api-key

# Skip bootstrap entirely (useful after initial setup)
SKIP_BOOTSTRAP=false|true
```

#### Bootstrap Process

When `KAGGLE_ENABLED=true` and databases are empty:

```
Container Start
    ↓
Wait for MongoDB
    ↓
Initialize Schemas & Collections
    ↓
Check if databases empty?
    │
    ├─ Yes (fresh install) → Download Kaggle dataset
    │                           ↓
    │                      Parse JSON files
    │                           ↓
    │                      Ingest into raw collection
    │                           ↓
    │                      Run cleaning pipeline
    ├─ No (data exists) → Skip bootstrap
    ↓
Start Service (API or jobs)
```

#### After Bootstrap

Once bootstrap completes:
- Database is pre-populated with ~44K articles from Kaggle dataset
- Cleaning pipeline has ranked articles (0=complete, 1=incomplete, 2=discard)
- Subsequent container restarts skip bootstrap automatically
- Volumes persist data across restarts

### Manual Job Execution (Development)

```bash
# Run scrape job
docker-compose exec jobs python scripts/run_job.py scrape

# Run clean job
docker-compose exec jobs python scripts/run_job.py clean

# Run with JSON output
docker-compose exec jobs python scripts/run_job.py classify --json

# Dry-run (no database changes)
docker-compose exec jobs python scripts/run_job.py evaluate --dry-run
```

### Local API Access

```bash
# API documentation
curl http://localhost:8000/docs

# Health check
curl http://localhost:8000/health

# List articles
curl http://localhost:8000/articles?limit=10

# Trigger job (not implemented in Phase 1)
curl -X POST http://localhost:8000/jobs/trigger \
  -H "Content-Type: application/json" \
  -d '{"job_name": "scrape", "date": null, "dry_run": false}'
```

### Database Access (Development)

```bash
# Connect to MongoDB container
docker-compose exec mongodb mongosh

# Query articles from Python
docker-compose exec jobs python3 << 'EOF'
from database.connection import get_raw_db
db = get_raw_db()
col = db["articles"]
print(f"Raw articles count: {col.count_documents({})}")
EOF
```

## CI/CD (GitHub Actions)

The project includes GitHub Action workflows for automated deployment to a remote server (e.g., Hetzner).

### Workflows

1. **Reusable Deploy** (`.github/workflows/reusable-deploy.yml`)
   - A base workflow that handles SSH connection, repository syncing, and Docker builds.
   - Can be called by other workflows for different environments (staging, production).

2. **Deploy to Production** (`.github/workflows/deploy-prod.yml`)
   - Triggers on every push to the `main` branch.
   - Calls the reusable workflow with production-specific parameters.

### Required Secrets & Variables

To enable automated deployment, configure the following in your GitHub repository settings (**Settings > Secrets and variables > Actions**):

#### Secrets
- `HETZNER_KEY`: Your SSH private key used to access the server.
- `HETZNER_IP`: The public IP address of your server.
- `HETZNER_USER`: The SSH username (e.g., `root` or `deploy`).
- `HETZNER_PORT`: (Optional) The SSH port. Defaults to `22`.

#### Variables
- (Currently none required for base deployment; can be used for environment-specific configs)

### Deployment Flow

1. Developer pushes code to the `main` branch.
2. GitHub Actions triggers the "Deploy to Production" workflow.
3. The workflow SSHs into the server using the provided credentials.
4. It navigates to `~/nlp-project` (creates it if missing).
5. It clones the repository or pulls the latest changes.
6. It runs `docker compose -f docker-compose.prod.yml build` and `up -d`.
7. It prunes old Docker images to save disk space.

---

## Production Deployment

### Prerequisites

- Docker Engine 20.10+ with Buildkit
- Docker Compose 2.0+
- External Docker network (for proxy)
- Persistent storage/volume mount point
- Reverse proxy (Traefik, nginx, HAProxy, etc.)

### Setup Steps

#### 1. Create External Network

```bash
# Create network for proxy and services
docker network create --driver bridge nlp_proxy_network

# Or if using Traefik, add services to existing traefik_network:
docker network create --driver bridge traefik_network
# (then update docker-compose.prod.yml network name)
```

#### 2. Prepare Storage

```bash
# Create persistent data directory
sudo mkdir -p /mnt/nlp_data/mongo
sudo chown 999:999 /mnt/nlp_data/mongo  # MongoDB user in container
sudo chmod 700 /mnt/nlp_data/mongo
```

#### 3. Start Services

```bash
# Navigate to project
cd nlp-article_analyzer

# Build production image
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Verify
docker-compose -f docker-compose.prod.yml ps
```

#### 3.5 Configure Bootstrap (First-Time Setup Only)

For initial data population, you can enable Kaggle dataset bootstrap on first startup:

```bash
# Edit .env for production
cat > .env << EOF
KAGGLE_ENABLED=true
# Modern tokens: leave KAGGLE_USERNAME empty, paste full token in KAGGLE_KEY
KAGGLE_USERNAME=
KAGGLE_KEY=your-kaggle-api-key
SKIP_BOOTSTRAP=false
EOF

# Restart services (bootstrap runs on init)
docker-compose -f docker-compose.prod.yml restart

# Watch logs
docker-compose -f docker-compose.prod.yml logs -f api

# After bootstrap completes, disable for future restarts
sed -i 's/SKIP_BOOTSTRAP=false/SKIP_BOOTSTRAP=true/' .env
docker-compose -f docker-compose.prod.yml restart
```

**Note**: `docker-compose.prod.yml` already defaults to `SKIP_BOOTSTRAP=true` in production. Only enable bootstrap for initial setup.

#### 4. Configure Reverse Proxy

**Traefik Example** (`docker-compose.proxy.yml`):
```yaml
version: "3.9"
services:
  traefik:
    image: traefik:v3.0
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command:
      - --api.insecure=true
      - --providers.docker=true
      - --providers.docker.network=nlp_proxy_network
      - --entrypoints.web.address=:80
    networks:
      - nlp_proxy_network

networks:
  nlp_proxy_network:
    external: true
```

**Nginx Example** (reverse proxy config):
```nginx
upstream nlp_api {
    server nlp_api_prod:80;
}

server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://nlp_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### 5. Schedule Jobs (Cron)

```bash
# Edit crontab
sudo crontab -e

# Add job schedule (runs as root or dedicated user)
0 0 * * * cd /opt/nlp-article_analyzer && /bin/bash scripts/orchestrate_jobs.sh scrape >> /var/log/nlp-jobs.log 2>&1
0 2 * * * cd /opt/nlp-article_analyzer && /bin/bash scripts/orchestrate_jobs.sh clean >> /var/log/nlp-jobs.log 2>&1
0 4 * * * cd /opt/nlp-article_analyzer && /bin/bash scripts/orchestrate_jobs.sh classify >> /var/log/nlp-jobs.log 2>&1
0 5 * * * cd /opt/nlp-article_analyzer && /bin/bash scripts/orchestrate_jobs.sh evaluate >> /var/log/nlp-jobs.log 2>&1
```

Or use systemd timer:

```bash
# Create service file
sudo tee /etc/systemd/system/nlp-scrape.service << EOF
[Unit]
Description=NLP Article Analyzer - Scrape Job
After=docker.service
Requires=docker.service

[Service]
User=root
WorkingDirectory=/opt/nlp-article_analyzer
ExecStart=/bin/bash scripts/orchestrate_jobs.sh scrape
StandardOutput=journal
StandardError=journal
EOF

# Create timer
sudo tee /etc/systemd/system/nlp-scrape.timer << EOF
[Unit]
Description=NLP Article Analyzer - Scrape Job Timer

[Timer]
OnCalendar=daily
OnCalendar=*-*-* 00:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable nlp-scrape.timer
sudo systemctl start nlp-scrape.timer
```

### Monitoring & Logging

```bash
# View logs
docker-compose -f docker-compose.prod.yml logs -f api

# Monitor resources
docker-compose -f docker-compose.prod.yml stats

# Backup MongoDB
docker-compose -f docker-compose.prod.yml exec mongodb mongodump --out /backup
```

### Network Architecture

```
┌─────────────────────────────────────────────────┐
│ External Network (nlp_proxy_network)            │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────────────┐                      │
│  │ Reverse Proxy        │                      │
│  │ (Traefik/nginx)      │◄──── Internet        │
│  │ Port 80/443          │                      │
│  └──────────────┬───────┘                      │
│                 │                              │
│       ┌─────────┼─────────┬──────────┐         │
│       ▼         ▼         ▼          ▼         │
│  ┌─────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐   │
│  │ MongoDB │ │ API Service  │ │   Frontend   │ │  Jobs    │   │
│  │ :27017  │ │ :80          │ │   Dashboard  │ │ Service  │   │
│  │(exposed)│ │ (no exposed  │ │   :3000      │ │ (no port)│   │
│  │         │ │  port)       │ │   (exposed)  │ │          │   │
│  └─────────┘ └──────────────┘ └──────────────┘ └──────────┘   │
│                                                 │
│  Vol: /mnt/nlp_data/mongo                      │
└─────────────────────────────────────────────────┘
```

## Environment Variables

Common environment variables for both dev and prod:

```
MONGO_URI=mongodb://mongodb:27017
RAW_DB_NAME=nlp_raw
CLEAN_DB_NAME=nlp_clean
CLASSIFIED_DB_NAME=nlp_classified
MODELS_DB_NAME=nlp_models
PYTHONUNBUFFERED=1
LOG_LEVEL=INFO
```

Production-only (optional):

```
SENTRY_DSN=https://...@sentry.io/...  # Error tracking
ENVIRONMENT=production
```

## Troubleshooting

### MongoDB Connection Issues

```bash
# Check if MongoDB is healthy
docker-compose exec mongodb python3 -c "import socket; socket.create_connection(('localhost', 27017), timeout=2); print('OK')"

# Check MongoDB logs
docker-compose logs mongodb | tail -20
```

### API Service Not Responding

```bash
# Check if API container is running
docker-compose ps api

# Check API logs
docker-compose logs -f api

# Test API health
curl http://localhost:8000/health
```

### Job Execution Failures

```bash
# Run job with verbose logging
docker-compose exec jobs python scripts/run_job.py scrape --json

# Check job logs
docker-compose logs jobs | tail -30
```

### Disk Space Issues (Production)

```bash
# Check MongoDB data size
du -sh /mnt/nlp_data/mongo

# Rotate logs
docker-compose logs --tail=100 > /var/backups/nlp-logs-backup.json

# Clear docker logs (be careful!)
# docker system prune -a
```

## Security Considerations

### Production Checklist

- [ ] MongoDB authentication enabled (`MONGO_INITDB_ROOT_USERNAME`, `MONGO_INITDB_ROOT_PASSWORD`)
- [ ] All services behind reverse proxy (no direct port exposure)
- [ ] HTTPS configured on reverse proxy (Let's Encrypt certificates)
- [ ] API rate limiting configured
- [ ] Log aggregation enabled (ELK stack, CloudWatch, etc.)
- [ ] Regular backups of MongoDB data
- [ ] Network isolation (services only accessible via proxy)
- [ ] Resource limits enforced (CPU, memory)
- [ ] Health checks monitored

### MongoDB Security (Recommended for Production)

Update `docker-compose.prod.yml`:

```yaml
mongodb:
  environment:
    MONGO_INITDB_ROOT_USERNAME: admin
    MONGO_INITDB_ROOT_PASSWORD: ${MONGODB_PASSWORD}
    MONGO_INITDB_DATABASE: admin

jobs:
  environment:
    MONGO_URI: mongodb://admin:${MONGODB_PASSWORD}@mongodb:27017
```

### Enable MongoDB Authentication

```bash
# Set password in environment
export MONGODB_PASSWORD=$(openssl rand -base64 32)

# Start with auth
docker-compose -f docker-compose.prod.yml up -d

# Verify
docker-compose -f docker-compose.prod.yml exec mongodb mongosh -u admin -p $MONGODB_PASSWORD --authenticationDatabase admin
```

## Backup & Recovery

### Backup MongoDB

```bash
# Full backup
docker-compose -f docker-compose.prod.yml exec mongodb mongodump --out /data/backups

# Compressed backup
docker-compose -f docker-compose.prod.yml exec mongodb sh -c 'mongodump --out - | gzip' > /backups/nlp_backup_$(date +%Y%m%d).tar.gz
```

### Restore MongoDB

```bash
# Restore from backup
docker-compose -f docker-compose.prod.yml exec mongodb mongorestore /data/backups
```

## Next Steps (Phase 6)

- [ ] Kubernetes deployment manifests
- [ ] Helm charts
- [ ] Auto-scaling based on load
- [ ] Multi-region deployment
- [ ] Disaster recovery plan
- [ ] Performance benchmarking

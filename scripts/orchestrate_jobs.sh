#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────
# Local Job Orchestration Script
# ──────────────────────────────────────────────────────────────────────────
#
# This script orchestrates job execution via REST API or CLI.
# Designed to be called by cron or similar scheduler.
#
# Usage (via cron):
#   0 0 * * * /path/to/orchestrate_jobs.sh scrape >> /var/log/nlp-jobs.log 2>&1
#   0 2 * * * /path/to/orchestrate_jobs.sh clean >> /var/log/nlp-jobs.log 2>&1
#   0 4 * * * /path/to/orchestrate_jobs.sh classify >> /var/log/nlp-jobs.log 2>&1
#   0 5 * * * /path/to/orchestrate_jobs.sh evaluate >> /var/log/nlp-jobs.log 2>&1
#
# Or manually:
#   ./orchestrate_jobs.sh scrape
#   ./orchestrate_jobs.sh clean

set -e

JOB_NAME="${1:-scrape}"
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Timestamp for logging
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Colors for output (optional, disable if piping to file)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    NC='\033[0m'  # No Color
else
    GREEN=''
    RED=''
    YELLOW=''
    NC=''
fi

log_info() {
    echo -e "${TIMESTAMP}  ${GREEN}INFO${NC}  $*"
}

log_error() {
    echo -e "${TIMESTAMP}  ${RED}ERROR${NC} $*" >&2
}

log_warn() {
    echo -e "${TIMESTAMP}  ${YELLOW}WARN${NC}  $*"
}

# Validate job name
case "$JOB_NAME" in
    scrape|clean|classify|evaluate)
        log_info "Starting job: $JOB_NAME"
        ;;
    *)
        log_error "Invalid job: $JOB_NAME. Must be one of: scrape, clean, classify, evaluate"
        exit 1
        ;;
esac

# Try REST API first, fall back to CLI
run_via_api() {
    local job=$1
    log_info "Attempting to run via REST API: POST $API_BASE_URL/jobs/trigger"
    
    response=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE_URL/jobs/trigger" \
        -H "Content-Type: application/json" \
        -d "{\"job_name\": \"$job\", \"date\": null, \"dry_run\": false}")
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "202" ]; then
        log_info "API request succeeded (HTTP $http_code)"
        echo "$body" | jq '.' 2>/dev/null || echo "$body"
        return 0
    else
        log_warn "API request failed (HTTP $http_code), falling back to CLI"
        return 1
    fi
}

run_via_cli() {
    local job=$1
    log_info "Running via CLI: python scripts/run_job.py $job"
    
    # Determine if running in Docker or locally
    if command -v docker-compose &> /dev/null; then
        docker-compose exec -T jobs python scripts/run_job.py "$job" --json
    elif command -v python &> /dev/null; then
        python scripts/run_job.py "$job" --json
    else
        log_error "No runner found (docker-compose or python)"
        return 1
    fi
}

# Execute job
if ! run_via_api "$JOB_NAME"; then
    if ! run_via_cli "$JOB_NAME"; then
        log_error "Job failed: $JOB_NAME"
        exit 1
    fi
fi

log_info "Job completed: $JOB_NAME"
exit 0

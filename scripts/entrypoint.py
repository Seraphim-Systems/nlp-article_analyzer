#!/usr/bin/env python
"""
Container entrypoint script.

Handles initialization on container startup:
1. Wait for MongoDB connection
2. Check if databases are empty
3. If empty, bootstrap with Kaggle dataset (if enabled)
4. Run cleaning pipeline
5. Start main service (API or job runner)

Usage (set in Dockerfile):
  ENTRYPOINT ["python", "scripts/entrypoint.py"]
  CMD ["api"]  # or "jobs" or specific job
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from datetime import datetime

# ANSI colours
_GREEN = "\033[0;32m"
_RED = "\033[0;31m"
_YELLOW = "\033[1;33m"
_CYAN = "\033[0;36m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

OK = f"{_GREEN}[ OK ]{_RESET}"
FAIL = f"{_RED}[FAIL]{_RESET}"
INFO = f"{_CYAN}[INFO]{_RESET}"
WARN = f"{_YELLOW}[WARN]{_RESET}"


def _status(tag: str, msg: str) -> None:
    print(f"  {tag} {msg}", flush=True)


def _print_stack_ready(service: str) -> None:
    """Print the post-init stack summary banner."""
    sep = f"{_CYAN}{'─' * 62}{_RESET}"

    print(f"\n{_BOLD}{_GREEN}{'━' * 62}{_RESET}", flush=True)
    print(f"{_BOLD}  NLP Article Analyzer — Stack Ready{_RESET}", flush=True)
    print(f"{_BOLD}{_GREEN}{'━' * 62}{_RESET}\n", flush=True)

    print(f"  {_BOLD}Services{_RESET}", flush=True)
    print(f"  {sep}", flush=True)
    print(f"  API          {_CYAN}http://localhost:8000{_RESET}", flush=True)
    print(f"  Docs         {_CYAN}http://localhost:8000/docs{_RESET}", flush=True)
    print(f"  Frontend     {_CYAN}http://localhost:5173{_RESET}", flush=True)
    print(f"  MongoDB      {_CYAN}mongodb://localhost:27017{_RESET}", flush=True)

    print(f"\n  {_BOLD}API Endpoints{_RESET}", flush=True)
    print(f"  {sep}", flush=True)
    endpoints = [
        ("GET", "/", "API info"),
        ("GET", "/health", "Full stack health + collection counts"),
        ("GET", "/stats", "Collection sizes by pipeline stage"),
        ("GET", "/articles", "Paginated articles (?collection=clean|ner&search=)"),
        ("GET", "/articles/ner/{url_b64}", "Full NER detail by base64-encoded URL"),
        (
            "GET",
            "/compare/tfidf",
            "TF-IDF: clean text vs NER-enhanced (?sample_size=200)",
        ),
        ("POST", "/jobs/trigger", "Trigger a pipeline job (scrape|clean|ner|evaluate)"),
        ("GET", "/jobs/{id}", "Poll job status by ID"),
        ("GET", "/jobs", "List all tracked jobs"),
        ("GET", "/metrics", "Model performance metrics (stub)"),
    ]
    for method, path, desc in endpoints:
        colour = _GREEN if method == "GET" else _YELLOW
        print(
            f"  {colour}{method:<5}{_RESET}  {_BOLD}{path:<36}{_RESET}  {desc}",
            flush=True,
        )

    print(f"\n  {_BOLD}Useful Commands{_RESET}", flush=True)
    print(f"  {sep}", flush=True)
    cmds = [
        (
            "Run NER job natively (MPS/GPU/CPU):",
            "PYTHONPATH=src:. .venv/bin/python scripts/run_job.py ner",
        ),
        (
            "Run any job in Docker:",
            "docker compose exec jobs python scripts/run_job.py {scrape|clean|ner|evaluate}",
        ),
        ("Export MongoDB snapshot:", "./scripts/db_dump.sh"),
        (
            "Import MongoDB snapshot:",
            "./scripts/db_restore.sh ~/Downloads/nlp_mongo_dump_YYYYMMDD.tar.gz",
        ),
        ("Follow API logs:", "docker compose logs -f api"),
        ("Follow job logs:", "docker compose logs -f jobs"),
        ("Rebuild and restart:", "docker compose up --build -d"),
        ("Stop stack (keep data):", "docker compose down"),
    ]
    for label, cmd in cmds:
        print(f"  {_YELLOW}{label}{_RESET}", flush=True)
        print(f"    {cmd}\n", flush=True)

    print(f"{_BOLD}{_GREEN}{'━' * 62}{_RESET}\n", flush=True)


# Configure logging early
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("entrypoint")


def wait_for_mongodb(max_retries: int = 30, retry_delay: int = 2) -> bool:
    """
    Wait for MongoDB to be ready.

    Parameters
    ----------
    max_retries : int
        Maximum connection attempts
    retry_delay : int
        Seconds between retries

    Returns
    -------
    bool
        True if connected, False if timeout
    """
    from database.connection import get_client

    for attempt in range(max_retries):
        try:
            logger.info(
                "Connecting to MongoDB (attempt %d/%d)...", attempt + 1, max_retries
            )
            client = get_client()
            client.admin.command("ping")
            logger.info("MongoDB connection established")
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(
                    "Connection failed: %s. Retrying in %ds...", e, retry_delay
                )
                time.sleep(retry_delay)
            else:
                logger.error(
                    "Failed to connect to MongoDB after %d attempts", max_retries
                )

    return False


def is_database_empty() -> bool:
    """
    Check if any application database has documents.

    Returns True if all databases are empty (fresh install).
    """
    from database.connection import get_client
    from config.settings import settings

    client = get_client()
    dbs = [
        settings.RAW_DB_NAME,
        settings.CLEAN_DB_NAME,
        settings.CLASSIFIED_DB_NAME,
        settings.MODELS_DB_NAME,
        settings.NER_DB_NAME,
    ]

    for db_name in dbs:
        db = client[db_name]
        # Check if any collection has documents
        for collection_name in db.list_collection_names():
            col = db[collection_name]
            if col.count_documents({}) > 0:
                logger.info(
                    "Database %s.%s has %d documents",
                    db_name,
                    collection_name,
                    col.count_documents({}),
                )
                return False

    logger.info("All databases are empty (fresh install)")
    return True


def bootstrap_from_kaggle() -> bool:
    """
    Bootstrap with Kaggle dataset if enabled and credentials provided.

    Returns True if bootstrap succeeded or was skipped, False on error.
    """
    from config.settings import settings
    from database.kaggle_ingestor import ingest_kaggle_dataset
    from cleaning.cleaner import run_cleaning_pipeline

    if settings.SKIP_BOOTSTRAP:
        logger.info("Bootstrap skipped (SKIP_BOOTSTRAP=true)")
        _status(INFO, "Bootstrap skipped (SKIP_BOOTSTRAP=true)")
        return True

    if not settings.KAGGLE_ENABLED:
        logger.info("Kaggle bootstrap disabled (KAGGLE_ENABLED=false)")
        _status(INFO, "Kaggle bootstrap disabled (KAGGLE_ENABLED=false)")
        return True

    if not settings.KAGGLE_KEY:
        logger.warning(
            "Kaggle bootstrap enabled but API key not provided — skipping bootstrap"
        )
        _status(WARN, "Kaggle bootstrap enabled but KAGGLE_KEY not provided")
        return True  # Not an error, just skip

    _status(INFO, f"Downloading dataset: {settings.KAGGLE_DATASET}...")
    logger.info("Kaggle bootstrap enabled, dataset=%s", settings.KAGGLE_DATASET)

    try:
        ingestion_result = ingest_kaggle_dataset()

        if ingestion_result["status"] != "success":
            errors = "\n  ".join(ingestion_result.get("errors", ["Unknown error"]))
            _status(FAIL, f"Kaggle ingestion failed:\n  {errors}")
            logger.error(
                "Kaggle ingestion failed with status=%s: %s",
                ingestion_result.get("status"),
                errors,
            )
            return False

        articles = ingestion_result.get("inserted_articles", 0)
        entities = ingestion_result.get("inserted_entities", 0)
        sentences = ingestion_result.get("inserted_sentences", 0)
        total_inserted = articles + entities + sentences

        # Also log parsed counts for comparison (shows if parsing failed vs insertion failed)
        parsed_articles = ingestion_result.get("parsed_articles", 0)
        parsed_entities = ingestion_result.get("parsed_entities", 0)
        parsed_sentences = ingestion_result.get("parsed_sentences", 0)

        _status(
            OK,
            f"Bootstrap complete  inserted_articles={articles}  inserted_entities={entities}  inserted_sentences={sentences}",
        )
        logger.info(
            "Kaggle ingestion complete: inserted=%d articles, %d entities, %d sentences (parsed=%d, %d, %d)",
            articles,
            entities,
            sentences,
            parsed_articles,
            parsed_entities,
            parsed_sentences,
        )

        if total_inserted == 0:
            _status(WARN, "No documents inserted — skipping cleaning pipeline")
            return True

        _status(INFO, "Running cleaning pipeline...")
        clean_result = run_cleaning_pipeline(
            skip_rank1_recovery=settings.SKIP_RANK1_RECOVERY
        )
        _status(
            OK,
            f"Cleaning done  promoted={clean_result.get('promoted', 0)}  discarded={clean_result.get('discarded', 0)}",
        )

        return True

    except Exception as e:
        _status(FAIL, f"Bootstrap exception: {type(e).__name__}: {e}")
        logger.exception("Bootstrap failed with exception")
        import traceback

        logger.error("Full traceback:\n%s", traceback.format_exc())
        return False


def initialize_databases() -> bool:
    """
    Initialize all databases and collections with schemas.

    Returns True on success.
    """
    try:
        from database.init_db import init_databases

        logger.info("Initializing databases...")
        init_databases()
        logger.info("Databases initialized")
        return True
    except Exception as e:
        logger.exception("Database initialization failed")
        return False


def run_entrypoint_sequence(skip_bootstrap: bool = False) -> int:
    """
    Execute the full initialization sequence.
    """
    print(f"\n{_BOLD}NLP Article Analyzer{_RESET}", flush=True)
    print(f"  Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", flush=True)

    # Step 1: Wait for MongoDB
    _status(INFO, "Waiting for MongoDB...")
    if not wait_for_mongodb():
        _status(FAIL, "MongoDB not available")
        return 1
    _status(OK, "MongoDB connected")

    if skip_bootstrap:
        _status(INFO, "Skipping bootstrap (SKIP_BOOTSTRAP=true)")
        return 0

    # Step 2: Initialize database schemas
    _status(INFO, "Initializing databases...")
    if not initialize_databases():
        _status(FAIL, "Database initialization failed")
        return 1
    _status(OK, "Databases initialized")

    # Step 3: Check if bootstrap needed
    _status(INFO, "Checking if bootstrap required...")
    if is_database_empty():
        _status(INFO, "Fresh install — running Kaggle bootstrap...")
        if not bootstrap_from_kaggle():
            _status(FAIL, "Bootstrap failed")
            return 1
        _status(OK, "Bootstrap complete")
    else:
        _status(OK, "Database already populated — skipping bootstrap")

    _status(OK, "Initialization complete")
    return 0


def main() -> int:
    """
    Main entrypoint.
    """
    # Validate environment before doing anything
    try:
        from config.settings import settings

        settings.validate()
    except EnvironmentError as e:
        print(f"\n  {FAIL} Configuration error:\n    {e}\n", flush=True)
        return 1

    args = sys.argv[1:] if len(sys.argv) > 1 else ["api"]
    service_arg = args[0] if args else "api"

    # Setup mode: Run init and exit
    if service_arg == "setup":
        return run_entrypoint_sequence(skip_bootstrap=False)

    # All other modes: Run minimal init (just wait for DB)
    import os

    skip_heavy = os.environ.get("SKIP_SETUP_SEQUENCE", "false").lower() == "true"
    init_result = run_entrypoint_sequence(skip_bootstrap=skip_heavy)
    if init_result != 0:
        return init_result

    _print_stack_ready(service_arg)

    # Start the requested service
    logger.info("Starting service: %s", service_arg)

    try:
        if service_arg == "api":
            # Start FastAPI service
            import subprocess

            cmd = [
                "uvicorn",
                "web.app:app",
                "--host",
                "0.0.0.0",
                "--port",
                "80",
                "--workers",
                "4",
            ]
            logger.info("Executing: %s", " ".join(cmd))
            return subprocess.call(cmd)

        elif service_arg == "wait":
            # Container initialized, keep it running (manual job execution)
            logger.info("Container initialized. Waiting for manual job execution.")
            logger.info(
                "Trigger jobs via: docker-compose exec jobs python scripts/run_job.py <job>"
            )
            # Keep container alive indefinitely
            signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
            while True:
                time.sleep(3600)  # Sleep for 1 hour at a time
            return 0

        elif service_arg == "job":
            # Run a specific job (argument: job scrape/clean/classify/evaluate)
            from jobs import run_job

            job_name = args[1] if len(args) > 1 else "scrape"
            logger.info("Running job: %s", job_name)
            result = run_job(job_name)
            return 0 if result["status"] == "success" else 1

        elif service_arg in ["scrape", "clean", "classify", "ner", "evaluate"]:
            # Run as job (backward compatible)
            from jobs import run_job

            logger.info("Running job: %s", service_arg)
            result = run_job(service_arg)
            return 0 if result["status"] == "success" else 1

        else:
            logger.error("Unknown service: %s", service_arg)
            logger.error(
                "Valid services: api, wait, job <job_name>, scrape, clean, classify, ner, evaluate"
            )
            return 1

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception("Service execution failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

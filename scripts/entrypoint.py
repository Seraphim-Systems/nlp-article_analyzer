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
        return True

    if not settings.KAGGLE_ENABLED:
        logger.info("Kaggle bootstrap disabled (KAGGLE_ENABLED=false)")
        return True

    if not settings.KAGGLE_USERNAME or not settings.KAGGLE_KEY:
        logger.warning("Kaggle bootstrap enabled but credentials not provided")
        logger.warning("  Set KAGGLE_USERNAME and KAGGLE_KEY in .env to enable")
        return True  # Not an error, just skip

    logger.info("Starting Kaggle dataset bootstrap...")

    try:
        # Download and ingest dataset
        ingestion_result = ingest_kaggle_dataset()

        if ingestion_result["status"] != "success":
            logger.error("Kaggle ingestion failed: %s", ingestion_result["errors"])
            return False

        logger.info(
            "Ingestion complete: parsed=%d, inserted=%d",
            ingestion_result["parsed"],
            ingestion_result["inserted"],
        )

        if ingestion_result["inserted"] == 0:
            logger.warning("No articles were inserted; skipping cleaning pipeline")
            return True

        # Run cleaning pipeline on newly ingested articles
        logger.info("Running cleaning pipeline on ingested articles...")
        clean_result = run_cleaning_pipeline()
        logger.info("Cleaning complete: %s", clean_result)

        return True

    except Exception as e:
        logger.exception("Bootstrap failed")
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


def run_entrypoint_sequence() -> int:
    """
    Execute the full initialization sequence.

    Returns exit code.
    """
    logger.info("=== NLP Article Analyzer - Container Startup ===")
    logger.info("Start time: %s", datetime.now().isoformat())

    # Step 1: Wait for MongoDB
    logger.info("\n[1/4] Waiting for MongoDB...")
    if not wait_for_mongodb():
        logger.error("MongoDB not available. Aborting.")
        return 1

    # Step 2: Initialize database schemas
    logger.info("\n[2/4] Initializing databases...")
    if not initialize_databases():
        logger.error("Database initialization failed. Aborting.")
        return 1

    # Step 3: Check if bootstrap needed
    logger.info("\n[3/4] Checking if bootstrap required...")
    if is_database_empty():
        logger.info("Database empty. Attempting bootstrap...")
        if not bootstrap_from_kaggle():
            logger.error("Bootstrap failed. Aborting.")
            return 1
    else:
        logger.info("Database already populated. Skipping bootstrap.")

    # Step 4: Ready to start service
    logger.info("\n[4/4] Ready to start service...")
    logger.info("Initialization complete")
    logger.info("=== Startup sequence finished ===\n")

    return 0


def main() -> int:
    """
    Main entrypoint.

    Runs initialization sequence, then delegates to the requested service.
    """
    # Parse command line arguments
    args = sys.argv[1:] if len(sys.argv) > 1 else ["api"]

    # Determine service mode
    service_arg = args[0] if args else "api"

    # Run initialization
    init_result = run_entrypoint_sequence()
    if init_result != 0:
        return init_result

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

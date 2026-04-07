#!/usr/bin/env python
"""
CLI entry point for running jobs independently.

Usage:
    python scripts/run_job.py scrape
    python scripts/run_job.py scrape --date 2026-03-20
    python scripts/run_job.py clean
    python scripts/run_job.py classify --dry-run
    python scripts/run_job.py evaluate

In docker-compose:
    command: python scripts/run_job.py scrape
    command: uvicorn web.app:app --host 0.0.0.0 --port 80
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date

# Add the 'src' directory to the Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Configure logging first, before any imports that log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("run_job")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run independent NLP pipeline jobs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scrape
  %(prog)s scrape --date 2026-03-20
  %(prog)s clean
  %(prog)s classify --dry-run
  %(prog)s evaluate
        """,
    )

    parser.add_argument(
        "job",
        nargs="?",
        default="scrape",
        choices=["scrape", "clean", "classify", "ner", "evaluate", "analyze"],
        help="Job to run (default: scrape)",
    )

    parser.add_argument(
        "--date",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="Target date for scrape/classify (ISO format: YYYY-MM-DD). Default: today.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform job analysis without updating databases.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON instead of human-readable text.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of articles to process (0 for unlimited).",
    )

    args = parser.parse_args()

    try:
        from jobs import run_job

        logger.info("Running job: %s", args.job)
        result = run_job(
            job_name=args.job,
            for_date=args.date,
            dry_run=args.dry_run,
            limit=args.limit,
        )

        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            logger.info("Job result: %s", result)
            if result["status"] == "success":
                logger.info("✓ Job succeeded")
                if result.get("errors"):
                    logger.warning("  Warnings: %s", result["errors"])
            else:
                logger.error("✗ Job failed")
                if result.get("errors"):
                    for error in result["errors"]:
                        logger.error("  - %s", error)

        return 0 if result["status"] == "success" else 1

    except Exception as e:
        logger.exception("Unexpected error")
        return 1


if __name__ == "__main__":
    sys.exit(main())

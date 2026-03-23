"""
Main daily pipeline: scrape → clean → promote.

This is the single entry-point that ties together the scraper scheduler
and the cleaning pipeline.  Running this script once is equivalent to one
full daily cycle.

Usage
-----
    python src/pipeline.py               # run a single cycle right now
    python src/pipeline.py --date 2026-03-10  # back-fill a specific date
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pipeline")


def run(for_date: date | None = None) -> None:
    # Import here so logging is configured before any module-level log calls
    from scraper.scheduler import run_scrape_job
    from cleaning.cleaner import run_cleaning_pipeline

    target = for_date or date.today()
    logger.info("Pipeline starting for date: %s", target)

    # Phase 1 — Collect
    run_scrape_job(for_date=target, run_cleaning=False)

    # Phase 2 — Clean
    summary = run_cleaning_pipeline()
    logger.info("Pipeline complete. Summary: %s", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run one full scrape + clean cycle.")
    parser.add_argument(
        "--date",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    args = parser.parse_args()
    run(for_date=args.date)

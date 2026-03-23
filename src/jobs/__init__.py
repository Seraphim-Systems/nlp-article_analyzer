"""
Job orchestration module.

Provides a unified interface for running and managing jobs: scrape, clean,
classify, and evaluate. Each job is independently callable and idempotent.

Usage:
    from jobs import run_job
    result = run_job("scrape", for_date=None)
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)


def run_job(
    job_name: str,
    for_date: date | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Run a named job with optional date override and dry-run mode.

    Parameters
    ----------
    job_name : str
        One of: 'scrape', 'clean', 'classify', 'evaluate'
    for_date : date, optional
        Target date for the job (used by scrape, classify). Defaults to today.
    dry_run : bool
        If True, print actions but don't commit changes.

    Returns
    -------
    dict
        Job result with keys: status, count, errors, duration_seconds

    Raises
    ------
    ValueError
        If job_name is not recognized.
    """
    job_name = job_name.lower().strip()

    if job_name == "scrape":
        from jobs.scrape_job import run as scrape_run

        return scrape_run(for_date=for_date, dry_run=dry_run)
    elif job_name == "clean":
        from jobs.clean_job import run as clean_run

        return clean_run(dry_run=dry_run)
    elif job_name == "classify":
        from jobs.classify_job import run as classify_run

        return classify_run(for_date=for_date, dry_run=dry_run)
    elif job_name == "evaluate":
        from jobs.evaluate_job import run as evaluate_run

        return evaluate_run(dry_run=dry_run)
    else:
        raise ValueError(
            f"Unknown job: {job_name}. "
            f"Valid jobs: scrape, clean, classify, evaluate"
        )


__all__ = ["run_job"]

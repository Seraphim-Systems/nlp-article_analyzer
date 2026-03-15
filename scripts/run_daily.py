"""
Long-running scheduler entry point.

Start this script with a process manager (systemd, Docker CMD, etc.) and it
will wake up every day at the configured hour and run the full pipeline.

    python scripts/run_daily.py
"""

from __future__ import annotations

import logging
import sys
import os

# Ensure src/ is on the Python path when running from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from scraper.scheduler import start_scheduler  # noqa: E402 (after sys.path setup)

if __name__ == "__main__":
    start_scheduler()

"""
Standalone archive cleaner.

Reads the JSONL archive file produced by the scraper/export, ranks every
article with the project's own ranker, normalises MongoDB-style date fields,
and writes the results to three output files inside the archive folder:

  archive/cleaned_rank0.json   — complete articles (rank 0), ready for NLP
  archive/cleaned_rank1.json   — partial articles (rank 1), recoverable
  archive/cleaned_rank2.json   — discarded articles (rank 2), missing crucial fields

Usage
-----
    python scripts/clean_archive.py
    python scripts/clean_archive.py --input archive/relevant_articles_line_by_line.json
    python scripts/clean_archive.py --input archive/relevant_articles.json --output-dir archive/out
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

# Make src/ and project root importable
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPTS_DIR)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "src"))
sys.path.insert(0, _PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("clean_archive")

from cleaning.ranker import rank_article, summarise_ranks  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_dates(article: dict) -> dict:
    """
    Convert MongoDB Extended JSON date objects  {"$date": "..."}  to plain
    ISO strings so downstream code can treat them as normal strings.
    """
    out = dict(article)
    for field in ("pub", "ret"):
        val = out.get(field)
        if isinstance(val, dict) and "$date" in val:
            out[field] = val["$date"]
    return out


def _load_jsonl(path: str):
    """Yield one parsed dict per non-empty line (JSON Lines format)."""
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Skipping malformed line %d: %s", lineno, exc)


def _load_json_array(path: str):
    """Load a file that is a single JSON array of objects."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array at top level in {path!r}")
    yield from data


def _load_articles(path: str):
    """
    Auto-detect JSONL vs JSON-array format and yield article dicts.
    JSONL is tried first (peek at the first non-empty line).
    """
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                is_array = stripped.startswith("[")
                break
        else:
            return  # empty file

    if is_array:
        logger.info("Detected JSON-array format.")
        yield from _load_json_array(path)
    else:
        logger.info("Detected JSON Lines (JSONL) format.")
        yield from _load_jsonl(path)


def _write_json(articles: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(articles, fh, ensure_ascii=False, indent=2)
    logger.info("Wrote %d articles → %s", len(articles), path)


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def clean_archive(input_path: str, output_dir: str) -> None:
    logger.info("Loading articles from: %s", input_path)

    buckets: dict[int, list[dict]] = {0: [], 1: [], 2: []}
    total = 0

    for raw in _load_articles(input_path):
        article = _normalise_dates(raw)
        rank = rank_article(article)
        article["rank"] = rank
        buckets[rank].append(article)
        total += 1

        if total % 10_000 == 0:
            logger.info("  processed %d articles so far…", total)

    logger.info("Finished processing %d articles total.", total)

    counts = {r: len(b) for r, b in buckets.items()}
    logger.info(
        "Rank distribution — Rank 0 (clean): %d | Rank 1 (partial): %d | Rank 2 (discard): %d",
        counts[0], counts[1], counts[2],
    )

    _write_json(buckets[0], os.path.join(output_dir, "cleaned_rank0.json"))
    _write_json(buckets[1], os.path.join(output_dir, "cleaned_rank1.json"))
    _write_json(buckets[2], os.path.join(output_dir, "cleaned_rank2.json"))

    logger.info("Done. Cleaned data is in: %s", output_dir)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    default_input = os.path.join(_PROJECT_ROOT, "archive", "relevant_articles_line_by_line.json")
    default_output = os.path.join(_PROJECT_ROOT, "archive")

    parser = argparse.ArgumentParser(description="Rank and clean archive JSON articles.")
    parser.add_argument(
        "--input", "-i",
        default=default_input,
        help=f"Path to the source JSONL or JSON-array file  (default: {default_input})",
    )
    parser.add_argument(
        "--output-dir", "-o",
        default=default_output,
        dest="output_dir",
        help=f"Directory to write the three output files into  (default: {default_output})",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    clean_archive(input_path=args.input, output_dir=args.output_dir)

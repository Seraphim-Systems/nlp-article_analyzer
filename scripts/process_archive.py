"""
process_archive.py — Standalone cleaning script for archive JSONL data.

Reads:   archive/relevant_articles_line_by_line.json  (JSONL, ~400 MB)
Writes:
  archive/cleaned_articles.json   — rank-0 (complete) articles only, JSONL
  archive/partial_articles.json   — rank-1 (recoverable) articles, JSONL

Normalisations applied to every article before ranking:
  1. pub / ret : {"$date": "..."} -> plain ISO string
  2. text field dropped (it is just sum + body combined; redundant)

Usage:
  python scripts/process_archive.py
  python scripts/process_archive.py --input archive/relevant_articles_line_by_line.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow importing from src/ without installing the package
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from cleaning.ranker import rank_article  # noqa: E402  (after sys.path patch)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_date(value: object) -> object:
    """Convert MongoDB extended JSON date {"$date": "..."} to a plain ISO string."""
    if isinstance(value, dict) and "$date" in value:
        return value["$date"]
    return value


def _clean_article(raw: dict) -> dict:
    """Apply all normalisations to a raw article dict."""
    article = dict(raw)

    # Normalise MongoDB date objects
    article["pub"] = _normalise_date(article.get("pub"))
    article["ret"] = _normalise_date(article.get("ret"))

    # Drop the redundant `text` field (sum + body combined)
    article.pop("text", None)

    return article


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def process(input_path: Path, output_clean: Path, output_partial: Path) -> None:
    print(f"Reading : {input_path}")
    print(f"Writing rank-0 -> {output_clean}")
    print(f"Writing rank-1 -> {output_partial}")
    print()

    counts = {0: 0, 1: 0, 2: 0}
    errors = 0

    with (
        input_path.open(encoding="utf-8") as fin,
        output_clean.open("w", encoding="utf-8") as fout_clean,
        output_partial.open("w", encoding="utf-8") as fout_partial,
    ):
        for line_num, line in enumerate(fin, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                errors += 1
                print(f"  [WARN] line {line_num}: JSON parse error — {exc}", file=sys.stderr)
                continue

            article = _clean_article(raw)
            rank = rank_article(article)
            article["rank"] = rank
            counts[rank] = counts.get(rank, 0) + 1

            if rank == 0:
                fout_clean.write(json.dumps(article, ensure_ascii=False) + "\n")
            elif rank == 1:
                fout_partial.write(json.dumps(article, ensure_ascii=False) + "\n")
            # rank-2 articles are discarded (not written)

            if line_num % 10_000 == 0:
                print(f"  processed {line_num:,} lines …")

    total = sum(counts.values())
    print()
    print("=" * 50)
    print(f"  Total articles processed : {total:,}")
    print(f"  Rank 0 — complete        : {counts[0]:,}  ({counts[0]/total*100:.1f}%)")
    print(f"  Rank 1 — partial         : {counts[1]:,}  ({counts[1]/total*100:.1f}%)")
    print(f"  Rank 2 — discarded       : {counts[2]:,}  ({counts[2]/total*100:.1f}%)")
    if errors:
        print(f"  Parse errors (skipped)  : {errors:,}")
    print("=" * 50)
    print()
    print(f"Done. cleaned_articles.json has {counts[0]:,} articles ready for NLP.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Clean archive JSONL for NLP use.")
    parser.add_argument(
        "--input",
        type=Path,
        default=REPO_ROOT / "archive" / "relevant_articles_line_by_line.json",
        help="Path to the source JSONL file (default: archive/relevant_articles_line_by_line.json)",
    )
    parser.add_argument(
        "--out-clean",
        type=Path,
        default=REPO_ROOT / "archive" / "cleaned_articles.json",
        help="Output path for rank-0 articles (default: archive/cleaned_articles.json)",
    )
    parser.add_argument(
        "--out-partial",
        type=Path,
        default=REPO_ROOT / "archive" / "partial_articles.json",
        help="Output path for rank-1 articles (default: archive/partial_articles.json)",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    process(args.input, args.out_clean, args.out_partial)


if __name__ == "__main__":
    main()

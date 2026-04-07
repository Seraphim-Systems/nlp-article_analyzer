"""
Classify job — extracts named entities from clean articles and writes results to ner_articles.

Entry point: run()
"""

from __future__ import annotations

import logging
import time
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

_GREEN  = "\033[0;32m"
_CYAN   = "\033[0;36m"
_YELLOW = "\033[1;33m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"

OK   = f"{_GREEN}[ OK ]{_RESET}"
INFO = f"{_CYAN}[INFO]{_RESET}"
WARN = f"{_YELLOW}[WARN]{_RESET}"


def _print(tag: str, msg: str) -> None:
    print(f"  {tag} {msg}", flush=True)


def _print_comparison(clean_article: dict, ner_article: dict) -> None:
    """Print a side-by-side comparison of clean vs NER-enriched article."""
    url = clean_article.get("url", "?")
    body = (clean_article.get("body") or "")[:400]
    preprocessed = (clean_article.get("preprocessed_text") or "")[:400]
    entities = ner_article.get("entities", [])

    print(f"\n  {_BOLD}{'─' * 70}{_RESET}", flush=True)
    print(f"  {_BOLD}NER SAMPLE COMPARISON{_RESET}", flush=True)
    print(f"  {_BOLD}{'─' * 70}{_RESET}\n", flush=True)
    print(f"  {_CYAN}Article:{_RESET} {url}\n", flush=True)

    print(f"  {_BOLD}[clean_articles] body (first 400 chars):{_RESET}", flush=True)
    print(f"  {body!r}\n", flush=True)

    print(f"  {_BOLD}[clean_articles] preprocessed_text (first 400 chars):{_RESET}", flush=True)
    print(f"  {preprocessed!r}\n", flush=True)

    print(f"  {_BOLD}[ner_articles] entities found:{_RESET} {len(entities)}", flush=True)
    if entities:
        by_label: dict[str, list[str]] = {}
        for ent in entities:
            by_label.setdefault(ent.get("label", "?"), []).append(ent.get("text", ""))
        for label, texts in sorted(by_label.items()):
            unique = sorted(set(texts))[:8]
            print(f"    {_GREEN}{label}{_RESET}: {', '.join(unique)}", flush=True)
    else:
        print(f"  {_YELLOW}  (no entities extracted){_RESET}", flush=True)
    print(f"\n  {_BOLD}{'─' * 70}{_RESET}\n", flush=True)


def _print_collection_sizes() -> None:
    """Print final document counts for all pipeline collections."""
    from database.connection import get_client
    from config.settings import settings

    client = get_client()
    collections = [
        (settings.RAW_DB_NAME,        settings.RAW_COLLECTION,  "raw articles"),
        (settings.CLEAN_DB_NAME,      settings.CLEAN_COLLECTION,"clean articles"),
        (settings.NER_DB_NAME,        settings.NER_COLLECTION,  "ner articles"),
    ]

    print(f"\n  {_BOLD}Collection sizes:{_RESET}", flush=True)
    for db_name, col_name, label in collections:
        count = client[db_name][col_name].count_documents({})
        bar_len = min(count // 1000, 30)
        bar = f"{_GREEN}{'●' * bar_len}{'○' * (30 - bar_len)}{_RESET}"
        print(f"  {bar}  {_BOLD}{count:>7,}{_RESET}  {label}", flush=True)
    print("", flush=True)


def run(for_date: date | None = None, dry_run: bool = False, log_fn=None) -> dict[str, Any]:
    """
    Execute the NER classification job.

    Fetches all clean articles not yet in ner_articles, runs NER extraction
    via dslim/bert-base-NER, and upserts enriched documents into ner_articles.
    """
    import re as _re
    _log = log_fn or (lambda _: None)

    def _print(tag: str, msg: str) -> None:
        print(f"  {tag} {msg}", flush=True)
        _log(_re.sub(r'\x1b\[[0-9;]*m', '', msg).strip())

    from utils.progress import make_pbar_simple

    start_time = time.time()
    result: dict[str, Any] = {
        "status": "success",
        "classified_count": 0,
        "errors": [],
        "duration_seconds": 0,
    }

    try:
        from database.init_db import init_databases
        from database.repositories import (
            get_unprocessed_clean_articles,
            get_clean_collection,
            get_ner_collection,
            insert_ner_articles,
        )
        from features.ner_extractor import batch_extract, get_device_label
        from preprocessing.ner_text_builder import build_ner_preprocessed_text

        init_databases()

        _print(INFO, "=== NER (classify) job started ===")
        _print(INFO, f"Loading NER model... (device: {get_device_label()})")

        articles = get_unprocessed_clean_articles()
        _print(INFO, f"Unprocessed clean articles: {len(articles):,}")

        if not articles:
            _print(OK, "Nothing to process — all articles already enriched.")
            _print_collection_sizes()
            return result

        BATCH = 64
        FLUSH_EVERY = BATCH * 4
        pending: list[dict[str, Any]] = []
        total_written = 0
        total_entities = 0
        batch_count = (len(articles) + BATCH - 1) // BATCH

        _print(INFO, f"Batch size: {BATCH} | Total batches: {batch_count}")

        pbar = make_pbar_simple(
            range(0, len(articles), BATCH),
            total=batch_count,
            desc="NER extraction",
            unit="batch",
        )

        for i in pbar:
            chunk = articles[i : i + BATCH]

            _batch_start = time.time()
            enriched_chunk = batch_extract(chunk)
            _batch_duration = time.time() - _batch_start

            for article in enriched_chunk:
                article["ner_preprocessed_text"] = build_ner_preprocessed_text(
                    article.get("body") or "",
                    article.get("entities", []),
                )

            pending.extend(enriched_chunk)

            if (i // BATCH) % 8 == 0 and i > 0:
                _log(f"Progress: {articles_done:,}/{len(articles):,} articles — {total_entities:,} entities found")

            batch_entities = sum(len(a.get("entities", [])) for a in enriched_chunk)
            total_entities += batch_entities
            articles_done = min(i + BATCH, len(articles))

            pbar.set_postfix(
                arts=f"{articles_done:,}",
                ents=f"{total_entities:,}",
                db=f"{total_written:,}",
            )

            # Prometheus instrumentation (no-op if running outside API context)
            try:
                from web.prometheus_metrics import (
                    NER_ARTICLES_PROCESSED_TOTAL,
                    NER_BATCH_DURATION_SECONDS,
                    NER_ENTITIES_EXTRACTED_TOTAL,
                )
                NER_ARTICLES_PROCESSED_TOTAL.inc(len(chunk))
                NER_BATCH_DURATION_SECONDS.observe(_batch_duration)
                for a in enriched_chunk:
                    for ent in a.get("entities", []):
                        NER_ENTITIES_EXTRACTED_TOTAL.labels(
                            entity_type=ent.get("label", "MISC")
                        ).inc()
            except ImportError:
                pass

            if not dry_run and len(pending) >= FLUSH_EVERY:
                flushed = insert_ner_articles(pending)
                total_written += flushed
                pending = []

        if not dry_run:
            if pending:
                flushed = insert_ner_articles(pending)
                total_written += flushed
            result["classified_count"] = total_written
        else:
            result["classified_count"] = len(articles)

        duration = time.time() - start_time
        arts_per_sec = len(articles) / max(duration, 1)

        _print(OK, (
            f"NER complete | articles={len(articles):,}"
            f" | entities={total_entities:,}"
            f" | written={result['classified_count']:,}"
            f" | {arts_per_sec:.1f} art/s"
        ))

        # ── Sample comparison: one article from clean vs ner ──────────────────
        clean_sample = get_clean_collection().find_one(
            {"preprocessed_text": {"$exists": True, "$ne": ""}},
            {"url": 1, "body": 1, "preprocessed_text": 1},
        )
        if clean_sample:
            ner_sample = get_ner_collection().find_one({"url": clean_sample["url"]})
            if ner_sample:
                _print_comparison(clean_sample, ner_sample)
            else:
                _print(WARN, "Sample article not yet in ner_articles (may still be flushing)")

        # ── Final collection sizes ────────────────────────────────────────────
        _print_collection_sizes()

    except Exception as e:
        logger.exception("Classify job failed")
        result["status"] = "failed"
        result["errors"].append(str(e))

    finally:
        result["duration_seconds"] = time.time() - start_time
        _print(
            OK if result["status"] == "success" else f"\033[0;31m[FAIL]{_RESET}",
            f"=== Classify job finished | status={result['status']}"
            f" | duration={result['duration_seconds']:.1f}s ===",
        )

    return result


__all__ = ["run"]

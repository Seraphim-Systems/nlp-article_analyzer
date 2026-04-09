"""
Classify job — extracts named entities from clean articles and writes results to ner_articles.

Entry point: run()
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

_GREEN = "\033[0;32m"
_CYAN = "\033[0;36m"
_YELLOW = "\033[1;33m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

OK = f"{_GREEN}[ OK ]{_RESET}"
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

    print(
        f"  {_BOLD}[clean_articles] preprocessed_text (first 400 chars):{_RESET}",
        flush=True,
    )
    print(f"  {preprocessed!r}\n", flush=True)

    print(
        f"  {_BOLD}[ner_articles] entities found:{_RESET} {len(entities)}", flush=True
    )
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
        (settings.RAW_DB_NAME, settings.RAW_COLLECTION, "raw articles"),
        (settings.CLEAN_DB_NAME, settings.CLEAN_COLLECTION, "clean articles"),
        (settings.NER_DB_NAME, settings.NER_COLLECTION, "ner articles"),
    ]

    print(f"\n  {_BOLD}Collection sizes:{_RESET}", flush=True)
    for db_name, col_name, label in collections:
        count = client[db_name][col_name].count_documents({})
        bar_len = min(count // 1000, 30)
        bar = f"{_GREEN}{'●' * bar_len}{'○' * (30 - bar_len)}{_RESET}"
        print(f"  {bar}  {_BOLD}{count:>7,}{_RESET}  {label}", flush=True)
    print("", flush=True)


def run(
    for_date: date | None = None, limit: int = 0, dry_run: bool = False, log_fn=None
) -> dict[str, Any]:
    """
    Execute the NER classification job.

    Fetches all clean articles not yet in ner_articles, runs NER extraction
    via dslim/bert-base-NER, and upserts enriched documents into ner_articles.
    """
    import re as _re

    _log = log_fn or (lambda _: None)
    _stop = threading.Event()

    def _print(tag: str, msg: str) -> None:
        print(f"  {tag} {msg}", flush=True)
        _log(_re.sub(r"\x1b\[[0-9;]*m", "", msg).strip())

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
        from features.ner_extractor import (
            batch_extract,
            get_device_label,
            get_batch_size_recommendation,
            is_cpu_device,
        )
        from preprocessing.ner_text_builder import build_ner_preprocessed_text

        init_databases()

        _print(INFO, "=== NER (classify) job started ===")
        device_label = get_device_label()
        is_cpu = is_cpu_device()
        _print(INFO, f"Loading NER model... (device: {device_label})")

        articles = get_unprocessed_clean_articles(limit=limit)
        _print(INFO, f"Unprocessed clean articles: {len(articles):,}")

        if not articles:
            _print(OK, "Nothing to process — all articles already enriched.")
            _print_collection_sizes()
            return result

        # Adaptive batch sizing: smaller batches on CPU for faster throughput
        # Sort articles by body length for better batch composition
        articles_sorted = sorted(
            articles, key=lambda a: len(a.get("body", "")), reverse=True
        )
        _print(INFO, f"Articles sorted by size (longest first) for efficient batching")

        BATCH = get_batch_size_recommendation()
        # On CPU: flush every 1-2 batches to free memory aggressively
        # On GPU: flush less frequently to amortize DB overhead
        FLUSH_EVERY = BATCH if is_cpu else BATCH * 2
        pending: list[dict[str, Any]] = []
        total_written = 0
        total_entities = 0
        batch_count = (len(articles_sorted) + BATCH - 1) // BATCH

        time_estimate = batch_count * (8 if is_cpu else 3)  # rough estimate
        _print(
            INFO,
            f"Batch size: {BATCH} (device-optimized) | "
            f"Total batches: {batch_count} | "
            f"Flush every: {FLUSH_EVERY} | "
            f"Est. time: ~{time_estimate}s",
        )

        pbar = make_pbar_simple(
            range(0, len(articles_sorted), BATCH),
            total=batch_count,
            desc="NER extraction",
            unit="batch",
        )

        for i in pbar:
            if _stop.is_set():
                _print(WARN, "NER job cancelled.")
                break
            chunk = articles_sorted[i : i + BATCH]
            batch_num = i // BATCH + 1
            
            # Log batch start
            avg_body_len = sum(len(a.get("body", "")) for a in chunk) / max(len(chunk), 1)
            logger.info(
                "Batch %d/%d START: %d articles (avg body: %d chars)",
                batch_num,
                batch_count,
                len(chunk),
                int(avg_body_len),
            )

            _batch_start = time.time()
            try:
                enriched_chunk = batch_extract(chunk)
            except Exception as e:
                logger.error(
                    "Batch %d/%d FAILED: batch_extract error: %s",
                    batch_num,
                    batch_count,
                    e,
                    exc_info=True,
                )
                _print(
                    f"{_YELLOW}[WARN]{_RESET}",
                    f"Batch {batch_num}/{batch_count}: batch_extract failed: {e}. Skipping.",
                )
                result["errors"].append(f"batch_extract at batch {batch_num}: {e}")
                continue
            _batch_duration = time.time() - _batch_start
            
            # Calculate batch metrics
            batch_entities = sum(len(a.get("entities", [])) for a in enriched_chunk)
            articles_done = min(i + BATCH, len(articles_sorted))
            
            # Log batch completion with full metrics
            logger.info(
                "Batch %d/%d COMPLETE: %d articles processed | "
                "%d entities extracted | %.2fs duration | "
                "%.1f art/s | cumulative: %d articles, %d entities",
                batch_num,
                batch_count,
                len(chunk),
                batch_entities,
                _batch_duration,
                len(chunk) / max(_batch_duration, 0.01),
                articles_done,
                total_entities + batch_entities,
            )

            for article in enriched_chunk:
                article["ner_preprocessed_text"] = build_ner_preprocessed_text(
                    article.get("body") or "",
                    article.get("entities", []),
                )

            pending.extend(enriched_chunk)
            total_entities += batch_entities

            # Progress summary logging every 3 batches
            if batch_num % 3 == 0 or batch_num == batch_count:
                elapsed = time.time() - start_time
                rate = articles_done / max(elapsed, 1)
                eta_remaining = (len(articles_sorted) - articles_done) / max(rate, 1)
                _log(
                    f"[Batch {batch_num}/{batch_count}] "
                    f"Progress: {articles_done:,}/{len(articles_sorted):,} "
                    f"({100*articles_done//len(articles_sorted)}%) | "
                    f"Entities: {total_entities:,} | "
                    f"Flushed: {total_written:,} | "
                    f"Rate: {rate:.1f} art/s | "
                    f"ETA: {int(eta_remaining)}s"
                )

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
            except (ImportError, AttributeError, TypeError, ValueError):
                pass

            if not dry_run and len(pending) >= FLUSH_EVERY:
                _flush_start = time.time()
                pending_entities = sum(len(a.get("entities", [])) for a in pending)
                try:
                    flushed = insert_ner_articles(pending)
                    total_written += flushed
                    _flush_duration = time.time() - _flush_start
                    logger.info(
                        "DB FLUSH (batch %d/%d): %d articles, %d entities | %.2fs | cumulative: %d written",
                        batch_num,
                        batch_count,
                        flushed,
                        pending_entities,
                        _flush_duration,
                        total_written,
                    )
                    pending = []
                except Exception as e:
                    logger.error(
                        "DB FLUSH FAILED (batch %d/%d): %d pending articles, error: %s",
                        batch_num,
                        batch_count,
                        len(pending),
                        e,
                        exc_info=True,
                    )
                    _print(
                        f"{_YELLOW}[WARN]{_RESET}",
                        f"Batch {batch_num}: DB write failed: {e}. Continuing...",
                    )
                    result["errors"].append(f"DB write at batch {batch_num}: {e}")

        if not dry_run:
            if pending:
                _final_flush_start = time.time()
                pending_entities = sum(len(a.get("entities", [])) for a in pending)
                try:
                    flushed = insert_ner_articles(pending)
                    total_written += flushed
                    _final_flush_duration = time.time() - _final_flush_start
                    logger.info(
                        "DB FINAL FLUSH: %d articles, %d entities | %.2fs | total written: %d",
                        flushed,
                        pending_entities,
                        _final_flush_duration,
                        total_written,
                    )
                except Exception as e:
                    logger.error(
                        "DB FINAL FLUSH FAILED: %d pending articles, error: %s",
                        len(pending),
                        e,
                        exc_info=True,
                    )
                    result["errors"].append(f"DB final flush: {e}")
            result["classified_count"] = total_written
        else:
            result["classified_count"] = len(articles_sorted)

        duration = time.time() - start_time
        arts_per_sec = len(articles_sorted) / max(duration, 1)

        # Final comprehensive logging
        logger.info(
            "=== NER JOB COMPLETED ===\n"
            "Total Statistics:\n"
            "  Articles processed: %d\n"
            "  Total entities extracted: %d\n"
            "  Articles written to DB: %d\n"
            "  Total batches: %d\n"
            "  Duration: %.2fs (%.1f art/s)\n"
            "  Processing complete: %s",
            len(articles_sorted),
            total_entities,
            result["classified_count"],
            batch_count,
            duration,
            arts_per_sec,
            "SUCCESS" if not result["errors"] else f"WITH {len(result['errors'])} ERROR(S)",
        )

        _print(
            OK,
            (
                f"NER complete | articles={len(articles_sorted):,}"
                f" | entities={total_entities:,}"
                f" | written={result['classified_count']:,}"
                f" | {arts_per_sec:.1f} art/s"
            ),
        )

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
                _print(
                    WARN,
                    "Sample article not yet in ner_articles (may still be flushing)",
                )

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

"""
Kaggle dataset ingestion module.

Downloads and parses the Kaggle newsdata dataset, then ingests articles
into the raw MongoDB collection.

Dataset: https://www.kaggle.com/datasets/julianschelb/newsdata
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def ingest_kaggle_dataset(
    download_path: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Download Kaggle newsdata dataset and ingest into MongoDB.

    Parameters
    ----------
    download_path : str, optional
        Path to download dataset files. Defaults to /tmp/kaggle_datasets.
    dry_run : bool
        If True, download and parse but don't insert into DB.

    Returns
    -------
    dict
        Ingestion result with keys:
        - status: 'success' or 'failed'
        - downloaded: number of files downloaded
        - parsed: total articles parsed
        - inserted: articles newly inserted into DB
        - errors: list of error messages
    """
    from config.settings import settings

    result: dict[str, Any] = {
        "status": "success",
        "downloaded": 0,
        "parsed_articles": 0,
        "parsed_entities": 0,
        "parsed_sentences": 0,
        "inserted_articles": 0,
        "inserted_entities": 0,
        "inserted_sentences": 0,
        "errors": [],
    }

    try:
        # Validate Kaggle credentials
        # Modern tokens only require KAGGLE_KEY; username is optional
        logger.info("Starting Kaggle dataset ingestion...")
        logger.info(
            "  KAGGLE_ENABLED=%s, KAGGLE_DATASET=%s, SKIP_BOOTSTRAP=%s",
            settings.KAGGLE_ENABLED,
            settings.KAGGLE_DATASET,
            settings.SKIP_BOOTSTRAP,
        )

        if not settings.KAGGLE_KEY:
            msg = "Kaggle API key not configured (KAGGLE_KEY). Modern tokens only require the key."
            logger.error(msg)
            result["status"] = "failed"
            result["errors"].append(msg)
            return result

        logger.info(
            "Kaggle credentials validated (key present, username=%s)",
            settings.KAGGLE_USERNAME or "(none)",
        )

        # Prepare download path
        dl_path = download_path or settings.KAGGLE_DOWNLOAD_PATH
        dl_path_obj = Path(dl_path)
        logger.info("Creating download directory: %s", dl_path)
        dl_path_obj.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Downloading Kaggle dataset: %s to %s", settings.KAGGLE_DATASET, dl_path
        )

        # Setup Kaggle API authentication
        # Pass None for username if not configured (modern token format)
        username = settings.KAGGLE_USERNAME or None
        logger.info("Setting up Kaggle authentication (token-based)...")
        _setup_kaggle_auth(username, settings.KAGGLE_KEY)

        # Download dataset
        logger.info("Starting download from Kaggle API...")
        downloaded = _download_kaggle_dataset(settings.KAGGLE_DATASET, str(dl_path_obj))
        result["downloaded"] = downloaded
        logger.info("Download complete: %d files retrieved", downloaded)

        if downloaded == 0:
            msg = "No files downloaded from Kaggle (check API credentials and network)"
            logger.error(msg)
            result["status"] = "failed"
            result["errors"].append(msg)
            return result

        logger.info("Downloaded %d files, parsing…", downloaded)

        # Parse dataset files (returns articles, entities, sentences)
        articles, entities, sentences = _parse_kaggle_files(str(dl_path_obj))
        result["parsed_articles"] = len(articles)
        result["parsed_entities"] = len(entities)
        result["parsed_sentences"] = len(sentences)

        total_parsed = len(articles) + len(entities) + len(sentences)
        if total_parsed == 0:
            logger.warning("No records found in downloaded dataset")
            return result

        logger.info(
            "Parsing complete: %d articles, %d entities, %d sentences",
            len(articles),
            len(entities),
            len(sentences),
        )
        logger.info("Beginning MongoDB ingestion...")

        # Ingest into MongoDB
        if not dry_run:
            from database.repositories import (
                insert_raw_articles,
                insert_entities,
                insert_sentences,
            )

            # Ingest articles (usually a smaller number)
            if articles:
                logger.info(
                    "Ingesting %d articles into nlp_raw.articles...", len(articles)
                )
                inserted_articles = insert_raw_articles(articles)
                logger.info(
                    "Articles ingestion complete: inserted=%d (duplicates skipped)",
                    inserted_articles,
                )
            else:
                inserted_articles = 0
                logger.warning("No articles to ingest")
            result["inserted_articles"] = inserted_articles

            # Ingest entities in chunks (millions of records)
            if entities:
                logger.info("Ingesting %d entities in small batches…", len(entities))
                chunk_size = 10000
                total_inserted_entities = 0
                for i in range(0, len(entities), chunk_size):
                    chunk = entities[i : i + chunk_size]
                    chunk_inserted = insert_entities(chunk)
                    total_inserted_entities += chunk_inserted
                    if (i // chunk_size) % 10 == 0:  # Log every 100k
                        logger.info(
                            "  Entities progress: %d / %d (inserted this batch: %d)",
                            i,
                            len(entities),
                            chunk_inserted,
                        )
                result["inserted_entities"] = total_inserted_entities

            # Ingest sentences in chunks (millions of records)
            if sentences:
                logger.info("Ingesting %d sentences in small batches…", len(sentences))
                chunk_size = 10000
                total_inserted_sentences = 0
                for i in range(0, len(sentences), chunk_size):
                    chunk = sentences[i : i + chunk_size]
                    chunk_inserted = insert_sentences(chunk)
                    total_inserted_sentences += chunk_inserted
                    if (i // chunk_size) % 10 == 0:  # Log every 100k
                        logger.info(
                            "  Sentences progress: %d / %d (inserted this batch: %d)",
                            i,
                            len(sentences),
                            chunk_inserted,
                        )
                result["inserted_sentences"] = total_inserted_sentences

            logger.info(
                "Ingestion complete: %d articles, %d entities, %d sentences",
                result["inserted_articles"],
                result["inserted_entities"],
                result["inserted_sentences"],
            )
        else:
            logger.info(
                "DRY RUN: Would ingest %d articles, %d entities, %d sentences",
                len(articles),
                len(entities),
                len(sentences),
            )
            result["inserted_articles"] = len(articles)
            result["inserted_entities"] = len(entities)
            result["inserted_sentences"] = len(sentences)

        # Cleanup
        logger.info("Cleaning up downloaded files from %s...", dl_path)
        try:
            shutil.rmtree(str(dl_path_obj), ignore_errors=True)
            logger.info("Downloaded files cleaned up")
        except Exception as e:
            logger.warning("Failed to clean up downloaded files: %s", e)

        logger.info(
            "Kaggle ingestion SUCCESS: inserted %d articles, %d entities, %d sentences",
            result["inserted_articles"],
            result["inserted_entities"],
            result["inserted_sentences"],
        )
        result["status"] = "success"

    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        logger.exception("Kaggle dataset ingestion FAILED")
        logger.error("Error details: %s", msg)
        result["status"] = "failed"
        result["errors"].append(msg)

    return result


def _setup_kaggle_auth(username: str | None, key: str) -> None:
    """
    Configure Kaggle API authentication via environment.

    Supports both legacy (username + key) and modern (token-only) formats:
    - Legacy: username="myusername", key="mykey"
    - Modern: username=None or "", key="full_token"
    """
    # Kaggle CLI uses these env vars
    # For modern tokens, username can be empty or any placeholder
    os.environ["KAGGLE_USERNAME"] = username or "kaggle_token"
    os.environ["KAGGLE_KEY"] = key
    logger.debug(
        "Kaggle authentication configured (token-based)"
        if not username
        else "Kaggle authentication configured (username + key)"
    )


def _download_kaggle_dataset(dataset_id: str, output_path: str) -> int:
    """
    Download dataset from Kaggle.

    Returns number of files downloaded.
    """
    try:
        from kaggle.api.kaggle_api_extended import KaggleApi

        logger.info("Initializing Kaggle API client...")
        api = KaggleApi()

        logger.info("Authenticating with Kaggle API...")
        api.authenticate()
        logger.info("Kaggle API authentication successful")

        logger.info("Downloading dataset: %s to %s", dataset_id, output_path)
        api.dataset_download_files(dataset_id, path=output_path, unzip=True)

        # Count downloaded files
        files = list(Path(output_path).glob("**/*"))
        files = [f for f in files if f.is_file()]

        logger.info(
            "Download complete: %d files (types: %s)",
            len(files),
            set(Path(f).suffix for f in files),
        )
        return len(files)

    except Exception as e:
        logger.error("Failed to download from Kaggle: %s: %s", type(e).__name__, e)
        logger.exception("Kaggle download traceback")
        raise


def _parse_kaggle_files(
    dataset_path: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Parse Kaggle newsdata dataset files (JSON format).

    Expected files:
    - relevant_articles.json: article documents
    - relevant_entities.json: named entities
    - relevant_sent.json or sentences_matched_entities.json: sentences

    Prioritises relevant_articles.json for article ingestion; falls back to
    all JSON files in the directory if it is absent.

    Returns tuple of (articles, entities, sentences) lists.
    """
    articles: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    sentences: list[dict[str, Any]] = []

    dataset_dir = Path(dataset_path)

    # Use relevant_articles.json as the primary source; fall back to any JSON
    target = dataset_dir / "relevant_articles.json"
    json_files = [target] if target.exists() else list(dataset_dir.glob("*.json"))

    if not json_files:
        logger.warning("No JSON files found in %s", dataset_path)
        return articles, entities, sentences

    logger.info("Found %d JSON file(s) to parse", len(json_files))

    for json_file in json_files:
        logger.info("Parsing %s", json_file.name)
        try:
            # Try standard JSON first, fall back to JSONL (line-by-line)
            with open(json_file, encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        records = data
                    elif isinstance(data, dict):
                        records = data.get("data", data.get("records", [data]))
                    else:
                        records = []
                except json.JSONDecodeError:
                    f.seek(0)
                    records = []
                    for line in f:
                        if line.strip():
                            try:
                                records.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue

            if not records:
                continue

            # Classify records by structure
            for record in records:
                if not isinstance(record, dict):
                    continue

                # Articles: have 'title' and ('url' or 'text' or '_id')
                if "title" in record and (
                    "text" in record or "url" in record or "_id" in record
                ):
                    article = _parse_article_record(record)
                    if article:
                        articles.append(article)

                elif "NE" in record and ("docID" in record or "doc_id" in record):
                    entity = _parse_entity_record(record)
                    if entity:
                        entities.append(entity)

                elif "text" in record and "docID" in record and "senDocID" in record:
                    sentence = _parse_sentence_record(record)
                    if sentence:
                        sentences.append(sentence)

        except Exception as e:
            logger.warning("Error processing %s: %s", json_file.name, e)

    logger.info(
        "Parsed %d articles, %d entities, %d sentences",
        len(articles),
        len(entities),
        len(sentences),
    )
    return articles, entities, sentences


def _parse_article_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """
    Convert a julianschelb/newsdata JSON record to our article schema.

    Handles both legacy format (_id, url, title, feed, body, pub as $date object)
    and modern format (url/id, title, text/content, publishedAt as ISO string).
    """
    try:
        # Robust URL and Title extraction
        url = str(record.get("url") or record.get("_id") or "").strip()
        title = (record.get("title") or "").strip()
        body = (
            record.get("body") or record.get("text") or record.get("content") or ""
        ).strip()

        if not title or not body:
            return None

        def _extract_date(val: Any) -> str | None:
            if not val:
                return None
            if isinstance(val, dict):
                val = val.get("$date", "")
            try:
                return datetime.fromisoformat(
                    str(val).replace("Z", "+00:00")
                ).isoformat()
            except (ValueError, AttributeError):
                return None

        # Publication date — support both legacy $date objects and plain ISO strings
        pub_date = _extract_date(record.get("pub") or record.get("publishedAt"))
        ret_date = (
            _extract_date(record.get("ret")) or datetime.now(timezone.utc).isoformat()
        )

        # Capture Kaggle internal ID for potential joins
        kaggle_id = record.get("_id") or record.get("id")

        return {
            "url": url,
            "title": title,
            "feed": (record.get("feed") or "Kaggle Dataset").strip(),
            "type": (record.get("type") or "news").strip(),
            "pub": pub_date,
            "ret": ret_date,
            "lang": (record.get("lang") or "en").strip(),
            "body": body,
            "text": (record.get("text") or body).strip(),
            "refs": record.get("refs") or [],
            "sum": (record.get("sum") or "").strip(),
            "kaggle_id": kaggle_id,
            "rank": None,
        }

    except Exception as e:
        logger.debug("Failed to parse article record: %s", e)
        return None


def _parse_entity_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Parse entity from JSON record."""
    try:
        docID = str(record.get("docID", "")).strip()
        senDocID = int(record.get("senDocID", 0))
        ne = record.get("NE", "").strip()
        s_sen = int(record.get("sSen", 0))
        e_sen = int(record.get("eSen", 0))

        if not docID or not ne:
            return None

        return {
            "docID": docID,
            "senDocID": senDocID,
            "NE": ne,
            "sSen": s_sen,
            "eSen": e_sen,
        }

    except (ValueError, TypeError, AttributeError) as e:
        logger.debug("Failed to parse entity record: %s", e)
        return None


def _parse_sentence_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Parse sentence from JSON record."""
    try:
        docID = str(record.get("docID", "")).strip()
        senDocID = int(record.get("senDocID", 0))
        text = record.get("text", "").strip()

        if not docID or not text:
            return None

        return {
            "docID": docID,
            "senDocID": senDocID,
            "text": text,
        }

    except (ValueError, TypeError, AttributeError) as e:
        logger.debug("Failed to parse sentence record: %s", e)
        return None


__all__ = ["ingest_kaggle_dataset"]

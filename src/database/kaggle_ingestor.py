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
        if not settings.KAGGLE_KEY:
            result["status"] = "failed"
            result["errors"].append(
                "Kaggle API key not configured (KAGGLE_KEY). Modern tokens only require the key, not a username."
            )
            return result

        # Prepare download path
        dl_path = download_path or settings.KAGGLE_DOWNLOAD_PATH
        dl_path_obj = Path(dl_path)
        dl_path_obj.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Downloading Kaggle dataset: %s to %s", settings.KAGGLE_DATASET, dl_path
        )

        # Setup Kaggle API authentication
        # Pass None for username if not configured (modern token format)
        username = settings.KAGGLE_USERNAME or None
        _setup_kaggle_auth(username, settings.KAGGLE_KEY)

        # Download dataset
        downloaded = _download_kaggle_dataset(settings.KAGGLE_DATASET, str(dl_path_obj))
        result["downloaded"] = downloaded

        if downloaded == 0:
            result["status"] = "failed"
            result["errors"].append("No files downloaded from Kaggle")
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
            "Parsed %d articles, %d entities, %d sentences; ingesting into MongoDB…",
            len(articles),
            len(entities),
            len(sentences),
        )

        # Ingest into MongoDB
        if not dry_run:
            from database.repositories import (
                insert_raw_articles,
                insert_entities,
                insert_sentences,
            )

            # Ingest articles (usually a smaller number)
            inserted_articles = insert_raw_articles(articles) if articles else 0
            result["inserted_articles"] = inserted_articles

            # Ingest entities in chunks (millions of records)
            if entities:
                logger.info("Ingesting %d entities in small batches…", len(entities))
                chunk_size = 10000
                total_inserted_entities = 0
                for i in range(0, len(entities), chunk_size):
                    chunk = entities[i : i + chunk_size]
                    total_inserted_entities += insert_entities(chunk)
                    if (i // chunk_size) % 10 == 0:  # Log every 100k
                        logger.info("  Progress: %d / %d entities", i, len(entities))
                result["inserted_entities"] = total_inserted_entities
            
            # Ingest sentences in chunks (millions of records)
            if sentences:
                logger.info("Ingesting %d sentences in small batches…", len(sentences))
                chunk_size = 10000
                total_inserted_sentences = 0
                for i in range(0, len(sentences), chunk_size):
                    chunk = sentences[i : i + chunk_size]
                    total_inserted_sentences += insert_sentences(chunk)
                    if (i // chunk_size) % 10 == 0:  # Log every 100k
                        logger.info("  Progress: %d / %d sentences", i, len(sentences))
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
        logger.info("Cleaning up downloaded files…")
        shutil.rmtree(str(dl_path_obj), ignore_errors=True)

        result["status"] = "success"

    except Exception as e:
        logger.exception("Kaggle dataset ingestion failed")
        result["status"] = "failed"
        result["errors"].append(str(e))

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

        api = KaggleApi()
        api.authenticate()

        logger.info("Authenticated with Kaggle API")
        logger.info("Downloading dataset: %s", dataset_id)

        # Download to specified path
        api.dataset_download_files(dataset_id, path=output_path, unzip=True)

        # Count downloaded files
        files = list(Path(output_path).glob("**/*"))
        files = [f for f in files if f.is_file()]

        logger.info("Download complete: %d files", len(files))
        return len(files)

    except Exception as e:
        logger.exception("Failed to download from Kaggle")
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

    Returns tuple of (articles, entities, sentences) lists.
    """
    articles: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    sentences: list[dict[str, Any]] = []

    dataset_dir = Path(dataset_path)

    # Search for JSON files only (enforcing JSON extraction)
    json_files = list(dataset_dir.glob("*.json"))

    if not json_files:
        logger.warning("No JSON files found in %s", dataset_path)
        return articles, entities, sentences

    logger.info("Found %d JSON files", len(json_files))

    for json_file in json_files:
        logger.info("Parsing %s", json_file.name)

        try:
            # Try standard JSON first
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
                    # If standard JSON fails, try JSONL (line-by-line)
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

                # Articles usually have 'title' and ('url' or 'text' or '_id')
                if "title" in record and ("text" in record or "url" in record or "_id" in record):
                    # Article record
                    article = _parse_article_record(record)
                    if article:
                        articles.append(article)

                elif "NE" in record and ("docID" in record or "doc_id" in record):
                    # Entity record
                    entity = _parse_entity_record(record)
                    if entity:
                        entities.append(entity)

                elif (
                    "text" in record and "docID" in record and "senDocID" in record
                ):
                    # Sentence record
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
    """Parse article from JSON record (new format)."""
    try:
        # Robust URL and Title extraction
        url = str(record.get("url") or record.get("_id") or "").strip()
        title = record.get("title", "").strip()
        body = record.get("text", record.get("content", "")).strip()

        if not title or not body:
            return None

        # Publication date
        pub_date = record.get("pub", record.get("publishedAt", "")).strip()
        if pub_date:
            try:
                pub_date = datetime.fromisoformat(
                    pub_date.replace("Z", "+00:00")
                ).isoformat()
            except (ValueError, AttributeError):
                pub_date = None

        ret_date = datetime.now(timezone.utc).isoformat()

        # Capture Kaggle internal ID for potential joins
        kaggle_id = record.get("_id") or record.get("id")

        return {
            "url": url,
            "title": title,
            "feed": record.get("feed", "Kaggle Dataset").strip(),
            "type": record.get("type", "news").strip(),
            "pub": pub_date,
            "ret": ret_date,
            "lang": record.get("lang", "en").strip(),
            "body": body,
            "text": body,  # using body as text if text field is same
            "refs": record.get("refs", []),
            "sum": record.get("sum", "").strip(),
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

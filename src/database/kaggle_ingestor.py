"""
Kaggle dataset ingestion module.

Downloads and parses the Kaggle newsdata dataset, then ingests articles
into the raw MongoDB collection.

Dataset: https://www.kaggle.com/datasets/julianschelb/newsdata
"""

from __future__ import annotations

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

            inserted_articles = insert_raw_articles(articles) if articles else 0
            inserted_entities = insert_entities(entities) if entities else 0
            inserted_sentences = insert_sentences(sentences) if sentences else 0

            result["inserted_articles"] = inserted_articles
            result["inserted_entities"] = inserted_entities
            result["inserted_sentences"] = inserted_sentences

            logger.info(
                "Ingested %d articles, %d entities, %d sentences",
                inserted_articles,
                inserted_entities,
                inserted_sentences,
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
    import json

    articles: list[dict[str, Any]] = []
    entities: list[dict[str, Any]] = []
    sentences: list[dict[str, Any]] = []

    dataset_dir = Path(dataset_path)

    # Try both old CSV and new JSON formats
    csv_files = list(dataset_dir.glob("*.csv"))
    json_files = list(dataset_dir.glob("*.json"))

    # Parse CSV files (old format)
    if csv_files:
        logger.info("Found %d CSV files (old format)", len(csv_files))
        articles.extend(_parse_csv_files(json_files))

    # Parse JSON files (new format)
    if json_files:
        logger.info("Found %d JSON files (new format)", len(json_files))

        for json_file in json_files:
            logger.info("Parsing %s", json_file.name)

            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                # Handle list of records
                if isinstance(data, list):
                    records = data
                # Handle dict with records in a key
                elif isinstance(data, dict):
                    records = data.get("data", data.get("records", [data]))
                else:
                    logger.warning("Unexpected JSON structure in %s", json_file.name)
                    continue

                # Classify records by structure
                for record in records:
                    if not isinstance(record, dict):
                        continue

                    if "title" in record and "url" in record:
                        # Article record
                        article = _parse_article_record(record)
                        if article:
                            articles.append(article)

                    elif "NE" in record and "docID" in record:
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

            except json.JSONDecodeError as e:
                logger.warning("Failed to parse JSON %s: %s", json_file.name, e)
            except Exception as e:
                logger.warning("Error processing %s: %s", json_file.name, e)

    logger.info(
        "Parsed %d articles, %d entities, %d sentences",
        len(articles),
        len(entities),
        len(sentences),
    )
    return articles, entities, sentences


def _parse_csv_files(csv_files: list[Path]) -> list[dict[str, Any]]:
    """Parse old CSV format (fallback for backward compatibility)."""
    import csv

    articles: list[dict[str, Any]] = []

    for csv_file in csv_files:
        try:
            with open(csv_file, encoding=" utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    continue

                for row in reader:
                    article = _parse_kaggle_row(row)
                    if article:
                        articles.append(article)

        except Exception as e:
            logger.warning("Failed to parse CSV %s: %s", csv_file.name, e)

    return articles


def _parse_article_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Parse article from JSON record (new format)."""
    try:
        url = record.get("url", "").strip()
        title = record.get("title", "").strip()
        body = record.get("text", "").strip() or record.get("content", "").strip()

        if not url or not title or not body:
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

        return {
            "url": url,
            "title": title,
            "feed": record.get("feed", record.get("source", "Kaggle Dataset")).strip(),
            "type": record.get("type", "news").strip(),
            "pub": pub_date,
            "ret": ret_date,
            "lang": record.get("lang", "en").strip(),
            "body": body,
            "text": record.get("text", "").strip(),
            "refs": record.get("refs", []),
            "sum": record.get("sum", record.get("description", "")).strip(),
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


def _parse_kaggle_row(row: dict[str, str]) -> dict[str, Any] | None:
    """
    Convert a Kaggle CSV row to article dict.

    Kaggle newsdata typically has columns:
    - title, description, content, url, urlToImage, publishedAt, source
    """
    try:
        # Required fields
        url = row.get("url", "").strip()
        title = row.get("title", "").strip()
        body = row.get("content", "").strip() or row.get("description", "").strip()

        if not url or not title or not body:
            return None

        # Publication date
        pub_date = row.get("publishedAt", "").strip()
        if pub_date:
            try:
                # Parse ISO-8601 date
                pub_date = datetime.fromisoformat(
                    pub_date.replace("Z", "+00:00")
                ).isoformat()
            except (ValueError, AttributeError):
                pub_date = None

        # Retrieval date (now)
        ret_date = datetime.now(timezone.utc).isoformat()

        return {
            "url": url,
            "title": title,
            "feed": row.get("source", "Kaggle Dataset").strip(),
            "type": "news",
            "pub": pub_date,
            "ret": ret_date,
            "lang": "en",  # Assume English from Kaggle dataset
            "body": body,
            "text": row.get("description", "").strip(),
            "refs": [],
            "sum": row.get("description", "").strip(),
            "rank": None,  # Will be ranked by cleaning pipeline
        }

    except (KeyError, AttributeError, TypeError):
        return None


__all__ = ["ingest_kaggle_dataset"]

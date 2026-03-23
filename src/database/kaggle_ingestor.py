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
        "parsed": 0,
        "inserted": 0,
        "errors": [],
    }

    try:
        # Validate Kaggle credentials
        if not settings.KAGGLE_USERNAME or not settings.KAGGLE_KEY:
            result["status"] = "failed"
            result["errors"].append(
                "Kaggle credentials not configured (KAGGLE_USERNAME, KAGGLE_KEY)"
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
        _setup_kaggle_auth(settings.KAGGLE_USERNAME, settings.KAGGLE_KEY)

        # Download dataset
        downloaded = _download_kaggle_dataset(settings.KAGGLE_DATASET, str(dl_path_obj))
        result["downloaded"] = downloaded

        if downloaded == 0:
            result["status"] = "failed"
            result["errors"].append("No files downloaded from Kaggle")
            return result

        logger.info("Downloaded %d files, parsing…", downloaded)

        # Parse dataset files
        articles = _parse_kaggle_files(str(dl_path_obj))
        result["parsed"] = len(articles)

        if not articles:
            logger.warning("No articles found in downloaded dataset")
            return result

        logger.info("Parsed %d articles, ingesting into MongoDB…", len(articles))

        # Ingest into MongoDB
        if not dry_run:
            from database.repositories import insert_raw_articles

            inserted = insert_raw_articles(articles)
            result["inserted"] = inserted
            logger.info("Ingested %d articles into raw collection", inserted)
        else:
            logger.info("DRY RUN: Would ingest %d articles", len(articles))
            result["inserted"] = len(articles)

        # Cleanup
        logger.info("Cleaning up downloaded files…")
        shutil.rmtree(str(dl_path_obj), ignore_errors=True)

        result["status"] = "success"

    except Exception as e:
        logger.exception("Kaggle dataset ingestion failed")
        result["status"] = "failed"
        result["errors"].append(str(e))

    return result


def _setup_kaggle_auth(username: str, key: str) -> None:
    """Configure Kaggle API authentication via environment."""
    # Kaggle CLI uses these env vars
    os.environ["KAGGLE_USERNAME"] = username
    os.environ["KAGGLE_KEY"] = key
    logger.debug("Kaggle authentication configured")


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


def _parse_kaggle_files(dataset_path: str) -> list[dict[str, Any]]:
    """
    Parse downloaded Kaggle dataset files.

    The newsdata dataset typically includes CSV files with article data.
    Returns list of article dicts compatible with MongoDB schema.
    """
    import csv

    articles: list[dict[str, Any]] = []
    dataset_dir = Path(dataset_path)

    # Find CSV files
    csv_files = list(dataset_dir.glob("*.csv"))
    logger.info("Found %d CSV files to parse", len(csv_files))

    for csv_file in csv_files:
        logger.info("Parsing %s", csv_file.name)

        try:
            with open(csv_file, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    logger.warning("Empty CSV file: %s", csv_file.name)
                    continue

                for row in reader:
                    article = _parse_kaggle_row(row)
                    if article:
                        articles.append(article)

        except Exception as e:
            logger.warning("Failed to parse %s: %s", csv_file.name, e)

    logger.info("Parsed total %d articles from all files", len(articles))
    return articles


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

"""
backfill_weaviate.py
=====================
One-time (safely rerunnable) migration script: seeds a fresh Weaviate instance
with the article history already published from this repo, so duplicate-content
checks (orchestrator.py's DuplicateContentGuard) have real history from the
first run on a new deployment instead of starting blind.

Weaviate is normally populated incrementally by add_article() after every
publish (see utils/utils.py VectorStoreManager) — there is no bulk seed path,
so this walks data/output/json/*.json (the only place full article HTML is
stored; data/database/articles.csv has titles/URLs but not content) and calls
add_article() for each one, matching each JSON file to its article_id in
articles.csv by title (falls back to the filename stem if no match is found).

Run this against the target Weaviate, e.g. on the new server after
`docker compose up -d`:
    docker compose run --rm blog-generator python backfill_weaviate.py

Safe to run more than once: add_article() only appends chunks, so re-running
after a partial run duplicates already-backfilled articles. Wipe first with
VectorStoreManager.clear_all_data() if you need a clean re-seed.
"""
import csv
import json
import logging
import os
from types import SimpleNamespace

from src.config import Config
from utils.utils import VectorStoreManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ARTICLES_CSV = os.path.join(Config.BASE_DIR, "database", "articles.csv")


def _load_article_ids_by_title() -> dict:
    if not os.path.exists(ARTICLES_CSV):
        return {}
    with open(ARTICLES_CSV, "r", encoding="utf-8") as file_handle:
        return {row["title"]: row["article_id"] for row in csv.DictReader(file_handle)}


def main():
    if not os.path.isdir(Config.JSON_OUTPUT_DIR):
        logger.warning("No JSON output directory found at %s — nothing to backfill.", Config.JSON_OUTPUT_DIR)
        return

    vector_store = VectorStoreManager(Config.VECTOR_STORE_PATH)
    if not vector_store.client:
        logger.error("Weaviate is not reachable (check WEAVIATE_HOST/PORT) — aborting.")
        return

    article_ids_by_title = _load_article_ids_by_title()
    added = 0

    for filename in sorted(os.listdir(Config.JSON_OUTPUT_DIR)):
        if not filename.endswith(".json"):
            continue
        json_path = os.path.join(Config.JSON_OUTPUT_DIR, filename)
        try:
            with open(json_path, "r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
        except (OSError, ValueError) as error:
            logger.warning("Could not read %s: %s — skipping.", filename, error)
            continue

        title = data.get("title", "")
        content_html = data.get("article_content", "")
        if not title or not content_html:
            logger.warning("%s missing title/article_content — skipping.", filename)
            continue

        article_id = article_ids_by_title.get(title, os.path.splitext(filename)[0])
        article = SimpleNamespace(title=title, content_html=content_html)
        vector_store.add_article(article, article_id)
        added += 1
        logger.info("Backfilled: '%s'", title[:70])

    logger.info("Done. Backfilled %d article(s) into Weaviate.", added)


if __name__ == "__main__":
    main()

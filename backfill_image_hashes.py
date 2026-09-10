"""
backfill_image_hashes.py
=========================
One-time (safely rerunnable) maintenance script: fingerprints every hero image
already in data/output/images/ and records it in the ImageDedupGuard history,
so the near-duplicate guard protects against the full existing catalog instead
of only images generated after the guard was added. Matches each image to its
real article title via the JSON output file of the same base filename;
falls back to the filename itself if no matching JSON is found.

Safe to run more than once: skips any title already present in the history.
"""
import json
import logging
import os

from src.config import Config
from src.services.image_dedup import ImageDedupGuard

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    if not os.path.isdir(Config.IMAGES_DIR):
        logger.warning("No images directory found at %s — nothing to backfill.", Config.IMAGES_DIR)
        return

    existing_titles = {rec.get("title") for rec in ImageDedupGuard._load_history()}
    added = skipped = 0

    for filename in sorted(os.listdir(Config.IMAGES_DIR)):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue

        base_name = os.path.splitext(filename)[0]
        json_path = os.path.join(Config.JSON_OUTPUT_DIR, f"{base_name}.json")
        title = base_name
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as file_handle:
                    title = json.load(file_handle).get("title", base_name)
            except (OSError, ValueError) as error:
                logger.warning("Could not read %s: %s — using filename as title.", json_path, error)

        if title in existing_titles:
            skipped += 1
            continue

        image_path = os.path.join(Config.IMAGES_DIR, filename)
        try:
            with open(image_path, "rb") as file_handle:
                image_hash = ImageDedupGuard.compute_hash(file_handle.read())
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.warning("Could not hash %s: %s — skipping.", filename, error)
            continue

        ImageDedupGuard.record(image_hash, title)
        existing_titles.add(title)
        added += 1
        logger.info("Backfilled: '%s'", title[:70])

    logger.info("Done. Backfilled %d image(s), skipped %d already-recorded.", added, skipped)


if __name__ == "__main__":
    main()

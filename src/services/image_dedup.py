"""
ImageDedupGuard Module
=======================
Fingerprints generated hero images and flags near-duplicates against recently
generated ones, so two articles never ship the same "photo" (e.g. two different
zipline articles both getting a lone-rider-silhouetted-at-sunset shot).

Uses a dependency-free difference hash (dHash) — Pillow is already a project
dependency, nothing new to install. dHash was chosen over the simpler average
hash (aHash) after testing both against a real confirmed-duplicate pair from
this project (two "zipline" articles' hero images) plus five unrelated images:
aHash ranked the true duplicate as an unremarkable middle-of-the-pack pair
(19th percentile), while dHash correctly ranked it as the single most similar
pair in the whole set. aHash encodes absolute brightness per pixel, which on
these outdoor/sky/water-heavy photos is dominated by generic tonal similarity
between totally unrelated images; dHash encodes the *gradient* between
adjacent pixels (edges/structure), which tracks composition similarity much
more closely — see tests/test_suite.py for the synthetic regression tests.
"""
import json
import logging
import os
from io import BytesIO
from typing import Dict, List, Optional

from PIL import Image

from src.config import Config

logger = logging.getLogger(__name__)


class ImageDedupGuard:
    """Utility to fingerprint generated images and detect near-duplicates."""

    HASH_SIZE = 8  # 8x8 grid of horizontal gradients -> 64-bit hash

    @classmethod
    def compute_hash(cls, image_bytes: bytes) -> int:
        """Difference hash: shrink to a (HASH_SIZE+1) x HASH_SIZE greyscale
        thumbnail and record, for each pixel, whether it's brighter than its
        right-hand neighbour. This encodes the image's edge/structure pattern
        rather than absolute brightness, which is what actually tracks
        composition similarity between two photos — see the module docstring
        for why this beat average-hash on real data."""
        img = Image.open(BytesIO(image_bytes)).convert("L").resize(
            (cls.HASH_SIZE + 1, cls.HASH_SIZE), Image.LANCZOS
        )
        pixels = list(img.getdata())
        bits = []
        for row in range(cls.HASH_SIZE):
            for col in range(cls.HASH_SIZE):
                left = pixels[row * (cls.HASH_SIZE + 1) + col]
                right = pixels[row * (cls.HASH_SIZE + 1) + col + 1]
                bits.append("1" if left > right else "0")
        return int("".join(bits), 2)

    @staticmethod
    def hamming_distance(hash_a: int, hash_b: int) -> int:
        return bin(hash_a ^ hash_b).count("1")

    @classmethod
    def _load_history(cls) -> List[Dict]:
        if not os.path.exists(Config.IMAGE_HASHES_PATH):
            return []
        try:
            with open(Config.IMAGE_HASHES_PATH, 'r', encoding='utf-8') as file_handle:
                return json.load(file_handle)
        except (OSError, ValueError) as error:
            logger.warning("[IMAGE_DEDUP] Could not read %s: %s", Config.IMAGE_HASHES_PATH, error)
            return []

    @classmethod
    def find_closest_match(cls, image_hash: int) -> Optional[Dict]:
        """Returns the closest-matching history record with a 'distance' key
        added, or None if there's no history yet. Callers compare `distance`
        against Config.IMAGE_SIMILARITY_THRESHOLD themselves."""
        history = cls._load_history()
        if not history:
            return None
        best = min(history, key=lambda rec: cls.hamming_distance(image_hash, rec["hash"]))
        best = dict(best)
        best["distance"] = cls.hamming_distance(image_hash, best["hash"])
        return best

    @classmethod
    def record(cls, image_hash: int, title: str) -> None:
        """Appends this image's fingerprint to the history file, capped to the
        most recent Config.IMAGE_HASH_HISTORY_LIMIT entries so the file — and
        every future comparison — stays small and fast indefinitely."""
        history = cls._load_history()
        history.append({"hash": image_hash, "title": title})
        history = history[-Config.IMAGE_HASH_HISTORY_LIMIT:]
        try:
            os.makedirs(os.path.dirname(Config.IMAGE_HASHES_PATH), exist_ok=True)
            with open(Config.IMAGE_HASHES_PATH, 'w', encoding='utf-8') as file_handle:
                json.dump(history, file_handle, indent=2)
        except OSError as error:
            logger.warning("[IMAGE_DEDUP] Failed to persist image hash history: %s", error)

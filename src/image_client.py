"""
Image Generation Client Module
This module provides interface for generating blog banner images via Google's Gemini image models.
It includes rate limiting and multi-model fallback support.

Migration note (Aug 2026):
  - Imagen models (imagen-3.0-generate-002 etc.) are DEPRECATED and shut down Aug 17 2026.
  - Replaced by gemini-2.0-flash-preview-image-generation via
    client.models.generate_content() with response_modalities=["IMAGE"].
  - Authentication is now via GOOGLE_AI_STUDIO_API_KEY (Gemini Developer API),
    not Vertex AI. Set USE_VERTEX_AI=False in .env.
"""
import logging
import random
import threading
import time
from typing import Optional, Tuple

from google import genai
from google.genai import types

from src.config import Config
from src.llm_client import ClientManager, TokenBucketLimiter

logger = logging.getLogger(__name__)

# Pricing per image for Gemini image generation models (Aug 2026 rates)
IMAGE_PRICING = {
    "gemini-2.0-flash-preview-image-generation": 0.04,
    "gemini-2.5-flash-image": 0.04,
    "gemini-2.0-flash-exp-image-generation": 0.04,
    "default": 0.04
}


class ImagenLimiterManager:
    """Manages the thread-safe token bucket rate limiter for image generation."""

    _limiter: Optional[TokenBucketLimiter] = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get_limiter(cls) -> Optional[TokenBucketLimiter]:
        """Get or initialize the rate limiter."""
        if not Config.RATE_LIMIT_ENABLED:
            return None
        with cls._lock:
            if cls._limiter is None:
                rpm: float = Config.IMAGEN_RPM_LIMIT
                cls._limiter = TokenBucketLimiter(capacity=1.0, fill_rate=rpm / 60.0)
                logger.info("[RATE_LIMIT_INIT] Created image generation limiter with %.1f RPM", rpm)
            return cls._limiter


def _extract_image_bytes_from_response(response) -> Optional[bytes]:
    """
    Extract raw image bytes from a generate_content() response.

    Gemini image generation returns images as inline_data inside
    response.candidates[0].content.parts. We iterate parts and return
    the first one that carries image bytes.
    """
    try:
        candidates = getattr(response, "candidates", None)
        if not candidates:
            return None
        parts = getattr(candidates[0].content, "parts", None) if candidates else None
        if not parts:
            return None
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None:
                data = getattr(inline_data, "data", None)
                if data:
                    return data  # raw bytes from SDK
        return None
    except (IndexError, AttributeError, TypeError) as e:
        logger.debug("Could not extract image bytes from response: %s", e)
        return None


def generate_blog_image(prompt: str) -> Tuple[Optional[bytes], float]:
    """
    Generates an image using Google's Gemini image generation via the Gen AI SDK.

    Uses generate_content() with response_modalities=["IMAGE"] — the correct
    approach for Gemini image models accessed via Gemini Developer API key.

    Args:
        prompt: The text prompt for generating the image.

    Returns:
        A tuple of (image_bytes, cost), or (None, 0.0) if generation failed.
    """
    try:
        client = ClientManager.get_client()
    except (RuntimeError, ValueError, TypeError, OSError, AttributeError, LookupError) as e:
        logger.error("Could not initialize GenAI Client for image generation: %s", e)
        return None, 0.0

    primary_model: str = Config.IMAGE_MODEL or "gemini-2.5-flash-image"

    # Ordered fallback chain for Gemini image models
    models_to_try = [
        primary_model,
        "gemini-2.5-flash-image",
        "gemini-2.0-flash-exp-image-generation",
        "imagen-3.0-generate-002",
    ]
    # Remove duplicates while preserving order
    models_to_try = list(dict.fromkeys(models_to_try))

    for model in models_to_try:
        max_retries: int = 2  # 3 total attempts per model
        for attempt in range(max_retries + 1):
            try:
                limiter = ImagenLimiterManager.get_limiter()
                if limiter:
                    limiter.acquire()

                logger.info(
                    "Attempting image generation with model: %s (attempt %d/%d)",
                    model, attempt + 1, max_retries + 1
                )

                # New API: generate_content() with IMAGE response modality.
                # Replaces the deprecated generate_images() used with Imagen/Vertex AI.
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=[types.Modality.IMAGE, types.Modality.TEXT],
                    )
                )

                image_bytes = _extract_image_bytes_from_response(response)

                if image_bytes:
                    cost = IMAGE_PRICING.get(model, IMAGE_PRICING["default"])
                    logger.info("SUCCESS: Image generated using %s (Cost: $%.4f)", model, cost)
                    return image_bytes, cost

                logger.warning("Model %s returned success but no image data found in response.", model)
                break

            except Exception as e:  # pylint: disable=broad-exception-caught
                is_429: bool = any(
                    k in str(e).upper()
                    for k in ("429", "RESOURCE_EXHAUSTED", "TOO MANY REQUESTS")
                )
                if is_429 and attempt < max_retries:
                    sleep_duration: float = (2.0 ** attempt) + random.uniform(0.5, 1.5)
                    logger.warning(
                        "Rate limit hit for image model %s. Retrying in %.1fs... Error: %s",
                        model, sleep_duration, e
                    )
                    time.sleep(sleep_duration)
                    continue

                logger.warning(
                    "Error generating image with %s (attempt %d/%d): %s",
                    model, attempt + 1, max_retries + 1, e
                )
                break

    logger.warning("All image generation models failed.")
    return None, 0.0



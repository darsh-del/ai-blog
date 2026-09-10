"""
Cart Export Service Module
============================
Fetches the okghumo cart-export spreadsheet (xlsx) for a single day and hands
it back as raw bytes so EmailService can attach it to the campaign email.
Entirely additive: any failure (network, timeout, bad response, disabled via
.env) is logged and swallowed here — never raises — so a dead/slow endpoint
can never break article generation or delivery.
"""
import logging
from datetime import date, timedelta
from typing import Optional, Tuple

import requests

from src.config import Config

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SEC = 20


def fetch_cart_export() -> Optional[Tuple[bytes, str]]:
    """
    Downloads the cart-export xlsx for the configured lookback window
    (Config.CART_EXPORT_LOOKBACK_DAYS days before today, a single-day range).

    Returns:
        (file_bytes, filename) on success, or None if the export is disabled
        or the request fails for any reason.
    """
    if not Config.CART_EXPORT_ENABLED:
        logger.info("[CART_EXPORT] Disabled via CART_EXPORT_ENABLED; skipping.")
        return None

    export_date = date.today() - timedelta(days=Config.CART_EXPORT_LOOKBACK_DAYS)
    date_str = export_date.isoformat()

    logger.info(
        "[CART_EXPORT] GET %s?startDate=%s&endDate=%s (timeout=%ds)",
        Config.CART_EXPORT_API_URL, date_str, date_str, _REQUEST_TIMEOUT_SEC
    )
    try:
        response = requests.get(
            Config.CART_EXPORT_API_URL,
            params={"startDate": date_str, "endDate": date_str},
            timeout=_REQUEST_TIMEOUT_SEC,
        )
        response.raise_for_status()
        if not response.content:
            logger.warning("[CART_EXPORT] Empty response body (HTTP %d) for %s; skipping attachment.",
                            response.status_code, date_str)
            return None
        logger.info(
            "[CART_EXPORT] Success: HTTP %d, %d bytes, content-type=%s for %s.",
            response.status_code, len(response.content),
            response.headers.get("Content-Type", "unknown"), date_str
        )
        return response.content, f"cart-export_{date_str}.xlsx"
    except requests.RequestException as exc:
        logger.warning("[CART_EXPORT] Request failed for %s: %s", date_str, exc)
        return None

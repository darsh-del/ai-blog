"""
Alert Service Module
=====================
Sends a short notification email when the generation pipeline hits a *real*
failure — not a routine rate-limit backoff, but something a human should look
at: an LLM provider rejecting requests (e.g. expired key, exhausted billing
credits) and falling back to another provider, every LLM fallback exhausted,
or hero image generation failing across every model. Ordinary 429 retries
that succeed are never alerted; this is for degraded/broken states only.
"""
import logging
import smtplib
import threading
import time
from email.mime.text import MIMEText

from src.config import Config

logger = logging.getLogger(__name__)

# ponytail: process-local, in-memory cooldown keyed by alert_key. Resets on
# restart and isn't shared across processes — fine for a single-machine
# campaign run. Swap for a shared store (Redis/file) if this ever runs
# as multiple processes hammering the same failing key at once.
_ALERT_COOLDOWN_SEC = 900.0  # don't resend the same alert more than once per 15 min
_last_alert_sent: dict = {}
_alert_lock = threading.Lock()


def send_error_alert(alert_key: str, subject: str, message: str) -> None:
    """
    Send a plain-text alert email to Config.ALERT_EMAIL_TO, throttled per
    `alert_key` so a persistent failure (e.g. a dead API key) doesn't flood
    the inbox with one email per article. Never raises — a broken alert
    must never break the generation pipeline.
    """
    with _alert_lock:
        now = time.time()
        if now - _last_alert_sent.get(alert_key, 0.0) < _ALERT_COOLDOWN_SEC:
            return
        _last_alert_sent[alert_key] = now

    if not (Config.SMTP_USERNAME and Config.SMTP_PASSWORD):
        logger.warning("[ALERT_SKIPPED] SMTP not configured; could not send alert: %s", subject)
        return

    # ALERT_EMAIL_TO is comma-separated (e.g. "a@x.com, b@y.com"); scoped to this
    # module only — does not touch EmailService's own SMTP_TO/SMTP_CC recipients.
    recipients = [addr.strip() for addr in Config.ALERT_EMAIL_TO.split(",") if addr.strip()]
    if not recipients:
        logger.warning("[ALERT_SKIPPED] ALERT_EMAIL_TO has no valid recipients; could not send alert: %s", subject)
        return

    logger.info("[ALERT_TRIGGERED] %s | Recipients: %s", subject, recipients)

    try:
        msg = MIMEText(message)
        msg["Subject"] = f"⚠️ AI Blog Generator Alert: {subject}"
        msg["From"] = Config.SMTP_USERNAME
        msg["To"] = ", ".join(recipients)

        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
            server.sendmail(Config.SMTP_USERNAME, recipients, msg.as_string())

        logger.info("[ALERT_SENT] %s -> %s", subject, recipients)
    except (smtplib.SMTPException, OSError) as ex:
        logger.error("[ALERT_FAILED] Could not send alert email '%s' to %s: %s", subject, recipients, ex)

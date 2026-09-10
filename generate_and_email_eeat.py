"""
generate_and_email_eeat.py
===========================
Experimental twin of `generate_and_email.py` that trials the recalibrated
E-E-A-T / keyword-density SEO scoring (`src/agents_eeat.SEOEvaluatorAgentEEAT`)
without touching the production script, `src/agents.py`, or `src/services/
orchestrator.py` at all.

Isolation:
- Uses its own LLM API key (`EEAT_ANTHROPIC_API_KEY` / `EEAT_OPENAI_API_KEY`
  in `.env`) so this experiment's usage/cost is tracked separately from the
  production key. Falls back to the normal key with a warning if not set.
- Swaps only `orchestrator.seo_evaluator` for the EEAT variant after
  construction — every other component (scraper, content generator, healer,
  linker, image client, email service) is the exact same code path
  `generate_and_email.py` uses.

If this doesn't pan out, delete this file and `src/agents_eeat.py` —
`generate_and_email.py` is completely unaffected either way.
"""
import os
import sys
import logging
from pathlib import Path

# Force UTF-8 encoding for standard streams to prevent UnicodeEncodeError on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Bootstrap path so imports work from project root
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Separate API key for this experiment, applied BEFORE Config/litellm import
# so it's picked up as the provider key for this process only. Sibling runs of
# generate_and_email.py are separate processes and never see this override.
# ponytail: only anthropic/openai mapped (the two providers this project's
# .env supports) — add a provider here if LLM_MODEL ever points elsewhere.
# ─────────────────────────────────────────────────────────────────────────────
_EEAT_KEY_MAP = {
    "anthropic": ("EEAT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
    "openai": ("EEAT_OPENAI_API_KEY", "OPENAI_API_KEY"),
}
_provider = os.getenv("LLM_MODEL", "anthropic/claude-3-5-haiku-20241022").split("/")[0].lower()
if _provider in _EEAT_KEY_MAP:
    eeat_env_name, prod_env_name = _EEAT_KEY_MAP[_provider]
    eeat_key = os.getenv(eeat_env_name)
    if eeat_key:
        os.environ[prod_env_name] = eeat_key
        logger.info(f"[EEAT_KEY] Using separate API key from {eeat_env_name} for this run.")
    else:
        logger.warning(
            f"[EEAT_KEY] {eeat_env_name} not set in .env — falling back to {prod_env_name} "
            "(usage will NOT be isolated from the production script)."
        )

from src.config import Config
# Force IMAGE_GENERATION_RATIO to 1.0 dynamically in memory to guarantee image generation
Config.IMAGE_GENERATION_RATIO = 1.0

from src.services import BlogGeneratorOrchestrator
from src.concurrent_manager import ConcurrentCampaignManager
from src.services.email_service import EmailService
from src.agents_eeat import SEOEvaluatorAgentEEAT


def _build_orchestrator() -> BlogGeneratorOrchestrator:
    """Same orchestrator as production, with only its SEO evaluator swapped
    for the EEAT-recalibrated one. No orchestrator code is modified."""
    orchestrator = BlogGeneratorOrchestrator()
    orchestrator.seo_evaluator = SEOEvaluatorAgentEEAT()
    return orchestrator


def main():
    print("\n=======================================================")
    print("Starting Article Generation & Email Automation Script (EEAT scoring trial)")
    print(f"Text Model: {Config.MODEL_NAME}")
    print(f"Image Model: {Config.IMAGE_MODEL}")
    print("SEO Scoring: recalibrated keyword density + scored E-E-A-T specificity")
    print("Target: 2 Articles with Hero Banner Images")
    print("=======================================================\n")

    Config.ensure_directories()

    orchestrator = _build_orchestrator()
    manager = ConcurrentCampaignManager(orchestrator)

    logger.info("Starting concurrent generation for 2 articles (EEAT scoring)...")
    successful_articles = manager.run_campaign(
        total_articles=2,
        max_workers=2,
        publish_to_wordpress=False
    )

    if not successful_articles:
        logger.error("No articles were successfully generated. Email delivery skipped.")
        return

    print(f"\nSuccessfully generated {len(successful_articles)} article(s).")
    for idx, art in enumerate(successful_articles, 1):
        has_img = "Yes" if art.get("image_path") else "No"
        print(f"  - Article {idx}: '{art.get('title')}' | Has Image: {has_img} ({art.get('image_path')})")

    email_service = EmailService()

    cc_info = f" (CC: {Config.SMTP_CC})" if Config.SMTP_CC else ""
    print(f"\n[EMAIL PROCESS] Packaging and sending set of {len(successful_articles)} article(s) to TO: {Config.SMTP_TO}{cc_info}...")
    delivery_status = email_service.send_articles_set(successful_articles)

    print(f"\n=======================================================")
    print("Process Complete! (EEAT scoring trial)")
    print(f"Email Delivery Status: {delivery_status.upper()}")
    print("=======================================================\n")


if __name__ == "__main__":
    main()

"""
generate_and_email.py
======================
Generates exactly 2 high-quality, SEO-enhanced articles with related banner images
generated using the Google GenAI SDK (Imagen) and sends them to the email ID
configured in the env file.
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

from src.config import Config
# Force IMAGE_GENERATION_RATIO to 1.0 dynamically in memory to guarantee image generation
Config.IMAGE_GENERATION_RATIO = 1.0

from src.services import BlogGeneratorOrchestrator
from src.concurrent_manager import ConcurrentCampaignManager
from src.services.email_service import EmailService

# Configure logging: INFO level to console for clear monitoring
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    print("\n=======================================================")
    print("Starting Article Generation & Email Automation Script")
    print(f"Text Model: {Config.MODEL_NAME}")
    print(f"Image Model: {Config.IMAGE_MODEL}")
    print("Target: 2 Articles with Hero Banner Images")
    print("=======================================================\n")
    
    # Ensure all data and output directories exist
    Config.ensure_directories()
    
    # Initialize generators and managers
    orchestrator = BlogGeneratorOrchestrator()
    manager = ConcurrentCampaignManager(orchestrator)
    
    logger.info("Starting concurrent generation for 2 articles...")
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

    # Initialize Email Service
    email_service = EmailService()
    
    cc_info = f" (CC: {Config.SMTP_CC})" if Config.SMTP_CC else ""
    print(f"\n[EMAIL PROCESS] Packaging and sending set of {len(successful_articles)} article(s) to TO: {Config.SMTP_TO}{cc_info}...")
    delivery_status = email_service.send_articles_set(successful_articles)
    
    print(f"\n=======================================================")
    print("Process Complete!")
    print(f"Email Delivery Status: {delivery_status.upper()}")
    print("=======================================================\n")

if __name__ == "__main__":
    main()

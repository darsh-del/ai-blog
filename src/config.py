"""
Configuration Module
This module centralizes all configuration variables for the application,
including API keys, file paths, and SEO settings.
"""
import os
import json
import logging
import random
import inspect
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Premium Knowledge Injection Wrappers (Pylint compliant)
# ─────────────────────────────────────────────────────────────────────────────

class PremiumPlacesDetails(dict):
    """
    Custom dictionary wrapper that dynamically returns premium verified data
    when the context corresponds to one of the target 2026 Rishikesh categories.
    """
    def __init__(self, original_data, premium_data):
        super().__init__(original_data)
        self.premium_data = premium_data

    def get(self, key, default=None):
        title = ""
        category = ""
        try:
            for frame_info in inspect.stack():
                if frame_info.function == 'generate_article':
                    frame = frame_info.frame
                    title = (frame.f_locals.get('title') or '').lower()
                    category = (frame.f_locals.get('category') or '').lower()
                    break
        except (OSError, ValueError, KeyError, AttributeError):
            pass

        if key == "locations":
            return self._get_premium_locations(title, category)
        if key == "rafting_routes":
            return self._get_premium_rafting_routes()
        if key == "travel_tips_2026":
            return self._get_premium_travel_tips()

        return super().get(key, default)

    def _get_premium_locations(self, title: str, category: str):
        original_locations = super().get("locations", [])
        merged_locations = list(original_locations)
        categories_data = self.premium_data.get("categories", {})

        is_rafting = "rafting" in title or "rafting" in category
        is_todo = "things to do" in title or "places to visit" in title or \
                  "things to do" in category or "places to visit" in category
        is_aarti = "aarti" in title or "aarti" in category
        is_stay = "hotel" in title or "hostel" in title or "stay" in title or \
                  "hotel" in category or "hostel" in category or "stay" in category
        is_reach = "reach" in title or "travel" in title or "how to get" in title or \
                   "reach" in category or "travel" in category

        if is_aarti:
            self._add_aarti_locations(merged_locations, categories_data)
        if is_stay:
            self._add_stay_locations(merged_locations, categories_data)
        if is_todo or (not is_rafting and not is_aarti and not is_stay and not is_reach):
            self._add_todo_locations(merged_locations, categories_data)

        return merged_locations

    def _add_aarti_locations(self, merged_locations, categories_data):
        aarti_data = categories_data.get("ganga_aarti", {})
        for k, v in aarti_data.items():
            t_data = v.get('timings_2026', {})
            t_str = f"Summer: {t_data.get('summer')} | Winter: {t_data.get('winter')}"
            merged_locations.append({
                "name": f"Ganga Aarti at {k.replace('_', ' ').title()}",
                "famous_for": f"Spiritual light ritual: {v.get('vibe')}",
                "things_to_do": [v.get("features", "")],
                "timings_2026": t_str,
                "how_to_reach": "Accessible by walking or auto-rickshaw to the ghat.",
                "fee": "Free",
                "tips": v.get("tips") or v.get("rules") or ""
            })

    def _add_stay_locations(self, merged_locations, categories_data):
        stay_data = categories_data.get("hotels_hostels", {})
        for hostel in stay_data.get("hostels", []):
            merged_locations.append({
                "name": hostel["name"],
                "famous_for": f"Top-rated social hostel in {hostel['location']}",
                "things_to_do": ["Socializing", "Coworking", "Budget travel stay"],
                "how_to_reach": f"Located in {hostel['location']}, accessible by auto-rickshaw.",
                "fee": f"Approx {hostel['range_inr']} INR per night",
                "tips": hostel["highlights"]
            })
        for hotel in stay_data.get("hotels", []):
            merged_locations.append({
                "name": hotel["name"],
                "famous_for": f"{hotel.get('type', 'Hotel')} in {hotel['location']}",
                "things_to_do": ["Relaxed stay", "Premium amenities"],
                "how_to_reach": f"Located in {hotel['location']}, easy road access.",
                "fee": "Varies by season",
                "tips": hotel["highlights"]
            })

    def _add_todo_locations(self, merged_locations, categories_data):
        todo_data = categories_data.get("things_to_do", {})
        for cafe in todo_data.get("food_and_cafes", []):
            merged_locations.append({
                "name": cafe["name"],
                "famous_for": f"Vibrant {cafe['type']} in Rishikesh",
                "things_to_do": ["Dining", "Coffee", "River viewing"],
                "how_to_reach": "Located in popular areas like Tapovan/Laxman Jhula.",
                "fee": "A la carte pricing",
                "tips": cafe["highlights"]
            })
        for place in todo_data.get("places_to_visit", []):
            merged_locations.append({
                "name": place["name"],
                "famous_for": place["description"],
                "things_to_do": ["Sightseeing", "Photography"],
                "how_to_reach": "Local transport / walking",
                "fee": "Free or low cost",
                "tips": "Carry a camera and check weather."
            })

        # Add Bungee Operators
        bungee_data = categories_data.get("bungee_jumping", {})
        for op in bungee_data.get("operators", []):
            merged_locations.append({
                "name": op["name"],
                "famous_for": f"Bungee Jumping ({op['height']}). {op['highlights']}",
                "things_to_do": ["Bungee Jumping", "Extreme Sports"],
                "how_to_reach": op["logistics"],
                "fee": op["price_inr"],
                "tips": " / ".join(bungee_data.get("safety_rules", []))[:200]
            })

        # Add Giant Swing
        swing_data = categories_data.get("other_adventure_sports", {}).get("giant_swing", {})
        for loc in swing_data.get("locations_and_operators", []):
            merged_locations.append({
                "name": f"Giant Swing at {loc['name']}",
                "famous_for": f"Giant swing from height of {loc['height']}. {swing_data.get('description', '')}",
                "things_to_do": ["Giant Swing", "Pendulum drop"],
                "how_to_reach": f"Located at {loc['name']}.",
                "fee": loc["price_inr"],
                "tips": f"Limits: {loc['limits']}"
            })

        # Add Flying Fox / Ziplining
        fox_data = categories_data.get("other_adventure_sports", {}).get("flying_fox_zipline", {})
        for loc in fox_data.get("locations_and_operators", []):
            merged_locations.append({
                "name": f"Ziplining/Flying Fox at {loc['name']}",
                "famous_for": f"Zipline / Flying Fox of length {loc.get('length', 'N/A')}. {loc.get('notes', '')}",
                "things_to_do": ["Ziplining", "Flying Fox"],
                "how_to_reach": f"Located at {loc['name']}.",
                "fee": loc["price_inr"],
                "tips": f"Limits: {loc['limits']}"
            })

        # Add Paragliding
        paragliding_data = categories_data.get("other_adventure_sports", {}).get("paragliding", {})
        logistics = paragliding_data.get("logistics", {})
        for pkg in paragliding_data.get("flight_packages", []):
            merged_locations.append({
                "name": f"Paragliding: {pkg['name']}",
                "famous_for": f"Paragliding flight lasting {pkg['duration']}. Best for: {pkg.get('best_for', '')}",
                "things_to_do": ["Paragliding", "Scenic flight"],
                "how_to_reach": f"Operates at: {logistics.get('locations', 'N/A')}",
                "fee": pkg["price_inr"],
                "tips": f"Limits: {logistics.get('limits', 'N/A')}"
            })

        # Add Rope Jump
        rope_data = categories_data.get("other_adventure_sports", {}).get("rope_jump", {})
        for loc in rope_data.get("locations_and_operators", []):
            merged_locations.append({
                "name": f"Rope Jump at {loc['name']}",
                "famous_for": f"Rope Jump from height of {loc['height']}. {rope_data.get('description', '')}",
                "things_to_do": ["Rope Jump", "Valley swing"],
                "how_to_reach": f"Located at {loc['name']}.",
                "fee": loc["price_inr"],
                "tips": f"Limits: {loc['limits']}"
            })

    def _get_premium_rafting_routes(self):
        original_routes = super().get("rafting_routes", [])
        merged_routes = list(original_routes)
        categories_data = self.premium_data.get("categories", {})
        rafting_data = categories_data.get("river_rafting", {})

        if rafting_data:
            routes_to_add = [
                ("rafting_9km", "9 KM - Brahmpuri to NIM Beach"),
                ("rafting_16km", "16 KM - Shivpuri to NIM Beach"),
                ("rafting_24km", "24 KM - Marine Drive to NIM Beach"),
                ("rafting_35km", "35 KM - Kaudiyala to NIM Beach"),
                ("rafting_100km", "100 KM - Bhagwan to Rishikesh (Expedition)")
            ]
            names = [r["name"] for r in merged_routes]
            for key, name in routes_to_add:
                r_data = rafting_data.get(key, {})
                if r_data and name not in names:
                    merged_routes.append({
                        "name": name,
                        "distance": r_data.get("actual_river_distance", "N/A"),
                        "grade": r_data.get("grade", "N/A"),
                        "best_for": r_data.get("recommendation") or r_data.get("highlights") or "N/A",
                        "rapids": r_data.get("notable_rapids", "N/A")
                    })
        return merged_routes

    def _get_premium_travel_tips(self):
        original_tips = super().get("travel_tips_2026", {})
        merged_tips = dict(original_tips)
        categories_data = self.premium_data.get("categories", {})
        reach_data = categories_data.get("how_to_reach", {})

        if reach_data:
            air = reach_data.get("by_air", {})
            train = reach_data.get("by_train", {})
            road = reach_data.get("by_road", {})
            infra = reach_data.get("infrastructure_updates_2026", {})

            air_desc = f"{air.get('airport')} ({air.get('distance')}) | Onward: {air.get('onward_travel')}"
            train_desc = f"Local: {train.get('local_stations')}. Hub: {train.get('major_hub')}"

            merged_tips["nearest_airport"] = air_desc
            merged_tips["train_info"] = train_desc
            merged_tips["road_info"] = f"Buses: {road.get('bus_connectivity')}. Driving: {road.get('driving')}"
            merged_tips["infrastructure_2026"] = infra.get("karnaprayag_railway_project")

        return merged_tips


class PremiumPlaces(dict):
    """
    Custom dictionary wrapper that dynamically returns premium verified tourist places
    and underrated gems based on the active article category.
    """
    def __init__(self, original_data, premium_data):
        super().__init__(original_data)
        self.premium_data = premium_data

    def get(self, key, default=None):
        if key in ("top_tourist_places", "underrated_hidden_gems"):
            original_list = super().get(key, [])
            merged_list = list(original_list)
            categories_data = self.premium_data.get("categories", {})
            todo_data = categories_data.get("things_to_do", {})
            names = [p["name"] for p in merged_list]

            if key == "top_tourist_places":
                for place in todo_data.get("places_to_visit", []):
                    if place["name"] not in names:
                        merged_list.append({
                            "name": place["name"],
                            "description": place["description"]
                        })
            else:
                for cafe in todo_data.get("food_and_cafes", []):
                    if cafe["name"] not in names:
                        merged_list.append({
                            "name": cafe["name"],
                            "description": f"A popular {cafe['type']} noted for: {cafe['highlights']}"
                        })
            return merged_list

        return super().get(key, default)


class PremiumKeywords(dict):
    """
    Custom dictionary wrapper for KEYWORDS_ALL to dynamically map enriched
    categories and return targeted keywords for the major topics.
    """
    def __init__(self, original_data):
        super().__init__(original_data)
        self.aliases = {
            "river_rafting_in_rishikesh": "river_rafting",
            "things_to_do_in_rishikesh": "things_to_do_rishikesh",
            "ganga_aarti_in_rishikesh": "spiritual_cultural",
            "best_hotels_and_hostels_in_rishikesh": "best_hotels_and_hostels",
            "how_to_reach_rishikesh": "how_to_reach"
        }

    def get(self, key, default=None):
        normalized_key = key.lower().replace(" ", "_").strip()
        mapped_key = self.aliases.get(normalized_key, normalized_key)

        result = None
        if mapped_key == "river_rafting":
            result = [
                "river rafting in rishikesh",
                "rafting in rishikesh",
                "white water rafting in rishikesh",
                "35 km rafting rishikesh",
                "100 km rafting rishikesh",
                "rafting safety tips rishikesh",
                "what to carry for rafting rishikesh",
                "best rafting in rishikesh",
                "kaudiyala to nim beach rafting"
            ]
        elif mapped_key == "things_to_do_rishikesh":
            result = [
                "things to do in rishikesh",
                "places to visit in rishikesh",
                "best cafes in rishikesh",
                "little buddha cafe rishikesh",
                "beatles ashram rishikesh",
                "bajrang setu glass bridge",
                "waterfalls in rishikesh",
                "adventure sports in rishikesh",
                "rishikesh sightseeing places"
            ]
        elif mapped_key == "spiritual_cultural":
            result = [
                "ganga aarti rishikesh",
                "triveni ghat ganga aarti",
                "parmarth niketan ganga aarti",
                "ganga aarti timings rishikesh",
                "ganga aarti at triveni ghat",
                "rishikesh ganga aarti experience",
                "sunset ganga aarti rishikesh",
                "triveni ghat rishikesh",
                "parmarth niketan ashram"
            ]
        elif mapped_key == "best_hotels_and_hostels":
            result = [
                "best hotels in rishikesh",
                "best hostels in rishikesh",
                "luxury resorts in rishikesh",
                "places to stay in rishikesh",
                "gostops rishikesh",
                "zostel rishikesh",
                "the hosteller rishikesh",
                "aloha on the ganges",
                "taj rishikesh resort",
                "ananda in the himalayas",
                "tapovan hotels",
                "hostels in rishikesh near laxman jhula"
            ]
        elif mapped_key == "how_to_reach":
            result = [
                "how to reach rishikesh",
                "nearest airport to rishikesh",
                "delhi to rishikesh train",
                "haridwar to rishikesh taxi",
                "delhi to rishikesh bus timing",
                "rishikesh railway station trains",
                "rishikesh travel guide",
                "how to travel to rishikesh"
            ]
        else:
            # 1. Try to get from top-level keys
            val = super().get(mapped_key)
            if val is not None:
                result = val
            else:
                # 2. Try to search nested dictionaries
                for _, v in self.items():
                    if isinstance(v, dict) and mapped_key in v:
                        result = v[mapped_key]
                        break

        if result is not None:
            return result
        return super().get(key, default)



class Config:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_DIR = os.path.join(PROJECT_ROOT, "data", "config")

    # Brand and Industry Configuration
    BRAND_NAME = os.getenv("BRAND_NAME", "your_brand_name")
    INDUSTRY_NAME = os.getenv("INDUSTRY_NAME", "your_industry_name")
    BRAND_MENTION_RATIO = float(os.getenv("BRAND_MENTION_RATIO", "0.25"))

    # Location Configuration
    TARGET_CITY = os.getenv("TARGET_CITY", "your_city").strip()
    TARGET_STATE = os.getenv("TARGET_STATE", "your_state").strip()

    # Content Configuration
    BRAND_PROMOTION_ENABLED = os.getenv("BRAND_PROMOTION_ENABLED", "True").lower() == "true"
    DEFAULT_LINK_URL = os.getenv("DEFAULT_LINK_URL", "https://your-website.com/blog")
    DEFAULT_LINK_TEXT = os.getenv("DEFAULT_LINK_TEXT", "Visit our website")
    # URL path segment where published blog posts actually live (e.g. bucketlistt.com/blogs/<slug>).
    # Must match the live site's real permalink structure so canonical URLs are accurate for SEO.
    BLOG_URL_PATH = os.getenv("BLOG_URL_PATH", "blogs").strip("/")

    # Scraper Configuration
    SCRAPER_RAW_MODE = os.getenv("SCRAPER_RAW_MODE", "0") == "1"
    SCRAPER_PAGE_LOAD_TIMEOUT = int(os.getenv("SCRAPER_PAGE_LOAD_TIMEOUT", "30"))
    SCRAPER_ELEMENT_WAIT_TIMEOUT = int(os.getenv("SCRAPER_ELEMENT_WAIT_TIMEOUT", "20"))
    SCRAPER_MAX_RETRIES = int(os.getenv("SCRAPER_MAX_RETRIES", "2"))
    SCRAPER_RETRY_DELAY = int(os.getenv("SCRAPER_RETRY_DELAY", "5"))
    SCRAPER_SITE_GAP = int(os.getenv("SCRAPER_SITE_GAP", "10"))


    # API Configuration
    # Primary key name (preferred): Google AI Studio key used for Gemini text + (optionally) image generation.
    # Backward-compat: fall back to GEMINI_API_KEY if an existing .env still uses it.
    GOOGLE_AI_STUDIO_API_KEY = os.getenv("GOOGLE_AI_STUDIO_API_KEY") or os.getenv("GEMINI_API_KEY")
    # Backward-compat alias. Keep until old envs are migrated.
    GEMINI_API_KEY = GOOGLE_AI_STUDIO_API_KEY

    # Text-generation model. Uses LiteLLM naming: bare "gpt-4o-mini" for OpenAI,
    # "gemini/gemini-2.0-flash" for Gemini, "anthropic/claude-sonnet-5" for Anthropic.
    # OPENAI_API_KEY / GEMINI_API_KEY / ANTHROPIC_API_KEY are read from env automatically.
    LLM_MODEL = os.getenv("LLM_MODEL") or os.getenv("GEMINI_MODEL") or "gpt-4o-mini"
    MODEL_NAME = LLM_MODEL
    # Kept for Imagen (image_client.py) which still uses the Google GenAI SDK directly.
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    IMAGE_MODEL = os.getenv("IMAGE_MODEL", "imagen-4.0-generate-001")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    API_KEY = os.getenv('API_KEY')
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
    PRESENCE_PENALTY = float(os.getenv("PRESENCE_PENALTY", "0.8"))
    FREQUENCY_PENALTY = float(os.getenv("FREQUENCY_PENALTY", "0.6"))
    WEBSITE_START_DATE = os.getenv("WEBSITE_START_DATE", "2024-01-01")

    # Vertex AI / Google Gen AI SDK Configuration
    GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "ai-blog-genrator")
    GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "asia-south1")
    USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "True").lower() == "true"

    # Rate Limiting Configuration
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"

    # Smart defaults depending on Vertex AI setting
    _default_flash_rpm = "120" if os.getenv("USE_VERTEX_AI", "True").lower() == "true" else "15"
    _default_pro_rpm = "20" if os.getenv("USE_VERTEX_AI", "True").lower() == "true" else "2"

    GEMINI_RPM_LIMIT_FLASH = float(os.getenv("GEMINI_RPM_LIMIT_FLASH", _default_flash_rpm))
    GEMINI_RPM_LIMIT_PRO = float(os.getenv("GEMINI_RPM_LIMIT_PRO", _default_pro_rpm))
    GEMINI_RPM_LIMIT_DEFAULT = float(os.getenv("GEMINI_RPM_LIMIT_DEFAULT", "15"))
    IMAGEN_RPM_LIMIT = float(os.getenv("IMAGEN_RPM_LIMIT", "5"))
    GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "5"))
    # Provider-agnostic RPM caps consumed by llm_client. Default to the Gemini-tier values
    # so behaviour on legacy .env files is unchanged; override via LLM_RPM_LIMIT_* for OpenAI.
    LLM_RPM_LIMIT_FLASH = float(os.getenv("LLM_RPM_LIMIT_FLASH", str(GEMINI_RPM_LIMIT_FLASH)))
    LLM_RPM_LIMIT_PRO = float(os.getenv("LLM_RPM_LIMIT_PRO", str(GEMINI_RPM_LIMIT_PRO)))
    LLM_RPM_LIMIT_DEFAULT = float(os.getenv("LLM_RPM_LIMIT_DEFAULT", str(GEMINI_RPM_LIMIT_DEFAULT)))

    # WordPress Configuration
    WORDPRESS_BASE_URL = os.getenv("WORDPRESS_BASE_URL")
    WORDPRESS_USERNAME = os.getenv("WORDPRESS_USERNAME")
    WORDPRESS_TOKEN = os.getenv("WORDPRESS_TOKEN")

    # SMTP Email Configuration
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "darshshah.cs@gmail.com")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_TO = os.getenv("SMTP_TO", "prachi@bucketlistt.com")
    SMTP_CC = os.getenv("SMTP_CC", "founder@bucketlistt.com, divyam.shah@bucketlistt.com, nitant.desai@bucketlistt.com")
    SMTP_BCC = os.getenv("SMTP_BCC", "")

    @classmethod
    def reload_env(cls):
        """Reloads .env file from disk into os.environ and class attributes."""
        load_dotenv(override=True)
        cls.SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
        cls.SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        cls.SMTP_USERNAME = os.getenv("SMTP_USERNAME", "darshshah.cs@gmail.com")
        cls.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        cls.SMTP_TO = os.getenv("SMTP_TO", "prachi@bucketlistt.com")
        cls.SMTP_CC = os.getenv("SMTP_CC", "founder@bucketlistt.com, divyam.shah@bucketlistt.com, nitant.desai@bucketlistt.com")
        cls.SMTP_BCC = os.getenv("SMTP_BCC", "")

    @classmethod
    def get_smtp_to(cls) -> str:
        val = getattr(cls, "SMTP_TO", None)
        return val if val is not None and val != "" else (os.getenv("SMTP_TO") or "prachi@bucketlistt.com")

    @classmethod
    def get_smtp_cc(cls) -> str:
        val = getattr(cls, "SMTP_CC", None)
        return val if val is not None and val != "" else (os.getenv("SMTP_CC") or "founder@bucketlistt.com, divyam.shah@bucketlistt.com, nitant.desai@bucketlistt.com")

    @classmethod
    def get_smtp_bcc(cls) -> str:
        val = getattr(cls, "SMTP_BCC", None)
        return val if val is not None and val != "" else (os.getenv("SMTP_BCC") or "")

    @classmethod
    def validate_api_key(cls):
        model = (cls.LLM_MODEL or "").lower()
        # Detect the provider from the model name (LiteLLM convention).
        if model.startswith("gemini/") or model.startswith("gemini-") or "gemini" in model:
            provider = "gemini"
        elif model.startswith("anthropic/") or model.startswith("claude"):
            provider = "anthropic"
        else:
            provider = "openai"

        if provider == "openai":
            if not cls.OPENAI_API_KEY:
                logger.warning("OPENAI_API_KEY not set. Set it to enable live article generation.")
            else:
                logger.info("OpenAI API key loaded (LLM_MODEL=%s)", cls.LLM_MODEL)
        elif provider == "anthropic":
            if not cls.ANTHROPIC_API_KEY:
                logger.warning("ANTHROPIC_API_KEY not set. Set it to enable live article generation.")
            else:
                logger.info("Anthropic API key loaded (LLM_MODEL=%s)", cls.LLM_MODEL)
        else:  # gemini
            if cls.USE_VERTEX_AI:
                if not cls.GOOGLE_CLOUD_PROJECT or not cls.GOOGLE_CLOUD_LOCATION:
                    logger.warning("Vertex AI enabled but GOOGLE_CLOUD_PROJECT/LOCATION missing.")
                else:
                    logger.info("Vertex AI configured: Project=%s, Location=%s",
                                cls.GOOGLE_CLOUD_PROJECT, cls.GOOGLE_CLOUD_LOCATION)
            elif not cls.GOOGLE_AI_STUDIO_API_KEY:
                logger.warning("GOOGLE_AI_STUDIO_API_KEY not found. Running in fallback (offline) mode.")
            else:
                logger.info("Google AI Studio API key loaded successfully")

        # Imagen still needs a Google key regardless of the text-generation provider.
        if not cls.GOOGLE_AI_STUDIO_API_KEY and not cls.USE_VERTEX_AI:
            logger.info("No Google credentials found — image generation (Imagen) will be skipped.")

    @classmethod
    def get_random_category(cls, article_type: str) -> str:
        categories = cls.PRODUCT_CATEGORIES if article_type == "brand" else cls.INDUSTRY_CATEGORIES
        if categories:
            return random.choice(categories)
        logger.warning("No categories configured for article_type=%s. Using industry fallback.", article_type)
        return cls.INDUSTRY_NAME or "general"

    # Storage Configuration
    BASE_DIR = os.getenv("APP_DATA_DIR", os.path.join(PROJECT_ROOT, "data"))
    PROJECT_DATA_CSV = os.path.join(BASE_DIR, "services.csv")  # Renamed from products.csv
    CSV_PATH = os.path.join(BASE_DIR, "database", "articles.csv")
    USED_TITLES_CSV = os.path.join(BASE_DIR, "database", "used_titles.csv")
    VECTOR_STORE_PATH = os.path.join(BASE_DIR, "vector_store")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")
    BRAND_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "brand")
    IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
    JSON_OUTPUT_DIR = os.path.join(OUTPUT_DIR, "json")
    # Social cross-posting export directories
    SOCIAL_DIR         = os.path.join(OUTPUT_DIR, "social")
    EMAILS_DIR          = os.path.join(OUTPUT_DIR, "emails")

    @classmethod
    def ensure_directories(cls):
        try:
            os.makedirs(cls.BASE_DIR, exist_ok=True)
            os.makedirs(os.path.dirname(cls.CSV_PATH), exist_ok=True)
            os.makedirs(cls.OUTPUT_DIR, exist_ok=True)
            os.makedirs(cls.BRAND_OUTPUT_DIR, exist_ok=True)
            os.makedirs(cls.IMAGES_DIR, exist_ok=True)
            os.makedirs(cls.JSON_OUTPUT_DIR, exist_ok=True)
            os.makedirs(cls.EMAILS_DIR, exist_ok=True)
            logger.info("Storage directories ensured under: %s", cls.BASE_DIR)
        except OSError as error:
            logger.warning("Could not create storage directories at %s: %s", cls.BASE_DIR, error)

    # Scraped data paths
    SCRAPED_TITLES_CSV = os.path.join(BASE_DIR, "database", "scraped_blog_titles.csv")
    SCRAPED_KEYWORDS_CSV = os.path.join(BASE_DIR, "database", "scraped_blog_keywords.csv")
    SCRAPED_ARTICLES_JSON = os.path.join(BASE_DIR, "database", "scraped_articles.json")



    @staticmethod
    def _load_json_config(path: str, default: dict = None) -> dict:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as config_file:
                    return json.load(config_file)
            except (OSError, json.JSONDecodeError) as error:
                logger.warning("Failed to load %s: %s. Using defaults.", path, error)
        else:
            logger.warning("Config file not found at %s. Using defaults.", path)
        return default or {}

    # Load specific configs using locally available CONFIG_DIR
    _keywords_cfg = _load_json_config.__func__(os.path.join(CONFIG_DIR, "keywords.json"), {
        "primary": [], "curated": [], "location": [], "forbidden": []
    })
    _competitors_cfg = _load_json_config.__func__(os.path.join(CONFIG_DIR, "competitors.json"), {
        "scraper_targets": {}, "brand_blacklist": []
    })
    _categories_cfg = _load_json_config.__func__(os.path.join(CONFIG_DIR, "categories.json"), {
        "product_categories": [], "industry_categories": []
    })
    _templates_cfg = _load_json_config.__func__(os.path.join(CONFIG_DIR, "templates.json"), {})
    CATEGORIES_MAPPING = {}
    _schema_map_cfg = _load_json_config.__func__(os.path.join(CONFIG_DIR, "schema_map.json"), {
        "mapping": {}, "id_column": "id"
    })

    @staticmethod
    def _get_env_json(env_name: str, default_val):
        """Helper to load JSON structures from environment variables."""
        val = os.getenv(env_name)
        if val:
            try:
                return json.loads(val)
            except json.JSONDecodeError as error:
                logger.warning("Failed to parse JSON for %s from env: %s", env_name, error)
        return default_val

    # Expose as Class Attributes - Prioritize .env if available
    # Keywords
    # Load ALL keywords from keywords.json for deep-topic targeting
    KEYWORDS_ALL = PremiumKeywords(_keywords_cfg)

    PRIMARY_KEYWORDS = (
        os.getenv("PRIMARY_KEYWORDS", "").split(",")
        if os.getenv("PRIMARY_KEYWORDS")
        else _keywords_cfg.get("primary", [])
    )
    CURATED_KEYWORDS = (
        os.getenv("CURATED_KEYWORDS", "").split(",")
        if os.getenv("CURATED_KEYWORDS")
        else _keywords_cfg.get("curated", [])
    )
    LOCATION_KEYWORDS = (
        os.getenv("LOCATION_KEYWORDS", "").split(",")
        if os.getenv("LOCATION_KEYWORDS")
        else _keywords_cfg.get("location", [])
    )
    FORBIDDEN_KEYWORDS = (
        os.getenv("FORBIDDEN_KEYWORDS", "").split(",")
        if os.getenv("FORBIDDEN_KEYWORDS")
        else _keywords_cfg.get("forbidden", [])
    )

    # Filter out empty strings from splitting
    PRIMARY_KEYWORDS = [k.strip() for k in PRIMARY_KEYWORDS if k.strip()]
    CURATED_KEYWORDS = [k.strip() for k in CURATED_KEYWORDS if k.strip()]
    LOCATION_KEYWORDS = [k.strip() for k in LOCATION_KEYWORDS if k.strip()]
    FORBIDDEN_KEYWORDS = [k.strip() for k in FORBIDDEN_KEYWORDS if k.strip()]

    # Places Data
    PLACES_PATH = os.path.join(CONFIG_DIR, "places.json")
    _places_raw = _load_json_config.__func__(PLACES_PATH, {"top_tourist_places": [], "underrated_hidden_gems": []})

    # Detailed Places Information (New Researcher Data)
    PLACES_DETAILS_PATH = os.path.join(CONFIG_DIR, "rishikesh_places_details.json")
    _places_details_raw = _load_json_config.__func__(
        PLACES_DETAILS_PATH,
        {"locations": [], "rafting_routes": [], "travel_tips_2026": {}}
    )

    # Premium Knowledge Database File
    PREMIUM_KNOWLEDGE_PATH = os.path.join(CONFIG_DIR, "rishikesh_premium_knowledge.json")
    _premium_cfg = _load_json_config.__func__(PREMIUM_KNOWLEDGE_PATH, {})

    # Wrap PLACES_DATA and PLACES_DETAILS_DATA with the premium wrapper classes
    PLACES_DATA = PremiumPlaces(_places_raw, _premium_cfg)
    PLACES_DETAILS_DATA = PremiumPlacesDetails(_places_details_raw, _premium_cfg)

    # Scraper Targets & Blacklist (Override with JSON strings in .env if needed)
    SCRAPER_TARGETS = _get_env_json.__func__("SCRAPER_TARGETS", _competitors_cfg.get("scraper_targets", {}))
    SCRAPER_BRAND_BLACKLIST = _get_env_json.__func__(
        "SCRAPER_BRAND_BLACKLIST", _competitors_cfg.get("brand_blacklist", [])
    )

    # Categories
    PRODUCT_CATEGORIES = _get_env_json.__func__("PRODUCT_CATEGORIES", _categories_cfg.get("product_categories", []))
    INDUSTRY_CATEGORIES = _get_env_json.__func__("INDUSTRY_CATEGORIES", _categories_cfg.get("industry_categories", []))

    # Templates & Schema
    TEMPLATES = _get_env_json.__func__("TEMPLATES", _templates_cfg)
    SCHEMA_MAP = _get_env_json.__func__("SCHEMA_MAP", _schema_map_cfg.get("mapping", {}))
    PRODUCT_ID_COL = _schema_map_cfg.get("id_column", os.getenv("PRODUCT_ID_COL", "service_name"))

    IMAGE_GENERATION_RATIO = float(os.getenv("IMAGE_GENERATION_RATIO", "1.0"))

    # SEO Configuration
    MIN_WORD_COUNT = int(os.getenv("MIN_WORD_COUNT", "1000"))
    MAX_WORD_COUNT = int(os.getenv("MAX_WORD_COUNT", "1500"))
    SEO_THRESHOLD = int(os.getenv("SEO_THRESHOLD", "80"))
    MAX_ITERATIONS = int(os.getenv("MAX_ARTICLE_RETRIES", "3"))
    MAX_TOTAL_ARTICLES = int(os.getenv("MAX_TOTAL_ARTICLES", "50000"))



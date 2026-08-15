"""
Title Prompts Module
Contains prompt generation functions for titles and location sanitization.
"""
import random
from typing import List

from src.config import Config


def create_title_prompt(
    num: int,
    project_context: str,
    *,
    article_type: str = "generic",
    scraped_keywords: List[str] = None,
    category: str = "",
    seed_title: str = ""
) -> str:
    """
    Creates a prompt for generating SEO-optimized blog titles.
    """
    is_brand_article = article_type.lower() == "brand"

    # Add category context if present
    category_instruction = ""
    if category:
        if is_brand_article:
            category_instruction = (
                f"- **Product Category Focus:** The title MUST be about the specific product '{category}'.\n"
                "- **Angle:** Focus on 'how-to-use', 'where-to-apply', "
                "'optimal usage scenarios', and 'product-specific features'.\n"
                f"    - **Example Style:** 'The Ultimate Guide to Using {category} for [Need]', "
                f"'Top Features of {category}'."
            )
        else:
            category_instruction = (
                f"- **Category Focus:** The title MUST be SPECIFICALLY about the travel topic/activity '{category}'.\n"
                f"    - **Angle:** Focus on 'travel itineraries', 'essential tips', 'visitor guides', "
                "and 'experiential reviews'.\n"
                f"    - **Mandatory Term:** The title **MUST** contain the word/phrase '{category}' "
                "or a direct synonym to ensure topic clarity.\n"
                f"    - **Hierarchy:** The CATEGORY ({category}) is the MASTER TOPIC. Keywords are just modifiers.\n"
                "- **DYNAMIC TOPICAL ISOLATION:** \n"
                f"        - The title MUST stay exclusively within the specific universe of '{category}'.\n"
                "        - Identify the relevant travel theme and FORBID context-mixing from unrelated niches.\n"
                "        - Ensure the title remains focused on the primary experience and value of "
                f"'{category}' for visitors to Rishikesh."
            )

    # Include scraped keywords if available (for generic articles)
    keywords_instruction = ""
    if scraped_keywords and not is_brand_article:
        # Pick 8 random keywords to ensure variety across batches
        keyword_sample = random.sample(scraped_keywords, min(len(scraped_keywords), 8))
        sample_keywords = ", ".join(keyword_sample)
        keywords_instruction = f"- **Secondary Keywords (Use ONLY as modifiers):** {sample_keywords}"

    brand_instruction = ""
    if is_brand_article:
        brand_instruction = f"""
        - **Brand Focus:** Titles MUST mention "{Config.BRAND_NAME}".
        - **Format:** Focus on high-value benefits, specific product durability, or solving maintenance problems.
        - **NO LOCATION:** Do NOT mention specific cities like "{Config.TARGET_CITY}" in the TITLE.
        """
    else:
        brand_instruction = f"""
        - **Travel Focus:** Educational, informative, inspirational, and broad. 
        - **Brand Exclusion:** Do NOT mention specific brands like "{Config.BRAND_NAME}".
        - **No City:** Do NOT mention specific cities like "{Config.TARGET_CITY}".
        - **Styles:** Use "Comparison", "Ultimate Guide", "First-timer Guide", or "Local Secrets".
        """

    seed_instruction = ""
    if seed_title:
        seed_instruction = f"- **Seed Title:** Use this as a base and REPHRASE it: '{seed_title}'"

    prompt = f"""
    You are an SEO expert and Travel Writer specializing in {Config.INDUSTRY_NAME}. Generate {num} distinct, unique, and high-CTR blog post titles.

    **CONTEXT:**
    {project_context}
    
    **REQUIREMENTS:**
    - **LANGUAGE: MUST be in English ONLY.** Failure to comply will result in immediate rejection.
    - **Article Type:** {'Brand-Specific' if is_brand_article else 'Informational-Generic'}
    {category_instruction}
    {brand_instruction}
    {keywords_instruction}
    {seed_instruction}
    - **Length:** 40-65 characters.
    - **SEO:** Title MUST contain a relevant travel keyword naturally.
    
    - **SERP-MATCHING FORMAT (MANDATORY):**
        Look at what actually ranks on page 1 of Google for travel/adventure queries.
        Ranking titles are BORING, CONCRETE, and LEAD WITH THE KEYWORD.
        Approved patterns (pick one per title, vary across the batch):
          A) "[Primary Keyword]: [Concrete Benefit] ([Year])"
             e.g. "Bungee Jumping in Rishikesh: Price, Height & Booking Guide (2026)"
          B) "[Number] [Thing] in [City] [Year] — [Qualifier]"
             e.g. "15 Best Adventure Sports in Rishikesh 2026 — Prices & Booking"
          C) "[Primary Keyword] — [Practical Angle]"
             e.g. "River Rafting in Rishikesh — Route Comparison for First-Timers"
          D) Question format (only for informational queries):
             e.g. "How Much Does Bungee Jumping in Rishikesh Cost?"

    - **PRICE / YEAR SIGNAL:** If the topic is commercial (bungee, rafting, packages,
      hotels, tickets), the title SHOULD include either a starting price ("from ₹XXX")
      or the current year (2026). These beat plain titles on CTR.

    - **VARIETY CHECKLIST:**
        1. Vary starting word across the batch (not all titles start the same way).
        2. Mix at least two of the four approved patterns (A–D) across the batch.
        3. Every title must contain the primary keyword or a very close variant.

    - **FORBIDDEN — DO NOT USE THESE WORDS OR PHRASES IN ANY TITLE:**
        Hype verbs: Unleash, Unlock, Elevate, Transform, Transformative, Discover,
        Master, Mastering, Conquer, Navigate (as verb), Embark, Journey (as verb),
        Ignite, Awaken, Explore (as opener).
        Empty modifiers: Ultimate, Complete, Perfect, Insider (as noun), Essential (as opener),
        Everything You Need To Know, Ultimate Guide (unless the topic is genuinely
        exhaustive), Comprehensive.
        Clickbait: Shocking, Guaranteed, Revolutionary, You Won't Believe, Secret,
        Hidden Gems (overused), Life-Changing.
        Brand fluff: BUCKETLISTT's, Elevate Your, Craft Your, Curate Your.

        Reason: these read as AI-written and depress CTR. Ranking pages use plain,
        keyword-forward titles that match how people actually search.
        
    - **OUTPUT FORMAT:** Return ONLY a numbered list of titles, one per line. No introduction, no markdown notes.
    """
    return prompt


def create_location_sanitizer_prompt(
    sample_titles: List[str],
    sample_keywords: List[str],
    need_titles: int,
    need_keywords: int,
    allowed_localities: List[str],
) -> str:
    """Creates a prompt that forces titles/keywords to be strictly specific to the target city."""
    allowed = ", ".join(allowed_localities)
    sample_titles_block = "\n".join(sample_titles)
    sample_keywords_block = ", ".join(sample_keywords)
    city = Config.TARGET_CITY

    prompt = (
        f"You will SANITIZE and TOP UP {Config.INDUSTRY_NAME} blog TITLES and KEYWORDS "
        f"to be strictly {city}-only for travel guides.\n\n"
        "STRICT LOCATION POLICY:\n"
        f"- All outputs must be about {city}.\n"
        f"- Treat allowed localities as {city} (allowed).\n"
        f"- If any item mentions a non-{city} city/locality, rewrite it to '{city}' or an allowed locality.\n"
        f"- Allowed localities: [{allowed}]\n"
        "- Any locality not in this list is forbidden; rewrite or replace.\n"
        f"- If an item cannot be localized, DROP it and create an {city}-only alternative.\n\n"
        f"NEEDS: +{need_titles} TITLES and +{need_keywords} KEYWORDS after sanitizing and deduping.\n\n"
        f"INPUT (examples):\n"
        f"Current Titles:\n{sample_titles_block}\n\n"
        f"Current Keywords:\n{sample_keywords_block}\n\n"
        "OUTPUT FORMAT (CRITICAL — EXACTLY THIS):\n"
        "TITLES:\n"
        f"1. <{city}-only title>\n"
        f"2. <{city}-only title>\n"
        "...\n"
        "KEYWORDS:\n"
        "keyword 1, keyword 2, keyword 3, ...\n"
    )
    return prompt

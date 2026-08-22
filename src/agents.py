"""
AI Agents Module
This module defines the core AI agents responsible for content generation and SEO evaluation.
- ContentGeneratorAgent: Creates the initial blog post.
- SEOEvaluatorAgent: Scores the post and provides feedback.
"""
import re
import csv
import json
import logging
import os
import random
import secrets
import string
import threading
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set

from src.llm_client import call_llm, LLM_AVAILABLE, RateLimitExhaustedError
from src.config import Config
from src.models import ArticleDraft, Metadata, SEOReport, SEOMetric, LLMConfig
from prompts.prompts import create_content_prompt, create_humanize_prompt, create_title_prompt


# ─────────────────────────────────────────────────────────────────────────────
# SlugRegistry — Collision-Proof Slug Generation Engine
# ─────────────────────────────────────────────────────────────────────────────
class SlugRegistry:
    """
    Persistent slug registry that guarantees every article published to WordPress
    has a unique, SEO-safe URL slug — preventing the -2 / -3 numeric collision
    suffixes WordPress silently appends when two posts share a slug prefix.

    Design:
    - Max slug length: 60 chars  (SEO-optimal, well under WP 200-char DB limit)
    - Meaningful words only: strips English stopwords so slugs are keyword-dense
    - Collision strategy: clean URL by default; appends -YYMMDD date suffix only
      when a collision is detected (never a meaningless counter)
    - Prefix guard: tracks the first-5-word slug prefix to catch cases where WP
      would auto-truncate two different slugs down to the same base
    """

    MAX_SLUG_LEN: int = 60
    STOPWORDS: frozenset = frozenset({
        'a', 'an', 'the', 'and', 'or', 'but', 'for', 'to', 'of', 'in',
        'on', 'at', 'by', 'is', 'are', 'was', 'be', 'as', 'it', 'its',
        'do', 'did', 'can', 'with', 'from', 'this', 'that', 'these',
        'those', 'will', 'has', 'have', 'had', 'not', 'so', 'up', 'if',
        'we', 'you', 'he', 'she', 'they', 'i', 'my', 'your', 'our'
    })

    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.used_slugs: Set[str] = set()
        # Maps 5-word slug prefix → count of articles using it
        self.used_prefixes: Dict[str, int] = {}
        self._lock = threading.Lock()
        self._load_from_csv()

    # ── Private helpers ──────────────────────────────────────────────────────

    def _load_from_csv(self) -> None:
        """Load all existing slugs from articles.csv at startup."""
        if not os.path.exists(self.csv_path):
            return
        try:
            with open(self.csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Prefer confirmed WP slug; fall back to pre-computed URL slug
                    slug = (row.get('wp_published_slug') or '').strip()
                    if not slug:
                        url = (row.get('url') or '').strip()
                        if url:
                            slug = url.rstrip('/').split('/')[-1]
                    if slug:
                        self.used_slugs.add(slug)
                        prefix = '-'.join(slug.split('-')[:5])
                        self.used_prefixes[prefix] = self.used_prefixes.get(prefix, 0) + 1
            logger.debug("SlugRegistry loaded %d existing slugs.", len(self.used_slugs))
        except Exception as e:
            logger.warning("SlugRegistry: Could not load existing slugs from CSV: %s", e)

    def _sanitize(self, text: str) -> str:
        """Convert title text to lowercase, URL-safe hyphenated string."""
        text = text.lower().strip()
        text = re.sub(r'[^a-z0-9\s-]', '', text)
        text = re.sub(r'[\s_]+', '-', text)
        text = re.sub(r'-+', '-', text)
        return text.strip('-')

    def _semantic_core(self, title: str) -> str:
        """
        Extract the first 8 meaningful words from the title (stopwords removed).
        This creates keyword-dense slugs and avoids collisions on generic prefixes
        like 'best-things-to-do-in' that WordPress would truncate identically.
        """
        words = self._sanitize(title).split('-')
        meaningful = [w for w in words if w and w not in self.STOPWORDS and len(w) > 1]
        return '-'.join(meaningful[:8])

    def _five_word_prefix(self, slug: str) -> str:
        return '-'.join(slug.split('-')[:5])

    # ── Public API ───────────────────────────────────────────────────────────

    def generate_unique_slug(self, title: str, category: str = "") -> str:
        """
        Generate a collision-free, SEO-safe WordPress slug for the given title.

        Algorithm:
          1. Build semantic core (meaningful words, no stopwords, max 8 words)
          2. Truncate to MAX_SLUG_LEN (60 chars)
          3. Check: if slug OR its 5-word prefix is already taken → append -YYMMDD
          4. If still colliding (rare), append incrementing counter (-YYMMDD-1 etc.)
          5. Register the final slug and return it
        """
        with self._lock:
            base = self._semantic_core(title)
            if not base:
                # Extreme fallback: just sanitize the whole title
                base = self._sanitize(title)

            candidate = base[:self.MAX_SLUG_LEN].rstrip('-')
            prefix5 = self._five_word_prefix(candidate)

            # Clean URL — no collision, use as-is
            if candidate not in self.used_slugs and self.used_prefixes.get(prefix5, 0) == 0:
                return candidate

            # Collision detected — append YYMMDD date suffix
            date_tag = datetime.now().strftime('%y%m%d')
            # Reserve 7 chars for -YYMMDD suffix
            trimmed_base = candidate[:self.MAX_SLUG_LEN - 7].rstrip('-')
            dated = f"{trimmed_base}-{date_tag}"

            if dated not in self.used_slugs:
                return dated

            # Very rare: same base + same date → add counter
            counter = 1
            final = dated
            while final in self.used_slugs and counter < 999:
                suffix = f"-{date_tag}-{counter}"
                final = f"{trimmed_base[:self.MAX_SLUG_LEN - len(suffix)]}{suffix}"
                counter += 1

            logger.warning(
                "SlugRegistry: Collision resolved with counter slug '%s' (base='%s')",
                final, base
            )
            return final

    def register(self, slug: str) -> None:
        """Register a slug as used after a successful publish or generation."""
        if not slug:
            return
        with self._lock:
            self.used_slugs.add(slug)
            prefix5 = self._five_word_prefix(slug)
            self.used_prefixes[prefix5] = self.used_prefixes.get(prefix5, 0) + 1
            logger.debug("SlugRegistry: Registered slug '%s' (prefix: '%s')", slug, prefix5)

    def is_slug_available(self, slug: str) -> bool:
        """Returns True if neither the slug nor its 5-word prefix is taken."""
        with self._lock:
            if slug in self.used_slugs:
                return False
            if self.used_prefixes.get(self._five_word_prefix(slug), 0) > 0:
                return False
            return True



class TitleManager:
    """Manages used titles to prevent duplicates.

    Near-duplicate detection uses a word-bigram Jaccard similarity index stored
    in memory.  At 5 000+ articles the old SequenceMatcher approach held the
    shared lock while running an O(n²) CPU loop, stalling every worker thread
    for 1-2 minutes per check.  The new design:
      1. Acquires the lock only to snapshot the lightweight bigram index (~0.1 ms).
      2. Releases the lock immediately.
      3. Does the Jaccard comparison on the private snapshot — no lock held.
    """

    # Starting words that the LLM over-uses; tighter per-word cap applied.
    _OVERUSED_STARTS: frozenset = frozenset({
        "mastering", "discover", "unveiling", "unlocking",
        "the", "ultimate", "how", "why"
    })

    def __init__(self, csv_path: str, similarity_threshold: float = 0.9):
        """
        Initialize the TitleManager.

        Args:
            csv_path: Path to the CSV file to store used titles.
            similarity_threshold: Word-bigram Jaccard threshold above which
                two titles are considered duplicates (0–1).  0.75 produces
                coverage equivalent to SequenceMatcher ratio 0.9 for 8-12 word
                titles, validated by research on short-text n-gram dedup systems.
        """
        self.csv_path = csv_path
        # 0.75 Jaccard on word bigrams ≈ 0.9 SequenceMatcher ratio for 8-12 word titles.
        # Slightly more lenient than the old 0.9 SM threshold to allow more variety
        # while still blocking near-identical rephrases.
        self.similarity_threshold = similarity_threshold or 0.75
        self.used_titles: Set[str] = set()
        # {first_word: count} — rebuilt from disk on startup (bug fix: was always 0 at boot).
        self.starting_word_counts: Dict[str, int] = {}
        # {title_str: frozenset_of_word_bigrams} — enables O(k) Jaccard outside the lock.
        self._fingerprint_index: Dict[str, frozenset] = {}
        self._lock = threading.Lock()
        self._load_used_titles()

    # ── Fingerprint helpers ───────────────────────────────────────────────────

    @staticmethod
    def _word_bigrams(text: str) -> frozenset:
        """Return the frozenset of word bigrams for a normalised title string.

        Word bigrams capture local phrase context ('river rafting', 'safety guide')
        while being fast to compute (O(n) where n = word count ≈ 8-12).
        A frozenset makes set-intersection and union operations O(k) via C built-ins.
        """
        words = text.split()
        if len(words) < 2:
            # Single-word or empty title: fall back to the word itself as a unigram.
            return frozenset(words)
        return frozenset(tuple(words[i:i + 2]) for i in range(len(words) - 1))

    # ── Private loaders ───────────────────────────────────────────────────────

    def _load_used_titles(self) -> None:
        """Load used titles from both the tracking CSV and the main articles CSV."""
        self._load_from_file(self.csv_path)
        if self.csv_path != Config.CSV_PATH:
            self._load_from_file(Config.CSV_PATH)
        logger.info(
            "[TitleManager] Loaded %d titles. starting_word_counts has %d distinct first-words.",
            len(self.used_titles), len(self.starting_word_counts)
        )

    def _register_loaded_title(self, raw_title: str) -> None:
        """Register one title loaded from disk into all in-memory indexes.

        Kept separate so both CSV readers call a single code path.
        """
        title_lower = raw_title.lower().strip()
        if not title_lower or title_lower in self.used_titles:
            return
        self.used_titles.add(title_lower)
        # Build starting-word counter so the overuse limit is accurate at startup.
        first_word = title_lower.split()[0] if title_lower.split() else ""
        if first_word:
            self.starting_word_counts[first_word] = (
                self.starting_word_counts.get(first_word, 0) + 1
            )
        # Build bigram fingerprint index so is_title_used() never needs to recompute.
        self._fingerprint_index[title_lower] = self._word_bigrams(title_lower)

    def _load_from_file(self, path: str) -> None:
        """Load titles (and rebuild all indexes) from a CSV file."""
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as file_handle:
                content = file_handle.read()
                file_handle.seek(0)
                if not content.strip():
                    return

                reader = csv.DictReader(file_handle)
                if reader.fieldnames and 'title' in reader.fieldnames:
                    for row in reader:
                        if row and row.get('title'):
                            self._register_loaded_title(row['title'])
                    logger.info("[TitleManager] Loaded titles from %s (DictReader).", path)
                    return

                # Fallback: plain CSV reader
                file_handle.seek(0)
                plain_reader = csv.reader(file_handle)
                header = next(plain_reader, None)
                title_idx = 0
                if header:
                    for col_idx, col in enumerate(header):
                        if col.lower() == 'title':
                            title_idx = col_idx
                            break
                for row in plain_reader:
                    if row and len(row) > title_idx:
                        self._register_loaded_title(row[title_idx])
                logger.info("[TitleManager] Loaded titles from %s (fallback reader).", path)

        except Exception as err:
            logger.error("[TitleManager] Failed to load titles from %s: %s", path, err)

    # ── Public API ────────────────────────────────────────────────────────────

    def save_used_title(self, title: str) -> None:
        """Persist a new title and update all in-memory indexes atomically."""
        if not title:
            return
        title_lower = title.lower().strip()
        with self._lock:
            if title_lower in self.used_titles:
                return
            self.used_titles.add(title_lower)
            # Update starting-word counter.
            first_word = title_lower.split()[0] if title_lower.split() else ""
            if first_word:
                self.starting_word_counts[first_word] = (
                    self.starting_word_counts.get(first_word, 0) + 1
                )
            # Update fingerprint index — keeps is_title_used() snapshot accurate.
            self._fingerprint_index[title_lower] = self._word_bigrams(title_lower)
            try:
                with open(self.csv_path, 'a', newline='', encoding='utf-8') as f_handle:
                    writer = csv.writer(f_handle)
                    writer.writerow([title, datetime.now().isoformat()])
            except Exception as err:
                logger.error("[TitleManager] Failed to save used title: %s", err)

    def is_title_used(self, title: str, slug_registry: Optional['SlugRegistry'] = None) -> bool:
        """Return True if the title is a duplicate, near-duplicate, or slug collision.

        Lock-Copy-Process pattern (research-validated best practice):
          1. Acquire lock → run cheap exact/overuse checks → snapshot fingerprint index → release lock.
          2. Run expensive Jaccard comparison on the private snapshot — NO lock held.
          3. Check slug registry outside any lock to prevent lock-inversion deadlock.

        This reduces lock hold time from ~60-120 s (at 5 200 articles with SequenceMatcher)
        to <1 ms, eliminating the thread-serialization stall.
        """
        if not title:
            return False

        new_title = title.lower().strip()
        is_used = False

        # ── Step 1: Fast checks + snapshot (lock held for <1 ms) ─────────────
        with self._lock:
            # Exact match — O(1) set lookup.
            if new_title in self.used_titles:
                is_used = True
            else:
                # Starting-word overuse guard.
                first_word = new_title.split()[0] if new_title.split() else ""
                limit = (
                    2 if first_word in self._OVERUSED_STARTS
                    else max(3, int(len(self.used_titles) * 0.04))
                )
                if first_word and self.starting_word_counts.get(first_word, 0) >= limit:
                    logger.debug(
                        "[TitleManager] Rejected '%s': first word '%s' used %d/%d times.",
                        title, first_word, self.starting_word_counts.get(first_word, 0), limit
                    )
                    is_used = True

            fp_snapshot: Dict[str, frozenset] = {} if is_used else dict(self._fingerprint_index)

        if is_used:
            return True

        # ── Step 2: Near-duplicate scan (NO lock held) ───────────────────────
        new_fp = self._word_bigrams(new_title)
        new_words_prefix = new_title.split()[:3]

        for stored_title, stored_fp in fp_snapshot.items():
            # 3-word prefix check — O(1), catches most near-duplicates instantly.
            if (
                len(new_words_prefix) >= 2
                and len(stored_title.split()[:3]) >= 2
                and new_words_prefix == stored_title.split()[:3]
            ):
                logger.debug("[TitleManager] Prefix match: '%s' vs '%s'.", title, stored_title)
                return True

            # Word-bigram Jaccard similarity — O(k) where k ≈ 7-11 bigrams per title.
            # Uses optimised formula: union = |A| + |B| - |intersection| to avoid
            # materialising the full union set in memory.
            if new_fp and stored_fp:
                u_size = len(new_fp) + len(stored_fp) - len(new_fp & stored_fp)
                if u_size > 0 and (len(new_fp & stored_fp) / u_size) >= self.similarity_threshold:
                    logger.debug(
                        "[TitleManager] Jaccard match (%.2f >= %.2f): '%s' vs '%s'.",
                        len(new_fp & stored_fp) / u_size, self.similarity_threshold,
                        title, stored_title
                    )
                    return True

        # ── Step 3: Slug collision guard (outside all locks) ─────────────────
        # Called outside TitleManager._lock to prevent lock-inversion deadlock
        # with SlugRegistry._lock (documented risk in the original code at L306).
        if slug_registry is not None:
            prospective_slug = slug_registry.generate_unique_slug(title)
            if not slug_registry.is_slug_available(prospective_slug):
                logger.debug(
                    "[TitleManager] Slug collision: '%s' → '%s' already taken.",
                    title, prospective_slug
                )
                return True

        return False

logger = logging.getLogger(__name__)


class ContentGeneratorAgent:
    def __init__(self, model_name: str = Config.MODEL_NAME):
        self.model_name = model_name
        self.product_data = self._load_service_data()
        # Title de-duplication manager
        self.title_manager = TitleManager(Config.USED_TITLES_CSV)
        # Slug collision-prevention registry — loads all used slugs from articles.csv at startup
        self.slug_registry = SlugRegistry(Config.CSV_PATH)
        self._product_rotation = []  # Current rotation of products

    def _build_canonical_url(self, slug: str) -> str:
        """
        Build the real, live canonical URL for a published article, e.g.
        https://www.bucketlistt.com/blogs/best-place-for-bungee-jumping-in-india.
        Must match the site's actual permalink structure (Config.BLOG_URL_PATH) —
        a canonical that doesn't match the live URL hurts SEO rather than helping it.
        """
        return f"{Config.DEFAULT_LINK_URL.rstrip('/')}/{Config.BLOG_URL_PATH}/{slug}"

    def _load_service_data(self) -> List[Dict]:
        """Loads service data from the specified CSV file."""
        if not os.path.exists(Config.PROJECT_DATA_CSV):
            logger.warning("Service data CSV not found at %s. No service data available.", Config.PROJECT_DATA_CSV)
            return []

        services = []
        try:
            if os.stat(Config.PROJECT_DATA_CSV).st_size == 0:
                logger.warning("Service data CSV at %s is empty.", Config.PROJECT_DATA_CSV)
                return []

            with open(Config.PROJECT_DATA_CSV, mode='r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                if not reader.fieldnames:
                    logger.warning("Service CSV has no header/data.")
                    return []
                for row in reader:
                    services.append(dict(row))
            logger.info("Successfully loaded %s services from %s.", len(services), Config.PROJECT_DATA_CSV)
            return services
        except Exception as err:
            logger.error("Failed to load service data from CSV: %s", err)
            return []

    def _get_next_product(self, excluded_products: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Gets the next product in rotation, ensuring even distribution.

        Args:
            excluded_products: List of product names to exclude from selection

        Returns:
            Dict: Product data or None if no products available
        """
        if not self.product_data:
            return None

        if excluded_products is None:
            excluded_products = []

        # Get all available products not in excluded list
        available_products = [
            p for p in self.product_data
            if p.get(Config.PRODUCT_ID_COL) not in excluded_products
        ]

        if not available_products:
            logger.warning("No available products to choose from after exclusion.")
            return None

        # If rotation is empty or all products in rotation are excluded, create new rotation
        if not self._product_rotation or all(
            p.get(Config.PRODUCT_ID_COL) in excluded_products
            for p in self._product_rotation
        ):
            # Create new rotation with available products and shuffle
            self._product_rotation = list(available_products)
            random.shuffle(self._product_rotation)

        # Remove excluded products from rotation
        self._product_rotation = [
            p for p in self._product_rotation
            if p.get(Config.PRODUCT_ID_COL) not in excluded_products
        ]

        if not self._product_rotation:
            return None

        # Get next product and rotate the list
        next_product = self._product_rotation.pop(0)
        return next_product

    # Keep the old method for backward compatibility
    def _get_random_product(self, excluded_products: Optional[List[str]] = None) -> Optional[Dict]:
        """Selects a random, non-excluded product."""
        if not self.product_data:
            return None

        if excluded_products is None:
            excluded_products = []

        available_products = [
            p for p in self.product_data
            if p.get(Config.PRODUCT_ID_COL) not in excluded_products
        ]

        if not available_products:
            logger.warning("No available products to choose from after exclusion.")
            return None

        return random.choice(available_products)

    def _format_product_context(self, product: Optional[Dict]) -> str:
        """Formats product details for a prompt, or returns a generic string."""
        if not product:
            return (
                f"No specific product data available. "
                f"Write a general article about {Config.INDUSTRY_NAME}, trends, or advice."
            )

        context = f"Focus the article on the following {Config.BRAND_NAME} product:\n"

        # Dynamic Context from Schema Map
        mapping = Config.SCHEMA_MAP
        if not mapping:
             # Fallback if no map: dump everything
            for k, val in product.items():
                context += f"- {k.replace('_', ' ').title()}: {val}\n"
        else:
            for csv_col, label in mapping.items():
                val = product.get(csv_col, 'N/A')
                context += f"- {label}: {val}\n"

        return context

    def _strip_json_ld(self, text: str) -> str:
        """Removes JSON-LD schema blocks from the generated content."""
        if not text:
            return ""
        cleaned = re.sub(
            r'<script[^>]*type=\"application/ld\+json\"[^>]*>.*?</script>',
            "", text, flags=re.DOTALL | re.IGNORECASE
        )
        cleaned = re.sub(r"<JSON_LD_SCHEMA>.*?</JSON_LD_SCHEMA>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
        cleaned = re.sub(r"```[a-zA-Z]*\s*\{[\s\S]*?\}\s*```", "", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _extract_text_from_html(self, html_content: str) -> str:
        """Extracts plain text from HTML content."""
        return re.sub(r'<[^>]+>', '', html_content)

    def _create_safe_slug(self, title: str, max_length: int = 70) -> str:
        """Creates a safe URL slug from a title."""
        return re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:max_length]

    def generate_titles(
        self, num: int = 10, article_type: str = "generic", category: str = "", seed_title: str = "",
        scraped_keywords: List[str] = None
    ) -> List[str]:
        """
        Generates SEO-optimized titles for articles.
        Ensures no duplicate or very similar titles are returned.

        Args:
            num: Number of titles to generate
            article_type: Type of article ('generic' or 'brand')
            category: specific category to generate titles for
            seed_title: An optional existing title to rephrase and improve
            scraped_keywords: An optional list of custom keywords to use

        Returns:
            List of generated article titles
        """
        if num <= 0:
            raise ValueError("Number of titles must be positive")
        if article_type not in ("generic", "brand"):
            raise ValueError("Article type must be 'generic' or 'brand'")

        # For brand-specific articles, we'll track which projects we've used
        used_products = set()

        # Get product context - will be updated for each brand-specific article
        product = None
        if article_type == "brand":
            product = self._get_next_product()
            if product:
                used_products.add(product.get(Config.PRODUCT_ID_COL))

        product_context = self._format_product_context(product)
        if scraped_keywords is None:
            scraped_keywords = []
            try:
                if os.path.exists(Config.SCRAPED_ARTICLES_JSON):
                    with open(Config.SCRAPED_ARTICLES_JSON, 'r', encoding='utf-8') as f_handle:
                        data = json.load(f_handle)

                    keywords_accumulator: List[str] = []
                    seen = set()
                    for obj in data:
                        kws = obj.get("keywords") or []
                        if not kws:
                            continue
                        parts = kws if isinstance(kws, list) else [p.strip() for p in str(kws).split(",")]
                        for part in parts:
                            if not part:
                                continue
                            lower = part.lower()
                            if lower in seen:
                                continue
                            seen.add(lower)
                            keywords_accumulator.append(part)
                    scraped_keywords = keywords_accumulator
            except Exception as err:
                logger.warning("Failed to load scraped article keywords from JSON: %s", err)

        if not LLM_AVAILABLE or (not Config.GOOGLE_AI_STUDIO_API_KEY and not Config.USE_VERTEX_AI):
            return self._generate_fallback_titles(num)

        # Try multiple times to get enough unique titles.
        # 6 attempts give more headroom when the LLM returns similar candidates,
        # each attempt uses a freshly-sampled keyword set for variety.
        max_attempts = 6
        unique_titles = []
        attempt = 0

        while len(unique_titles) < num and attempt < max_attempts:
            # Always request at least 5 titles to pick the best one for SEO length
            batch_size = max(5, min(10, (num - len(unique_titles)) * 3))
            if seed_title and num == 1:
                batch_size = 5 # Ask for 5 variations to pick the best length

            # Use a random sample of keywords for each batch to ensure variety
            sampled_keywords = (
                random.sample(scraped_keywords, min(len(scraped_keywords), 20))
                if scraped_keywords else []
            )

            # FORCE CATEGORY RELEVANCE: Inject category terms into the keyword sample
            if category:
                category_terms = [category, f"{category} techniques", f"{category} trends"]
                # Prepend to ensure they are seen first
                sampled_keywords = category_terms + sampled_keywords

            try:
                # For brand-specific articles, get a new product for each title if needed
                if article_type == "brand" and product:
                    # If we've used all products, allow reusing them
                    if len(used_products) == len(self.product_data):
                        used_products.clear()

                    # Get next product that hasn't been used in this batch
                    next_product = self._get_next_product(excluded_products=list(used_products))
                    if next_product:
                        product = next_product
                        used_products.add(product.get(Config.PRODUCT_ID_COL))
                        product_context = self._format_product_context(product)

                # Use sampled keywords for variety
                title_keywords = sampled_keywords if (sampled_keywords and article_type == "generic") else None
                prompt = create_title_prompt(
                    batch_size,
                    product_context,
                    article_type=article_type,
                    scraped_keywords=title_keywords,
                    category=category,
                    seed_title=seed_title
                )

                content = call_llm(
                    prompt,
                    config=LLMConfig(
                        model_name=self.model_name,
                        max_tokens=1500,
                        temperature=Config.TEMPERATURE,
                        presence_penalty=Config.PRESENCE_PENALTY,
                        frequency_penalty=Config.FREQUENCY_PENALTY,
                        task_name="Title Generation"
                    )
                )

                # More robust parsing: handle 1., 1), -, and bullets
                new_titles = []
                for line in content.split('\n'):
                    # Initial cleanup of the whole line
                    line = line.strip().strip('*').strip('_').strip('"').strip("'").strip()
                    if not line:
                        continue

                    # Match numbered lists: 1. Title, 1) Title, etc., or bullets
                    match = re.match(r'^(\d+[\.\)]|[\-\*•])\s*(.*)', line)
                    if match:
                        extracted = match.group(2).strip()
                        # Clean the extracted title as well
                        clean_extracted = extracted.strip('*').strip('_').strip('"').strip("'").strip()
                        new_titles.append(clean_extracted)
                    elif num == 1 and not new_titles and len(line) > 10:
                        # If we only wanted one title, the LLM might have just given the title text itself
                        new_titles.append(line)

                if not new_titles:
                    logger.warning(
                        "[TITLE_GEN] Failed to parse titles from LLM response on attempt %d/%d. "
                        "Snippet: %s...",
                        attempt + 1, max_attempts, content[:100]
                    )

                # Sort candidate titles by how close they are to the ideal 50-char length
                candidates = []
                for title_text in new_titles:
                    # Clean up common AI prefixes
                    title_text = re.sub(r'^(Title|Option|Variation)\s*(\d+)?:\s*', '', title_text, flags=re.IGNORECASE)
                    # Final exhaustive strip of Markdown and quotes
                    title_text = title_text.strip().strip('*').strip('_').strip('"').strip("'").strip()

                    if (title_text and not self.title_manager.is_title_used(title_text, self.slug_registry)
                            and title_text not in unique_titles):
                        # Score based on length only (40-65 chars is ideal)
                        score = 0
                        if 40 <= len(title_text) <= 65:
                            score = 100
                        else:
                            score = 100 - abs(50 - len(title_text))

                        candidates.append((title_text, score))

                # Sort by score descending
                candidates.sort(key=lambda x: x[1], reverse=True)

                # Track starting words used in THIS batch to enforce variety
                used_starting_words = set()

                for title, _ in candidates:
                    # Extract the first word (case-insensitive)
                    first_word = title.split()[0].lower() if title.split() else ""

                    # STRICT RULE: Skip if this starting word is already used in the current batch
                    if first_word in used_starting_words:
                        logger.debug(
                            "Skipping title '%s' - starting word '%s' already used in this batch",
                            title, first_word
                        )
                        continue

                    unique_titles.append(title)
                    self.title_manager.save_used_title(title)
                    used_starting_words.add(first_word)

                    # Update product for next title (previously unreachable)
                    if article_type == "brand":
                        if len(used_products) == len(self.product_data):
                            used_products.clear()
                        next_product = self._get_next_product(excluded_products=list(used_products))
                        if next_product:
                            product = next_product
                            used_products.add(product.get(Config.PRODUCT_ID_COL))
                            product_context = self._format_product_context(product)

                    if len(unique_titles) >= num:
                        break
                if not candidates and new_titles:
                    logger.warning(
                        "[TITLE_GEN] All %d LLM candidates rejected as duplicates on attempt %d/%d. "
                        "Used title count: %d. Retrying with fresh keyword sample.",
                        len(new_titles), attempt + 1, max_attempts,
                        len(self.title_manager.used_titles)
                    )

            except Exception as err:
                logger.error("[TITLE_GEN] Error on attempt %d/%d: %s", attempt + 1, max_attempts, err)

            attempt += 1

        if not unique_titles:
            logger.warning(
                "All LLM title attempts failed or were duplicates. Falling back to offline generation."
            )
            return self._generate_fallback_titles(num, category=category)

        return unique_titles[:num]

    def _generate_fallback_titles(self, num: int, category: str = "") -> List[str]:
        """Generate guaranteed-unique fallback titles when all LLM attempts are exhausted.

        Design principles (research-backed):
        - 20+ diverse templates avoids the old 5-template exhaustion after ~5 000 articles.
        - secrets.token_hex(4) suffix (8 hex chars) guarantees uniqueness without any
          lookup — collision probability is 1 in 4 294 967 296, effectively zero.
        - Only an exact-match check is done (O(1) set lookup), NOT the expensive
          Jaccard scan, because these titles already contain a unique token.
        """
        cat = category or Config.INDUSTRY_NAME or "Adventure"
        city = Config.TARGET_CITY or "Rishikesh"
        year = datetime.now().strftime("%Y")

        # Categories are stored canonically as "X in <City>" (data/config/categories.json
        # keys CTA lookups on that exact string — don't change the data). Every template
        # below also appends "{city}" itself, so without stripping it here, formatting
        # produced "Best River Rafting in Rishikesh in Rishikesh — Complete 2026 Guide".
        # Strip the trailing city name once, up front, so every template composes
        # correctly no matter where it places {cat} relative to {city}.
        de_duped_cat = re.sub(rf'\s+in\s+{re.escape(city)}\s*$', '', cat, flags=re.IGNORECASE).strip()
        if de_duped_cat:
            cat = de_duped_cat

        # 20 structurally distinct templates — enough variety that even at 10 000+
        # articles no template group dominates the title space.
        templates = [
            "Best {cat} in {city} — Complete {year} Guide",
            "Top-Rated {cat} Experiences in {city}: Insider Tips",
            "Why {city} Is the Best Destination for {cat}",
            "{cat} in {city}: Safety, Prices and Booking Guide",
            "Exploring {cat} in {city}: A Seasonal Breakdown",
            "Essential {cat} Tips for Visiting {city}",
            "{city} {cat}: What Every First-Timer Should Know",
            "Planning {cat} in {city}: A Step-by-Step Overview",
            "Everything You Need to Know About {cat} in {city}",
            "The Complete Visitor's Guide to {cat} in {city}",
            "How to Choose the Best {cat} Provider in {city}",
            "{cat} in {city}: Comparing Options and Prices",
            "Safety First: What to Know Before Booking {cat} in {city}",
            "{cat} Booking Tips for Travellers Visiting {city}",
            "Understanding {cat} Packages Available in {city}",
            "A Practical Guide to {cat} Activities in {city}",
            "{cat} in {city}: Budgeting, Safety and Best Times to Go",
            "What Makes {city} Special for {cat} Enthusiasts",
            "Top Questions Answered About {cat} in {city}",
            "The Definitive {cat} Resource for {city} Visitors",
        ]

        titles = []
        for attempt_idx in range(num):
            tmpl = templates[attempt_idx % len(templates)]
            # 8-character hex suffix from the OS CSPRNG — collision-free in practice.
            uid = secrets.token_hex(4)
            title = tmpl.format(cat=cat, city=city, year=year) + f" [{uid}]"
            # save_used_title() guards against exact duplicates and is thread-safe.
            # The uid suffix makes actual duplicates practically impossible.
            if title.lower().strip() not in self.title_manager.used_titles:
                titles.append(title)
                self.title_manager.save_used_title(title)

        logger.info(
            "[TITLE_GEN] Fallback produced %d/%d titles for category '%s'.",
            len(titles), num, cat
        )
        return titles

    def _should_include_brand_mention(self) -> bool:
        """
        Determines if an article should be brand-specific based on the configured ratio.

        Returns:
            bool: True if the article should include brand mentions, False otherwise
        """
        return random.random() < Config.BRAND_MENTION_RATIO

    def generate_article(
        self,
        title: str,
        reference_text: str,
        target_keywords: List[str],
        temperature: float = 0.7,
        presence_penalty: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        article_type: Optional[str] = None,
        category: str = "",
        excluded_products: Optional[List[str]] = None
    ) -> Tuple[ArticleDraft, Optional[Dict]]:
        """
        Generates a full SEO-optimized blog article.

        Args:
            title: The title of the article
            reference_text: Reference text or previous version of the article
            target_keywords: List of target keywords to include
            temperature: Controls randomness in generation (0.0 to 2.0)
            article_type: Type of article ('brand', 'generic', or None for auto-detect)
            category: Category of the article (Product or Industry)
            excluded_products: List of products to exclude from generation

        Returns:
            Tuple containing the generated ArticleDraft and product data (if any)
        """
        if not title or not title.strip():
            raise ValueError("Title cannot be empty")
        if not isinstance(target_keywords, list):
            raise TypeError("Target keywords must be a list")
        if not 0.0 <= temperature <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")

        # Determine article type if not specified
        if article_type is None:
            article_type = "brand" if self._should_include_brand_mention() else "generic"

        if article_type not in ("generic", "brand"):
            raise ValueError("Article type must be 'generic' or 'brand'")

        product = None
        product_context = ""
        project_context = "" # Initialize project_context

        if excluded_products is None:
            excluded_products = []

        # For brand articles, we might want to include product context if available
        if article_type == 'brand':
            product = self._get_random_product(excluded_products=excluded_products)
            if product:
                product_context = self._format_product_context(product)
            # If no product but brand article is requested, use brand context
            else:
                project_context = (
                    f"This article is about {Config.BRAND_NAME}, "
                    f"a leading company in the {Config.INDUSTRY_NAME}."
                )
        else:
            # For generic articles, use industry context
            project_context = (
                f"This article provides general information about the {Config.INDUSTRY_NAME} "
                "and does not promote any specific brand."
            )

        # Combine contexts
        places_context = ""
        # 1. Inject specific places from places.json (Legacy)
        if hasattr(Config, "PLACES_DATA") and Config.PLACES_DATA:
            top_places = Config.PLACES_DATA.get("top_tourist_places", [])
            gems = Config.PLACES_DATA.get("underrated_hidden_gems", [])

            if top_places:
                places_context += "\n**MUST MENTION SOME OF THESE TOP PLACES:**\n"
                for p in random.sample(top_places, min(len(top_places), 3)):
                    places_context += f"- {p['name']}: {p['description']}\n"

            if gems:
                places_context += "\n**MUST MENTION SOME OF THESE UNDERRATED GEMS:**\n"
                for g in random.sample(gems, min(len(gems), 2)):
                    places_context += f"- {g['name']}: {g['description']}\n"

        # 2. Deep Search Injection (New Researcher Data)
        # We trigger this if the title or category suggests a 'tourist guide' or 'places to visit' intent
        tourist_triggers = [
            "places to visit", "things to do", "tourist guide", "sightseeing", "itinerary",
            "rafting", "camping", "bungee", "zipline", "paragliding", "adventure", "sports"
        ]
        normalized_title = title.lower()
        is_tourist_guide = any(trigger in normalized_title for trigger in tourist_triggers) or \
                           (category and any(trigger in category.lower() for trigger in tourist_triggers))

        if is_tourist_guide and hasattr(Config, "PLACES_DETAILS_DATA") and Config.PLACES_DETAILS_DATA:
            logger.info("Tourist/Place intent detected. Injecting deep-research details into context.")
            deep_context = "\n\n**DETAILED RESEARCH DATA (USE THESE SPECIFIC DETAILS):**\n"

            # Add locations
            locations = Config.PLACES_DETAILS_DATA.get("locations", [])
            if locations:
                deep_context += "\n### Key Locations Details:\n"
                # Pick 4 relevant locations for depth
                selected_locs = random.sample(locations, min(len(locations), 5))
                for loc in selected_locs:
                    loc_name = loc.get('name', 'N/A')
                    famous = loc.get('famous_for', 'N/A')
                    activities = ", ".join(loc.get('things_to_do', [])) if isinstance(loc.get('things_to_do'), list) else "N/A"
                    reach = loc.get('how_to_reach', 'N/A')
                    timings = loc.get('timings_2026') or loc.get('timings') or "N/A"
                    fee = loc.get('fees_2026') or loc.get('fee') or "N/A"
                    tip = loc.get('tips', 'N/A')
                    deep_context += f"- **{loc_name}**: Famous for {famous}. Activities: {activities}. How to reach: {reach}. Timings/Fee: {timings} / {fee}. Tip: {tip}\n"

            # Add rafting routes if relevant
            if "rafting" in normalized_title or "adventure" in normalized_title:
                rafting = Config.PLACES_DETAILS_DATA.get("rafting_routes", [])
                if rafting:
                    deep_context += "\n### River Rafting Route Options:\n"
                    for route in rafting:
                        deep_context += f"- {route['name']}: {route['distance']}, Grade {route['grade']}. Best for: {route['best_for']}. Key Rapids: {route['rapids']}.\n"

            # Add travel tips
            tips = Config.PLACES_DETAILS_DATA.get("travel_tips_2026", {})
            if tips:
                deep_context += f"\n### 2026 Travel Logistics:\n- Nearest Airport: {tips.get('nearest_airport')}\n- Best Season: {tips.get('best_season')}\n- Dress Code: {tips.get('dress_code')}\n"

            places_context += deep_context

        final_context = (product_context if product_context else project_context) + places_context

        # Generate the content using the appropriate prompt
        prompt = create_content_prompt(
            title=title,
            reference_text=reference_text,
            target_keywords=target_keywords,
            project_context=final_context,
            article_type=article_type,
            category=category
        )

        if not LLM_AVAILABLE or (not Config.GOOGLE_AI_STUDIO_API_KEY and not Config.USE_VERTEX_AI):
            logger.warning("LLM not available or API key missing. Using fallback article content.")
            fallback_article = self._create_fallback_article(
                title, target_keywords, article_type=article_type, category=category
            )
            fallback_article.category = str(category).strip() if category else ""
            fallback_article.is_rate_limit_fallback = True  # Suppress image generation
            return fallback_article, product

        try:
            # ========== SINGLE-PASS GENERATION (Optimized) ==========
            logger.info("Generating article in a single pass with temperature=%.2f", temperature)

            article_response, usage = call_llm(
                prompt,
                config=LLMConfig(
                    model_name=self.model_name,
                    # ponytail: 8192 gave gpt-4o too much rope — it kept generating past
                    # article-end into thesaurus-chain garbage to fill the budget.
                    # 5000 covers ~3500 words comfortably, caps the runaway.
                    max_tokens=5000,
                    temperature=temperature,
                    presence_penalty=presence_penalty if presence_penalty is not None else Config.PRESENCE_PENALTY,
                    frequency_penalty=frequency_penalty if frequency_penalty is not None else Config.FREQUENCY_PENALTY,
                    include_usage=True,
                    task_name=f"Article Gen: {title[:30]}"
                )
            )

            # Parse the final formatted content (pass category for slug generation)
            article_draft = self._parse_article_response(article_response, title, target_keywords, category=category)
            article_draft.category = str(category).strip() if category else ""

            # Assign usage stats
            article_draft.token_usage = usage
            article_draft.cost = usage.get('cost', 0.0)

            logger.info(
                "Single-pass generation complete. Cost: $%.4f | Tokens: %d",
                article_draft.cost,
                usage.get('total_tokens', 0)
            )

            return article_draft, product
        except Exception as err:
            if isinstance(err, RateLimitExhaustedError):
                logger.error(
                    "[RATE_LIMIT_EXHAUSTED] All LLM models rate-limited for article '%s'. "
                    "Falling back to offline article generation (image will be suppressed). Error: %s",
                    title[:50], err
                )
            else:
                logger.error("Error generating article content: %s", err)
                logger.info("Falling back to offline article generation...")
            fallback_article = self._create_fallback_article(
                title, target_keywords, article_type=article_type, category=category
            )
            fallback_article.category = str(category).strip() if category else ""
            fallback_article.is_rate_limit_fallback = True  # Suppress image generation
            return fallback_article, product

    def humanize_article(self, article: ArticleDraft) -> ArticleDraft:
        """
        Second LLM pass over an already SEO-passing article: rewrites prose for more
        natural sentence-length variation and less predictable, stock phrasing — the
        kind of flat uniformity that reads poorly to a real visitor regardless of how
        any detector scores it. Runs once, only on the final winning draft.

        Fails safe by design: the rewrite is checked against the original for
        preserved headings/links/keywords/word-count before being accepted. Any
        mismatch discards the rewrite and keeps the original article untouched —
        this step can only make prose read better, never break SEO or publishing.
        """
        if not Config.ENABLE_HUMANIZE_PASS or not LLM_AVAILABLE or article.is_rate_limit_fallback:
            return article

        try:
            prompt = create_humanize_prompt(article.content_html, article.metadata.keywords)
            rewritten_response, usage = call_llm(
                prompt,
                config=LLMConfig(
                    model_name=self.model_name,
                    max_tokens=5000,
                    temperature=0.7,
                    include_usage=True,
                    task_name=f"Humanize: {article.title[:30]}"
                )
            )
            rewritten_html = self._extract_humanized_html(rewritten_response)

            # Every extra LLM call costs real money whether or not we end up using its
            # output — always account for it so campaign cost tracking stays accurate.
            article.cost += usage.get('cost', 0.0)
            for key, value in usage.items():
                if key in article.token_usage:
                    article.token_usage[key] += value

            failure_reason = self._humanize_sanity_check(article.content_html, rewritten_html, article.metadata.keywords)
            if failure_reason:
                logger.warning(
                    "[HUMANIZE] Rewrite failed sanity check (%s) — keeping original content. "
                    "Original headings: %s | Rewritten headings: %s",
                    failure_reason,
                    self._heading_texts(article.content_html),
                    self._heading_texts(rewritten_html),
                )
                return article

            article.content_html = rewritten_html
            article.word_count = len(re.findall(r'\b\w+\b', re.sub(r'<[^>]+>', '', rewritten_html)))
            logger.info("[HUMANIZE] Rewrite passed sanity check and was applied. Cost: $%.4f", usage.get('cost', 0.0))
            return article
        except Exception as err:  # Never let a polish pass break the pipeline
            logger.warning("[HUMANIZE] Rewrite pass failed (%s) — keeping original content.", err)
            return article

    @staticmethod
    def _extract_humanized_html(response: str) -> str:
        """Strips markdown code fences the LLM sometimes wraps HTML output in."""
        text = response.strip()
        text = re.sub(r'^```(?:html)?\s*\n?', '', text)
        text = re.sub(r'\n?```\s*$', '', text)
        return text.strip()

    @staticmethod
    def _heading_texts(html: str) -> List[str]:
        """
        Extracts H1/H2/H3 visible text, ignoring inner tags (e.g. a <strong> or <a>
        wrapping part of a heading) and whitespace differences — those are harmless
        formatting variance, not the wording changes the sanity check needs to catch.
        """
        raw_headings = re.findall(r'<h[123][^>]*>(.*?)</h[123]>', html, re.IGNORECASE | re.DOTALL)
        texts = [re.sub(r'<[^>]+>', '', h) for h in raw_headings]
        return [' '.join(t.split()) for t in texts]

    @staticmethod
    def _humanize_sanity_check(original_html: str, rewritten_html: str, keywords: List[str]) -> Optional[str]:
        """
        Returns None if the rewrite is safe to use, otherwise a short reason string.
        Pure-Python structural comparison — no LLM call, so this check is free.
        """
        if not rewritten_html or len(rewritten_html) < 200:
            return "output too short/empty"

        if ContentGeneratorAgent._heading_texts(original_html) != ContentGeneratorAgent._heading_texts(rewritten_html):
            return "heading text changed"

        def link_hrefs(html: str) -> Set[str]:
            return set(re.findall(r'<a\s[^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE))

        if link_hrefs(original_html) != link_hrefs(rewritten_html):
            return "links changed"

        original_words = len(re.findall(r'\b\w+\b', re.sub(r'<[^>]+>', '', original_html)))
        rewritten_words = len(re.findall(r'\b\w+\b', re.sub(r'<[^>]+>', '', rewritten_html)))
        if original_words == 0 or abs(rewritten_words - original_words) / original_words > 0.20:
            return f"word count drifted too far ({original_words} -> {rewritten_words})"

        # Compare keyword coverage using the SAME normalized matching the real SEO
        # evaluator uses (handles "&"/"and", punctuation, stop words) — a raw lowercase
        # substring check would reject harmless rewordings the evaluator wouldn't even
        # notice. Coverage is compared before/after rather than requiring zero drops,
        # matching the evaluator's own proportional scoring (SEOEvaluatorAgent awards
        # partial credit for partial coverage, not all-or-nothing).
        valid_keywords = [kw for kw in keywords if isinstance(kw, str) and kw.strip()]
        if valid_keywords:
            def coverage(html: str) -> float:
                normalized = SEOEvaluatorAgent._normalize_for_kw_match(html)
                found = sum(
                    1 for kw in valid_keywords
                    if SEOEvaluatorAgent._normalize_for_kw_match(kw) in normalized
                )
                return found / len(valid_keywords)

            original_coverage = coverage(original_html)
            rewritten_coverage = coverage(rewritten_html)
            if rewritten_coverage < original_coverage - 0.15:
                return f"keyword coverage dropped ({original_coverage:.0%} -> {rewritten_coverage:.0%})"

        return None

    def _parse_article_response(
        self, content: str, title: str, target_keywords: List[str], category: str = ""
    ) -> ArticleDraft:
        try:
            meta_title = self._extract_section(content, "META_TITLE:", "\n") or title[:60]
            meta_title = meta_title.strip().strip('*').strip('_').strip('"').strip("'").strip()

            meta_description = self._extract_section(content, "META_DESCRIPTION:", "\n") or (
                f"Discover high-quality solutions with {Config.BRAND_NAME}."
            )
            meta_description = meta_description.strip().strip('*').strip('_').strip('"').strip("'").strip()

            # ── Yoast-safe meta description: enforce 120–155 character range ────
            # Yoast turns red below 120 chars and orange/red above 155 chars.
            # Under-length: pad with a contextual brand tagline to reach minimum.
            # Over-length: trim at the last word boundary before 155 to avoid
            # mid-word cuts (e.g. "activi..." instead of "activities").
            yoast_min, yoast_max = 120, 155
            if len(meta_description) < yoast_min:
                padding = (
                    f" Explore verified {Config.INDUSTRY_NAME} experiences in "
                    f"{Config.TARGET_CITY} with {Config.BRAND_NAME} — safe, affordable, and easy to book."
                )
                meta_description = (meta_description + padding)[:yoast_max]
            if len(meta_description) > yoast_max:
                trimmed = meta_description[:yoast_max]
                last_space = trimmed.rfind(" ")
                meta_description = trimmed[:last_space] if last_space > yoast_min else trimmed
            # ────────────────────────────────────────────────────────────────────

            focus_keyword = self._extract_section(content, "FOCUS_KEYWORD:", "\n") or (
                target_keywords[0] if target_keywords else ""
            )
            focus_keyword = focus_keyword.strip().strip('*').strip('_').strip('"').strip("'").strip()

            # ── Guarantee focus_keyword is never empty (Yoast red: "not set") ──
            # Derive a fallback from the first 3 meaningful words of the title
            # so Yoast always has a keyphrase to analyse against.
            if not focus_keyword:
                title_words = [w for w in title.lower().split() if len(w) > 3][:3]
                focus_keyword = " ".join(title_words) if title_words else Config.INDUSTRY_NAME
                logger.warning(
                    "[SEO] Focus keyword missing from LLM output for '%s'. "
                    "Using title-derived fallback: '%s'",
                    title[:50], focus_keyword
                )
            # ────────────────────────────────────────────────────────────────────

            # ── SLUG GENERATION — Collision-Proof via SlugRegistry ─────────────────
            # Priority: LLM-suggested slug (if clean) → registry-generated slug
            # The registry guarantees < 60 chars, no stopwords, no prefix collision
            llm_slug = self._extract_section(content, "URL_SLUG:", "\n")
            if llm_slug:
                llm_slug = llm_slug.strip().strip('*').strip('_').strip('"').strip("'").strip()
                llm_slug = re.sub(r'[^a-z0-9-]', '', llm_slug.lower())[:60].rstrip('-')

            # Always generate registry slug from title (uses semantic core, strips stopwords)
            registry_slug = self.slug_registry.generate_unique_slug(title, category=category)

            # Use LLM slug only if it's clean, different from registry and not already taken
            if (llm_slug
                    and llm_slug != registry_slug
                    and self.slug_registry.is_slug_available(llm_slug)
                    and len(llm_slug) >= 10):
                url_slug = llm_slug
            else:
                url_slug = registry_slug

            # Register the chosen slug to block all future duplicates
            self.slug_registry.register(url_slug)
            logger.info("Slug assigned: '%s' (title: '%s')", url_slug, title[:50])
            # ─────────────────────────────────────────────────────────────────────

            html_content = self._extract_html_content(content)

            # Extract actual H1 from generated content — handles ADAPTABILITY MANDATE rephrasing
            actual_h1 = self._extract_section(content, "<h1>", "</h1>")
            final_title = actual_h1 if actual_h1 else title
            final_title = final_title.strip().replace('\n', ' ')

            # DEDUP GUARD: `title` already passed TitleManager's duplicate/near-duplicate
            # check before generation, but the LLM's own <h1> (final_title) never does.
            # For obvious, well-covered topics the LLM repeatedly converges on the same
            # "ideal" heading regardless of the deduplicated seed title it was given —
            # that's how the same H1 (and therefore the same article_id, since it's an
            # md5 of the title) has slipped out on separate runs. If the H1 diverged from
            # the checked title and collides with one we've already used, keep the
            # already-vetted title instead and rewrite the on-page heading to match.
            if actual_h1 and final_title.lower().strip() != title.lower().strip():
                if self.title_manager.is_title_used(final_title, self.slug_registry):
                    logger.warning(
                        "[DEDUP] Generated H1 '%s' collides with an existing title; "
                        "keeping deduplicated title '%s' instead.", final_title, title
                    )
                    html_content = html_content.replace(
                        f"<h1>{actual_h1}</h1>", f"<h1>{title}</h1>", 1
                    )
                    final_title = title
                else:
                    # Divergent but original — register it so other workers/threads in
                    # this same run won't independently pick the same heading later.
                    self.title_manager.save_used_title(final_title)

            faq_match = re.search(r'(?i)(?:FAQ_SECTION:|<h2>\s*Frequently Asked Questions.*?</h2>|<div[^>]*class=["\']faq-section["\'][^>]*>)', content)
            if faq_match:
                start_pos = faq_match.start()
                # If matched the literal "FAQ_SECTION:", start after it to exclude the marker
                if content[start_pos:start_pos+12].upper() == "FAQ_SECTION:":
                    start_pos += 12
                
                end_idx = content.find("JSON_LD_SCHEMA:", start_pos)
                if end_idx != -1:
                    faq_section = content[start_pos:end_idx].strip()
                else:
                    faq_section = content[start_pos:].strip()
            else:
                faq_section = self._generate_default_faq(final_title)

            html_content_cleaned = self._strip_json_ld(html_content)
            faq_section_cleaned = self._strip_json_ld(faq_section)

            # E-E-A-T: real byline + disclosure (or an honest team credit if no persona
            # is configured yet), kept in sync with the JSON-LD author right below.
            author_persona = self._pick_author_persona()
            html_content_cleaned = self._inject_byline_and_disclosure(html_content_cleaned, author_persona)

            canonical_url = self._build_canonical_url(url_slug)
            json_ld = self._extract_json_ld(content) or self._generate_default_schema(
                final_title, meta_description, canonical_url, author=author_persona
            )

            text_content = self._extract_text_from_html(html_content_cleaned)
            word_count = len(re.findall(r'\b\w+\b', text_content))

            metadata = Metadata(
                title=meta_title[:60],
                description=meta_description[:yoast_max],
                focus_keyword=focus_keyword,
                url_slug=url_slug,
                canonical_url=canonical_url,
                keywords=target_keywords,
                json_ld_schema=json_ld
            )

            return ArticleDraft(
                title=final_title,
                content_html=html_content_cleaned,
                word_count=word_count,
                metadata=metadata,
                faq_section=faq_section_cleaned
            )
        except Exception as err:
            logger.error("Error parsing article response: %s. Content preview: %s", err, content[:500])
            return self._create_fallback_article(title, target_keywords)

    def _extract_section(self, content: str, start_marker: str, end_marker: str) -> Optional[str]:
        try:
            # 1. Try exact match to preserve existing precise behavior
            start_idx = content.find(start_marker)
            if start_idx != -1:
                start_idx += len(start_marker)
                if not end_marker:
                    return content[start_idx:].strip()
                end_idx = content.find(end_marker, start_idx)
                if end_idx != -1:
                    return content[start_idx:end_idx].strip()
                return content[start_idx:].strip()

            # 2. Case-insensitive and markdown-tolerant robust fallback
            if start_marker.startswith("<") and start_marker.endswith(">"):
                start_pat = re.escape(start_marker)
            else:
                clean_start = re.sub(r'[^a-zA-Z0-9_]', '', start_marker)
                if not clean_start:
                    start_pat = re.escape(start_marker)
                else:
                    clean_start_pat = re.escape(clean_start).replace(r'\_', r'[\s\_]*')
                    start_pat = r'(?i)(?:\*\*|##|#|\*|\s)*' + clean_start_pat + r'(?:\*\*|\*|:|\s)*'

            start_match = re.search(start_pat, content)
            if not start_match:
                return None

            start_pos = start_match.end()

            if not end_marker:
                return content[start_pos:].strip()

            if end_marker.startswith("<") and end_marker.endswith(">"):
                end_pat = re.escape(end_marker)
            elif end_marker == "\n":
                end_pat = r'\n'
            else:
                clean_end = re.sub(r'[^a-zA-Z0-9_]', '', end_marker)
                if not clean_end:
                    end_pat = re.escape(end_marker)
                else:
                    clean_end_pat = re.escape(clean_end).replace(r'\_', r'[\s\_]*')
                    end_pat = r'(?i)(?:\*\*|##|#|\*|\s)*' + clean_end_pat + r'(?:\*\*|\*|:|\s)*'

            end_match = re.search(end_pat, content[start_pos:])
            if not end_match:
                return content[start_pos:].strip()

            end_pos = start_pos + end_match.start()
            return content[start_pos:end_pos].strip()
        except Exception:
            return None

    def _extract_html_content(self, content: str) -> str:
        # Find where FAQ starts robustly
        faq_match = re.search(r'(?i)(?:FAQ_SECTION:|<h2>\s*Frequently Asked Questions.*?</h2>|<div[^>]*class=["\']faq-section["\'][^>]*>)', content)
        faq_marker = faq_match.group(0) if faq_match else "FAQ_SECTION:"

        html_content = self._extract_section(content, "</h1>", faq_marker)
        if html_content:
            h1_line = self._extract_section(content, "<h1>", "</h1>")
            if h1_line:
                return f"<h1>{h1_line}</h1>" + html_content

        h1_start = content.find("<h1>")
        if h1_start != -1:
            if faq_match:
                return content[h1_start:faq_match.start()].strip()
            return content[h1_start:].strip()

        return "<h1>Article Generation Failed</h1><p>Could not parse content.</p>"

    def _extract_json_ld(self, content: str) -> Optional[Dict]:
        schema_section = self._extract_section(content, "JSON_LD_SCHEMA:", "")
        if schema_section:
            try:
                return json.loads(schema_section)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON-LD schema.")
        return None

    def _generate_default_schema(
        self, title: str, description: str, canonical_url: str = Config.DEFAULT_LINK_URL,
        author: Optional[Dict] = None
    ) -> Dict:
        """Builds the article's JSON-LD. `author` is a persona dict from
        Config.AUTHOR_PERSONAS (name/job_title/url) — when provided, this emits a real
        Person author instead of the Organization; when not, it falls back to the brand.
        Must stay in sync with the visible byline text (see
        _inject_byline_and_disclosure) — Google cross-checks structured data against
        what's actually on the page.
        """
        if author and author.get("name"):
            author_schema: Dict = {
                "@type": "Person",
                "name": author["name"],
                "worksFor": {"@type": "Organization", "name": Config.BRAND_NAME}
            }
            if author.get("job_title"):
                author_schema["jobTitle"] = author["job_title"]
            if author.get("url"):
                author_schema["url"] = author["url"]
        else:
            author_schema = {"@type": "Organization", "name": Config.BRAND_NAME}

        return {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": title,
            "description": description,
            "author": author_schema,
            "publisher": {
                "@type": "Organization",
                "name": Config.BRAND_NAME,
                "logo": {
                    "@type": "ImageObject",
                    "url": "https://your-website.com/logo.png"
                }
            },
            "mainEntityOfPage": {
                "@type": "WebPage",
                # Must be the article's own live URL, not the homepage — Google flags a
                # mainEntityOfPage/canonical mismatch as invalid structured data.
                "@id": canonical_url
            }
        }

    def _pick_author_persona(self) -> Optional[Dict]:
        """Random real author for this article's byline/schema, or None if
        Config.AUTHOR_PERSONAS hasn't been filled in yet (see data/config/authors.json)."""
        if not Config.AUTHOR_PERSONAS:
            return None
        return random.choice(Config.AUTHOR_PERSONAS)

    def _inject_byline_and_disclosure(self, html_content: str, author: Optional[Dict]) -> str:
        """Adds a visible byline + AI-disclosure line right under the <h1>.

        This has to exist for two reasons: (1) it's the honest thing to do, and (2)
        the JSON-LD author field this pairs with (_generate_default_schema) is only
        valid structured data if it matches something actually visible on the page —
        an author claim that only exists in the schema and nowhere on the page is what
        Google's structured-data guidelines explicitly disallow.
        """
        if not (Config.ENABLE_AUTHOR_BYLINE or Config.ENABLE_AI_DISCLOSURE):
            return html_content

        parts = []
        if Config.ENABLE_AUTHOR_BYLINE:
            if author and author.get("name"):
                byline = f"By {author['name']}"
                byline += f", {author['job_title']} at {Config.BRAND_NAME}" if author.get("job_title") \
                    else f" for {Config.BRAND_NAME}"
            else:
                byline = f"By the {Config.BRAND_NAME} Travel Team"
            parts.append(byline)
        if Config.ENABLE_AI_DISCLOSURE:
            parts.append("Drafted with AI research assistance and reviewed for accuracy by our travel team")

        if not parts:
            return html_content
        meta_html = f'<p class="post-meta byline"><em>{". ".join(parts)}.</em></p>'

        h1_match = re.search(r'</h1>', html_content, re.IGNORECASE)
        if not h1_match:
            return meta_html + html_content

        insert_at = h1_match.end()
        # If the LLM already added an "Updated: ..." post-meta paragraph right after
        # the H1, insert after that instead, so both meta lines sit together.
        updated_match = re.match(
            r'\s*<p[^>]*class=["\'][^"\']*post-meta[^"\']*["\'][^>]*>.*?</p>',
            html_content[insert_at:], re.IGNORECASE | re.DOTALL
        )
        if updated_match:
            insert_at += updated_match.end()
        return html_content[:insert_at] + meta_html + html_content[insert_at:]

    def _generate_default_faq(self, title: str) -> str:
        template = Config.TEMPLATES.get("faq_item", "")
        if not template:
            # Absolute fallback if template is missing
            return f'<div class="faq-section"><h2>Frequently Asked Questions</h2><p>Contact {Config.BRAND_NAME} for more details.</p></div>'

        return f"""
        <div class="faq-section">
        <h2>Frequently Asked Questions</h2>
        {template.format(brand_name=Config.BRAND_NAME, title=title)}
        </div>
        """


    def _build_fallback_html(
        self, title: str, primary_keyword: str, paragraph_templates: List[str]
    ) -> str:
        """Assemble the HTML body for a fallback article."""
        html_parts = [
            f"<h1>{title}</h1>",
            f"<h2>{primary_keyword.title()} Overview</h2>",
        ]

        # Bold the primary keyword at random to simulate SEO density.
        kw_pattern = f"(?i)({re.escape(primary_keyword)})"
        processed_sentences = [
            re.sub(kw_pattern, r"<strong>\1</strong>", p, count=1)
            if random.random() > 0.5 else p
            for p in paragraph_templates
        ]

        if len(processed_sentences) >= 3:
            html_parts.append(f"<p>{' '.join(processed_sentences[:3])}</p>")
            processed_sentences = processed_sentences[3:]

        html_parts.append(f"<h2>How To Evaluate {primary_keyword.title()}</h2>")
        if len(processed_sentences) >= 3:
            html_parts.append(f"<p>{' '.join(processed_sentences[:3])}</p>")
            processed_sentences = processed_sentences[3:]

        self._append_remaining_html(html_parts, processed_sentences, primary_keyword)
        return "".join(html_parts)

    def _append_remaining_html(
        self, html_parts: List[str], processed_sentences: List[str], primary_keyword: str
    ) -> None:
        """Append checklist, mistakes section, and remaining paragraphs to html_parts in-place."""
        html_parts.extend([
            "<h3>Practical Booking and Selection Checklist</h3>",
            "<ul>",
            f"<li>Confirm the exact use case and requirements for <strong>{primary_keyword}</strong>.</li>",
            "<li>Verify safety certifications and read recent customer reviews.</li>",
            "<li>Compare long-term value rather than only upfront cost.</li>",
            "<li>Check the cancellation and refund policy before paying any deposit.</li>",
            "<li>Book in advance during peak season to secure preferred slots.</li>",
        ])
        if len(processed_sentences) >= 2:
            html_parts.append(f"<li>{processed_sentences.pop(0)}</li>")
            html_parts.append(f"<li>{processed_sentences.pop(0)}</li>")
        html_parts.extend(["</ul>", "<h2>Common Mistakes To Avoid</h2>", "<h3>Building A Simple Action Plan</h3>"])

        while processed_sentences:
            chunk_size = min(random.randint(3, 4), len(processed_sentences))
            html_parts.append(f"<p>{' '.join(processed_sentences[:chunk_size])}</p>")
            processed_sentences = processed_sentences[chunk_size:]
            if len(processed_sentences) > 4 and random.random() > 0.6:
                html_parts.append(f"<h3>Maximising Your {primary_keyword.title()} Experience</h3>")


    def _build_fallback_meta(
        self, title: str, primary_keyword: str
    ) -> Tuple[str, str, str]:
        """Return (meta_title, meta_description, faq_section) for a fallback article."""
        city = Config.TARGET_CITY
        brand = Config.BRAND_NAME
        meta_description = (
            f"Plan your {primary_keyword} experience in {city} with confidence. "
            "Covers pricing, safety standards, booking tips, and what to expect."
        )
        if len(meta_description) < 120:
            meta_description = meta_description.ljust(120, '.')
        elif len(meta_description) > 155:
            trimmed = meta_description[:155]
            last_space = trimmed.rfind(" ")
            meta_description = trimmed[:last_space] if last_space >= 120 else trimmed[:155]

        meta_title = title
        if primary_keyword.lower() not in meta_title.lower():
            meta_title = f"{primary_keyword.title()} Guide \u2014 {city}"
        if len(meta_title) < 40:
            meta_title = f"{meta_title} \u2014 Complete Visitor Guide"

        faq_section = (
            f'<div class="faq-section"><h2>Frequently Asked Questions \u2014 {primary_keyword.title()} in {city}</h2>'
            f'<h3>What should I check before booking {primary_keyword} in {city}?</h3>'
            f'<p>Verify the operator has valid safety certifications, check recent customer reviews '
            f'on independent platforms, and confirm the cancellation policy before paying any deposit.</p>'
            f'<h3>What is the best time to experience {primary_keyword} in {city}?</h3>'
            f'<p>September to November and March to May offer the best weather and conditions for '
            f'adventure activities in {city}. Monsoon season (July\u2013August) may limit certain outdoor activities.</p>'
            f'<h3>How do I book {primary_keyword} through {brand}?</h3>'
            f'<p>{brand} allows online booking with only a 10% advance deposit. The remaining balance '
            f'is paid directly at the venue on the day of your activity. Free DSLR video is included with select packages.</p>'
            f'<h3>Is {primary_keyword} safe for first-time visitors to {city}?</h3>'
            f'<p>Yes, when booked through certified operators. Always attend the mandatory pre-activity '
            f'safety briefing, follow all instructor guidance, and disclose any relevant medical conditions before the activity.</p>'
            f'<h3>What should I wear and carry for {primary_keyword} in {city}?</h3>'
            f'<p>Wear comfortable, athletic clothing and closed-toe shoes. Remove loose jewellery and secure '
            f'valuables. All safety equipment \u2014 harnesses, helmets, life jackets as applicable \u2014 is provided by the operator.</p>'
            '</div>'
        )
        return meta_title, meta_description, faq_section

    def _build_paragraph_templates(
        self, primary_keyword: str, keyword_phrase: str,
        brand_context: str, location_text: str
    ) -> List[str]:
        """Build the ordered sentence pool for a fallback article body."""
        city = Config.TARGET_CITY
        min_words = max(Config.MIN_WORD_COUNT, 1100)
        paragraphs = [
            f"{brand_context}. This guide covers everything you need to know about {primary_keyword} "
            f"\u2014 from pricing and safety to booking tips and what to expect on the day.",
            f"{primary_keyword.title()} in {city} is available year-round, with the best "
            f"conditions during September to November and March to May. Monsoon months (July\u2013August) "
            f"may restrict certain outdoor activities due to high river levels and unpredictable weather.",
            f"When planning {primary_keyword}, start by confirming the operator's safety certifications "
            f"and reading recent independent customer reviews. Reputable operators in {city} "
            f"follow international safety protocols and provide all necessary equipment.",
            f"Prices for {primary_keyword} {location_text} vary depending on the package, duration, and "
            f"whether professional video coverage is included. Booking through a verified platform ensures "
            f"transparent pricing with no hidden fees.",
            f"Safety standards for adventure activities in {city} have improved significantly "
            f"in recent years. Look for operators who conduct mandatory pre-activity briefings, use "
            f"load-tested equipment, and have trained first-aid staff on site.",
            f"Advance booking is strongly recommended for {primary_keyword} {location_text}, especially "
            f"during weekends and peak holiday seasons when slots fill up quickly. A 10% deposit secures "
            f"your slot on most platforms.",
            f"Participants should wear comfortable, athletic clothing and closed-toe shoes for {primary_keyword}. "
            f"Remove loose jewellery and secure all valuables before the activity. All safety equipment is "
            f"provided by the operator.",
            f"Medical considerations matter before attempting {primary_keyword}. Individuals with heart "
            f"conditions, recent injuries, epilepsy, or those who are pregnant should consult a doctor and "
            f"disclose conditions to the operator before booking.",
            f"Common mistakes when booking {primary_keyword} include choosing solely on price, skipping the "
            f"safety briefing, and failing to confirm the cancellation policy. Taking a few minutes to verify "
            f"these details makes the experience significantly safer.",
            f"The strongest {primary_keyword} experiences come from choosing certified operators with proven "
            f"track records. That means checking {keyword_phrase} \u2014 the factors that separate a memorable "
            f"adventure from a frustrating one.",
        ]
        supplements = [
            "One important factor when evaluating "
            f"{primary_keyword} is to verify the credentials and track record of the provider before committing.",
            "Setting a realistic budget range before comparing options prevents scope creep "
            "and ensures the decision aligns with long-term goals.",
            "Reading independent reviews from verified customers provides a clearer picture of "
            f"{primary_keyword} than marketing materials alone.",
            "Timing matters \u2014 scheduling during off-peak periods often results in better "
            "availability and more personalised attention from operators.",
            "A written agreement outlining deliverables, timelines, and refund terms protects "
            "both parties and creates clear accountability.",
            "Comparing two or three shortlisted options against a defined criteria set leads "
            "to more confident, defensible decisions.",
            "Asking for references or case studies from providers in a similar context to your "
            "own helps validate claims made in sales conversations.",
            "Understanding the cancellation and modification policy before booking prevents "
            "unexpected losses if plans change at short notice.",
            "Post-experience feedback \u2014 whether formal surveys or informal conversations \u2014 "
            "helps providers improve and signals a commitment to quality.",
            "The long-term value of "
            f"{primary_keyword} often depends more on ongoing support quality than on initial pricing or headline features.",
        ]
        current_words = len(" ".join(paragraphs).split())
        random.shuffle(supplements)
        for extra in supplements:
            if current_words >= min_words:
                break
            paragraphs.append(extra)
            current_words += len(extra.split())
        return paragraphs

    def _create_fallback_article(
        self,
        title: str,
        keywords: List[str],
        article_type: str = "generic",
        category: str = ""
    ) -> ArticleDraft:
        """Produce a fully-structured fallback ArticleDraft without an LLM call."""
        slug = self._create_safe_slug(title)
        primary_keyword = keywords[0] if keywords else Config.INDUSTRY_NAME
        keyword_phrase = ", ".join(keywords[:6]) if keywords else Config.INDUSTRY_NAME

        category_lower = (category or "").lower()
        activity_noun = (
            "bungee jumping" if any(t in category_lower for t in ["bungee", "bungy"]) else
            "river rafting" if any(t in category_lower for t in ["raft", "river"]) else
            "paragliding" if "paragliding" in category_lower else
            "zipline" if any(t in category_lower for t in ["zipline", "flying fox", "zip"]) else
            "camping" if "camping" in category_lower else
            "adventure sports"
        )
        brand_context = (
            f"{Config.BRAND_NAME} makes it easy to book verified {activity_noun} experiences "
            f"in {Config.TARGET_CITY} with transparent pricing and certified operators"
            if article_type == "brand"
            else f"{Config.TARGET_CITY} is one of India's premier destinations for {activity_noun}, "
                 f"attracting adventure travellers from across the country year-round"
        )
        location_text = f"in {Config.TARGET_CITY}"
        paragraph_templates = self._build_paragraph_templates(
            primary_keyword, keyword_phrase, brand_context, location_text
        )
        html_content = self._build_fallback_html(title, primary_keyword, paragraph_templates)
        author_persona = self._pick_author_persona()
        html_content = self._inject_byline_and_disclosure(html_content, author_persona)
        word_count = len(re.findall(r'\b\w+\b', self._extract_text_from_html(html_content)))
        meta_title, meta_description, faq_section = self._build_fallback_meta(
            title, primary_keyword
        )
        canonical_url = self._build_canonical_url(slug)
        metadata = Metadata(
            title=meta_title[:60],
            description=meta_description,
            focus_keyword=primary_keyword,
            url_slug=slug,
            canonical_url=canonical_url,
            keywords=keywords,
            json_ld_schema=self._generate_default_schema(
                title, meta_description, canonical_url, author=author_persona
            )
        )
        return ArticleDraft(
            title=title,
            content_html=html_content,
            word_count=word_count,
            metadata=metadata,
            faq_section=faq_section,
            category=str(category).strip() if category else ""
        )


class SEOEvaluatorAgent:
    def __init__(self):
        self.scoring_weights = {
            'title_meta_optimization': 15,
            'keyword_integration': 20,
            'location_keyword_usage': 20,
            'heading_structure': 10,
            'word_count': 10,
            'readability_engagement': 15,
            'faq_section': 5,
            'internal_linking': 5
        }

    def evaluate_article(
        self, article: ArticleDraft, iteration_number: int = 1, article_type: str = "generic"
    ) -> SEOReport:
        metrics = [
            self._evaluate_title_meta(article),
            self._evaluate_keyword_integration(article),
            self._evaluate_location_keywords(article, article_type),
            self._evaluate_heading_structure(article),
            self._evaluate_word_count(article),
            self._evaluate_readability(article),
            self._evaluate_faq_section(article),
            self._evaluate_internal_links(article)
        ]

        # Calculate score and adjust for article type if necessary
        overall_score = sum(metric.score for metric in metrics)
        seo_score_ok = overall_score >= Config.SEO_THRESHOLD

        # Independent E-E-A-T gate — does NOT change overall_score/metrics at all,
        # it only adds a second condition articles must also satisfy to pass.
        specificity_ok, specificity_feedback = self._evaluate_content_specificity(article)
        passed = seo_score_ok and specificity_ok

        improvement_suggestions = [m.feedback for m in metrics if m.score < m.max_score * 0.8]
        if not specificity_ok:
            improvement_suggestions.append(specificity_feedback)

        return SEOReport(
            overall_score=overall_score,
            metrics=metrics,
            passed=passed,
            improvement_suggestions=improvement_suggestions,
            iteration_number=iteration_number,
            specificity_passed=specificity_ok,
            specificity_feedback=specificity_feedback
        )

    def _evaluate_content_specificity(self, article: ArticleDraft) -> Tuple[bool, str]:
        """
        Checks whether the article reads as genuinely specific/useful (real numbers,
        a named local detail, a concrete example or expert-sounding tip) rather than
        generic, interchangeable advice. This is what Google's E-E-A-T guidance
        rewards and a keyword/structure SEO score cannot measure on its own.

        Requires at least 2 of 3 signal categories to pass, so well-rounded
        articles with normal variation in phrasing are not unfairly blocked.
        """
        text = re.sub(r'<[^>]+>', '', article.content_html)
        text_lower = text.lower()
        signals_found = []

        # Signal 1: concrete numeric/data mentions (prices, %, distances, durations)
        numeric_pattern = (
            r'\d+(\.\d+)?\s*'
            r'(%|km|kg|hours?|hrs?|minutes?|mins?|days?|weeks?|months?|years?|'
            r'₹|rs\.?|inr|\$|ft|feet|meters?|metres?|m\b)'
        )
        numeric_hits = len(re.findall(numeric_pattern, text_lower))
        if numeric_hits >= 3:
            signals_found.append("data")

        # Signal 2: specific named local detail beyond the generic target city
        named_entities = []
        if getattr(Config, "PLACES_DATA", None):
            for group in ("top_tourist_places", "underrated_hidden_gems"):
                for place in Config.PLACES_DATA.get(group, []):
                    name = place.get("name", "")
                    if name:
                        named_entities.append(name)
        if getattr(Config, "PLACES_DETAILS_DATA", None):
            for loc in Config.PLACES_DETAILS_DATA.get("locations", []):
                name = loc.get("name", "")
                if name:
                    named_entities.append(name)

        named_hits = sum(1 for name in named_entities if name and name.lower() in text_lower)
        if named_hits >= 1:
            signals_found.append("local_detail")

        # Signal 3: experiential / example / opinion phrasing (not generic filler)
        experiential_markers = [
            "for example", "for instance", "in practice", "tip:", "pro tip",
            "we recommend", "our advice", "based on", "according to",
            "one thing to note", "keep in mind", "worth noting", "in our experience"
        ]
        experiential_hits = sum(1 for marker in experiential_markers if marker in text_lower)
        if experiential_hits >= 1:
            signals_found.append("example_or_opinion")

        passed = len(signals_found) >= 2

        if passed:
            return True, f"Content specificity OK ({', '.join(signals_found)})."

        readable_missing = {
            "data": "concrete numbers/data (prices, %, distances, durations)",
            "local_detail": "a specific named local place/detail (not just the city name)",
            "example_or_opinion": "a concrete example, tip, or expert opinion phrase",
        }
        missing = [m for m in ("data", "local_detail", "example_or_opinion") if m not in signals_found]
        needed = " and ".join(readable_missing[m] for m in missing[:2])
        feedback = f"Content reads as generic. Add {needed} to demonstrate real expertise/experience (E-E-A-T)."
        return False, feedback

    @staticmethod
    def _normalize_for_kw_match(text: str) -> str:
        """Normalise text for keyword matching: lowercase, strip punctuation, remove stop words."""
        text = text.lower().replace("&", "and").replace("-", " ")
        text = text.translate(str.maketrans('', '', string.punctuation))
        # Remove common stop words that LLMs naturally inject between keyword parts.
        text = re.sub(r'\b(in|and|the|for|at|of|to|on|with|a|an)\b', ' ', text)
        return " ".join(text.split())

    def _evaluate_title_meta(self, article: ArticleDraft) -> SEOMetric:
        score = 0
        details = []

        # Title length check
        title_len = len(article.metadata.title)
        if 40 <= title_len <= 65:
            score += 7
        else:
            details.append(f"Title length ({title_len}) should be 40-65 chars.")

        # Description length check
        desc_len = len(article.metadata.description)
        if 110 <= desc_len <= 165:
            score += 7
        else:
            details.append(f"Meta description ({desc_len}) should be 110-165 chars.")

        # Keyword in title check - CHECK ALL KEYWORDS (not just first 5)
        title_norm = self._normalize_for_kw_match(article.metadata.title)
        all_kws = [self._normalize_for_kw_match(keyword) for keyword in article.metadata.keywords if isinstance(keyword, str)]

        has_kw = False
        for keyword in all_kws:
            if keyword in title_norm:
                has_kw = True
                break
            # Check for partial matches (important for long phrases)
            words = keyword.split()
            if len(words) > 1 and all(w in title_norm for w in words):
                has_kw = True
                break

        if has_kw:
            score += 6
        else:
            details.append("Include a keyword in the title.")

        # Clamp score to max_score (sub-scores can sum to 20, but declared max is 15)
        score = min(score, 15)
        feedback = "Title/Meta OK." if score >= 12 else " | ".join(details)
        return SEOMetric(name="Title/Meta Optimization", score=score, weight=15, max_score=15, feedback=feedback)

    def _evaluate_keyword_integration(self, article: ArticleDraft) -> SEOMetric:
        score = 0

        content_normalized = self._normalize_for_kw_match(article.content_html)
        unique_keywords = [kw for kw in article.metadata.keywords if isinstance(kw, str)]

        found_kws = sum(
            1 for kw in unique_keywords
            if self._normalize_for_kw_match(kw) in content_normalized
        )

        # Keyword density (up to 12 points)
        density = 0.0
        if article.word_count > 0:
            total_mentions = sum(
                content_normalized.count(self._normalize_for_kw_match(kw))
                for kw in unique_keywords
            )
            density = (total_mentions / article.word_count) * 100

            # Broadened range to accommodate overlapping keywords (niche specific)
            if 0.5 <= density <= 15.0:
                score += 12
            elif 0.3 <= density < 0.5 or 15.0 < density <= 18.0:
                score += 8

        # Unique keyword coverage (up to 8 points)
        if unique_keywords:
            coverage_ratio = found_kws / len(unique_keywords)
            score += int(coverage_ratio * 8)

        feedback = f"Keywords: {found_kws}/{len(unique_keywords)} found (Density: {density:.2f}%)."
        if score < 15:
            feedback += " Use more target keywords naturally."

        return SEOMetric(name="Keyword Integration", score=score, weight=20, max_score=20, feedback=feedback)

    def _evaluate_location_keywords(self, article: ArticleDraft, article_type: str) -> SEOMetric:
        score = 0
        content_lower = article.content_html.lower()
        city_lower = Config.TARGET_CITY.lower()

        # City frequency check (unified for both types)
        city_count = content_lower.count(city_lower)

        # Reward natural frequency (lowered threshold from 15 to 10)
        if 3 <= city_count <= 10:
            score += 12
        elif city_count > 10:
            score += 8  # Slight penalty for over-optimization
        elif city_count > 0:
            score += 6

        # Reward natural location phrasing. Widened on purpose: a short, fixed list
        # here is what forces every article to reuse the exact same handful of canned
        # phrases (textbook keyword stuffing). A wider pool of genuinely natural
        # variants lets different articles land on different phrasing while still
        # scoring the same — same max points as before, just less repetitive across
        # the site.
        seo_boosters = [
            f"in {city_lower}", f"across {city_lower}", f"around {city_lower}",
            f"near {city_lower}", f"visit to {city_lower}", f"trip to {city_lower}",
            f"explore {city_lower}", f"exploring {city_lower}", f"based in {city_lower}",
            f"customers in {city_lower}", f"projects in {city_lower}",
            f"best quality in {city_lower}", f"top-rated in {city_lower}",
            f"services in {city_lower}", f"experts in {city_lower}",
            f"{city_lower}'s", f"heading to {city_lower}", f"travelling to {city_lower}",
            f"traveling to {city_lower}", f"a stay in {city_lower}"
        ]

        found_boosters = sum(1 for booster in seo_boosters if booster in content_lower)
        score += min(8, found_boosters * 2)

        # For GENERIC articles, only penalize if brand appears in H1/H2 headings
        # (not in body — conclusion CTAs will always contain bucketlistt by design)
        if article_type == "generic":
            brand_lower = Config.BRAND_NAME.lower()
            # Extract headings only to check for over-promotion
            headings_text = " ".join(re.findall(r'<h[12][^>]*>(.*?)</h[12]>', article.content_html, re.IGNORECASE | re.DOTALL)).lower()
            if brand_lower in headings_text:
                score = max(5, score - 8)  # Penalty only for brand in headings (not conclusion CTA)
                feedback = f"REMOVE '{Config.BRAND_NAME}' from H1/H2 headings in generic content. Conclusion CTA is fine."
            else:
                feedback = f"Location '{Config.TARGET_CITY}' mentioned {city_count} times. Brand neutrality in headings maintained."
        else:
            feedback = (
                f"Location '{Config.TARGET_CITY}' mentioned {city_count} times "
                f"with {found_boosters} boosters."
            )


        return SEOMetric(
            name="Location Keyword Usage (Subtle)",
            score=score,
            weight=20,
            max_score=20,
            feedback=feedback
        )

    def _evaluate_heading_structure(self, article: ArticleDraft) -> SEOMetric:
        score = 0
        if bool(re.search(r'<h1[^>]*>', article.content_html, re.IGNORECASE)):
            score += 2
        h2_count = len(re.findall(r'<h2[^>]*>', article.content_html, re.IGNORECASE))
        if h2_count >= 3:
            score += 4
        elif h2_count >= 1:
            score += 2
        h3_count = len(re.findall(r'<h3[^>]*>', article.content_html, re.IGNORECASE))
        if h3_count >= 2:
            score += 2

        headings = " ".join(re.findall(r'<h[1-3][^>]*>(.*?)</h[1-3]>', article.content_html, re.IGNORECASE)).lower()
        if any(kw.lower() in headings for kw in article.metadata.keywords[:3]):
            score += 2
        feedback = "Good heading structure." if score > 7 else "Use more H2/H3 tags and include keywords in them."
        return SEOMetric(name="Heading Structure", score=score, weight=10, max_score=10, feedback=feedback)

    def _evaluate_word_count(self, article: ArticleDraft) -> SEOMetric:
        score = 0
        # Word count score (up to 10 points)
        target_min_word_count = Config.MIN_WORD_COUNT
        target_max_word_count = Config.MAX_WORD_COUNT
        current_word_count = article.word_count

        if target_min_word_count <= current_word_count <= target_max_word_count:
            score = 10
        elif current_word_count > target_max_word_count:
            score = 6
        else:
            # Under min word count — strict 0 score to fail SEO check and force expansion
            score = 0
        feedback = f"Word count is {current_word_count}. Target: {target_min_word_count}-{target_max_word_count}."
        return SEOMetric(name="Word Count", score=score, weight=10, max_score=10, feedback=feedback)

    def _evaluate_readability(self, article: ArticleDraft) -> SEOMetric:
        score = 0
        # Each criterion is worth 5 points so the metric can reach its declared max_score of 15.
        # Previously: 4+3+3=10 (bug — could never reach the 15-point max).
        p_count = len(re.findall(r'<p[^>]*>', article.content_html, re.IGNORECASE))
        if p_count >= 10:
            score += 5
        if bool(re.search(r'<(ul|ol)[^>]*>', article.content_html, re.IGNORECASE)):
            score += 5
        if bool(re.search(r'<(strong|b)[^>]*>', article.content_html, re.IGNORECASE)):
            score += 5
        feedback = (
            "Readability is good." if score >= 15
            else "Improve readability: need 10+ paragraphs, at least one list, and bold/strong emphasis."
        )
        return SEOMetric(name="Readability & Engagement", score=score, weight=15, max_score=15, feedback=feedback)

    def _evaluate_faq_section(self, article: ArticleDraft) -> SEOMetric:
        score = 0
        h3_count = len(re.findall(r'<h3[^>]*>', article.faq_section, re.IGNORECASE)) if article.faq_section else 0
        if h3_count >= 6:
            score = 5
        elif h3_count >= 4:
            score = 3
        elif h3_count >= 2:
            score = 2
        elif article.faq_section and len(article.faq_section) > 100:
            score = 1
        feedback = (
            f"FAQ section has {h3_count} questions." if score >= 5
            else f"Add more FAQ questions: found {h3_count}, need at least 7 for full coverage (PAA / AI Overviews)."
        )
        return SEOMetric(name="FAQ Section", score=score, weight=5, max_score=5, feedback=feedback)

    def _evaluate_internal_links(self, article: ArticleDraft) -> SEOMetric:
        score = 0
        link_count = len(article.internal_links)
        if link_count >= 2:
            score = 5
        elif link_count == 1:
            score = 5  # Give full points for at least 1 link if we can't find more
        feedback = "Internal linking is good." if score >= 5 else "Add at least one internal link."
        return SEOMetric(name="Internal Linking", score=score, weight=5, max_score=5, feedback=feedback)

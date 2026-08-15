# Core Codebase Functionality Directory

This document lists the critical components, modules, and functions of the AI Blog Generator and describes their purposes in simple terms.

---

## 1. Concurrent Campaign Components (`src/concurrent_manager.py`)

- **`ConcurrentCampaignManager`**: The top-level class orchestrating the multi-threaded concurrent publishing queue. It coordinates workers, manages exceptions, tracks global progress, and performs automated replacements for rejected articles.
- **`_generate_article_worker`**: A self-contained execution loop representing a single worker thread. It handles title generation, triggers the single-article pipeline, and returns execution metrics.
- **`_handle_worker_result`**: A callback executed upon completion of each worker task. It tracks overall successes, parses exceptions, logs campaign metrics, and schedules replenishment tasks with the rotation helper when a worker task skips or fails.

---

## 2. Agent Components (`src/agents.py`)

- **`ContentGeneratorAgent`**: The main interface for communicating with Google Gemini LLMs to write articles, create metadata (such as titles, slugs, excerpts, and meta descriptions), and generate FAQ sections. Now includes Yoast SEO guardrails: the meta description is automatically enforced to 120–155 characters (Yoast's green-light range), and the focus keyword is guaranteed to be non-empty by deriving a fallback from the article title when the LLM omits it.
- **`SEOEvaluator`**: Validates generated article HTML against a suite of 8 rigorous SEO metrics. It calculates sub-scores and aggregates them into a final 100-point score.
- **`normalize_for_kw_match`**: Sanitizes both target keywords and article text during evaluation (e.g. replacing `&` with `and`, stripping redundant whitespace, and converting characters to lowercase) to prevent false-negative score drops due to slight stylistic formatting differences.
- **`TitleManager._word_bigrams`** *(new)*: Converts a normalised title string into a `frozenset` of word bigrams (e.g. `("river", "rafting")`, `("safety", "guide")`). Used as a lightweight fingerprint for near-duplicate detection without external dependencies.
- **`TitleManager._register_loaded_title`** *(new)*: Single code path called by both CSV readers at startup to populate `used_titles`, `starting_word_counts`, and `_fingerprint_index`. Fixes the root-cause startup bug where `starting_word_counts` was always empty after a container restart, causing premature title rejection.
- **`TitleManager.is_title_used`** *(rewritten)*: Implements the **Lock-Copy-Process** pattern. Holds `_lock` only for fast O(1) checks + a shallow dict snapshot (~0.1 ms at 5 000 articles), then runs word-bigram Jaccard similarity (threshold 0.75) on the private snapshot with no lock held. Eliminates the 60-120 second lock contention caused by the old `SequenceMatcher` O(n²) scan.
- **`TitleManager.save_used_title`** *(updated)*: Now also writes the bigram fingerprint to `_fingerprint_index` atomically under the lock, keeping the snapshot consistent.
- **`ContentGeneratorAgent._generate_fallback_titles`** *(rewritten)*: 20 structurally distinct templates + `secrets.token_hex(4)` unique suffix per title. Guarantees `num` unique titles with O(1) exact-match check, eliminating the old 5-template pool exhaustion and seconds-precision timestamp collisions.
- **`ContentGeneratorAgent._build_fallback_html`** *(new)*: Assembles the full HTML body for a fallback article. Separated from `_create_fallback_article` to stay under pylint's statement limit.
- **`ContentGeneratorAgent._append_remaining_html`** *(new)*: Appends the checklist and tail paragraphs to an `html_parts` list in-place. Extracted to keep `_build_fallback_html` under pylint's local-variable limit.
- **`ContentGeneratorAgent._build_fallback_meta`** *(new)*: Returns `(meta_title, meta_description, faq_section)` for a fallback article. Separated from `_create_fallback_article` to stay under pylint's statement limit.

---

## 3. Orchestration & Services (`src/services/`)

- **`BlogGeneratorOrchestrator.generate_blog` (`src/services/orchestrator.py`)**: The central pipeline governing a single article's lifecycle. It extracts keywords, manages duplicate-checking checks, runs the generation and SEO-evaluation feedback loop, applies anchor linking, writes to WordPress, and updates database records. Incorporates the new auto-healer to optimize draft quality before evaluation.
- **`SEOAutoHealer.heal` (`src/services/seo_auto_healer.py`)**: A pure Python utility class that programmatically processes generated HTML and metadata to correct minor SEO defects (word count, headers, bolding, lists, meta tags, and city-mention/booster keyword frequencies) to guarantee passing scores under strict quality guardrails without high-cost API retries.
- **`_extract_keywords_from_scraped_titles` (`src/services/orchestrator.py`)**: Extracts high-intent search terms based on active categories. Incorporates advanced deduplication and city-keyword matching to prevent redundant combinations such as `"in rishikesh in rishikesh"`.
- **`LinkingManager` (`src/services/linking_manager.py`)**: Matches anchors and inserts appropriate internal links based on sitemap mappings to ensure natural internal SEO optimization.

---

## 4. Client & Rate Limiting Components (`src/llm_client.py` & `src/image_client.py`)

- **`RATE_LIMIT_FALLBACK_MODELS`**: A module-level ordered list defining the **strict priority fallback chain** for text generation: `gemini-2.5-flash` → `gemini-2.5-flash-lite` → `gemini-2.5-pro` → `gemini-3.0-flash-preview` → `gemini-3.1-flash-lite`. Every LLM call attempts models in this order, bypassing any that are currently in circuit breaker cooldown.
- **`get_fallback_models`**: Constructs the active model candidate list for a given call. If a custom primary model is set (e.g. via `.env`) but it is not in the priority chain, it is prepended to the list. If no custom fallbacks are specified, the full priority chain is used in order.
- **`_apply_circuit_breaker`**: Filters out models currently in 60-second cooldown (set after a 429 rate-limit error). Logs a `[CIRCUIT_BREAKER]` message if the first available model differs from the intended preferred model, indicating a real-time bypass.
- **`TokenBucketLimiter`**: A thread-safe, blocking token bucket rate limiter class that refuels lazily during access. Threads calling `acquire()` block safely if the rate limit is exceeded.
- **`get_limiter_for_model`**: A registry function that dynamically initializes and caches model-specific token buckets with safe defaults (e.g. 15 RPM for Flash, 2 RPM for Pro models on free-tier API Keys) or custom overrides from configuration.
- **`call_llm`**: Wraps the Google GenAI `generate_content` SDK method. Enforces proactive client-side rate limiting via model-specific token buckets and wraps requests in a highly resilient retry loop featuring exponential backoff and randomized jitter. When all models are rate-limited, raises `RateLimitExhaustedError` to signal callers to skip dependent work (e.g. image generation).
- **`get_imagen_limiter` & `generate_blog_image`**: Applies client-side token bucket rate limiting and a retry loop with exponential backoff specifically to Imagen banner image generation.

---

## 5. Publishing Components (`src/publishers/`)

- **`TumblrPublisher`**: Connects to the Tumblr API and handles markdown-to-HTML conversion, tags generation from keywords, and publishing text posts.
- **`TumblrAccountSelector`**: Dynamically discovers and loads all configured Tumblr accounts from the environment by scanning `os.environ` dynamically (finding all `TUMBLR_BLOG_HOSTNAME{n}` indices), facilitating round-robin multi-account rotation without hardcoded limits.

---

## 6. Database & Database Write Safety (`utils/utils.py`)

- **`CSVManager`**: Manages reading, writing, and updating records in `articles.csv` and `articles_external.csv`. It is now fully thread-safe across concurrent worker threads by wrapping all file read/write/append operations within a class-level re-entrant lock (`threading.RLock()`), preventing write collisions, duplicate assignments, or database corruption during parallel execution.

---

## 7. Web API Endpoints (`api/main.py`)

- **`/campaign/publish/email`**: A FastAPI campaign endpoint that runs a concurrent campaign of `total_articles` (defaulting to 5) articles, automatically sends them in sets of 5 to the recipient configured via `SMTP_TO` using the email service, and commits them thread-safely to the database.



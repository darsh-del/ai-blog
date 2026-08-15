# Graph Report - ai-blog-generator-base-refactor-segmentation  (2026-08-09)

## Corpus Check
- 58 files · ~77,656 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 742 nodes · 1351 edges · 43 communities
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 191 edges (avg confidence: 0.51)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 88|Community 88]]

## God Nodes (most connected - your core abstractions)
1. `Config` - 66 edges
2. `BlogGeneratorOrchestrator` - 41 edges
3. `ContentGeneratorAgent` - 36 edges
4. `ArticleDraft` - 31 edges
5. `RobustScraper` - 30 edges
6. `CSVManager` - 30 edges
7. `LLMConfig` - 28 edges
8. `SEOEvaluatorAgent` - 25 edges
9. `call_llm()` - 23 edges
10. `ArticleDraft` - 23 edges

## Surprising Connections (you probably didn't know these)
- `CSVManager` --uses--> `Config`  [INFERRED]
  utils/utils.py → src/config.py
- `ArticleDraft` --uses--> `Config`  [INFERRED]
  utils/utils.py → src/config.py
- `VectorStoreManager` --uses--> `Config`  [INFERRED]
  utils/utils.py → src/config.py
- `CSVManager` --uses--> `ArticleDraft`  [INFERRED]
  utils/utils.py → src/models.py
- `ArticleDraft` --uses--> `ArticleDraft`  [INFERRED]
  utils/utils.py → src/models.py

## Import Cycles
- None detected.

## Communities (43 total, 0 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.09
Nodes (16): CSVManager, ArticleDraft, Write just the header row — used for init and reset., Truncate the CSV to headers only — removes ALL article data.         Use this f, Save a newly generated article row. Platform columns are empty until publish., Updates the article_published column for a given article_id., After a confirmed WordPress publish, write the live WP URL, slug, rendered, After a confirmed Blogger publish (blogger_result.get('id') is non-empty), (+8 more)

### Community 1 - "Community 1"
Cohesion: 0.20
Nodes (9): Article Generation Process - Complete Technical Architecture, Overview, Phase 1: Topic Selection & Keyword Alignment, Phase 2: Content Generation (Anthropic Claude via LiteLLM), Phase 3: SEO Grading & Quality Enforcement, Phase 4: Guaranteed Live Internal Linking, Phase 5: Hero Image Generation (`gemini-2.5-flash-image`), Phase 6: Word Document (.docx) Packaging & Email Delivery (+1 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (20): Any, Extract unique, content-specific keywords using industry context., Generate unique, title-specific keywords using industry context., Load categories from the config file., Filter titles to only include those related to defined categories.         RELAX, Proactively find and close common cookie consent banners or popups., Simulate short reading/idle time with tiny scrolls to look more human., Scrolls the page in a more human-like way to trigger dynamic content. (+12 more)

### Community 3 - "Community 3"
Cohesion: 0.20
Nodes (7): dict, PremiumKeywords, PremiumPlaces, PremiumPlacesDetails, Custom dictionary wrapper that dynamically returns premium verified tourist plac, Custom dictionary wrapper for KEYWORDS_ALL to dynamically map enriched     categ, Custom dictionary wrapper that dynamically returns premium verified data     whe

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (33): create_content_prompt(), create_html_conversion_prompt(), create_keyword_extraction_prompt(), create_keyword_generation_prompt(), create_raw_content_prompt(), _get_brand_or_industry_content(), _get_conclusion_cta_block(), _get_content_requirements() (+25 more)

### Community 5 - "Community 5"
Cohesion: 0.12
Nodes (36): BeautifulSoup, main(), gather_rishikesh_premium_data.py -------------------------------- Scrapes and co, Helper to scrape headings and text from a public web page., scrape_page(), Page, clean_text(), _compile_bungee_operators() (+28 more)

### Community 6 - "Community 6"
Cohesion: 0.19
Nodes (9): _get_model(), RelatedArticleFinder ==================== Finds the top-N most semantically simi, Load all published articles (wp_published_url != '') from CSV., Force reload the corpus from disk (call after new WP publishes)., Cosine similarity via sentence-transformers., Keyword-overlap fallback. Jaccard similarity on tokenised title words.         W, Finds semantically related articles from the published CSV records.      Usage, Return up to *top_k* related articles similar to the given title.          Args: (+1 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (18): 10. Location-anchor content, 11. Core Web Vitals + performance, 12. Breadcrumbs + BreadcrumbList schema, 13. Sitemaps + robots.txt, 1. Populate the empty FAQ on every destination page, 2. Operator / route price comparison tables, 3. Review + AggregateRating schema on every activity page, 4. Visible "Updated: [month] YYYY" line + Article schema (+10 more)

### Community 8 - "Community 8"
Cohesion: 0.12
Nodes (23): LLMConfig, Ensure scraped titles/keywords are strictly specific to the target city using LL, _apply_circuit_breaker(), call_llm(), _extract_usage_data(), get_available_models(), get_fallback_models(), get_limiter_for_model() (+15 more)

### Community 9 - "Community 9"
Cohesion: 0.17
Nodes (11): Cost expectations (rough, per article), Cost & pricing, Env vars, How the provider is chosen, LLM Provider Migration — Google Gemini → OpenAI (via LiteLLM), Model-tier notes for the rate limiter, Quickstart, Sanity check (+3 more)

### Community 10 - "Community 10"
Cohesion: 0.19
Nodes (14): BaseModel, CSVManager, Metadata, Orchestrator Module This module orchestrates the entire blog generation process,, SEO Auto-Healer Module ====================== This module provides the SEOAutoHe, Configuration Module This module centralizes all configuration variables for the, ArticleDraft, InternalLink (+6 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (25): 0. General Principles, 10. Continuous Documentation Updates, 1. Deep Research & Production-Ready Planning, 2. Pylint Compliance (Non-Negotiable), 3. Code Clarity — Write for Humans First, 4. Security, 5. Robustness & Error Handling, 6. Logging Standards (+17 more)

### Community 12 - "Community 12"
Cohesion: 0.13
Nodes (17): Client, _extract_image_bytes_from_response(), generate_blog_image(), ImagenLimiterManager, Image Generation Client Module This module provides interface for generating blo, Manages the thread-safe token bucket rate limiter for image generation., Get or initialize the rate limiter., Extract raw image bytes from a generate_content() response.      Gemini image ge (+9 more)

### Community 13 - "Community 13"
Cohesion: 0.14
Nodes (8): BlogGeneratorOrchestrator, Returns a photorealistic Rishikesh travel scene description for image generation, Returns a Rishikesh travel scene for image generation.         Uses the determin, Extract 2-3 sentences from the intro paragraph as excerpt., Load keywords from both scraped data and the rich keywords.json configuration., Initializes and runs the robust web scraper, then saves the data., Creates a safe filename from a title., Extracts plain text from HTML content.

### Community 14 - "Community 14"
Cohesion: 0.08
Nodes (23): API Endpoint Summary, Automatic (happens after every WordPress publish), Generate 50 articles, no publishing:, Generate AND publish to WordPress (recommended production flow):, LinkedIn, Manual Export (for a single article via Python), Medium, Operations Guide: Running the AI Blog Generator (+15 more)

### Community 15 - "Community 15"
Cohesion: 0.06
Nodes (25): ContentGeneratorAgent, Generate a collision-free, SEO-safe WordPress slug for the given title., Assemble the HTML body for a fallback article., Append checklist, mistakes section, and remaining paragraphs to html_parts in-pl, Return (meta_title, meta_description, faq_section) for a fallback article., Build the ordered sentence pool for a fallback article body., Produce a fully-structured fallback ArticleDraft without an LLM call., Register a slug as used after a successful publish or generation. (+17 more)

### Community 16 - "Community 16"
Cohesion: 0.16
Nodes (10): Heals headings, location counts, keywords, readability, and FAQ., Balances target city mentions and adds exact location boosters., Enforces that the FAQ section has at least 6 H3 questions., Utility class to programmatically fix minor SEO and structural issues., Ensures the article draft contains at least one valid internal link., Ensures keyword density meets strict optimal thresholds., Main entry point for healing an article draft.          Args:             articl, Sanitizes text for keyword matching, matching SEOEvaluatorAgent. (+2 more)

### Community 18 - "Community 18"
Cohesion: 0.19
Nodes (12): RuntimeError, SEOReport, AI Agents Module This module defines the core AI agents responsible for content, Manages used titles to prevent duplicates.      Near-duplicate detection uses a, Persistent slug registry that guarantees every article published to WordPress, Load all existing slugs from articles.csv at startup., SlugRegistry, TitleManager (+4 more)

### Community 19 - "Community 19"
Cohesion: 0.13
Nodes (12): main(), generate_and_email.py ====================== Generates exactly 2 high-quality, S, main(), run_email_campaign.py ====================== Generates a batch of articles (defa, ConcurrentCampaignManager, Concurrent Campaign Manager Module This module is responsible for running large-, Executes the full concurrent generation campaign.         Safeguards: Continues, Orchestrates a concurrent article generation campaign. (+4 more)

### Community 21 - "Community 21"
Cohesion: 0.14
Nodes (10): Increment the count of published articles for a specific platform., Get current statistics., Reset all statistics to zero., Manages generation and publishing statistics with persistent storage., Ensure the stats file exists with proper structure., Load stats from JSON file., Save stats to JSON file., Increment the count of generated articles. (+2 more)

### Community 22 - "Community 22"
Cohesion: 0.32
Nodes (5): SEOMetric, ArticleDraft, Checks whether the article reads as genuinely specific/useful (real numbers,, Normalise text for keyword matching: lowercase, strip punctuation, remove stop w, SEOEvaluatorAgent

### Community 24 - "Community 24"
Cohesion: 0.14
Nodes (5): Templates Module Stores static prompt string blocks and base templates., EmailService Module =================== Handles the assembly and delivery of Set, Config, Helper to load JSON structures from environment variables., Web Scraper Module This module contains the RobustScraper class, which is respon

### Community 26 - "Community 26"
Cohesion: 0.14
Nodes (13): _build_anchor(), _build_cta_widget(), LinkingManager, _load_sitemap_config(), linking_manager.py ------------------ Injects contextual Bucketlistt.com backlin, Main entry point.  Takes an ArticleDraft, returns enriched HTML string., Scans the article HTML and converts the FIRST occurrence of each         activit, Replaces the FIRST occurrence of *keyword* (case-insensitive) in the BeautifulSo (+5 more)

### Community 31 - "Community 31"
Cohesion: 0.17
Nodes (16): classify_keyword(), extract_keywords_from_text(), extract_text_from_html(), main(), merge_into_keywords_json(), Competitor Keyword Scraper - Production Grade Scrapes: Thrillophilia, Klook, Inc, Strip HTML tags from raw content., Extract relevant keyword phrases from page text.     Returns list of {keyword, s (+8 more)

### Community 32 - "Community 32"
Cohesion: 0.12
Nodes (15): 1. Essential API Keys, 2. Branding (Tell the AI who you are), 3. Campaign & SEO Settings, 4. Publishing, AI-Powered SEO Blog Generator, 🎨 Article Generation Process (Two-Step LLM), 🔄 Complete Workflow, ⚙️ Configuration Guide (+7 more)

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (12): 1. WordPress API (Application Passwords), 2. Blogger API (Google Cloud), 3. Tumblr API (OAuth), 4. Understanding the .pkl and .json Files, API Authentication & Setup Guide, Part A: Get the Credentials File, Part A: Register Your App, Part B: Generate the .pkl Token (+4 more)

### Community 41 - "Community 41"
Cohesion: 0.13
Nodes (11): InternalLink, _clean_url(), InternalLinkingService, Main orchestrator for adding exactly 2 article links and 1 site link., Normalise a URL that may have a double-slash from trailing-slash + slug concaten, Inserts internal links into the content HTML.          Strategy:         1. Find, Extracts plain text from HTML content., Loads real, live activity URLs from sitemap_mapping.json as guaranteed working l (+3 more)

### Community 45 - "Community 45"
Cohesion: 0.29
Nodes (6): AI Blog Generator - Complete Updated Workflow, 🏗️ Phase 1: Preparation & Initialization, 🔍 Phase 2: Knowledge Base & Research, ✍️ Phase 3: Generation & SEO Evaluation, 🎨 Phase 4: Hero Image Generation, 📧 Phase 5: Formatting, DOCX Packaging & Email Delivery

### Community 46 - "Community 46"
Cohesion: 0.16
Nodes (10): EmailService, Adds a REAL clickable hyperlink to a python-docx paragraph.          python-docx, Recursively processes inline HTML tags (strong, b, em, i, a, span, etc.), Parses article HTML content and FAQ section using BeautifulSoup,         unwraps, Generates DOCX files for a list of articles and extracts image attachments., Sends SMTP email with HTML body and attachments., Manages email styling, packaging, and SMTP delivery or local fallback storage., Saves HTML summary, DOCX, and inline image files locally on failure. (+2 more)

### Community 48 - "Community 48"
Cohesion: 0.20
Nodes (9): 1. Google Blogger API Setup, 2. Tumblr API Setup, How to Get API Keys for Blogger & Tumblr, Step 1.1: Create a Google Cloud Project & Enable Blogger, Step 1.2: Configure the OAuth Consent Screen, Step 1.3: Generate OAuth Client ID (client_secrets.json), Step 1.4: Generate the Authorization Token (.pkl), Step 2.1: Register a Tumblr Application (+1 more)

### Community 49 - "Community 49"
Cohesion: 0.22
Nodes (8): 1. Core Modules, AI Blog Generator - Comprehensive System & Function Dictionary, `src/agents.py` — Article Generator & SEO Evaluator, `src/config.py` — Configuration & Environment Engine, `src/image_client.py` — Hero Image Generator, `src/llm_client.py` — LiteLLM Provider Client, `src/services/email_service.py` — DOCX Packaging & SMTP Email Dispatcher, `src/stats_manager.py` — Campaign Statistics Manager

### Community 50 - "Community 50"
Cohesion: 0.33
Nodes (5): API Keys & Authentication, Environment Configuration Guide, Model Selection, SEO & Word Count Requirements, SMTP Email Configuration

### Community 51 - "Community 51"
Cohesion: 0.20
Nodes (9): 🏗️ 1. The Blueprint (Config & Instructions), 🧠 2. The Writer (Anthropic Claude via LiteLLM), 📏 3. The Quality Inspector (SEO Evaluator), 🎨 4. The Illustrator (Google Gemini Image Generator), 🔗 5. The Linker (Guaranteed Live Internal Links), 📄 6. The Mailer (Word DOCX & Email Delivery), 📊 7. The Accountant (Stats Manager), The AI Blog Campaign Engine — Explained Simply (+1 more)

### Community 52 - "Community 52"
Cohesion: 0.25
Nodes (5): Gets the ID of a category by name. Does NOT create new categories.         If pa, Uploads an image to WordPress Media Library and sets its metadata.         Retur, WordPressPublisher, Any, ArticleDraft

### Community 53 - "Community 53"
Cohesion: 0.25
Nodes (4): Initialize the TitleManager.          Args:             csv_path: Path to the CS, Load used titles from both the tracking CSV and the main articles CSV., Register one title loaded from disk into all in-memory indexes.          Kept se, Load titles (and rebuild all indexes) from a CSV file.

### Community 54 - "Community 54"
Cohesion: 0.22
Nodes (8): 1. High-Level Process Architecture, 2. Component Workflow Stages, 5. Title Deduplication Strategy (Updated 2026-05-31), End-to-End Blog Generation & Campaign Workflow, Stage A: Ingestion & Environment Configuration, Stage B: Concurrent Campaign Orchestration, Stage C: Single-Article Generation, Auto-Healing & SEO Guardrails, Stage D: Linking & Publishing

### Community 61 - "Community 61"
Cohesion: 0.22
Nodes (8): 1. Concurrent Campaign Components (`src/concurrent_manager.py`), 2. Agent Components (`src/agents.py`), 3. Orchestration & Services (`src/services/`), 4. Client & Rate Limiting Components (`src/llm_client.py` & `src/image_client.py`), 5. Publishing Components (`src/publishers/`), 6. Database & Database Write Safety (`utils/utils.py`), 7. Web API Endpoints (`api/main.py`), Core Codebase Functionality Directory

### Community 77 - "Community 77"
Cohesion: 0.29
Nodes (6): AI Blog Generator: Detailed End-to-End Workflow, 🏗️ Phase 1: Initialization & Environment Safeguards, 🔍 Phase 2: Autonomous Research & Competitive Intelligence, 🧠 Phase 3: Intelligent Orchestration & Quality Generation, 🎨 Phase 4: Multimedia Enrichment & SEO Iteration, 🚀 Phase 5: Persistence & Deployment

### Community 88 - "Community 88"
Cohesion: 0.28
Nodes (10): Generate SEO report text for successful articles and iteration feedback., Exception, BlogGenerationError, DuplicateArticleError, NoAvailableProductError, Raised when no unique product is available for a brand article., Raised when an article with the same title already exists., Raised when blog generation fails to meet requirements. (+2 more)

## Knowledge Gaps
- **140 isolated node(s):** `ArticleDraft`, `Any`, `Page`, `1. Concurrent Campaign Components (`src/concurrent_manager.py`)`, `2. Agent Components (`src/agents.py`)` (+135 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Config` connect `Community 24` to `Community 0`, `Community 2`, `Community 4`, `Community 8`, `Community 41`, `Community 10`, `Community 12`, `Community 13`, `Community 46`, `Community 15`, `Community 16`, `Community 18`, `Community 19`, `Community 21`, `Community 22`, `Community 88`?**
  _High betweenness centrality (0.187) - this node is a cross-community bridge._
- **Why does `RobustScraper` connect `Community 2` to `Community 24`, `Community 10`, `Community 88`, `Community 13`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Why does `BlogGeneratorOrchestrator` connect `Community 13` to `Community 0`, `Community 2`, `Community 6`, `Community 8`, `Community 41`, `Community 10`, `Community 15`, `Community 16`, `Community 18`, `Community 19`, `Community 52`, `Community 21`, `Community 22`, `Community 88`, `Community 24`, `Community 26`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Are the 43 inferred relationships involving `Config` (e.g. with `Client` and `CSVManager`) actually correct?**
  _`Config` has 43 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `BlogGeneratorOrchestrator` (e.g. with `RelatedArticleFinder` and `WordPressPublisher`) actually correct?**
  _`BlogGeneratorOrchestrator` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 10 inferred relationships involving `ContentGeneratorAgent` (e.g. with `BlogGeneratorOrchestrator` and `Config`) actually correct?**
  _`ContentGeneratorAgent` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `ArticleDraft` (e.g. with `CSVManager` and `InternalLink`) actually correct?**
  _`ArticleDraft` has 22 INFERRED edges - model-reasoned connections that need verification._
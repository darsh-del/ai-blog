# AI Blog Generator - Comprehensive System & Function Dictionary

This document details the key files, classes, and functions powering the AI Blog Generator campaign engine.

---

## 1. Core Modules

### `src/config.py` — Configuration & Environment Engine
- **`Config`**: Loads environment variables from `.env`. Configures Anthropic Claude (`anthropic/claude-3-5-haiku-20241022`), Google Gemini (`gemini-2.5-flash-image`), SMTP settings (`SMTP_TO`, `SMTP_CC`), and SEO boundaries (`MIN_WORD_COUNT=1000`, `MAX_WORD_COUNT=1500`, `SEO_THRESHOLD=80`).
- **`ensure_directories()`**: Automatically creates `data/database/`, `data/output/json/`, `data/output/images/`, and `data/output/emails/` directories.

### `src/llm_client.py` — LiteLLM Provider Client
- **`call_llm(prompt, config)`**: Thread-safe LLM dispatcher using LiteLLM. Preserves provider prefixes (`anthropic/claude-3-5-haiku-20241022`) and handles parameter dropping (`litellm.drop_params = True`).
- **`get_fallback_models()`**: Returns the ordered fallback model chain (`anthropic/claude-3-5-haiku-20241022`, `anthropic/claude-3-5-sonnet-20241022`, `gemini/gemini-2.0-flash`, `gpt-4o-mini`).

### `src/image_client.py` — Hero Image Generator
- **`generate_blog_image(prompt)`**: Generates 16:9 aspect ratio high-resolution banner images (`.jpg`) using Google AI Studio Developer API (`GOOGLE_AI_STUDIO_API_KEY`) and `gemini-2.5-flash-image`.

### `src/agents.py` — Article Generator & SEO Evaluator
- **`ContentGenerationAgent`**: Constructs structured content prompts and calls `call_llm` to produce 1,000–1,500 word articles.
- **`SEOEvaluatorAgent._evaluate_word_count()`**: Evaluates word count against `MIN_WORD_COUNT` (1,000 words). Assigns 0 points to articles under 1,000 words to enforce mandatory 1k+ word count.

### `src/stats_manager.py` — Campaign Statistics Manager
- **`StatsManager`**: Thread-safe manager for `data/database/stats.json`.
- **`increment_generated()`**: Increments `generated.total` counter.
- **`increment_emailed(count)`**: Increments `emailed.total_sets` and `emailed.total_articles` counters when articles are packaged and emailed.

### `src/services/email_service.py` — DOCX Packaging & SMTP Email Dispatcher
- **`build_html_body(articles)`**: Generates a clean HTML summary message listing article titles, categories, and word counts.
- **`_html_to_docx(html_content, doc)`**: Converts HTML content into `.docx` format. Injects active OPC XML hyperlinks directly into relationship tables for full clickability.
- **`_send_smtp_email(html_body, docx_attachments, image_attachments, num_articles)`**: Sends MIME email packages via SMTP to primary recipients (`SMTP_TO`) and CC recipients (`SMTP_CC`), attaching `.docx` files and `.jpg` banner images.

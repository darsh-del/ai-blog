# AI Blog Generator - Complete Updated Workflow

This document provides a comprehensive technical walkthrough of the end-to-end operation of the AI Blog Generator campaign system.

---

## 🏗️ Phase 1: Preparation & Initialization

1. **Environment & Model Check**: `Config` (`src/config.py`) loads `.env` variables including `LLM_MODEL` (`anthropic/claude-3-5-haiku-20241022`), `IMAGE_MODEL` (`gemini-2.5-flash-image`), `GOOGLE_AI_STUDIO_API_KEY`, `ANTHROPIC_API_KEY`, and SMTP settings (`SMTP_TO`, `SMTP_CC`).
2. **Directory Setup**: Essential directories (`data/database/`, `data/output/json/`, `data/output/images/`, `data/output/emails/`, etc.) are initialized automatically.
3. **Database & Stats Sync**: `CSVManager` (`utils/utils.py`) and `StatsManager` (`src/stats_manager.py`) load and track campaign metrics persistently in `articles.csv` and `stats.json`.

---

## 🔍 Phase 2: Knowledge Base & Research

1. **Structured Sitemap Mapping**: `sitemap_mapping.json` supplies real, live activity URLs (`https://www.bucketlistt.com/rishikesh/river-rafting`, `bungee-jumping`, `zip-line-over-ganga`, `camping`) for context and internal linking.
2. **Keywords & Categories**: Keywords and brand guidelines are read from `keywords.json` and `sitemap_mapping.json`.

---

## ✍️ Phase 3: Generation & SEO Evaluation

1. **LLM Execution via LiteLLM**:
   - `ContentGenerationAgent` sends prompts to Anthropic Claude (`anthropic/claude-3-5-haiku-20241022`).
   - If Anthropic rate-limits or fails, LiteLLM routes automatically to `gemini/gemini-2.0-flash` or `gpt-4o-mini`.
2. **Word Count Target**:
   - Articles MUST achieve **1,000 to 1,500 words** (1k+ word count).
   - Any draft under 1,000 words receives 0 points on word count and is automatically re-queued for expansion.
3. **SEO Evaluation**:
   - `SEOEvaluatorAgent` grades heading structure, focus keyword density (2.5%–5.0%), internal links, and word count.
   - Requires a minimum score of **80/100** to pass.
4. **Guaranteed Live Internal Links**:
   - Injects exactly 3 working links per article: 2 links to published posts or live activity URLs from `sitemap_mapping.json`, plus 1 link to `https://www.bucketlistt.com/`.

---

## 🎨 Phase 4: Hero Image Generation

1. **Google AI Studio Developer API**:
   - Uses `gemini-2.5-flash-image` via `image_client.py` with `GOOGLE_AI_STUDIO_API_KEY`.
2. **High-Resolution Output**:
   - Generates 16:9 aspect ratio hero banner images (`.jpg`) saved in `data/output/images/`.

---

## 📧 Phase 5: Formatting, DOCX Packaging & Email Delivery

1. **Word Document (.docx) Generation**:
   - `EmailService` parses HTML content into `.docx` documents.
   - Injects active OPC XML hyperlinks directly into `.docx` relationship tables so every link remains clickable in Microsoft Word and Google Docs.
2. **Clean Email Summary**:
   - Builds a clean HTML email summary body detailing the generated articles, SEO scores, and word counts.
3. **SMTP Multi-Recipient Delivery**:
   - Packages `.docx` Word documents and `.jpg` banner images as attachments.
   - Dispatches email via SMTP (`smtp.gmail.com:587`) to all primary recipients (`SMTP_TO`) and CC recipients (`SMTP_CC`).
4. **Stats Manager Logging**:
   - Updates `stats.json` incrementing `generated.total`, `emailed.total_sets`, and `emailed.total_articles`.

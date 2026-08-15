# Article Generation Process - Complete Technical Architecture

## Overview

The AI Blog Generator campaign engine creates high-converting, SEO-optimized travel and adventure articles targeting a **1,000 to 1,500 word count**. 

It uses Anthropic Claude (`anthropic/claude-3-5-haiku-20241022`) as the primary text generation engine via LiteLLM, with automatic failover to Google Gemini (`gemini/gemini-2.0-flash`) and OpenAI (`gpt-4o-mini`).

---

## Technical Pipeline

### Phase 1: Topic Selection & Keyword Alignment
- Selects target topics from `categories.json` and `sitemap_mapping.json`.
- Enforces 1 + 1-2 + 2-3 keyword hierarchy (Main keyword, secondary keywords, location terms).

### Phase 2: Content Generation (Anthropic Claude via LiteLLM)
- **Primary Model**: `anthropic/claude-3-5-haiku-20241022`
- **Target Word Count**: Must be **1,000 to 1,500 words** (1k+ length).
- **Structure**: Includes introduction, multiple H2/H3 subheadings, actionable local travel advice, internal link anchors, and an explicit FAQ section.

### Phase 3: SEO Grading & Quality Enforcement
- `SEOEvaluatorAgent` evaluates the generated draft.
- **Word Count Enforcement**: Articles under 1,000 words receive 0 points on word count and get re-generated for expansion.
- **Passing Score**: Requires an overall score of **>= 80/100** to pass.

### Phase 4: Guaranteed Live Internal Linking
- Injects 3 active, working hyperlinks per article:
  - 2 links to existing published posts or live activity URLs from `sitemap_mapping.json` (`https://www.bucketlistt.com/rishikesh/river-rafting`, `bungee-jumping`, etc.).
  - 1 link to the main site (`https://www.bucketlistt.com/`).

### Phase 5: Hero Image Generation (`gemini-2.5-flash-image`)
- Generates a 16:9 aspect ratio high-resolution image (`.jpg`) using Google AI Studio Developer API (`GOOGLE_AI_STUDIO_API_KEY`).

### Phase 6: Word Document (.docx) Packaging & Email Delivery
- Converts article HTML to Microsoft Word (`.docx`) attachments.
- Registers active OPC XML hyperlinks so all internal links remain clickable in Word.
- Dispatches clean summary email with attached `.docx` and `.jpg` files via SMTP (`smtp.gmail.com:587`) to all configured primary (`SMTP_TO`) and CC (`SMTP_CC`) recipients.
- Automatically increments `generated.total`, `emailed.total_sets`, and `emailed.total_articles` in `data/database/stats.json`.

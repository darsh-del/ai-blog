# Environment Configuration Guide

This document provides a detailed explanation of the `.env` configuration file governing the behavior of the AI Blog Generator campaign system.

---

## API Keys & Authentication

| Variable | Description | Impact |
| :--- | :--- | :--- |
| `ANTHROPIC_API_KEY` | Your secret API key from Anthropic Console (`sk-ant-api03-...`). | **Critical**. Used for primary article content generation using Claude (`anthropic/claude-3-5-haiku-20241022`). |
| `GOOGLE_AI_STUDIO_API_KEY` | Your secret API key from Google AI Studio. | **Critical**. Used for generating hero banner images via `gemini-2.5-flash-image`. |
| `OPENAI_API_KEY` | Optional OpenAI API Key (`sk-proj-...`). | Used as a fallback LLM provider (`gpt-4o-mini`). |

---

## Model Selection

| Variable | Description | Impact |
| :--- | :--- | :--- |
| `LLM_MODEL` | Primary text generation model. Default: `anthropic/claude-3-5-haiku-20241022`. | Controls article quality via Anthropic Claude. LiteLLM handles provider routing. |
| `LLM_FALLBACK_MODELS` | Fallback models chain. Default: `anthropic/claude-3-5-haiku-20241022,anthropic/claude-3-5-sonnet-20241022,gemini/gemini-2.0-flash,gpt-4o-mini`. | Automatic failover when primary models hit rate limits or errors. |
| `IMAGE_MODEL` | Primary image generation model. Default: `gemini-2.5-flash-image`. | Generates 16:9 banner images via Google AI Studio API. |

---

## SEO & Word Count Requirements

| Variable | Description | Impact |
| :--- | :--- | :--- |
| `MIN_WORD_COUNT` | Minimum word count target. Default: `1000`. | **Strict Limit**. Articles under 1,000 words receive 0 points on word count and get re-generated. |
| `MAX_WORD_COUNT` | Maximum word count target. Default: `1500`. | Keeps generated articles focused in the optimal 1,000–1,500 word range. |
| `SEO_THRESHOLD` | Quality threshold. Default: `80`. | Quality gate: articles must achieve an internal SEO score >= 80 to pass. |
| `IMAGE_GENERATION_RATIO` | Probability ratio (0.0 to 1.0). Default: `1.0`. | Ensures hero images are generated for all campaign articles. |

---

## SMTP Email Configuration

| Variable | Description | Impact |
| :--- | :--- | :--- |
| `SMTP_HOST` | Remote SMTP server hostname. Default: `smtp.gmail.com`. | Server used to send article email packages. |
| `SMTP_PORT` | SMTP port. Default: `587` (STARTTLS). | Network port for secure mail submission. |
| `SMTP_USERNAME` | Sender email address. | Authenticated SMTP account. |
| `SMTP_PASSWORD` | App Password for Gmail/SMTP. | Authenticated SMTP password. |
| `SMTP_TO` | Primary recipient email(s), comma-separated. | Recipient address(es) for `.docx` & image attachments. |
| `SMTP_CC` | Optional CC recipient email(s), comma-separated. | Copy recipient address(es). |

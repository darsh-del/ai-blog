# The AI Blog Campaign Engine — Explained Simply

Think of this software as an **Automated AI Content Factory** that researches, writes, formats, and emails professional blog post bundles directly to your inbox. Here is how it works:

---

## 🏗️ 1. The Blueprint (Config & Instructions)
- **The Files:** `.env` and `src/config.py`
- **What they do:** Tell the factory which AI models to use (Anthropic Claude for writing, Google Gemini for images), minimum word count targets (1,000–1,500 words), and recipient email addresses (`SMTP_TO`, `SMTP_CC`).

## 🧠 2. The Writer (Anthropic Claude via LiteLLM)
- **The File:** `src/agents.py` & `src/llm_client.py`
- **What it does:** Uses Anthropic Claude (`anthropic/claude-3-5-haiku-20241022`) to draft rich, detailed travel and adventure articles. If Anthropic is busy, it automatically switches to Gemini or OpenAI without stopping.

## 📏 3. The Quality Inspector (SEO Evaluator)
- **The File:** `src/agents.py` (`SEOEvaluatorAgent`)
- **What it does:** Grades every draft. If an article is under 1,000 words or scores below 80/100, the inspector rejects it and sends it back to be expanded.

## 🎨 4. The Illustrator (Google Gemini Image Generator)
- **The File:** `src/image_client.py`
- **What it does:** Uses `gemini-2.5-flash-image` with your Google AI Studio key to generate high-resolution 16:9 hero banner pictures (`.jpg`).

## 🔗 5. The Linker (Guaranteed Live Internal Links)
- **The File:** `src/services/internal_linking.py`
- **What it does:** Injects 3 active, working links into every article: 2 links to real activity pages (`https://www.bucketlistt.com/rishikesh/river-rafting`, `bungee-jumping`, etc.) and 1 link to `https://www.bucketlistt.com/`.

## 📄 6. The Mailer (Word DOCX & Email Delivery)
- **The File:** `src/services/email_service.py`
- **What it does:** Converts articles into Word documents (`.docx`) with active clickable links, attaches the hero images, and emails the complete package to your primary and CC email addresses via SMTP.

## 📊 7. The Accountant (Stats Manager)
- **The Files:** `src/stats_manager.py` & `data/database/stats.json`
- **What it does:** Automatically keeps count of every generated article and emailed set in `stats.json`.

---

### The Summary in 5 Seconds:
1. **Configure** API keys and email recipients (`.env`).
2. **Write** 1,000+ word articles with Anthropic Claude (`src/agents.py`).
3. **Illustrate** with Google Gemini hero images (`src/image_client.py`).
4. **Package** into `.docx` files with clickable links (`src/services/email_service.py`).
5. **Email** the final set directly to your inbox and update stats (`stats.json`).

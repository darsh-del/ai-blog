"""
Content Prompts Module
Contains prompt generation functions for generating full blog article content.
"""
from typing import List, Optional, Dict

from src.config import Config
from .templates import (
    LINK_PLACEMENT_BLOCK,
    IMAGE_FIRST_BLOCK,
    REJECTION_CRITERIA,
    EXACT_OUTPUT_FORMAT,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def _get_keyword_hierarchy_block(main_keyword: str, secondary_str: str, additional_str: str) -> str:
    return f"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   KEYWORD TARGETING FRAMEWORK (CLIENT DIRECTIVE — MANDATORY)     ║
    ╚══════════════════════════════════════════════════════════════════╝

    This article MUST follow the 1 + 1-2 + 2-3 keyword hierarchy:

    ┌─ MAIN KEYWORD (×1 only) ───────────────────────────────────────┐
    │  "{main_keyword}"
    │  • Use in: H1 title, URL slug, first 50 words, image alt text
    │  • Repeat naturally throughout content (aim 2-4% density)
    │  • This keyword DRIVES the entire article topic
    └────────────────────────────────────────────────────────────────┘

    ┌─ SECONDARY KEYWORDS (1-2) ──────────────────────────────────────┐
    │  {secondary_str}
    │  • Use in: H2 subheadings and body paragraphs
    │  • Each must appear at least 2-3 times naturally
    └────────────────────────────────────────────────────────────────┘

    ┌─ ADDITIONAL KEYWORDS (2-3) ─────────────────────────────────────┐
    │  {additional_str}
    │  • Use in: H2 or H3 subheading text and body paragraphs
    │  • Each must appear at least 1-2 times
    │  • Do NOT force them — only where contextually natural
    └────────────────────────────────────────────────────────────────┘
    
    ⚠️ WARNING: NEVER REPHRASE OR SPLIT THE KEYWORDS.
    If the keyword is "best rishikesh food", do NOT write "the best food in Rishikesh".
    You MUST insert the EXACT phrase word-for-word into your sentences to pass the SEO audit.
    """


def _get_media_injection_block(media_assets: Optional[List[Dict]]) -> str:
    if not media_assets:
        return ""
    media_lines = []
    for asset in media_assets[:4]:  # cap at 4 media embeds per article
        anchor = asset.get("suggested_anchor_text", asset.get("title", "Watch on Instagram"))
        url = asset.get("url", "")
        context = asset.get("suggested_context", "")
        platform = asset.get("platform", "")
        icon = "▶" if "youtube" in platform else "📸"
        media_lines.append(f"    {icon} [{anchor}]({url}) — {context}")
    media_block_content = "\n".join(media_lines)
    return f"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   SOCIAL MEDIA EMBEDS — INJECT IN BODY (CLIENT DIRECTIVE)        ║
    ╚══════════════════════════════════════════════════════════════════╝

    Embed the following media links naturally inside the BODY of the article.
    RULES:
    - NEVER place ANY of these links in the first 3 paragraphs or the intro
    - Place AFTER the 4th paragraph minimum (mid-body or conclusion sections)
    - Format as contextual anchor text: e.g. <p>Watch this <a href="URL">real customer jump experience</a> to see what to expect.</p>
    - Max 1 YouTube embed. Max 3 Instagram embeds.
    - Only include if the link is contextually relevant at that point in the article

    APPROVED MEDIA FOR THIS ARTICLE:
{media_block_content}
    """


def _get_conclusion_cta_block(is_brand_article: bool, bucketlistt_cta_url: str) -> str:
    _forbidden = """
    ⛔ FORBIDDEN IN THE CONCLUSION (NON-NEGOTIABLE):
    - NEVER list or restate the article's target keywords, in ANY phrasing.
      Every one of these patterns is BANNED — do not paraphrase your way around them:
        · "This guide covered X, Y, Z..."
        · "In this article we discussed X, Y, Z..."
        · "As we've seen, X, Y, Z..."
        · "Our travel portal addresses key search topics such as X, Y, Z..."
        · "This article covers key topics such as X, Y, Z..."
        · "Topics covered include X, Y, Z..."
        · Any paragraph that reads as a bolded/linked keyword recap.
      Reason: this is the single most obvious "AI-written spam" pattern. Google's helpful
      content update penalises it. Human writers never do this. If you find yourself about
      to write the words "topics", "search terms", "keywords", "covered", or "addresses"
      in the conclusion, DELETE the sentence — it is the failure mode.
    - NEVER end with more than ONE contextual link. One is plenty.
    - NEVER end mid-sentence, with an emoji, with a stray backtick, or with a code fence.
      The final character of the article must be a period inside a </p>.
    """
    if is_brand_article:
        return f"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   CONCLUSION CTA RULES (CLIENT DIRECTIVE — BRAND ARTICLES)       ║
    ╚══════════════════════════════════════════════════════════════════╝

    The conclusion MUST always include:
    1. A 2-3 sentence summary of the article's key PRACTICAL takeaways (not a keyword list).
       Rephrase in fresh words. Reference specific concrete details from the body
       (a route name, an operator, a price, a timing) — never the target keywords.
    2. A single, natural booking suggestion (do NOT use pushy sales language):
       Example: "Ready to experience this for yourself? Browse and compare options on
       <a href="{bucketlistt_cta_url}">bucketlistt</a>."
    3. Tone: Helpful and informative, NOT promotional. Write as a knowledgeable local guide.
{_forbidden}
    """
    return f"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   CONCLUSION RULES (CLIENT DIRECTIVE — GENERIC ARTICLES)         ║
    ╚══════════════════════════════════════════════════════════════════╝

    The conclusion MUST:
    1. Summarise 2-3 key PRACTICAL takeaways from the article in fresh wording.
       Reference specific details (a route name, an operator, a price, a timing) —
       never the raw target keywords.
    2. Encourage the reader to plan their visit to Rishikesh.
    3. Optionally (not mandatory) include ONE natural contextual link:
       Example: "For a curated list of verified operators and packages, you can explore options on
       <a href="{bucketlistt_cta_url}">bucketlistt</a>."
    4. Tone: Authoritative travel guide. NOT salesy or promotional.
{_forbidden}
    """


def _get_serp_dominance_block(main_keyword: str, category: str) -> str:
    """Two high-value SERP signals the LLM CAN reliably produce inline: a featured-snippet
    answer paragraph and an updated-date line. Everything else that used to live here
    (operator price tables, TOC, author box, spatial-anchor rules) has been moved to the
    website-template layer — see documentation/WEBSITE_SEO_CHANGES.md. Reason: the LLM
    reliably mangled HTML tables and lost coherence past ~1500 words when the prompt was
    fat with nested mandates. Two focused rules beat seven ignored ones.
    """
    _ = category  # kept in signature so the wire-up in create_content_prompt stays stable
    return f"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   TWO SERP SIGNALS TO INCLUDE INLINE (KEEP IT TIGHT)             ║
    ╚══════════════════════════════════════════════════════════════════╝

    1. **FEATURED-SNIPPET ANSWER (first paragraph after the H1):**
       The FIRST <p> after the H1 must directly answer "{main_keyword}" in 40-60 words.
       Front-load the concrete facts (price range, height/distance, best months) that
       Google can lift as a featured snippet. This is a tight informational paragraph —
       NOT the storytelling intro. Start the storytelling intro in the SECOND paragraph.
       Example shape (adapt facts to topic):
         "<p><b>{main_keyword}</b> [does X], costing ₹A–₹B across the main options.
         The best window is [months]. [Concrete fact]. [Concrete fact].</p>"

    2. **"UPDATED" DATE LINE (immediately below the H1, before the featured-snippet paragraph):**
       Exactly one line: <p class="post-meta"><em>Updated: [Current Month] 2026</em></p>
       Google surfaces recency; readers trust dated content.

    That is the whole block. Do NOT generate a manual table of contents or
    spatial-anchor commentary. An HTML price table IS allowed if the reference
    brief supplies price data — keep it simple (no inline styles, no colspans).
    """


def _get_partner_brand_block(category: str, bucketlistt_cta_url: str) -> str:
    category_lower = (category or "").lower()
    _is_bungee_article = any(term in category_lower for term in ["bungee", "bungy", "jump", "comparison", "operator"])
    _is_paragliding_article = "paragliding" in category_lower
    _partner_is_relevant = _is_bungee_article or _is_paragliding_article

    if not _partner_is_relevant:
        return ""

    _approved_brands = []
    if _is_bungee_article:
        _approved_brands = [
            "- Himalayan Bungy — India's highest bungee at Rishikesh (117m and 111m variants)",
            "- Splash Bungy — Rishikesh bungee operator (109m splash experience, 85m freestyle)",
            "- Maa Ganga Bungy — India's highest bungee (200m+) at Devprayag, near Rishikesh",
        ]
    elif _is_paragliding_article:
        _approved_brands = [
            "- WhyNotFly — Paragliding operator, Rishikesh (tandem flights 7-20 min, safety-rated)",
        ]
    _approved_brands_str = "\n    ".join(_approved_brands)

    return f"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   PARTNER BRAND MENTIONS (CLIENT DIRECTIVE — CONDITIONAL)        ║
    ╚══════════════════════════════════════════════════════════════════╝

    This article may editorially mention the following PARTNER BRANDS by name.
    These are real, verified operators. Mentioning them builds
    Google E-E-A-T trust signals and makes the article genuinely informative.

    APPROVED PARTNER BRANDS FOR THIS ARTICLE TYPE:
    {_approved_brands_str}

    RULES FOR PARTNER BRAND MENTIONS:
    - Mention partner brands by name in body paragraphs AFTER paragraph 4
    - Mention price, height, and brief feature description (neutral, factual tone)
    - Always conclude with: "Compare and book via bucketlistt" — linking to {bucketlistt_cta_url}
    - In comparison articles, mention ALL relevant partners for full editorial coverage

    STRICTLY FORBIDDEN:
    - NEVER mention partner brands in the Introduction (first 3 paragraphs)
    - NEVER add links to ANY third-party operator website URL (e.g. their .com domain)
    - NEVER say one operator is "better" — present each factually, let the reader decide
    - NEVER fabricate heights, prices, or features — use only the approved facts above
    - DO NOT mention Maa Ganga Bungy as a "Rishikesh" operator — it is in Devprayag

    EXAMPLE APPROVED MENTION PATTERN (bungee articles):
    "Rishikesh has several bungee operators catering to different budgets and preferences.
    Himalayan Bungy offers jumps at 117 metres and 111 metres, while Splash Bungy
    provides a unique 109-metre experience where jumpers touch the Ganga river.
    For the highest bungee in India, Maa Ganga Bungy at Devprayag offers a 200+ metre
    jump — though it requires a separate trip from Rishikesh. Compare all
    available options and book online through
    <a href="{bucketlistt_cta_url}">bucketlistt</a>."
    """


def _get_authoritative_citation_block() -> str:
    """
    Optional (non-scored, non-mandatory) prompt to add ONE outbound link to a real,
    independent, authoritative source. This is a genuine E-E-A-T/trust signal that
    nothing else in the pipeline provides — every other outbound link this generator
    ever adds points back to bucketlistt or an approved partner. Kept to a short,
    hand-verified allowlist rather than letting the model invent a URL, so nothing
    can end up broken or unrelated.
    """
    return """
    ╔══════════════════════════════════════════════════════════════════╗
    ║   OPTIONAL EXTERNAL CITATION (NOT MANDATORY)                     ║
    ╚══════════════════════════════════════════════════════════════════╝

    If, and only if, it fits naturally (e.g. mentioning weather, best season, or
    official permits/safety rules), you MAY cite ONE of these real government
    sources by name with a link. Do not force it in if it doesn't fit:
    - Uttarakhand Tourism Development Board — https://uttarakhandtourism.gov.in
    - India Meteorological Department (Dehradun centre, for Rishikesh weather) —
      https://mausam.imd.gov.in/dehradun/
    Do NOT invent or guess any other external URL. If neither source is relevant
    to this specific article, skip this section entirely.
    """


def _get_faq_block(main_keyword: str) -> str:
    return f"""
    ╔══════════════════════════════════════════════════════════════════╗
    ║   FAQ SECTION RULES (CLIENT DIRECTIVE — MANDATORY)               ║
    ╚══════════════════════════════════════════════════════════════════╝

    You MUST add a mandatory FAQ section BEFORE the conclusion.
    REQUIREMENTS:
    - MINIMUM 7 questions, aim for 8-10 for best PAA / featured snippet / AI Overview coverage.
    - FAILURE TO INCLUDE AT LEAST 7 QUESTIONS WILL RESULT IN ARTICLE REJECTION.
    - Source questions from REAL things people search on Google about "{main_keyword}":
        • Google Autocomplete (type the keyword and note the dropdown suggestions)
        • "People Also Ask" boxes at the bottom of search results
        • Long-tail keyword variations ("how to", "best time", "is it safe", "cost", "duration")
    - Each answer: 2-4 direct, factual, conversational sentences. NO filler or vague responses.
    - Write answers as a knowledgeable local guide speaking to a first-time visitor.
    - Use FAQPage schema markup format (see output structure below)
    - NEVER use <h2> inside the FAQ body — ONLY <h3> for questions, <p> for answers
    """


def _get_title_instruction(title: str, category: str) -> str:
    return (
        f"The requested title is: '{title}'.\n"
        f"**ADAPTABILITY MANDATE:** If this title does not naturally fit the assigned category ({category}), "
        "you MUST rephrase the <h1> heading to be technically accurate and relevant to the category while "
        "retaining the core intent of the original title."
    )


def _get_brand_or_industry_content(is_brand_article: bool, category_context: str) -> str:
    if is_brand_article:
        return f"""
        - **Brand Tone:** Write as a local expert who recommends {Config.BRAND_NAME} based on genuine experience.
        - **Brand Mentions:** Mention "{Config.BRAND_NAME}" naturally 4-6 times MAXIMUM.
        - **Brand Voice:** Warm, helpful, and authoritative. Prioritise being useful to the reader.{category_context}
        - **Soft CTA:** One natural mention of booking/comparing via {Config.BRAND_NAME} in body or conclusion.
        """
    return f"""
    - **Primary Focus:** Write a PRACTICAL, USEFUL travel guide for someone planning to visit Rishikesh.
    - **Writing Style:** First-person knowledgeable travel guide voice.{category_context}
    - **Practical Content:** Include details like best time of day/year, what to wear, costs, and safety tips.
    - **Brand Neutral:** Do NOT mention {Config.BRAND_NAME} by name in the article body.
    - **Category vs Keywords:** The TOPIC is the travel category/guide. The KEYWORDS are just modifiers.
    - **Local Authority:** Include at least one specific local detail that demonstrates real local knowledge.
    """


def _get_content_requirements(is_brand_article: bool, category: str) -> str:
    category_context = ""
    if category:
        if is_brand_article:
            category_context = (
                f"\n- **Product Category Focus:** This article focuses on the specific product **{category}**. "
                f"Naturally mention {category} throughout. The content SHOULD focus on: "
                "Practical 'how-to' guides, optimal usage scenarios, and unique features."
            )
        else:
            category_context = (
                f"\n- **Category Focus:** The entire article MUST be about "
                f"the travel topic **{category}** in Rishikesh. "
                "Every section should discuss practical tips, details, routes, timing, "
                "safety recommendations, and specific travel advice."
            )

    detail_str = _get_brand_or_industry_content(is_brand_article, category_context)

    return f"""
    **META DATA REQUIREMENTS:**
    - **META_TITLE:** 50-65 characters, include primary keyword.
    - **META_DESCRIPTION:** EXACTLY 120-155 characters. Start with a bold claim, fact, or solution-oriented hook.
        - **UNIQUENESS RULE:** MUST be an engaging "hook" or "curiosity gap".
        - **FORBIDDEN starters:** "Introduction to", "Welcome to", "In this article", "Discover how", "Looking for".
    - **URL_SLUG:** hyphenated lowercase version of the title.
    - **FOCUS_KEYWORD:** MANDATORY — the single most important 1-3 word keyphrase.

    
    - **Word Count:** MUST be AT LEAST {Config.MIN_WORD_COUNT} words (aim for 1,100 to 1,400 words).
      Do NOT write short articles under {Config.MIN_WORD_COUNT} words. Expand sections thoroughly with rich, practical details.
    - **SEO Score Target:** Achieve 100/100 optimization.
    - **Keyword Density:** Maintain a strict density of 2.5% to 5.0% for the provided keywords.
      Mention each keyword at least 3-5 times in the content. Avoid repetitive sentences.
    - **Factual Accuracy:** Ensure all information is accurate and up-to-date (2026 data).
    {detail_str}
    """


def _get_human_voice_block() -> str:
    """
    Style constraints aimed at natural sentence-rhythm variation and avoiding the
    stock vocabulary/openers that make AI-written text read as flat and uniform
    (low perplexity/burstiness). Google doesn't rank by "AI-detector score" — it
    ranks by content quality and E-E-A-T — but flat, repetitive phrasing reads
    poorly to real visitors regardless, so this is a genuine writing-quality ask.
    """
    return """
    **WRITING VOICE — SOUND LIKE A PERSON, NOT A TEMPLATE:**
    - Vary sentence length deliberately. Do NOT write every sentence at a similar length.
      Cluster it the way people actually talk: two or three short, punchy sentences,
      then one longer sentence that threads a more complex idea, then short again.
      A paragraph where every sentence is 15-20 words is a dead giveaway of AI writing.
    - Vary how sections and paragraphs open. Do NOT start consecutive H2/H3 sections
      or paragraphs with the same sentence pattern (e.g. every section opening with
      "When it comes to..." or "If you're looking to...").
    - AVOID these overused AI-writing words and phrases entirely: delve, moreover,
      furthermore, additionally, leverage, utilize, seamless(ly), robust, boast,
      tapestry, realm, landscape (as a metaphor), underscore, testament to, embark on,
      navigate the complexities, unlock, unleash, elevate, game-changer, cutting-edge,
      in today's fast-paced world, in today's digital age, it's important to note,
      it's worth noting, at the end of the day, in conclusion. Use plain words instead.
    - Prefer concrete, specific detail (a real number, a named place, a practical tip)
      over generic filler adjectives. Write like someone who has actually been there.
    """


def _get_content_structure(is_brand_article: bool) -> str:
    if is_brand_article:
        return f"""
        **CONTENT STRUCTURE FOR BRAND-SPECIFIC ARTICLE:**
        Write this as a travel activity guide that features {Config.BRAND_NAME} contextually.

        1.  **ENGAGING INTRODUCTION (200-250 words):**
            - START with a vivid, specific scene or surprising fact about the experience in {Config.TARGET_CITY}.
            - Mention {Config.BRAND_NAME} ONCE in the intro — as a natural reference.
            - Include the primary keyword within the first 50 words.

        2.  **MAIN SECTION 1 - Complete Activity Guide (400-500 words):**
            - H2 heading: Practical guide to doing this activity in {Config.TARGET_CITY}.
            - Use at least two H3 sub-sections (e.g. "What to Expect on the Day", "Safety Tips and Requirements").

        3.  **MAIN SECTION 2 - Planning Your Experience (400-500 words):**
            - H2 heading: Planning and logistics (best time, how to get there, costs, booking tips).
            - Use at least two H3 sub-sections.

        4.  **MAIN SECTION 3 - Local Tips & Insider Knowledge (300-400 words):**
            - H2 heading: Insider tips and local knowledge for the best experience.
            - Reference {Config.BRAND_NAME} naturally if relevant.

        5.  **PRACTICAL CONCLUSION (150-200 words):**
            - END with actionable next steps and encouraging tone.
            - One natural booking mention: "You can compare operators and book your slot on {Config.BRAND_NAME}."
        """
    return """
        **CONTENT STRUCTURE FOR GENERIC RISHIKESH TRAVEL GUIDE ARTICLE:**
        Write this as a PRACTICAL, USEFUL guide for someone planning to visit Rishikesh.

        1.  **ENGAGING INTRODUCTION (200-250 words):**
            - START with a vivid, specific detail that puts the reader in Rishikesh right now.
            - Include the primary keyword within the first 50 words.

        2.  **MAIN SECTION 1 — What It Is & Why You Should Care (350-450 words):**
            - H2: Explain the specific experience and why it matters for a Rishikesh trip.
            - Use two H3 sub-sections.

        3.  **MAIN SECTION 2 — How To Do It: Practical Step-by-Step Guide (400-500 words):**
            - H2: The practical HOW-TO section. This is the heart of the article.
            - Use a numbered list OR bullet checklist for at least part of this section.
            - Use two H3 sub-sections.

        4.  **MAIN SECTION 3 — Insider Tips & Best Practices (300-400 words):**
            - H2: Insider knowledge that separates experienced travellers from tourists.
            - Optional: seasonal variation.

        5.  **PRACTICAL CONCLUSION (150-200 words):**
            - END with clear, actionable next steps and one key reminder.
            - One optional soft link to a booking platform in conclusion is acceptable.
        """


def _get_seo_requirements(is_brand_article: bool) -> str:
    base_requirements = """
    ╔══════════════════════════════════════════════════════════════════════════════╗
    ║  ABSOLUTE STRICT HTML FORMAT - MUST FOLLOW EXACTLY OR ARTICLE WILL BE REJECTED  ║
    ╚══════════════════════════════════════════════════════════════════════════════╝
    
    You are an **expert HTML developer** who has written thousands of perfectly formatted HTML documents.
    Write this article as if you are coding a production-ready HTML page. Every tag must be syntactically perfect.
    
    **STRICT HTML SYNTAX:** All HTML tags MUST be perfectly formatted.
        - NO Markdown: NEVER use `**` for bolding. Use `<strong>` or `<b>` only.
        - NO Naked Tags: Tag names (like h3, p, li) must NEVER appear as plain text. 
        - Tags MUST be wrapped in brackets (e.g., `<h3>`, NOT `h33` or `h3.`).
        - Every tag MUST have BOTH opening `<` and closing `>` brackets.
    
    ### HEADING HIERARCHY (MANDATORY - NO EXCEPTIONS):
    | Tag   | Usage                                      | Count  |
    |-------|-------------------------------------------|--------|
    | <h1>  | ONLY the main article title               | 1      |
    | <h2>  | Main sections (intro, body sections, FAQ) | 4-5    |
    | <h3>  | Subsections and FAQ questions             | 6-10   |
    
    ### ABSOLUTE TAG SYNTAX RULES:
    1. **ZERO SPACES IN TAGS:**
       ✅ CORRECT: <b>text</b>    <p>content</p>    <h2>heading</h2>
       ❌ WRONG:   < b>text< /b>  < p>content< /p>  <h2 >heading</h2 >
    2. **ALWAYS CLOSE TAGS IMMEDIATELY:**
       ✅ CORRECT: <b>important word</b> rest of sentence
       ❌ WRONG:   <b>important word rest of sentence</b> (closing too late)
    3. **NO NAKED TAG NAMES:**
       ✅ CORRECT: <h3>What Are The Benefits?</h3>
       ❌ WRONG:   h3 What Are The Benefits? h3
    4. **PROPER BOLD/STRONG USAGE:**
        RULE: Only bold SHORT PHRASES (1-5 words MAX). NEVER bold entire sentences or paragraphs!
        RULE: Close the </b> tag IMMEDIATELY after the emphasized word(s)!
       ✅ CORRECT EXAMPLES:
          - "We offer <b>premium quality</b> solutions for your business."
          - "Our <b>expert team</b> provides <b>reliable support</b> for all projects."
          - "Choose <b>{Config.BRAND_NAME}</b> for the best results."
    5. **PARAGRAPH STRUCTURE:**
       ✅ CORRECT: <p>This is a complete paragraph with proper closing.</p>
    6. **LIST FORMATTING:**
       ✅ CORRECT:
       <ul>
           <li>First item</li>
           <li>Second item</li>
       </ul>
    7. **COMPLETE TAG BRACKETS:**
       Every HTML tag MUST have BOTH angle brackets: opening < and closing >
    8. **MANDATORY TAG PAIRING (EVERY OPEN TAG MUST BE CLOSED):**
       CRITICAL: EVERY opening tag MUST have a corresponding closing tag!
       FOR EVERY <strong> YOU WRITE, YOU MUST WRITE </strong>:
       ✅ CORRECT: "We provide <strong>quality</strong> services."
       FOR EVERY <b> YOU WRITE, YOU MUST WRITE </b>:
       ✅ CORRECT: "Our <b>expert team</b> is here to help."
       FOR EVERY <h3> YOU WRITE, YOU MUST WRITE </h3>:
       ✅ CORRECT: "<h3>What Are The Benefits?</h3>"
       
       FAILURE TO CLOSE TAGS WILL CAUSE BOLD OVERFLOW AND IMMEDIATE REJECTION!
    
    ### CONTENT REQUIREMENTS:
    - Use at least 15-20 <p> paragraphs across the article.
    - Include at least two <ul> or <ol> lists with multiple <li> items.
    - Use <b> or <strong> to emphasize key phrases at least 10 times.
    - Use <blockquote> for at least one expert tip or important note.
    - Keyword density: 1.5% to 3.0% without keyword stuffing.
    
    ### BEFORE SUBMITTING - MANDATORY SELF-CHECK:
    □ Every opening/closing tag has BOTH brackets.
    □ Every <b> tag has a matching </b>.
    □ Every <strong> tag has a matching </strong>.
    □ Every <p> tag has a matching </p>.
    □ Every <h2>/<h3>/<li> tag has a matching closed tag.
    □ NO Markdown syntax (**bold**, - bullets, etc.)
    □ NO spaces inside any HTML tags
    """

    if is_brand_article:
        return base_requirements + f"""
        - Mention "{Config.BRAND_NAME}" naturally 4-6 times MAXIMUM.
        - **LOCAL SEO:** Weave "{Config.TARGET_CITY}" into the narrative naturally (4-6 mentions).
        - **NATURAL PHRASES:** Use location phrases like "in {Config.TARGET_CITY}", "near the Ganges".
        - The article must read like a helpful travel guide written by a local expert.
        """
    return base_requirements + f"""
    - **BRAND NEUTRALITY:** You are writing as an independent travel expert.
      Do NOT mention "{Config.BRAND_NAME}" in the article body except optionally in the conclusion. 
    - **FORBIDDEN HEADINGS:** NEVER place the word "{Config.BRAND_NAME}" inside any heading tag.
    - **LOCAL RELEVANCE:** Naturally weave "{Config.TARGET_CITY}" and "{Config.TARGET_STATE}" (5-7 mentions).
    - **Objective Authority:** Write from direct experience and knowledge.
    - **Reader First:** Every sentence should answer a question or solve a problem.
    """


def _get_revision_instruction(reference_text: str) -> str:
    if "PREVIOUS SEO REPORT" in reference_text or "previous attempt scored" in reference_text.lower():
        return """
    > [!IMPORTANT]
    > **CRITICAL REVISION INSTRUCTIONS:**
    > Your previous draft FAILED to meet the SEO criteria. You MUST prioritize fixing the specific issues.
    > 
    > **FAILURES TO ADDRESS:**
    > 1. Look closely at the "Previous attempt scored..." feedback.
    > 2. WORD COUNT: If it was low, you MUST double the length of your H3 sections.
    > 3. KEYWORDS: If missing, ensure each keyword is mentioned at least 3 times.
    > 4. STRUCTURE: Ensure strict adherence to 1 H1, 4+ H2s, and 6+ H3s.
    >
    > DO NOT just regenerate the same content. ACTIVE EXPANSION is required.
    """
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Main Functions
# ─────────────────────────────────────────────────────────────────────────────

def create_content_prompt(
    title: str,
    reference_text: str,
    target_keywords: List[str],
    project_context: str,
    *,
    article_type: str = "generic",
    category: str = "",
    **kwargs
) -> str:
    """
    Creates the main, detailed prompt for generating a full blog article.
    """
    media_assets = kwargs.get("media_assets")
    bucketlistt_cta_url = kwargs.get("bucketlistt_cta_url", "https://www.bucketlistt.com/")
    # Keyword hierarchy variables
    main_keyword = target_keywords[0] if target_keywords else ""
    secondary_str = (
        ", ".join(target_keywords[1:3])
        if len(target_keywords) > 1
        else "(none provided)"
    )
    additional_str = (
        ", ".join(target_keywords[3:6])
        if len(target_keywords) > 3
        else "(none provided)"
    )

    is_brand_article = article_type.lower() == "brand"

    role_context = (
        f"You are writing for {Config.BRAND_NAME}."
        if is_brand_article
        else (f"You are writing as a travel expert for {Config.BRAND_NAME}, a booking platform. "
              f"Mention {Config.BRAND_NAME} naturally 2-3 times as where readers can compare and book.")
    )

    return f"""
    You are an elite travel writer and SEO expert with 15+ years of experience writing for top-tier travel publications.
    {role_context}
    Your goal is to generate a deeply researched, highly engaging, and perfectly optimized travel article that ranks #1.
    
    ### [STRICT SEO COMPLIANCE COMMANDS]
    | Metric | Requirement |
    | :--- | :--- |
    | **Keyword Usage** | EXACT MATCH REQUIRED: You MUST use exact keywords at least 2 times each. |
    | **Keyword Density** | Overall primary keyword density must be between 2.0% - 6.0%. |
    | **Word Count** | STRICTLY between {Config.MIN_WORD_COUNT} and {Config.MAX_WORD_COUNT} words. DO NOT EXCEED {Config.MAX_WORD_COUNT}! |
    | **Title SEO** | Title MUST include at least one Primary Keyword. |
    | **Brand Neutrality** | {'If this is an objective/generic guide, DO NOT include brand in headings.' if not is_brand_article else 'Natural integration allowed.'} |
    | **Location Density** | **STRICT MENTION COUNT:** You MUST mention '{Config.TARGET_CITY}' exactly between 4 and 8 times TOTAL. |
    | **Location Booster** | Mention '{Config.TARGET_CITY}' with at least 4 *differently worded* phrasings (e.g. "in {Config.TARGET_CITY}", "a trip to {Config.TARGET_CITY}", "exploring {Config.TARGET_CITY}") — never the same phrase twice. |
    | **Structure** | 1 H1, at least 4 H2s, at least 2 H3s under EVERY H2. |
    | **Meta Data** | Meta Title: 50-65 chars. Meta Desc: 120-155 chars (no quotes). |
    | **LANGUAGE** | **MUST be in English ONLY.** |

    {_get_revision_instruction(reference_text)}

    {_get_human_voice_block()}

    {_get_content_requirements(is_brand_article, category)}

    **ARTICLE SPECIFICATIONS:**
    - **Title:** {title}
    - **Main Keyword:** {main_keyword}
    - **Secondary Keywords:** {secondary_str}
    - **Additional Keywords:** {additional_str}
    - **Article Type:** {'Brand-Specific' if is_brand_article else 'Industry-Generic'}
    {f"- **Category:** {category}" if category else ""}
    - **CONTEXT:** {project_context}

    {_get_keyword_hierarchy_block(main_keyword, secondary_str, additional_str)}

    {IMAGE_FIRST_BLOCK}

    {LINK_PLACEMENT_BLOCK}

    {_get_partner_brand_block(category, bucketlistt_cta_url)}

    {_get_authoritative_citation_block()}

    {_get_media_injection_block(media_assets)}

    {_get_serp_dominance_block(main_keyword, category)}

    {_get_faq_block(main_keyword)}

    {_get_conclusion_cta_block(is_brand_article, bucketlistt_cta_url)}
    
    {_get_title_instruction(title, category)}
    
    {_get_content_structure(is_brand_article)}
    
    {_get_seo_requirements(is_brand_article)}
    
    **REVISION MATERIALS (for reference only):**
    === BEGIN REVISION MATERIALS ===
    {reference_text}
    === END REVISION MATERIALS ===

    {REJECTION_CRITERIA}

    {EXACT_OUTPUT_FORMAT}
    """


def create_humanize_prompt(content_html: str, target_keywords: List[str]) -> str:
    """
    Creates a prompt for a second pass that rewrites already-finished, SEO-passing
    article HTML for more natural sentence-length variation and less predictable,
    stock phrasing, without touching anything downstream systems depend on:
    heading text, hyperlinks, or keyword presence. The rewrite is verified against
    the original by a structural check after this call — this prompt's job is just
    to make that check likely to pass while genuinely varying the prose.
    """
    keywords_str = ", ".join(target_keywords) if target_keywords else "(none provided)"
    return f"""
    You are a human copy editor doing a final polish pass on a travel article that has
    already been approved for publication. Your ONLY job is to make the prose read more
    naturally human-written. Do not change facts, meaning, structure, or SEO elements.

    **STRICT PRESERVATION RULES (breaking any of these fails the edit):**
    - Do NOT change any heading text: every <h1>, <h2>, <h3> must be word-for-word identical.
    - Do NOT change, remove, or add any <a href="..."> link — every link's href and position
      must stay exactly as-is. You may lightly reword the visible anchor text only if the
      surrounding sentence needs it, but never touch the href attribute.
    - Do NOT add, remove, merge, or reorder <p>, <ul>, <ol>, <li> elements — same count, same order.
    - Do NOT drop any of these keywords — every one must still appear at least once,
      naturally, somewhere in the text: {keywords_str}
    - Do NOT change overall word count by more than ~10%.
    - Keep the exact same HTML tag structure. Only the wording INSIDE tags may change.

    **WHAT TO ACTUALLY EDIT:**
    - Vary sentence length within paragraphs — break up runs of similarly-sized sentences,
      mix in a short sentence after a long one, the way a human editor tightens copy.
    - Replace any leftover stiff/formal phrasing with how a real travel writer would say it.
    - Remove these overused AI-writing words if present, replacing with plain language:
      delve, moreover, furthermore, additionally, leverage, utilize, seamless(ly), robust,
      boast, tapestry, realm, landscape (as metaphor), underscore, testament to, embark on,
      navigate the complexities, unlock, unleash, elevate, game-changer, cutting-edge.
    - Vary paragraph opening patterns — no two consecutive paragraphs should start the same way.

    **ARTICLE HTML TO EDIT:**
    {content_html}

    **OUTPUT FORMAT:**
    Return ONLY the complete, edited HTML. No commentary, no markdown code fences,
    no explanation before or after. Start directly with the opening tag.
    """


def create_keyword_extraction_prompt(text_chunk: str, num_keywords: int) -> str:
    """
    Creates a prompt for extracting high-value SEO keywords from a raw text chunk.
    """
    return f"""
    You are an expert SEO Strategist and Travel Writer specializing in {Config.INDUSTRY_NAME}. 
    Analyze the following text scraped from a competitor's post and extract the top {num_keywords} keywords.

    **CRITERIA:**
    1. **Relevance:** Must be highly relevant to {Config.INDUSTRY_NAME} and the content.
    2. **Specificity:** Prefer specific phrases over generic single words.
    3. **Value:** Focus on keywords that would drive qualified traffic.
    4. **Language:** Output must be in English ONLY.
    5. **Format:** Return ONLY a comma-separated list of keywords.

    **TEXT TO ANALYZE:**
    {text_chunk[:3000]}

    **OUTPUT:**
    """


def create_keyword_generation_prompt(text_chunk: str, num_keywords: int) -> str:
    """
    Creates a prompt to GENERATE missing keywords based on the article's topic.
    """
    return f"""
    You are an expert SEO Strategist and Travel Writer specializing in {Config.INDUSTRY_NAME}.
    The following text is a blog article. We extracted some keywords, but found too few.
    
    **TASK:**
    Generate {num_keywords} *additional* high-value SEO keywords.

    **CRITERIA:**
    1. **Relevance:** Must fit the article's theme.
    2. **Specificity:** Use long-tail keywords where possible.
    3. **Value:** Commercial or informational intent.
    4. **Language:** Output must be in English ONLY.
    5. **Format:** Return ONLY a comma-separated list.

    **ARTICLE CONTENT (Snippet):**
    {text_chunk[:2000]}

    **OUTPUT:**
    """


def create_raw_content_prompt(
    title: str,
    reference_text: str,
    target_keywords: List[str],
    project_context: str,
    *,
    article_type: str = "generic",
    category: str = ""
) -> str:
    """
    Creates a prompt for generating raw article content without HTML formatting.
    This is Step 1 of the two-step article generation process.
    """
    # For now, modify the existing prompt to output plain text
    base_prompt = create_content_prompt(
        title=title,
        reference_text=reference_text,
        target_keywords=target_keywords,
        project_context=project_context,
        article_type=article_type,
        category=category,
    )
    # Replace HTML instructions with plain text instructions
    return base_prompt.replace("HTML", "PLAIN TEXT")


def create_html_conversion_prompt(raw_content: str, *, article_type: str = "generic") -> str:
    """
    Creates a prompt for converting raw content to HTML.
    This is Step 2 - uses FIXED 0.1 temperature
    """
    _ = article_type  # Unused argument
    return f"""Convert the following plain text article to properly formatted HTML.
Use <h1>, <h2>, <h3>, <p>, <ul>, <li>, <b>, <strong> tags appropriately.
NO spaces in tags. Every tag must be properly closed.

{raw_content}
"""

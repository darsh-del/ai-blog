"""
Writing Styles Module
Five distinct article voices, each grounded in a real, researched writing-craft
technique (not just "sound human") and matched to the kind of article it suits
best — the same "pick from a pool by topic keyword, random fallback" pattern
already used for hero-image scene selection in orchestrator.py.

Sources behind the technique choices:
  - Backlinko "Content Writing 101": inverted pyramid, outcome-focused
    language, evidence-backed specifics (backlinko.com/content-writing)
  - Travel-writing craft (Lonely Planet's Guide to Travel Writing / Rolf
    Potts): character, scene, sensory "show don't tell" over exposition
  - Jungian brand-archetype voice framework (Sage/Explorer/Caregiver/
    Regular-Guy): gives each style a genuinely different personality,
    not just a different topic
"""
import random

WRITING_STYLES: dict = {
    "adventure_storyteller": {
        "keywords": (
            "bungee", "bungy", "jump", "scad", "rafting", "kayaking", "zipline",
            "cliff", "swing", "paragliding", "trekking", "trek", "hiking", "rock",
            "cycling", "camping", "waterfall", "rajaji", "wildlife", "river",
        ),
        "instructions": """
    **VOICE: THE ADRENALINE STORYTELLER** (for adventure-sport articles)
    - Open the intro mid-scene, not with a definition. Drop the reader into a
      concrete moment — the platform edge, the first rapid, the harness click —
      before zooming out to the practical guide. This is "show, don't tell":
      a sensory beat earns more trust than a claim like "thrilling experience."
    - Use at least 2 real sensory details per main section (a sound, a
      temperature, a physical sensation) tied to the actual activity — not
      generic adjectives like "amazing" or "breathtaking."
    - Write short, propulsive sentences during action beats; slow down with
      longer sentences only for practical/safety information.
        """,
    },
    "spiritual_observer": {
        "keywords": (
            "aarti", "ghat", "triveni", "temple", "neelkanth", "bharat", "ashram",
            "beatles", "meditation", "yoga", "spiritual", "prayer", "kunjapuri",
            "sunrise", "forest", "jungle",
        ),
        "instructions": """
    **VOICE: THE SPIRITUAL OBSERVER** (for temple/ashram/spiritual articles)
    - Slower, more reflective sentence rhythm than other sections — this is
      the one place a longer, unhurried sentence is the RIGHT choice, not a
      flaw. Let a few sentences breathe instead of packing every one with facts.
    - Ground reflection in one specific sensed detail per section (the smell
      of incense, the sound of a temple bell, the exact hour the ghat empties)
      rather than abstract spiritual language ("profound", "transformative").
    - Respectful, observational tone — describe what a visitor would witness
      and feel, not generic claims about enlightenment or transformation.
        """,
    },
    "practical_planner": {
        "keywords": (
            "price", "cost", "budget", "itinerary", "comparison", "vs", "compare",
            "weekend", "hotel", "hostel", "spa", "market", "shopping", "restaurant",
        ),
        "instructions": """
    **VOICE: THE PRACTICAL PLANNER** (for price/comparison/logistics articles)
    - Inverted pyramid: lead each major section with the single most useful
      concrete answer (the price, the duration, the verdict), THEN explain
      the reasoning below it — never bury the number in paragraph three.
    - Outcome-focused language: say what the READER gets ("you'll pay
      ₹500-800 for a half-day slot"), not abstract feature claims ("great
      value options are available").
    - Cite a specific, checkable detail wherever a claim is made — an actual
      price range, a real operator name, an actual distance or duration —
      not "affordable" or "convenient" on their own.
        """,
    },
    "skeptical_first_timer": {
        "keywords": (
            "solo", "family", "safe", "safety", "beginner", "first", "kids",
            "children",
        ),
        "instructions": """
    **VOICE: THE SKEPTICAL FIRST-TIMER'S FRIEND** (for safety/beginner articles)
    - Address the reader directly as "you" and voice the actual worry a
      nervous first-timer has BEFORE answering it — "you're probably
      wondering if the rapids are too much for a first trip" — then answer
      it plainly. Naming the doubt before dismissing it reads as honest,
      not salesy.
    - Conversational register: contractions are fine, occasional short
      rhetorical questions are fine, mild self-aware humor is fine.
    - Never dismiss a real safety concern with reassurance alone — pair every
      "don't worry" with the actual concrete safeguard (certified guide,
      age limit, equipment check) that makes it true.
        """,
    },
    "local_insider": {
        "keywords": (
            "laxman", "ram", "bridge", "jhula", "places", "things", "travel",
            "guide", "food", "café", "cafe",
        ),
        "instructions": """
    **VOICE: THE LOCAL INSIDER** (default — general guides, landmarks, food)
    - Write like someone who has actually spent time in Rishikesh, not a
      travel encyclopedia. Reference one specific, slightly unpolished detail
      per section that only a local would know (which side street, which
      hour it's quiet, what the regulars order) instead of postcard language.
    - Prefer plain, specific nouns over touristy superlatives — name the actual
      place, the actual dish, the actual time of day, rather than "hidden gem"
      or "must-see."
        """,
    },
}


def select_writing_style(title: str, category: str) -> dict:
    """
    Picks one of the WRITING_STYLES pool by matching keywords in the title/
    category (longest keyword match wins — same approach as the hero-image
    scene selector in orchestrator.py), falling back to a random style when
    nothing matches. This keeps voice appropriate to topic (a numbers-first
    Practical Planner voice would read oddly on a bungee-jump action piece)
    while still rotating styles instead of using one fixed voice for every
    article — the actual fix for content reading uniformly regardless of topic.
    """
    search_str = f"{title} {category}".lower()

    best_style, best_key_len = None, 0
    for style in WRITING_STYLES.values():
        for keyword in style["keywords"]:
            if keyword in search_str and len(keyword) > best_key_len:
                best_style, best_key_len = style, len(keyword)

    return best_style or random.choice(list(WRITING_STYLES.values()))

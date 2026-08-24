"""
Unified Test Suite for AI Blog Generator (Bucketlistt)
======================================================
Consolidates all essential unit tests across:
  - Configuration & Directory Management
  - Data & Pydantic Models Validation
  - Link Sanitizer & Soft-404 Auto-Healing
  - Linking Manager & Contextual Anchors
  - SEO Auto-Healer Rules
  - Email Service, DOCX & SMTP Packaging
  - Concurrency Safety & Thread Synchronization
  - Agent Content Generation & Fallback Templates
  - WordPress Publisher Integration
"""

import json
import logging
import os
import random
import threading
import time
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from src.agents import ContentGeneratorAgent, SlugRegistry, TitleManager
from src.concurrent_manager import ConcurrentCampaignManager
from src.config import Config
from src.models import ArticleDraft, InternalLink, LLMConfig, Metadata, SEOMetric, SEOReport
from src.publishers.wordpress import WordPressPublisher
from src.services.email_service import EmailService, _parse_email_list
from src.services.link_sanitizer import LinkSanitizer
from src.services.linking_manager import LinkingManager
from src.services.orchestrator import BlogGeneratorOrchestrator
from src.services.seo_auto_healer import SEOAutoHealer

_VALID_DESC = (
    "Explore Rishikesh rafting and bungee jumping with Bucketlistt. "
    "Find verified packages, prices, safety rules, and insider travel tips."
)


# ==============================================================================
# 1. CONFIGURATION TESTS
# ==============================================================================

def test_config_defaults() -> None:
    """Verify that default settings load correctly and types match."""
    assert Config.BASE_DIR is not None
    assert Config.CSV_PATH is not None
    assert isinstance(Config.BRAND_MENTION_RATIO, float)
    # TARGET_CITY has no fixed default (falls back to the "your_city" placeholder
    # when unset) — it's env-driven, not a constant, so just assert it loaded as a
    # non-empty string rather than asserting a specific deployment's city name.
    assert isinstance(Config.TARGET_CITY, str) and Config.TARGET_CITY


@patch('os.makedirs')
def test_ensure_directories(mock_makedirs: MagicMock) -> None:
    """Verify that ensure_directories triggers directory creation."""
    Config.ensure_directories()
    assert mock_makedirs.call_count >= 1


# ==============================================================================
# 2. DATA MODELS & VALIDATION TESTS
# ==============================================================================

def test_metadata_validation() -> None:
    """Verify that Metadata initializes correctly with valid constraints."""
    meta = Metadata(
        title="Valid Title Under 60 Chars",
        description=_VALID_DESC,
        focus_keyword="rafting",
        url_slug="valid-slug",
        canonical_url="https://www.bucketlistt.com/rishikesh/river-rafting",
        keywords=["rafting", "rishikesh"],
        json_ld_schema={}
    )
    assert meta.title == "Valid Title Under 60 Chars"
    assert meta.url_slug == "valid-slug"


def test_article_draft_word_count_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Verify that ArticleDraft logs a warning when word count is outside optimal range."""
    meta = Metadata(
        title="Valid Title",
        description=_VALID_DESC,
        focus_keyword="keyword",
        url_slug="valid-slug",
        canonical_url="https://www.bucketlistt.com/",
        keywords=["test"],
        json_ld_schema={}
    )
    with caplog.at_level(logging.WARNING):
        draft = ArticleDraft(
            title="Short Title",
            content_html="<p>Test</p>",
            word_count=50,
            metadata=meta,
            faq_section="<p>FAQ</p>"
        )
    assert draft.word_count == 50
    assert any("Word count" in record.message for record in caplog.records)


def test_seo_report_score_clamping() -> None:
    """Verify that overall_score in SEOReport is clamped correctly between 0 and 100."""
    report = SEOReport(
        overall_score=150,
        metrics=[SEOMetric(name="SEO", score=100, weight=1, max_score=100, feedback="Good")],
        passed=True,
        improvement_suggestions=[],
        iteration_number=1
    )
    assert report.overall_score == 100


# ==============================================================================
# 3. LINK SANITIZER & SOFT-404 AUTO-HEALING TESTS
# ==============================================================================

# ponytail: the correct "bungee" landing URL is a content decision that lives in
# data/config/sitemap_mapping.json, not a fact this test suite should hardcode a second
# copy of. Deriving it via find_best_matching_url() means these tests assert the real
# contract — "a dead link gets healed to whatever the config says is canonical" — and
# won't go stale again the next time that config legitimately changes.
def test_link_sanitizer_replaces_dead_domains() -> None:
    """Verify that dead external domains are auto-healed into verified live URLs."""
    html_input = (
        '<p>Check out <a href="https://placesinrishikesh.com/river-rafting">river rafting</a> '
        'and <a href="https://your-website.com/blog/bungee">bungee jumping</a> in Rishikesh.</p>'
    )
    expected_bungee_url = LinkSanitizer.find_best_matching_url(
        "bungee jumping", "https://your-website.com/blog/bungee"
    )
    # Sanity-check the resolver itself, not just that sanitize_html agrees with it —
    # otherwise this assertion would just be comparing the function to itself.
    assert "bungee" in expected_bungee_url.lower(), (
        "find_best_matching_url() no longer resolves 'bungee jumping' to a bungee URL "
        "— check the 'bungee' activity keywords in data/config/sitemap_mapping.json."
    )
    sanitized = LinkSanitizer.sanitize_html(html_input)
    assert "placesinrishikesh.com" not in sanitized
    assert "your-website.com" not in sanitized
    assert "https://www.bucketlistt.com/rishikesh/river-rafting" in sanitized
    assert expected_bungee_url in sanitized


def test_link_sanitizer_replaces_unverified_bucketlistt_subpaths() -> None:
    """Verify that unverified 404 paths and dead blog slugs are auto-healed."""
    html_input = (
        '<p>Read our <a href="https://www.bucketlistt.com/best-hotels-hostels-in-rishikeshurlslug">Rishikesh stay guide</a> '
        'and <a href="https://www.bucketlistt.com/bungee-jumping">Bungee Jumping</a> before booking.</p>'
    )
    expected_bungee_url = LinkSanitizer.find_best_matching_url(
        "Bungee Jumping", "https://www.bucketlistt.com/bungee-jumping"
    )
    assert "bungee" in expected_bungee_url.lower(), (
        "find_best_matching_url() no longer resolves 'Bungee Jumping' to a bungee URL "
        "— check the 'bungee' activity keywords in data/config/sitemap_mapping.json."
    )
    sanitized = LinkSanitizer.sanitize_html(html_input)
    assert "https://www.bucketlistt.com/best-hotels-hostels-in-rishikeshurlslug" not in sanitized
    assert "https://www.bucketlistt.com/bungee-jumping" not in sanitized
    assert expected_bungee_url in sanitized


def test_link_sanitizer_preserves_verified_urls() -> None:
    """Verify that verified live URLs in sitemap_mapping.json remain untouched."""
    valid_url = "https://www.bucketlistt.com/rishikesh/river-rafting"
    valid_url2 = "https://www.bucketlistt.com/safety-guidelines"
    html_input = f'<p>Book <a href="{valid_url}">Rafting</a> today and check <a href="{valid_url2}">Safety Guidelines</a>!</p>'
    sanitized = LinkSanitizer.sanitize_html(html_input)
    assert valid_url in sanitized
    assert valid_url2 in sanitized


def test_link_sanitizer_preserves_trusted_external_citation() -> None:
    """The E-E-A-T authoritative-citation allowlist must survive sanitization
    unrewritten, while a random/hallucinated external domain still gets healed."""
    html_input = (
        '<p>See the <a href="https://uttarakhandtourism.gov.in">Uttarakhand Tourism Board</a> '
        'and the <a href="https://mausam.imd.gov.in/dehradun/">IMD Dehradun forecast</a> for details, '
        'not <a href="https://some-random-blog.example">this random blog</a>.</p>'
    )
    sanitized = LinkSanitizer.sanitize_html(html_input)
    assert "https://uttarakhandtourism.gov.in" in sanitized
    assert "https://mausam.imd.gov.in/dehradun/" in sanitized
    assert "some-random-blog.example" not in sanitized


# ==============================================================================
# 4. LINKING MANAGER & CONTEXTUAL CTA TESTS
# ==============================================================================

def test_linking_manager_injects_anchors_and_cta() -> None:
    """Verify that LinkingManager injects contextual activity anchors and a high-converting CTA widget."""
    meta = Metadata(
        title="River Rafting in Rishikesh 2026 Guide",
        description=_VALID_DESC,
        focus_keyword="rafting",
        url_slug="river-rafting-rishikesh-guide",
        canonical_url="https://www.bucketlistt.com/rishikesh/river-rafting",
        keywords=["rafting", "rishikesh"],
        json_ld_schema={}
    )
    article = ArticleDraft(
        title="River Rafting in Rishikesh 2026 Guide",
        content_html=(
            "<h1>River Rafting in Rishikesh 2026 Guide</h1>"
            "<p>Rishikesh is world-famous for white-water rafting and thrilling bungee jumping off high cliffs.</p>"
            "<h2>Choosing the Right Stretch</h2>"
            "<p>The 16 km stretch from Shivpuri offers Grade III rapids. Prepare well for river rafting.</p>"
        ),
        word_count=200,
        metadata=meta,
        faq_section="<h2>FAQ</h2>"
    )
    injected_html = LinkingManager.inject_bucketlistt_links(article)
    assert "bucketlistt.com/rishikesh/river-rafting" in injected_html or "bucketlistt.com/rishikesh/bungee-jumping" in injected_html
    assert 'class="bucketlistt-cta-box"' in injected_html or 'Book' in injected_html


# ==============================================================================
# 5. SEO AUTO-HEALER TESTS
# ==============================================================================

@pytest.fixture
def low_score_article() -> ArticleDraft:
    """Fixture providing a draft article with sub-optimal SEO metrics."""
    meta = Metadata(
        title="Short Title",
        description=_VALID_DESC,
        focus_keyword="",
        url_slug="short-title",
        canonical_url="https://www.bucketlistt.com/short-title",
        keywords=["trekking", "adventure"],
        json_ld_schema={}
    )
    return ArticleDraft(
        title="Short Title",
        content_html="<h1>Short Title</h1><p>This is a short post about trekking.</p>",
        word_count=6,
        metadata=meta,
        faq_section="<div class='faq-section'><h3>Q1?</h3><p>A1</p></div>"
    )


def test_seo_auto_healer_optimizes_metadata(low_score_article: ArticleDraft) -> None:
    """Verify that title length, meta description, and focus keywords are auto-healed."""
    # SEOAutoHealer reads Config.TARGET_CITY to inject the city name into the title —
    # pin it so this test doesn't depend on a real .env being present (CI has none).
    with patch('src.services.seo_auto_healer.Config.TARGET_CITY', 'Rishikesh'):
        healed = SEOAutoHealer.heal(low_score_article, ["trekking", "adventure"])
    assert 40 <= len(healed.metadata.title) <= 65
    assert "Rishikesh" in healed.metadata.title
    assert 120 <= len(healed.metadata.description) <= 155
    assert healed.metadata.focus_keyword == "trekking"


# ==============================================================================
# 6. EMAIL SERVICE & DELIVERY TESTS
# ==============================================================================

def test_email_service_helpers() -> None:
    """Verify that email list parser and HTML builder work accurately."""
    res = _parse_email_list("user1@example.com; user2@example.com, user3@example.com <user4@example.com>")
    assert res == ["user1@example.com", "user2@example.com", "user3@example.com", "user4@example.com"]

    service = EmailService()
    assert service.send_articles_set([]) == "failed"

    mock_articles = [
        {"title": "Unforgettable Trekking in Rishikesh", "score": 92, "word_count": 1450, "type": "Industry-Generic"},
        {"title": "Top 10 Rafting Spots", "score": 88, "word_count": 1100, "type": "Brand-Specific"}
    ]
    html = service.build_html_body(mock_articles)
    assert "Unforgettable Trekking in Rishikesh" in html
    assert "92/100" in html
    assert "1450" in html


@patch('smtplib.SMTP')
def test_send_smtp_email_with_cc(mock_smtp_cls: MagicMock) -> None:
    """Verify that SMTP delivery handles both TO and CC recipient routing."""
    service = EmailService()
    mock_articles = [{"title": "Test CC Article", "score": 90, "word_count": 1200}]
    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    with patch.object(Config, 'SMTP_USERNAME', 'sender@example.com'), \
         patch.object(Config, 'SMTP_PASSWORD', 'secret'), \
         patch.object(Config, 'SMTP_TO', 'to1@example.com, to2@example.com'), \
         patch.object(Config, 'SMTP_CC', 'cc1@example.com; cc2@example.com'):
        status = service.send_articles_set(mock_articles)

    assert status == "sent"
    assert mock_server.sendmail.called
    sender, recipients, _ = mock_server.sendmail.mock_calls[0].args
    assert set(recipients) == {"to1@example.com", "to2@example.com", "cc1@example.com", "cc2@example.com"}


@patch('smtplib.SMTP')
def test_send_error_alert_sends_and_throttles(mock_smtp_cls: MagicMock) -> None:
    """Verify alert emails go to ALERT_EMAIL_TO and repeat alerts are cooldown-throttled."""
    from src.services import alert_service

    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server
    alert_service._last_alert_sent.clear()  # pylint: disable=protected-access

    with patch.object(Config, 'SMTP_USERNAME', 'sender@example.com'), \
         patch.object(Config, 'SMTP_PASSWORD', 'secret'), \
         patch.object(Config, 'ALERT_EMAIL_TO', 'ops1@example.com, ops2@example.com'):
        alert_service.send_error_alert("test_key", "Something broke", "details here")
        alert_service.send_error_alert("test_key", "Something broke again", "details here")  # throttled

    assert mock_server.sendmail.call_count == 1  # second call suppressed by cooldown
    sender, recipients, _ = mock_server.sendmail.mock_calls[0].args
    assert sender == 'sender@example.com'
    assert recipients == ['ops1@example.com', 'ops2@example.com']


# ==============================================================================
# 7. CONCURRENCY SAFETY & THREAD SYNCHRONIZATION TESTS
# ==============================================================================

def test_title_manager_concurrency_safety(tmp_path) -> None:
    """Verify high-frequency multithreaded operations on TitleManager cause no collisions."""
    csv_file = os.path.join(tmp_path, "used_titles.csv")
    title_manager = TitleManager(csv_path=csv_file)
    num_threads = 6
    ops_per_thread = 50
    errors = []

    def worker(tid: int):
        try:
            for i in range(ops_per_thread):
                title = f"Title {tid} variation {i} Discover ultimate"
                if i % 2 == 0:
                    title_manager.save_used_title(title)
                else:
                    title_manager.is_title_used(title)
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrency errors in TitleManager: {errors}"


def test_slug_registry_concurrency_safety(tmp_path) -> None:
    """Verify high-frequency multithreaded operations on SlugRegistry cause no collisions."""
    csv_file = os.path.join(tmp_path, "articles.csv")
    slug_registry = SlugRegistry(csv_path=csv_file)
    num_threads = 6
    ops_per_thread = 50
    errors = []

    def worker(tid: int):
        try:
            for i in range(ops_per_thread):
                title = f"Unveiling Rishikesh Adventure Thread {tid} Item {i}"
                slug = slug_registry.generate_unique_slug(title)
                if i % 2 == 0:
                    slug_registry.register(slug)
                else:
                    slug_registry.is_slug_available(slug)
                time.sleep(0.001)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrency errors in SlugRegistry: {errors}"


# ==============================================================================
# 8. CONCURRENT CAMPAIGN MANAGER TESTS
# ==============================================================================

def test_concurrent_campaign_worker() -> None:
    """Verify that ConcurrentCampaignManager worker accumulates and processes results."""
    mock_orchestrator = MagicMock()
    mock_article = MagicMock()
    mock_article.title = "Mocked Title"
    mock_article.word_count = 1000
    mock_article.token_usage = {"total_tokens": 150}
    mock_article.cost = 0.0001
    mock_article.useful_tokens = {"total_tokens": 150}
    mock_article.useful_cost = 0.0001
    mock_article.image_path = "path/to/img.png"
    mock_article.is_published = True

    mock_report = MagicMock()
    mock_report.overall_score = 92

    mock_orchestrator.generate_blog.return_value = (mock_article, mock_report, {"product_name": "Rafting"})

    manager = ConcurrentCampaignManager(orchestrator=mock_orchestrator)
    result = manager._generate_article_worker("brand", 1)

    assert result["status"] == "success"
    assert result["title"] == "Mocked Title"
    assert result["score"] == 92
    assert result["is_published"] is True


# ==============================================================================
# 9. AGENT GENERATOR & OFFLINE TEMPLATE TESTS
# ==============================================================================

@patch('src.agents.call_llm')
@patch('src.config.Config.GOOGLE_AI_STUDIO_API_KEY', 'test_key')
def test_generate_titles_success(mock_call: MagicMock) -> None:
    """Verify title generation parses clean title candidates."""
    with patch('src.agents.TitleManager') as mock_tm, patch('src.agents.SlugRegistry') as mock_sr:
        tm = MagicMock()
        tm.is_title_used.return_value = False
        mock_tm.return_value = tm
        sr = MagicMock()
        sr.generate_unique_slug.return_value = "test-slug"
        sr.is_slug_available.return_value = True
        mock_sr.return_value = sr

        agent = ContentGeneratorAgent(model_name="anthropic/claude-haiku-4-5-20251001")
        mock_call.return_value = "1. \"First Generated Title\"\n2. *Second Generated Title*"
        titles = agent.generate_titles(num=2)
        assert len(titles) == 2
        assert "First Generated Title" in titles


def test_offline_fallback_article_generation() -> None:
    """Verify offline fallback template creates structured articles when LLM is unavailable."""
    with patch('src.agents.TitleManager'), patch('src.agents.SlugRegistry'):
        agent = ContentGeneratorAgent(model_name="anthropic/claude-haiku-4-5-20251001")
        fallback = agent._create_fallback_article(
            title="Bungee Jumping in Rishikesh",
            keywords=["bungee jumping", "adventure"],
            article_type="brand",
            category="Bungee Jumping"
        )
        assert isinstance(fallback, ArticleDraft)
        assert "Bungee Jumping Overview" in fallback.content_html
        assert fallback.word_count > 100


def test_byline_injected_after_h1_and_matches_schema_author() -> None:
    """E-E-A-T: the visible byline and the JSON-LD author must agree, since Google
    cross-checks structured data against what's actually visible on the page. With
    a persona configured, both must name that real person; the fallback article's
    JSON-LD must match too."""
    with patch('src.agents.TitleManager'), patch('src.agents.SlugRegistry'):
        agent = ContentGeneratorAgent(model_name="anthropic/claude-haiku-4-5-20251001")
        persona = {"name": "Aditi Rawat", "job_title": "Senior Travel Writer"}

        html = "<h1>Test Title</h1><p>Body text.</p>"
        injected = agent._inject_byline_and_disclosure(html, persona)
        assert injected.index("</h1>") < injected.index("Aditi Rawat")
        assert "AI research assistance" in injected

        schema = agent._generate_default_schema("Test Title", _VALID_DESC, author=persona)
        assert schema["author"]["@type"] == "Person"
        assert schema["author"]["name"] == "Aditi Rawat"
        assert schema["author"]["jobTitle"] == "Senior Travel Writer"


def test_byline_falls_back_to_organization_without_persona() -> None:
    """No AUTHOR_PERSONAS configured yet (data/config/authors.json is empty) must
    still produce an honest team-credited byline, never a fabricated name, and the
    schema must fall back to the same Organization type as before this change."""
    with patch('src.agents.TitleManager'), patch('src.agents.SlugRegistry'):
        agent = ContentGeneratorAgent(model_name="anthropic/claude-haiku-4-5-20251001")

        html = "<h1>Test Title</h1><p>Body text.</p>"
        injected = agent._inject_byline_and_disclosure(html, None)
        assert f"{Config.BRAND_NAME} Travel Team" in injected

        schema = agent._generate_default_schema("Test Title", _VALID_DESC, author=None)
        assert schema["author"] == {"@type": "Organization", "name": Config.BRAND_NAME}


def test_byline_inserts_after_existing_updated_date_line() -> None:
    """When the LLM already added its own "Updated: ..." post-meta paragraph right
    after the H1, the byline must land after it, not split the two apart."""
    with patch('src.agents.TitleManager'), patch('src.agents.SlugRegistry'):
        agent = ContentGeneratorAgent(model_name="anthropic/claude-haiku-4-5-20251001")
        html = (
            '<h1>Test Title</h1>'
            '<p class="post-meta"><em>Updated: January 2026</em></p>'
            '<p>Body text.</p>'
        )
        injected = agent._inject_byline_and_disclosure(html, None)
        assert injected.index("Updated: January 2026") < injected.index("Travel Team")
        assert injected.index("Travel Team") < injected.index("Body text")


def test_fallback_title_does_not_double_city_name(tmp_path) -> None:
    """Regression test: category strings are stored as "X in <City>" (e.g. "River
    Rafting in Rishikesh"), but the fallback title templates also append "{city}"
    themselves. Without stripping the redundant city first, this produced titles
    like "Best River Rafting in Rishikesh in Rishikesh — Complete 2026 Guide"
    (seen live in a real generated/emailed article)."""
    with patch('src.agents.SlugRegistry'), patch('src.config.Config.TARGET_CITY', 'Rishikesh'):
        agent = ContentGeneratorAgent(model_name="anthropic/claude-haiku-4-5-20251001")
        agent.title_manager = TitleManager(csv_path=str(tmp_path / "used_titles.csv"))

        titles = agent._generate_fallback_titles(num=5, category="River Rafting in Rishikesh")

        assert titles, "Fallback generator produced no titles"
        for title in titles:
            assert "rishikesh in rishikesh" not in title.lower(), title


def test_duplicate_llm_h1_falls_back_to_deduped_title(tmp_path) -> None:
    """Regression test: two runs with different (already-deduped) seed titles
    must not publish the same article heading just because the LLM wrote the
    same <h1> both times (this is how "Best River Rafting in Rishikesh —
    Complete 2026 Guide" got published 4x — the LLM's own H1 was trusted
    without re-checking it against TitleManager)."""
    with patch('src.agents.SlugRegistry') as mock_sr:
        sr = MagicMock()
        sr.generate_unique_slug.return_value = "test-slug"
        sr.is_slug_available.return_value = True
        mock_sr.return_value = sr

        agent = ContentGeneratorAgent(model_name="anthropic/claude-haiku-4-5-20251001")
        # Isolate from the real used_titles.csv on disk.
        agent.title_manager = TitleManager(csv_path=str(tmp_path / "used_titles.csv"))

        # A synthetic heading guaranteed not to already exist in the real
        # articles.csv/used_titles.csv on disk (TitleManager loads both).
        duplicate_h1 = "Zzq Test Regression Heading For Dedup Guard 42"
        content = (
            f"<h1>{duplicate_h1}</h1><p>Body about rafting.</p>"
            "FAQ_SECTION:<p>Q&A</p>JSON_LD_SCHEMA:{}"
        )

        draft1 = agent._parse_article_response(content, title="Seed Title A", target_keywords=["rafting"])
        draft2 = agent._parse_article_response(content, title="Seed Title B", target_keywords=["rafting"])

        assert draft1.title == duplicate_h1
        # Second run must not silently republish the same heading.
        assert draft2.title == "Seed Title B"
        assert draft2.title != draft1.title
        assert "<h1>Seed Title B</h1>" in draft2.content_html


# ==============================================================================
# 10. WORDPRESS PUBLISHER TESTS
# ==============================================================================

@patch('requests.Session.post')
@patch('src.config.Config.WORDPRESS_BASE_URL', 'https://example.com')
@patch('src.config.Config.WORDPRESS_USERNAME', 'user')
@patch('src.config.Config.WORDPRESS_TOKEN', 'token')
@patch('src.stats_manager.StatsManager.increment_published')
def test_wordpress_publisher_success(mock_increment: MagicMock, mock_post: MagicMock) -> None:
    """Verify WordPress publishing correctly handles REST response."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": 123, "link": "https://example.com/test-slug", "slug": "test-slug"}
    mock_post.return_value = mock_response

    meta = Metadata(
        title="Test Article Title",
        description=_VALID_DESC,
        focus_keyword="keyword",
        url_slug="test-slug",
        canonical_url="https://example.com/test-slug",
        keywords=["keyword"],
        json_ld_schema={}
    )
    article = ArticleDraft(
        title="Test Article Title",
        content_html="<h1>Test Title</h1><p>Body</p>",
        word_count=200,
        metadata=meta,
        faq_section="<h2>FAQ</h2>"
    )

    publisher = WordPressPublisher()
    result = publisher.publish_article(article)
    assert result["id"] == 123
    assert result["link"] == "https://example.com/test-slug"


# ==============================================================================
# 10. ORCHESTRATOR: IMAGE SCENE DIVERSITY & DUPLICATE CONTENT GUARD
# ==============================================================================

def test_travel_scene_pool_gives_varied_output_for_same_topic() -> None:
    """Same-topic titles must not always get the exact same hero-image scene text.

    Regression guard for the bug that caused every 'rafting' article (etc.) to get
    an identical image prompt — each keyword now maps to a pool of variants.
    """
    orchestrator = object.__new__(BlogGeneratorOrchestrator)
    seen = {
        orchestrator._get_travel_scene("Best Rafting Spots Near Rishikesh")
        for _ in range(30)
    }
    assert len(seen) > 1, "Expected multiple distinct scene variants for the same keyword"
    assert all("rafting" in s.lower() or "raft" in s.lower() for s in seen)


def test_travel_scene_unmatched_title_uses_defaults_pool() -> None:
    orchestrator = object.__new__(BlogGeneratorOrchestrator)
    scene = orchestrator._get_travel_scene("Totally Unrelated Title With No Keyword")
    assert scene in orchestrator.RISHIKESH_TRAVEL_SCENES["defaults"]


def _make_article(content_html: str = "<h1>Title</h1><p>Some body text.</p>") -> ArticleDraft:
    meta = Metadata(
        title="Test Article Title",
        description=_VALID_DESC,
        focus_keyword="keyword",
        url_slug="test-slug",
        canonical_url="https://example.com/test-slug",
        keywords=["keyword"],
        json_ld_schema={}
    )
    return ArticleDraft(
        title="Test Article Title",
        content_html=content_html,
        word_count=200,
        metadata=meta,
        faq_section="<h2>FAQ</h2>"
    )


def test_duplicate_content_guard_flags_near_duplicate() -> None:
    """A draft that scores above CONTENT_SIMILARITY_THRESHOLD against an already
    -published article must be flagged so the caller retries instead of publishing it.
    """
    orchestrator = object.__new__(BlogGeneratorOrchestrator)
    orchestrator.vector_store = MagicMock(client=True)
    orchestrator.vector_store.find_similar_articles.return_value = [
        {"relevance_score": 0.97, "title": "Existing Rafting Guide", "article_id": "1", "content_snippet": ""}
    ]

    match = orchestrator._find_near_duplicate_match(_make_article())
    assert match is not None
    assert match["title"] == "Existing Rafting Guide"


def test_duplicate_content_guard_allows_dissimilar_article() -> None:
    orchestrator = object.__new__(BlogGeneratorOrchestrator)
    orchestrator.vector_store = MagicMock(client=True)
    orchestrator.vector_store.find_similar_articles.return_value = [
        {"relevance_score": 0.40, "title": "Unrelated Article", "article_id": "2", "content_snippet": ""}
    ]

    assert orchestrator._find_near_duplicate_match(_make_article()) is None


def test_duplicate_content_guard_noop_when_vector_store_unavailable() -> None:
    """Fails safe: no Weaviate client configured => guard never runs, never errors."""
    orchestrator = object.__new__(BlogGeneratorOrchestrator)
    orchestrator.vector_store = MagicMock(client=None)

    assert orchestrator._find_near_duplicate_match(_make_article()) is None
    orchestrator.vector_store.find_similar_articles.assert_not_called()

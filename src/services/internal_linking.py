import json
import os
import re
import random
import logging
from typing import Dict, List
from src.config import Config
from src.models import ArticleDraft, InternalLink
from utils.utils import CSVManager, VectorStoreManager

logger = logging.getLogger(__name__)


def _clean_url(url: str) -> str:
    """Normalise a URL that may have a double-slash from trailing-slash + slug concatenation.

    e.g. 'https://www.rishikeshplaces.com//best-hotels' → 'https://rishikeshplaces.com/best-hotels'
    Only the path portion is de-duplicated; the scheme '://' is left untouched.
    """
    if not url:
        return url
    # Split off scheme (http:// or https://) then fix double slashes in the rest
    if '://' in url:
        scheme, rest = url.split('://', 1)
        rest = re.sub(r'/{2,}', '/', rest)  # collapse //+ to /
        return f'{scheme}://{rest}'
    return re.sub(r'/{2,}', '/', url)

class InternalLinkingService:
    def __init__(self, csv_manager: CSVManager, vector_store: VectorStoreManager):
        self.csv_manager = csv_manager
        self.vector_store = vector_store

    def _extract_text_from_html(self, html_content: str) -> str:
        """Extracts plain text from HTML content."""
        return re.sub(r'<[^>]+>', ' ', html_content)

    def _get_sitemap_live_links(self) -> List[InternalLink]:
        """Loads real, live activity URLs from sitemap_mapping.json as guaranteed working links."""
        sitemap_path = os.path.join(Config.CONFIG_DIR, "sitemap_mapping.json")
        live_links = []
        if os.path.exists(sitemap_path):
            try:
                with open(sitemap_path, "r", encoding="utf-8") as f:
                    sitemap_data = json.load(f)
                activities = sitemap_data.get("activities", {})
                for act_key, act_val in activities.items():
                    url = act_val.get("url")
                    title = act_val.get("cta_button_text") or act_val.get("cta_title") or f"Explore {act_key.title()}"
                    if url:
                        live_links.append(InternalLink(
                            anchor_text=title,
                            target_url=_clean_url(url),
                            relevance_score=0.9
                        ))
            except Exception as e:
                logger.warning("Could not load sitemap_mapping.json for live links: %s", e)

        if not live_links:
            live_links.append(InternalLink(
                anchor_text=Config.DEFAULT_LINK_TEXT or "Explore Rishikesh Adventures on bucketlistt",
                target_url=Config.DEFAULT_LINK_URL,
                relevance_score=1.0
            ))
        return live_links

    def _get_csv_fallback_links(self, exclude_slug: str) -> List[InternalLink]:
        """Gets fallback links prioritizing published articles and live sitemap activity URLs.

        Always ensures exactly 3 live, working links are returned.
        """
        all_articles = self.csv_manager.get_all_articles()
        links = []

        # 1. Get up to 2 published article links from CSV (only if marked published or live)
        if all_articles:
            others = [
                a for a in all_articles
                if a.get('url') and exclude_slug not in a['url'] and str(a.get('is_published', '')).lower() in ('true', '1', 'yes')
            ]
            if others:
                sample_count = min(len(others), 2)
                sample = random.sample(others, sample_count)
                for sample_article in sample:
                    links.append(InternalLink(
                        anchor_text=self._generate_anchor_text(sample_article),
                        target_url=_clean_url(sample_article['url']),
                        relevance_score=0.6
                    ))

        # 2. Fill remaining slots using real live sitemap activity URLs
        if len(links) < 2:
            sitemap_links = self._get_sitemap_live_links()
            random.shuffle(sitemap_links)
            for s_link in sitemap_links:
                if len(links) >= 2:
                    break
                if s_link.target_url not in [l.target_url for l in links]:
                    links.append(s_link)

        # 3. Always add 1 direct site link
        links.append(InternalLink(
            anchor_text=Config.DEFAULT_LINK_TEXT,
            target_url=Config.DEFAULT_LINK_URL,
            relevance_score=1.0
        ))

        # 4. Fill remaining slots to reach exactly 3 links if needed
        while len(links) < 3:
            links.append(InternalLink(
                anchor_text=Config.DEFAULT_LINK_TEXT or "Explore Rishikesh Adventures on bucketlistt",
                target_url=Config.DEFAULT_LINK_URL,
                relevance_score=0.5
            ))

        logger.info("Internal linking (Fallback): Created %d live links", len(links))
        return links[:3]

    def _get_live_activity_links(self) -> List[InternalLink]:
        """Load all verified-live activity URLs from sitemap_mapping.json.

        These are the ONLY links we trust to exist on the website.
        Returns them in shuffled order so each article gets varied links.
        """
        sitemap_path = os.path.join(Config.CONFIG_DIR, "sitemap_mapping.json")
        live_links: List[InternalLink] = []
        if os.path.exists(sitemap_path):
            try:
                with open(sitemap_path, "r", encoding="utf-8") as f:
                    sitemap_data = json.load(f)
                activities = sitemap_data.get("activities", {})
                for act_key, act_val in activities.items():
                    url = act_val.get("url", "")
                    # Use cta_button_text as anchor, falling back to cta_title or key name
                    anchor = (
                        act_val.get("cta_button_text")
                        or act_val.get("cta_title")
                        or f"Explore {act_key.replace('_', ' ').title()} in Rishikesh"
                    )
                    if url:
                        live_links.append(InternalLink(
                            anchor_text=anchor,
                            target_url=_clean_url(url),
                            relevance_score=0.9
                        ))
            except Exception as e:
                logger.warning("Could not load sitemap_mapping.json for live links: %s", e)

        random.shuffle(live_links)
        return live_links

    def add_internal_links(self, article: ArticleDraft) -> ArticleDraft:
        """Add exactly 3 guaranteed-live links into article HTML.

        Strategy (100% safe — no article-to-article links that may 404):
          Slot 1 & 2 — Two distinct verified-live activity page URLs from sitemap_mapping.json
                        (e.g. /river-rafting, /bungee-jumping, /camping …)
          Slot 3      — The bucketlistt homepage / DEFAULT_LINK_URL (always live)

        Article links from the CSV are intentionally NOT used because no articles
        in the database are currently published live, which would cause 404 errors.
        """
        internal_links: List[InternalLink] = []

        # --- Slots 1 & 2: pick 2 distinct live sitemap activity URLs ---
        sitemap_links = self._get_live_activity_links()
        for link in sitemap_links:
            if len(internal_links) >= 2:
                break
            if link.target_url not in [l.target_url for l in internal_links]:
                internal_links.append(link)

        # --- Slot 3: always the direct site homepage link ---
        internal_links.append(InternalLink(
            anchor_text=Config.DEFAULT_LINK_TEXT or "Explore Rishikesh Adventures on bucketlistt",
            target_url=Config.DEFAULT_LINK_URL,
            relevance_score=1.0
        ))

        # --- Safety guard: pad with homepage link if sitemap had < 2 entries ---
        while len(internal_links) < 3:
            internal_links.append(InternalLink(
                anchor_text=Config.DEFAULT_LINK_TEXT or "Explore Rishikesh Adventures on bucketlistt",
                target_url=Config.DEFAULT_LINK_URL,
                relevance_score=0.8
            ))

        article.content_html = self._insert_links_into_content(article.content_html, internal_links[:3])
        try:
            from src.services.link_sanitizer import LinkSanitizer
            article.content_html = LinkSanitizer.sanitize_html(article.content_html)
        except Exception as san_err:
            logger.warning("Could not run LinkSanitizer on article HTML: %s", san_err)

        article.internal_links = internal_links[:3]
        logger.info(
            "Internal linking completed with %d guaranteed-live links: %s",
            len(article.internal_links),
            [l.target_url for l in article.internal_links]
        )
        return article

    def _generate_anchor_text(self, target_article: Dict) -> str:
        title = target_article.get('title', 'our latest article')
        return "Read more about: " + (title[:40] + "..." if len(title) > 40 else title)

    def _insert_links_into_content(self, content: str, links: list[InternalLink]) -> str:
        """Inserts internal links into the content HTML.

        Strategy:
        1. Find paragraphs in the content
        2. Insert links within paragraphs at appropriate positions
        3. Ensure links are properly wrapped and contextual
        """
        if not links:
            logger.debug("No internal links to insert.")
            return content

        # Case-insensitive split on </p> tag, handling variations like </P>, </p >, etc.
        paragraph_pattern = re.compile(r'(</[pP]\s*>)', re.IGNORECASE)
        parts = paragraph_pattern.split(content)

        if not parts or len(parts) < 3:
            # Fallback: append links at the end if too few paragraphs
            logger.warning("Article has fewer than 3 paragraphs. Appending links at end.")
            links_html = ''.join(
                f'<p>For more information, '
                f'<a href="{link.target_url}" title="{link.anchor_text}">'
                f'{link.anchor_text}</a>.</p>'
                for link in links
            )
            return content + links_html

        # Reconstruct paragraphs: combine content with closing tags
        paragraphs = []
        i = 0
        while i < len(parts):
            if i + 1 < len(parts) and paragraph_pattern.match(parts[i + 1]):
                paragraphs.append(parts[i] + parts[i + 1])
                i += 2
            else:
                paragraphs.append(parts[i])
                i += 1

        # Filter out empty paragraphs
        paragraphs = [p for p in paragraphs if p.strip()]

        if len(paragraphs) < 2:
            logger.warning("After reconstruction, too few paragraphs. Appending links at end.")
            links_html = ''.join(
                f'<p>For more information, '
                f'<a href="{link.target_url}" '
                f'title="{link.anchor_text}">'
                f'{link.anchor_text}</a>.</p>'
                for link in links
            )
            return content + links_html

        # Insert links at strategic positions (after 1/4, 2/4, and 3/4 of the content)
        total_paragraphs = len(paragraphs)
        link_positions = [
            max(1, total_paragraphs // 4),
            max(2, (2 * total_paragraphs) // 4),
            max(3, (3 * total_paragraphs) // 4)
        ]

        link_idx = 0
        inserted_count = 0
        result_parts = []

        for idx, para in enumerate(paragraphs):
            result_parts.append(para)

            # Insert link after this paragraph if it's a target position
            if idx in link_positions and link_idx < len(links):
                link = links[link_idx]
                # Insert a contextual link paragraph
                link_html = (
                f'<p class="internal-link">You might also be interested in: '
                f'<a href="{link.target_url}" title="{link.anchor_text}">'
                f'{link.anchor_text}</a></p>'
            )
                result_parts.append(link_html)
                link_idx += 1
                inserted_count += 1

        # If we still have remaining links, append them at the end
        while link_idx < len(links):
            link = links[link_idx]
            link_html = (
            f'<p class="internal-link">Related reading: '
            f'<a href="{link.target_url}" title="{link.anchor_text}">'
            f'{link.anchor_text}</a></p>'
        )
            result_parts.append(link_html)
            link_idx += 1
            inserted_count += 1

        logger.info("Inserted %d internal links into content.", inserted_count)
        return ''.join(result_parts)

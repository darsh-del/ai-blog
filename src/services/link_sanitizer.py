"""
LinkSanitizer Module
====================
Parses HTML content and validates all hyperlinks against a strict set of
verified live URLs from sitemap_mapping.json and Config.
Stale, 404, dead, or hallucinated links are automatically mapped to valid live URLs
or converted to clean text.
"""

import json
import logging
import os
import re
from typing import Dict, Set
from bs4 import BeautifulSoup
from src.config import Config

logger = logging.getLogger(__name__)

_SITEMAP_PATH = os.path.join(Config.CONFIG_DIR, "sitemap_mapping.json")


class LinkSanitizer:
    """Utility to validate and auto-heal all hyperlinks in generated articles."""

    # A small, hand-verified allowlist of real external authoritative sources the
    # generator is permitted to cite (see prompts/content_prompts.py,
    # _get_authoritative_citation_block) — a genuine trust/citation signal that
    # everything else in the pipeline can't provide, since every other link this
    # generator ever adds points back to bucketlistt or an approved partner.
    # Kept tiny and explicit on purpose so it can't become a loophole for
    # arbitrary or hallucinated external links: anything not in this list still
    # gets rewritten back to bucketlistt below, same as before.
    TRUSTED_EXTERNAL_DOMAINS = (
        "uttarakhandtourism.gov.in",
        "mausam.imd.gov.in",
    )

    @classmethod
    def get_verified_live_urls(cls) -> Set[str]:
        """Returns a set of all verified live URLs from sitemap_mapping.json and Config."""
        urls: Set[str] = {
            "https://www.bucketlistt.com/",
            "https://bucketlistt.com/",
            "https://www.bucketlistt.com",
            "https://bucketlistt.com",
            "https://www.bucketlistt.com/rishikesh",
            "https://www.bucketlistt.com/rishikesh/",
            "https://www.bucketlistt.com/rafting",
            "https://www.bucketlistt.com/bungee",
            "https://www.bucketlistt.com/zipline",
            "https://www.bucketlistt.com/paragliding",
            "https://www.bucketlistt.com/hot-air-balloon",
            "https://www.bucketlistt.com/blogs",
            "https://www.bucketlistt.com/about-bucketlistt",
            "https://www.bucketlistt.com/contact",
            "https://www.bucketlistt.com/safety-guidelines",
            "https://www.bucketlistt.com/terms",
            "https://www.bucketlistt.com/privacy",
            Config.DEFAULT_LINK_URL.rstrip("/"),
            f"{Config.DEFAULT_LINK_URL.rstrip('/')}/",
        }

        if os.path.exists(_SITEMAP_PATH):
            try:
                with open(_SITEMAP_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Add activity URLs
                activities = data.get("activities", {})
                for act in activities.values():
                    if act.get("url"):
                        urls.add(act["url"].rstrip("/"))
                        urls.add(f"{act['url'].rstrip('/')}/")
                    if act.get("category_url"):
                        urls.add(act["category_url"].rstrip("/"))
                        urls.add(f"{act['category_url'].rstrip('/')}/")

                # Add hub URLs
                hub_links = data.get("hub_links", {})
                for hub in hub_links.values():
                    if hub.get("url"):
                        urls.add(hub["url"].rstrip("/"))
                        urls.add(f"{hub['url'].rstrip('/')}/")

                # Add verified blog URLs
                verified_blogs = data.get("verified_blogs", [])
                for b in verified_blogs:
                    if b.get("url"):
                        urls.add(b["url"].rstrip("/"))
                        urls.add(f"{b['url'].rstrip('/')}/")

                # Add general CTA URL
                gen_cta = data.get("general_cta", {})
                if gen_cta.get("url"):
                    urls.add(gen_cta["url"].rstrip("/"))
                    urls.add(f"{gen_cta['url'].rstrip('/')}/")

            except Exception as err:
                logger.warning("[LinkSanitizer] Could not load sitemap_mapping.json: %s", err)

        return urls

    @classmethod
    def find_best_matching_url(cls, anchor_text: str, current_href: str) -> str:
        """Finds the best valid live URL based on anchor text, current href, or defaults to Rishikesh hub."""
        combined_text = f"{anchor_text} {current_href}".lower()

        if os.path.exists(_SITEMAP_PATH):
            try:
                with open(_SITEMAP_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 1. Match against activities
                activities = data.get("activities", {})
                for act_key, act_val in activities.items():
                    keywords = act_val.get("keywords", [])
                    if any(kw.lower() in combined_text for kw in keywords) or act_key.lower() in combined_text:
                        if act_val.get("url"):
                            return act_val["url"]

                # 2. Match against verified blog posts
                verified_blogs = data.get("verified_blogs", [])
                for blog in verified_blogs:
                    b_keywords = blog.get("keywords", [])
                    b_title = blog.get("title", "").lower()
                    if any(kw.lower() in combined_text for kw in b_keywords) or any(w in combined_text for w in b_title.split() if len(w) > 4):
                        if blog.get("url"):
                            return blog["url"]

            except Exception:
                pass

        # Fall back to main Rishikesh hub
        return "https://www.bucketlistt.com/rishikesh"

    @classmethod
    def sanitize_html(cls, html: str) -> str:
        """
        Scans HTML content, checks all <a href="..."> links, and auto-heals any stale,
        dead, soft-404, or unverified URLs into verified live URLs.
        """
        if not html or "<a " not in html.lower():
            return html

        verified_urls = cls.get_verified_live_urls()
        soup = BeautifulSoup(html, "html.parser")
        anchors = soup.find_all("a")

        sanitized_count = 0
        for a in anchors:
            href = (a.get("href") or "").strip()
            anchor_text = a.get_text().strip()

            if href.startswith("#"):
                continue

            if any(domain in href for domain in cls.TRUSTED_EXTERNAL_DOMAINS):
                continue

            # Normalize URL for comparison
            normalized_href = href.rstrip("/")

            # Dead domain or unverified URL check
            is_dead_domain = any(domain in href for domain in [
                "placesinrishikesh.com", "rishikeshplaces.com", "your-website.com", "example.com"
            ])
            is_unverified = normalized_href not in verified_urls

            if is_dead_domain or is_unverified:
                best_url = cls.find_best_matching_url(anchor_text, href)
                a["href"] = best_url
                # ponytail: no target="_blank" here — every URL this sanitizer maps to
                # is bucketlistt.com's own domain (get_verified_live_urls), so opening a
                # new tab for it is never correct, whether the link was original or repaired.
                if a.has_attr("target"):
                    del a["target"]
                if a.has_attr("rel"):
                    del a["rel"]
                logger.info(
                    "[LinkSanitizer] Replaced stale link '%s' (%s) -> '%s'",
                    anchor_text, href, best_url
                )
                sanitized_count += 1

        if sanitized_count > 0:
            logger.info("[LinkSanitizer] Sanitized %d stale/dead hyperlinks in article HTML.", sanitized_count)
            return str(soup)

        return html

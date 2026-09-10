"""
Concurrent Campaign Manager Module
This module is responsible for running large-scale article generation campaigns
concurrently, using a thread pool to manage multiple generation tasks at once.
"""
import os
import json
import concurrent.futures
import logging
import math
import random
import threading
from typing import TYPE_CHECKING

from src.config import Config
from src.models import NoAvailableProductError, BlogGenerationError

# Use a forward reference for type hinting to avoid circular imports
if TYPE_CHECKING:
    from src.services import BlogGeneratorOrchestrator

logger = logging.getLogger(__name__)


def _count_existing_articles_by_category() -> dict:
    """Counts already-published articles per category by scanning the JSON output
    directory (articles.csv has no category column, so this is the only source
    of truth). Used to seed the campaign's overuse guard with REAL history —
    without this, every run started the guard at zero, so a category that
    already has a dozen articles looked exactly as "fresh" as one with none,
    and the rotation (reshuffled from scratch every run, no memory between
    runs) could freely keep piling onto whichever category was already most
    covered. Root cause of "5 of my last 10 articles were the same topic."
    """
    counts: dict = {}
    try:
        json_dir = Config.JSON_OUTPUT_DIR
        if not os.path.isdir(json_dir):
            return counts
        for filename in os.listdir(json_dir):
            if not filename.endswith(".json"):
                continue
            try:
                with open(os.path.join(json_dir, filename), "r", encoding="utf-8") as file_handle:
                    category = (json.load(file_handle).get("category") or "").strip()
            except (OSError, ValueError) as error:
                logger.debug("Skipping unreadable article file %s: %s", filename, error)
                continue
            if category:
                counts[category] = counts.get(category, 0) + 1
    except OSError as error:
        logger.warning("Could not scan JSON output dir for category counts: %s", error)
    return counts


class ConcurrentCampaignManager:
    """Orchestrates a concurrent article generation campaign."""

    def __init__(self, orchestrator: 'BlogGeneratorOrchestrator'):
        """
        Initializes the campaign manager.

        Args:
            orchestrator: An instance of BlogGeneratorOrchestrator, which handles
                          the logic for generating a single article.
        """
        self.orchestrator = orchestrator

    def _persist_fresh_topics(self, topics: list) -> None:
        """Appends newly-found fresh topics to Config.SCRAPED_ARTICLES_JSON — the
        same file the (often unavailable) browser scraper would otherwise fill —
        de-duplicated by exact title match, so future campaign runs start with a
        fuller seed pool instead of an empty one, not just this run."""
        if not topics:
            return

        existing = []
        if os.path.exists(Config.SCRAPED_ARTICLES_JSON):
            try:
                with open(Config.SCRAPED_ARTICLES_JSON, 'r', encoding='utf-8') as file_handle:
                    existing = json.load(file_handle)
            except (OSError, ValueError) as error:
                logger.warning(
                    "[SEED_POOL] Could not read %s to merge fresh topics (starting fresh): %s",
                    Config.SCRAPED_ARTICLES_JSON, error
                )
                existing = []

        seen_titles = {(obj.get("title") or "").strip().lower() for obj in existing}
        new_entries = [t for t in topics if t.get("title", "").strip().lower() not in seen_titles]
        if not new_entries:
            logger.info("[SEED_POOL] All %d fresh topic(s) already present in %s — nothing to persist.",
                        len(topics), Config.SCRAPED_ARTICLES_JSON)
            return

        try:
            with open(Config.SCRAPED_ARTICLES_JSON, 'w', encoding='utf-8') as file_handle:
                json.dump(existing + new_entries, file_handle, indent=4)
            logger.info(
                "[SEED_POOL] Persisted %d new fresh topic(s) to %s (%d total now).",
                len(new_entries), Config.SCRAPED_ARTICLES_JSON, len(existing) + len(new_entries)
            )
        except OSError as error:
            logger.warning("[SEED_POOL] Failed to persist fresh topics to %s: %s",
                           Config.SCRAPED_ARTICLES_JSON, error)

    def _fetch_and_persist_fresh_topics(self, num: int) -> tuple:
        """Shared by the campaign-start pool top-up and the mid-run stagnation
        fallback: fetches fresh topics via web search and persists any new ones to
        disk (see _persist_fresh_topics), so a search triggered either way
        benefits every future run, not just the one that triggered it.
        Returns (topics, cost_usd) exactly like ContentGeneratorAgent.fetch_fresh_topics.
        """
        topics, cost = self.orchestrator.content_generator.fetch_fresh_topics(num=num)
        self._persist_fresh_topics(topics)
        return topics, cost

    def _generate_article_worker(
        self,
        article_type: str,
        article_index: int,
        publish_to_wordpress: bool = False,
        category: str = "",
        seed_title: str = "",
        override_keywords: list[str] = None
    ) -> dict:
        """
        A self-contained worker function for a single thread.
        It generates a title and then calls the main orchestrator's logic.
        """
        thread_name = threading.current_thread().name
        logger.info(
            "Worker %s (Task %s) starting job for type: %s",
            thread_name, article_index, article_type
        )
        try:
            # 1. Generate a unique title for this worker
            title_list = self.orchestrator.content_generator.generate_titles(
                num=1,
                article_type=article_type,
                category=category,
                seed_title=seed_title,
                scraped_keywords=override_keywords
            )
            if not title_list:
                raise ValueError("Could not generate a title.")
            title = title_list[0]
            logger.info("Worker %s generated title: '%s'", thread_name, title)

            # 2. Run the main, single-article generation pipeline
            article, report, product = self.orchestrator.generate_blog(
                title,
                article_type=article_type,
                publish_to_wordpress=publish_to_wordpress,
                category=category,
                override_keywords=override_keywords
            )

            metadata = getattr(article, "metadata", None)
            # 3. Return a success result with usage stats
            return {
                "status": "success",
                "title": article.title,
                "type": "Brand-Specific" if article_type == "brand" else "Industry-Generic",
                "product": product.get('product_name') if product else "N/A",
                "score": report.overall_score,
                "word_count": article.word_count,
                "total_tokens": article.token_usage.get('total_tokens', 0),
                "total_cost": article.cost,
                "useful_tokens": article.useful_tokens.get('total_tokens', 0),
                "useful_cost": article.useful_cost,
                "has_image": bool(article.image_path),
                "is_published": article.is_published,
                "article_id": getattr(article, "article_id", ""),
                "wp_link": getattr(article, "wp_link", ""),
                "wp_slug": getattr(article, "wp_slug", ""),
                "content_html": getattr(article, "content_html", ""),
                "faq_section": getattr(article, "faq_section", ""),
                "image_path": getattr(article, "image_path", ""),
                "category": getattr(article, "category", ""),
                "parent_category": getattr(article, "parent_category", ""),
                "focus_keyword": getattr(metadata, "focus_keyword", "") if metadata else "",
                "keywords": getattr(metadata, "keywords", []) if metadata else [],
                "meta_description": getattr(metadata, "description", "") if metadata else "",
                # meta_title is the <title>-tag text (<=60 chars), distinct from the
                # on-page H1 already covered by "title" above
                "meta_title": getattr(metadata, "title", "") if metadata else "",
                # canonical_url and url_slug are always generated by the SEO pipeline —
                # pass them so the email can show a preview link even when wp_link is empty
                "canonical_url": getattr(metadata, "canonical_url", "") if metadata else "",
                "url_slug": getattr(metadata, "url_slug", "") if metadata else "",
                "internal_links": getattr(article, "internal_links", []),
                # SEO-optimized hero image alt text — surfaced in the DOCX export below
                "image_description": getattr(article, "image_description", "")
            }

        except NoAvailableProductError as error:
            logger.warning("Worker %s skipped brand-specific article: %s", thread_name, error)
            return {"status": "skipped", "reason": str(error)}
        except BlogGenerationError as error:
            logger.error("Worker %s failed to generate article: %s", thread_name, error)
            return {
                "status": "failure",
                "error": str(error),
                "total_tokens": error.total_tokens.get('total_tokens', 0),
                "total_cost": error.total_cost,
                "useful_tokens": 0,
                "useful_cost": 0.0
            }
        except Exception as error:  # pylint: disable=broad-exception-caught
            logger.error(
                "Worker %s failed to generate article (unexpected): %s",
                thread_name, error, exc_info=True
            )
            return {
                "status": "failure",
                "error": str(error),
                "total_tokens": 0,
                "total_cost": 0.0,
                "useful_tokens": 0,
                "useful_cost": 0.0
            }

    def run_campaign(self, total_articles: int, max_workers: int = 6,
                     publish_to_wordpress: bool = False):
        """
        Executes the full concurrent generation campaign.
        Safeguards: Continues generating until 'total_articles' successes are achieved,
        replacing failed/skipped tasks automatically.
        """
        if total_articles <= 0 or max_workers <= 0:
            logger.error("Total articles and max workers must be positive integers.")
            return

        print(f"\nStarting concurrent generation for TARGET: {total_articles} successful articles...")
        logger.info("Target: %s successful articles. Max workers: %s.", total_articles, max_workers)

        # Tracking metrics
        stats = {
            "success_count": 0,
            "failure_count": 0,
            "skipped_count": 0,
            "processed_attempts": 0,
            # Stagnation tracking for the fresh-topic web-search fallback: counts
            # failures/skips since the last success, and whether this stagnation
            # streak has already triggered a web search (so it fires once per
            # streak, not on every single failure past the threshold).
            "consecutive_failures": 0,
            "fresh_topics_triggered": False,
            "total_tokens": 0,
            "total_cost": 0.0,
            "useful_tokens": 0,
            "useful_cost": 0.0,
            "articles_with_images_created": 0,
            "articles_published": 0,
            "articles_with_images_published": 0,
            "total_articles": total_articles,
            "successful_articles": []
        }

        # Prepare Coverage Mode Rotations & Seeds Pool
        seeds = {"articles": [], "pool": []}
        try:
            if os.path.exists(Config.SCRAPED_ARTICLES_JSON):
                with open(Config.SCRAPED_ARTICLES_JSON, 'r', encoding='utf-8') as file_handle:
                    seeds["articles"] = json.load(file_handle)
        except Exception as error:
            logger.warning("Failed loading scraped articles for campaign seeds: %s", error)

        seeds["pool"] = list(seeds["articles"])
        random.shuffle(seeds["pool"])

        # Seed-pool health check: SCRAPED_ARTICLES_JSON is often empty or stale —
        # e.g. the browser-scraper that normally fills it needs deps
        # (undetected-chromedriver) that aren't installed in this environment —
        # which otherwise means every 'generic' job silently falls back to the
        # fixed rotation categories with no fresh ideas at all. Top it up with a
        # real web search before the campaign starts instead of only reacting
        # after things stall (that's what FRESH_TOPIC_FAILURE_THRESHOLD covers,
        # unchanged, as a mid-run safety net below).
        if Config.ENABLE_FRESH_TOPIC_FALLBACK:
            title_manager = self.orchestrator.content_generator.title_manager
            slug_registry = self.orchestrator.content_generator.slug_registry
            usable_count = sum(
                1 for obj in seeds["articles"]
                if obj.get("title") and not title_manager.is_title_used(obj["title"], slug_registry)
            )
            logger.info(
                "[SEED_POOL] %d/%d seed(s) in %s are usable (not already published).",
                usable_count, len(seeds["articles"]), Config.SCRAPED_ARTICLES_JSON
            )
            if usable_count < Config.MIN_SEED_POOL_SIZE:
                print(
                    f"\n[SEED_POOL] Only {usable_count} usable seed(s) (minimum {Config.MIN_SEED_POOL_SIZE}) "
                    f"— topping up with a web search for fresh {Config.TARGET_CITY} topics..."
                )
                fresh_topics, topup_cost = self._fetch_and_persist_fresh_topics(Config.FRESH_TOPIC_TOPUP_BATCH_SIZE)
                stats["total_cost"] += topup_cost
                if fresh_topics:
                    seeds["pool"][:0] = fresh_topics
                    print(f"[SEED_POOL] Added {len(fresh_topics)} fresh topic(s) to the pool for this run.")
                else:
                    print("[SEED_POOL] Web search found no usable fresh topics — continuing with the existing pool.")

        industry_rotation = list(Config.INDUSTRY_CATEGORIES) or [Config.get_random_category("generic")]
        random.shuffle(industry_rotation)

        service_category_rotation = list(Config.PRODUCT_CATEGORIES) or [Config.get_random_category("brand")]
        random.shuffle(service_category_rotation)

        # Topic diversity guard: scraped seeds carry their own "category" and,
        # unlike the rotation pools above, were previously used as-is with no
        # anti-clustering check. If competitor scraping returns many seeds for
        # the same topic, this let one category dominate a whole campaign run.
        # Track usage counts and refuse a seed's category once it's notably
        # more used than average, falling back to the fair rotation instead.
        #
        # Seeded with REAL historical counts (not starting at zero every run) —
        # and now also applied to the plain rotation picks below, not just
        # scraped-seed categories. Previously the rotation's own shuffle-and
        # -pop was "fair" only within a single run and only among the 5
        # categories equally; it had no idea 3 of them already had 10+
        # published articles each and one had almost none, so it happily kept
        # feeding the already-saturated ones at the same rate as everyone else.
        category_usage_counts = _count_existing_articles_by_category()
        CATEGORY_OVERUSE_RATIO = 1.5

        def _record_category_use(cat):
            if cat:
                category_usage_counts[cat] = category_usage_counts.get(cat, 0) + 1

        def _is_category_overused(cat):
            if not cat or not category_usage_counts:
                return False
            total_used = sum(category_usage_counts.values())
            avg = total_used / len(category_usage_counts)
            return category_usage_counts.get(cat, 0) >= max(3, avg * CATEGORY_OVERUSE_RATIO)

        def _pop_next_category(rotation, config_categories, fallback_type):
            """Pops the next category off a rotation list, refilling/reshuffling
            when empty exactly like before — but now skips a category that's
            already overused (real historical count + this run) in favour of
            the next one in the shuffled order, instead of handing it out
            regardless. Bounded by the rotation's own length so this can never
            loop forever; if literally every category is equally saturated,
            the first draw is accepted rather than refusing to produce anything.
            """
            if not rotation:
                rotation.extend(list(config_categories) or [Config.get_random_category(fallback_type)])
                random.shuffle(rotation)
            for _ in range(len(rotation)):
                candidate = rotation.pop(0)
                if not _is_category_overused(candidate):
                    return candidate
                rotation.append(candidate)  # put it back at the end, try the next one
            return rotation.pop(0)  # every category is equally saturated — just take one

        def get_next_job_params(article_type: str) -> dict:
            seed_info = {
                "title": "",
                "keywords": None,
                "category": None
            }
            if article_type == "generic" and seeds["pool"]:
                # Pick a unique seed from the shuffled pool
                obj = seeds["pool"].pop(0)
                seed_info["title"] = obj.get("title", "")

                seed_source = obj.get("source", "scraped")
                logger.info(
                    "[SEED] Popped %s seed for generic job: '%s' (raw category hint: %s, %d left in pool)",
                    seed_source, seed_info["title"], obj.get("category") or "none", len(seeds["pool"])
                )

                # Let the seed's category (if available) drive the choice, otherwise
                # rotation — unless that category is already overused this run.
                scraped_cat = obj.get("category")
                if scraped_cat and not _is_category_overused(scraped_cat):
                    seed_info["category"] = scraped_cat
                else:
                    seed_info["category"] = _pop_next_category(
                        industry_rotation, Config.INDUSTRY_CATEGORIES, "generic"
                    )
                    if scraped_cat:
                        logger.info(
                            "[SEED] Category '%s' is overused this run — falling back to rotation category '%s'.",
                            scraped_cat, seed_info["category"]
                        )

                # Also use keywords from the seed if available
                kws = obj.get("keywords")
                if kws and isinstance(kws, list):
                    seed_info["keywords"] = kws[:15]

                # Refill pool if empty
                if not seeds["pool"]:
                    seeds["pool"] = list(seeds["articles"])
                    random.shuffle(seeds["pool"])
            elif article_type == "generic":
                seed_info["category"] = _pop_next_category(
                    industry_rotation, Config.INDUSTRY_CATEGORIES, "generic"
                )
            else:
                # For Brand-specific, use the product category rotation
                seed_info["category"] = _pop_next_category(
                    service_category_rotation, Config.PRODUCT_CATEGORIES, "brand"
                )

            _record_category_use(seed_info["category"])
            return seed_info

        def refresh_seeds_with_fresh_topics():
            """Stagnation fallback: the fixed category/keyword pool has produced too
            many consecutive duplicate/failed attempts to trust for a while — search
            the live web for current TARGET_CITY news and prepend fresh, real topics
            to the seed pool so the next 'generic' job gets one of these instead of
            colliding with the same exhausted pool again."""
            print(
                f"\n[STAGNATION] {stats['consecutive_failures']} consecutive failures — "
                f"searching the web for fresh {Config.TARGET_CITY} topics..."
            )
            fresh_topics, cost = self._fetch_and_persist_fresh_topics(Config.FRESH_TOPIC_TOPUP_BATCH_SIZE)
            stats["total_cost"] += cost
            if fresh_topics:
                seeds["pool"][:0] = fresh_topics  # prepend — used before the existing pool
                print(f"[STAGNATION] Added {len(fresh_topics)} fresh topic(s) to the seed pool.")
                logger.info(
                    "[STAGNATION] Injected %d fresh web-search topic(s) into seed pool. Cost: $%.4f",
                    len(fresh_topics), cost
                )
            else:
                print("[STAGNATION] Web search found no usable fresh topics — continuing with existing pool.")
                logger.warning("[STAGNATION] fetch_fresh_topics() returned no usable topics.")

        # Safety valve: Stop if we try too many times (e.g., 5x the target) to prevent infinite loops
        max_attempts = total_articles * 5

        # Initial Batch Calculation
        # We need 'total_articles' successes. We start by queueing that many.
        remaining_needed = total_articles

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix='ArticleWorker'
        ) as executor:
            futures_set = set()

            # Helper to submit new batch of tasks
            def submit_batch(count):
                # Calculate ratio for this specific batch size
                n_brand = math.ceil(count * Config.BRAND_MENTION_RATIO)
                n_generic = count - n_brand
                batch_types = ['brand'] * n_brand + ['generic'] * n_generic
                random.shuffle(batch_types)

                for atype in batch_types:
                    params = get_next_job_params(atype)
                    fut = executor.submit(
                        self._generate_article_worker,
                        atype,
                        0,
                        publish_to_wordpress,
                        params["category"],
                        params["title"],
                        params["keywords"]
                    )
                    futures_set.add(fut)

            # Submit initial batch
            submit_batch(remaining_needed)

            # Process Loop
            while (
                futures_set and
                stats["success_count"] < total_articles and
                stats["processed_attempts"] < max_attempts
            ):
                # Wait for at least one future to complete
                done, futures_set = concurrent.futures.wait(futures_set, return_when=concurrent.futures.FIRST_COMPLETED)

                for future in done:
                    # Pass context via stats or just assume it's there
                    stats['max_attempts'] = max_attempts
                    self._handle_worker_result(
                        future, stats, executor, futures_set,
                        publish_to_wordpress,
                        get_next_job_params,
                        refresh_seeds_with_fresh_topics
                    )

                # Check safety limit
                if stats["processed_attempts"] >= max_attempts and stats["success_count"] < total_articles:
                    print(
                        f"\n[WARNING] Reached maximum safety attempt limit ({max_attempts}). "
                        "Stopping campaign early."
                    )
                    logger.warning(
                        "Campaign stopped due to safety limit. Success: %s/%s",
                        stats["success_count"], total_articles
                    )
                    break

        self._print_campaign_summary(stats)

        logger.info(
            "Campaign finished. Target: %s, Achieved: %s, Cost: $%.4f",
            total_articles, stats["success_count"], stats["total_cost"]
        )
        return stats["successful_articles"]

    def _handle_worker_result(
        self, future, stats, executor, futures_set,
        publish_to_wordpress,
        get_next_job_params,
        refresh_seeds_fn=None
    ):
        """Helper to process a completed worker future and manage retries."""
        stats["processed_attempts"] += 1

        def _bump_stagnation_and_maybe_refresh():
            """Counts this failure/skip toward the stagnation threshold, and fires
            the fresh-topic web search exactly once per stagnation streak (reset by
            the next success) once Config.FRESH_TOPIC_FAILURE_THRESHOLD is hit."""
            stats["consecutive_failures"] += 1
            logger.info(
                "[STAGNATION] Consecutive failures: %d/%d (triggers fresh-topic web search at threshold)",
                stats["consecutive_failures"], Config.FRESH_TOPIC_FAILURE_THRESHOLD
            )
            if (
                refresh_seeds_fn is not None
                and not stats["fresh_topics_triggered"]
                and stats["consecutive_failures"] >= Config.FRESH_TOPIC_FAILURE_THRESHOLD
            ):
                stats["fresh_topics_triggered"] = True
                refresh_seeds_fn()

        try:
            result = future.result()

            # Accumulate stats
            if 'total_tokens' in result:
                stats["total_tokens"] += result['total_tokens']
                stats["total_cost"] += result['total_cost']
                stats["useful_tokens"] += result['useful_tokens']
                stats["useful_cost"] += result['useful_cost']

            status = result['status']

            if status == 'success':
                # A success ends the stagnation streak — a future streak (later in a
                # long campaign) can trigger fresh topics again.
                stats["consecutive_failures"] = 0
                stats["fresh_topics_triggered"] = False
                stats["success_count"] += 1
                stats["successful_articles"].append(result)
                if result.get('has_image'):
                    stats["articles_with_images_created"] += 1
                if result.get('is_published'):
                    stats["articles_published"] += 1
                    if result.get('has_image'):
                        stats["articles_with_images_published"] += 1

                progress = f"({stats['success_count']}/{stats['total_articles']})"
                print(
                    f"SUCCESS {progress}: '{result['title']}' "
                    f"(Score: {result['score']}, Type: {result['type']})"
                )
            else:
                # Handle Failure/Skip
                if status == 'skipped':
                    stats["skipped_count"] += 1
                    print(f"SKIPPED (Will Retry): {result['reason']}")
                else:
                    stats["failure_count"] += 1
                    print(f"FAILURE (Will Retry): {result['error']}")
                _bump_stagnation_and_maybe_refresh()

                # RETRY LOGIC: Replenish this slot immediately.
                if (
                    stats["success_count"] < stats["total_articles"] and
                    (stats["processed_attempts"] + len(futures_set)) < stats['max_attempts']
                ):
                    next_type = (
                        'brand' if random.random() < Config.BRAND_MENTION_RATIO
                        else 'generic'
                    )
                    params = get_next_job_params(next_type)
                    new_fut = executor.submit(
                        self._generate_article_worker,
                        next_type,
                        stats["processed_attempts"] + 1,
                        publish_to_wordpress,
                        params["category"],
                        params["title"],
                        params["keywords"]
                    )
                    futures_set.add(new_fut)
                    print("   -> Re-queued 1 new task to replace failed/skipped article.")

        except Exception as error:  # pylint: disable=broad-exception-caught
            stats["failure_count"] += 1
            print(f"CRITICAL WORKER FAIL: {error}")
            _bump_stagnation_and_maybe_refresh()
            # Even for crash, try to replenish
            if (
                stats["success_count"] < stats["total_articles"] and
                (stats["processed_attempts"] + len(futures_set)) < stats['max_attempts']
            ):
                next_type = 'generic'  # Fallback safe type
                params = get_next_job_params(next_type)
                new_fut = executor.submit(
                    self._generate_article_worker,
                    next_type,
                    stats["processed_attempts"] + 1,
                    publish_to_wordpress,
                    params["category"],
                    params["title"],
                    params["keywords"]
                )
                futures_set.add(new_fut)

    def _print_campaign_summary(self, stats):
        """Helper to print the campaign summary to console."""
        wasted_tokens = stats["total_tokens"] - stats["useful_tokens"]
        wasted_cost = stats["total_cost"] - stats["useful_cost"]

        print(f"\n{'='*100}")
        print(f"{'CONTINUOUS GENERATION CAMPAIGN SUMMARY':^100}")
        print(f"{'='*100}")
        print(f"{'METRIC':<30} | {'VALUE':<15}")
        print(f"{'-'*100}")
        print(f"{'Target Success Count':<30} | {stats['total_articles']:<15}")
        print(f"{'Actual Successes':<30} | {stats['success_count']:<15}")
        print(f"{'Total Attempts Made':<30} | {stats['processed_attempts']:<15}")
        print(f"{'Failures (Retried)':<30} | {stats['failure_count']:<15}")
        print(f"{'Skipped (Retried)':<30} | {stats['skipped_count']:<15}")
        print(f"{'-'*100}")
        print(f"{'Total Tokens Used':<30} | {stats['total_tokens']:<15}")
        print(f"{'Total Cost ($)':<30} | ${stats['total_cost']:<14.4f}")
        print(f"{'Useful Tokens (Published)':<30} | {stats['useful_tokens']:<15}")
        print(f"{'Useful Cost ($)':<30} | ${stats['useful_cost']:<14.4f}")
        print(f"{'Wasted Tokens':<30} | {wasted_tokens:<15}")
        print(f"{'Wasted Cost ($)':<30} | ${wasted_cost:<14.4f}")
        print(f"{'-'*100}")
        print(f"{'Articles with Images Created':<30} | {stats['articles_with_images_created']:<15}")
        print(f"{'Total Articles Published':<30} | {stats['articles_published']:<15}")
        print(f"{'Articles w/ Images Published':<30} | {stats['articles_with_images_published']:<15}")
        print(f"{'='*100}\n")

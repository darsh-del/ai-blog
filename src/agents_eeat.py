"""
agents_eeat.py
===============
Experimental SEO scoring variant — kept 100% separate from `src/agents.py`
so the production `generate_and_email.py` pipeline never changes behaviour.

`SEOEvaluatorAgentEEAT` subclasses the existing `SEOEvaluatorAgent` and only
overrides the two things the research says are miscalibrated against real
Google ranking behaviour:

1. Keyword density — the base class rewards up to 15% density (full points).
   Real top-10 pages average 1.2-2.4%; Google has stated density isn't a
   ranking factor. Rewarding 15% trains the writer/retry loop toward
   keyword stuffing. This narrows the full-score band to 0.8-1.5%.

2. E-E-A-T content specificity — the base class computes this
   (`_evaluate_content_specificity`) but only uses it as a pass/fail gate
   worth 0 points, so the retry loop has no incentive to chase it. This
   folds it into the score as a real 15-point metric, funded by trimming
   Location Keyword Usage from 20 -> 5 (that metric is the most
   keyword-stuffing-prone one and the least tied to actual rankings), so
   the total stays 100.

Everything else (title/meta, headings, word count, readability, FAQ,
internal links, and the specificity heuristic itself) is inherited
unchanged from `SEOEvaluatorAgent` — no duplicated logic to drift out of
sync.
"""
from src.agents import SEOEvaluatorAgent
from src.config import Config
from src.models import ArticleDraft, SEOMetric, SEOReport


class SEOEvaluatorAgentEEAT(SEOEvaluatorAgent):
    """SEOEvaluatorAgent with density recalibrated and E-E-A-T scored, not gated."""

    def __init__(self):
        super().__init__()
        # Location Keyword Usage funds the new E-E-A-T metric (20 -> 5), keeping the total at 100.
        self.scoring_weights['location_keyword_usage'] = 5
        self.scoring_weights['content_specificity_eeat'] = 15

    def evaluate_article(
        self, article: ArticleDraft, iteration_number: int = 1, article_type: str = "generic"
    ) -> SEOReport:
        metrics = [
            self._evaluate_title_meta(article),
            self._evaluate_keyword_integration(article),
            self._evaluate_location_keywords_capped(article, article_type),
            self._evaluate_heading_structure(article),
            self._evaluate_word_count(article),
            self._evaluate_readability(article),
            self._evaluate_faq_section(article),
            self._evaluate_internal_links(article),
            self._evaluate_specificity_scored(article),
        ]

        overall_score = sum(metric.score for metric in metrics)
        passed = overall_score >= Config.SEO_THRESHOLD

        improvement_suggestions = [m.feedback for m in metrics if m.score < m.max_score * 0.8]

        return SEOReport(
            overall_score=overall_score,
            metrics=metrics,
            passed=passed,
            improvement_suggestions=improvement_suggestions,
            iteration_number=iteration_number,
            specificity_passed=next(
                (m.score >= m.max_score * 0.5 for m in metrics if m.name == "Content Specificity (E-E-A-T)"),
                False,
            ),
            specificity_feedback=next(
                (m.feedback for m in metrics if m.name == "Content Specificity (E-E-A-T)"), ""
            ),
        )

    def _evaluate_keyword_integration(self, article: ArticleDraft) -> SEOMetric:
        """Same as the base metric, but the full-density band is 0.8-1.5%
        (real top-10-page average) instead of 0.5-15% (keyword-stuffing territory)."""
        score = 0
        content_normalized = self._normalize_for_kw_match(article.content_html)
        unique_keywords = [kw for kw in article.metadata.keywords if isinstance(kw, str)]

        found_kws = sum(
            1 for kw in unique_keywords
            if self._normalize_for_kw_match(kw) in content_normalized
        )

        density = 0.0
        if article.word_count > 0:
            total_mentions = sum(
                content_normalized.count(self._normalize_for_kw_match(kw))
                for kw in unique_keywords
            )
            density = (total_mentions / article.word_count) * 100

            # Recalibrated band: 0.8-1.5% = real-world natural usage on ranking pages.
            if 0.8 <= density <= 1.5:
                score += 12
            elif 0.5 <= density < 0.8 or 1.5 < density <= 2.5:
                score += 8
            elif density > 0:
                score += 3  # some usage still beats none, but stuffing no longer scores well

        if unique_keywords:
            coverage_ratio = found_kws / len(unique_keywords)
            score += int(coverage_ratio * 8)

        feedback = f"Keywords: {found_kws}/{len(unique_keywords)} found (Density: {density:.2f}%, target 0.8-1.5%)."
        if score < 15:
            feedback += " Use target keywords naturally, don't over-repeat."

        return SEOMetric(name="Keyword Integration", score=score, weight=20, max_score=20, feedback=feedback)

    def _evaluate_location_keywords_capped(self, article: ArticleDraft, article_type: str) -> SEOMetric:
        """Base metric's logic, rescaled from a 20-point max to 5 (funds the E-E-A-T metric)."""
        base_metric = self._evaluate_location_keywords(article, article_type)
        capped_score = round(base_metric.score * 5 / 20)
        return SEOMetric(
            name=base_metric.name, score=capped_score, weight=5, max_score=5, feedback=base_metric.feedback
        )

    def _evaluate_specificity_scored(self, article: ArticleDraft) -> SEOMetric:
        """Turns the base class's pass/fail E-E-A-T gate into a real, scored metric
        so the writer/retry loop is actually rewarded for demonstrating expertise."""
        passed, feedback = self._evaluate_content_specificity(article)
        score = 15 if passed else 0
        return SEOMetric(
            name="Content Specificity (E-E-A-T)", score=score, weight=15, max_score=15, feedback=feedback
        )

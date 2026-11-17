from core.domains import site_domain
from typing import Dict, List, Any, Set
from urllib.parse import urlparse
import math
from modules.keywords.analyzer import KeywordAnalyzer
from modules.competitors.discovery import CompetitorDiscovery


class ContentGapStrategyEngine:
    """
    Content Gap & Strategy Engine (Step 12).
    Compares our site's keyword coverage with competitors' analyzed content
    using strict input validation and robust domain extraction.
    """

    def __init__(self, min_competitor_presence: int = 2):
        self.min_competitor_presence = self._validate_positive_int(min_competitor_presence, "min_competitor_presence")

    @staticmethod
    def _validate_positive_int(val: Any, name: str) -> int:
        """Strict integer validation preventing boolean, float truncation, or non-positive values."""
        if isinstance(val, bool):
            raise TypeError(f"Parameter '{name}' must be an integer, got bool.")
        
        if isinstance(val, float):
            if not val.is_integer():
                raise ValueError(f"Parameter '{name}' cannot be a float with decimals, got {val}.")
            val = int(val)
        
        if isinstance(val, str):
            stripped = val.strip()
            if not stripped.isdigit():
                raise ValueError(f"Parameter '{name}' must be a valid integer string, got '{val}'.")
            val = int(val)

        if not isinstance(val, int) or val <= 0:
            raise ValueError(f"Parameter '{name}' must be a positive integer greater than 0, got {val}.")
        
        return val

    @staticmethod
    def _extract_clean_domain(url: str) -> str:
        """Safely extracts clean root domain from a URL."""
        if not isinstance(url, str) or not CompetitorDiscovery._is_valid_url(url):
            return ""
        hostname = urlparse(url).hostname.lower().rstrip(".")
        return hostname[4:] if hostname.startswith("www.") else hostname

    @staticmethod
    def _extract_site_terms(our_tf_idf_results: Dict[Any, Dict[str, Any]], min_threshold: float = 0.01) -> Set[str]:
        """Extracts all terms strongly covered across our site based on validated schema."""
        if not isinstance(our_tf_idf_results, dict):
            raise TypeError("our_tf_idf_results must be a dictionary.")

        site_terms = set()
        for page_data in our_tf_idf_results.values():
            if not isinstance(page_data, dict):
                continue
            for term, metrics in page_data.items():
                if not isinstance(term, str):
                    continue
                if isinstance(metrics, dict):
                    score = metrics.get("tf_idf_score", 0.0)
                    if isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score) and score >= min_threshold:
                        site_terms.add(KeywordAnalyzer.normalize_keyword(term))
        return site_terms

    def analyze_gaps(
        self,
        our_tf_idf_results: Dict[Any, Dict[str, Any]],
        competitors_analysis: List[Dict[str, Any]],
        min_coverage_threshold: float = 0.01
    ) -> Dict[str, Any]:
        """
        Analyzes content gaps by comparing our keyword footprint with competitors'
        using robust domain aggregation and structural safeguards.
        """
        if not isinstance(competitors_analysis, list):
            raise TypeError("competitors_analysis must be a list.")

        if (isinstance(min_coverage_threshold, bool)
                or not isinstance(min_coverage_threshold, (int, float))
                or not math.isfinite(min_coverage_threshold) or min_coverage_threshold < 0):
            raise ValueError("min_coverage_threshold must be finite and non-negative.")
        our_terms = self._extract_site_terms(our_tf_idf_results, min_threshold=min_coverage_threshold)

        # جمع‌آوری دامنه‌های رقبا برای هر کلمه کلیدی (جلوگیری از شمارش تکراری چند صفحه از یک دامنه)
        competitor_keyword_map: Dict[str, Set[str]] = {}
        evidence = {}

        for comp in competitors_analysis:
            if not isinstance(comp, dict) or not comp.get("success", False):
                continue
            
            # استفاده از final_url یا url برای استخراج امن دامنه رقیب
            target_url = comp.get("final_url") or comp.get("url", "")
            comp_domain = site_domain(target_url) if self._extract_clean_domain(target_url) else ""
            if not comp_domain:
                continue

            keywords_analysis = comp.get("keywords_analysis", {})
            terms_found = []
            
            if isinstance(keywords_analysis, dict):
                # اگر فرمت دیکشنری کلمه -> متریک باشد
                for term, metrics in keywords_analysis.items():
                    if isinstance(term, str):
                        # بررسی اینکه رقیب هم پوشش معتبری روی این کلمه داشته باشد
                        score = metrics.get("tf_idf_score", 0.0) if isinstance(metrics, dict) else 0.0
                        if isinstance(score, (int, float)) and not isinstance(score, bool) and math.isfinite(score) and score >= min_coverage_threshold:
                            terms_found.append(term)
            elif isinstance(keywords_analysis, list):
                for item in keywords_analysis:
                    if isinstance(item, dict):
                        term = item.get("term", "")
                        if isinstance(term, str):
                            terms_found.append(term)

            for term in terms_found:
                clean_term = KeywordAnalyzer.normalize_keyword(term)
                if len(clean_term) < 3:
                    continue

                if clean_term not in competitor_keyword_map:
                    competitor_keyword_map[clean_term] = set()
                
                competitor_keyword_map[clean_term].add(comp_domain)
                evidence.setdefault(clean_term, set()).add(target_url)

        overlap_keywords = []
        content_gaps = []

        for term, domains_set in competitor_keyword_map.items():
            presence_count = len(domains_set)
            comp_domains_list = sorted(domains_set)

            if term in our_terms:
                overlap_keywords.append({
                    "term": term,
                    "evidence_urls": sorted(evidence[term]),
                    "competitor_domains_count": presence_count,
                    "competitor_domains": comp_domains_list,
                    "keyword": term,
                    "competitors_count": presence_count,
                    "competing_domains": comp_domains_list,
                    "status": "Direct Overlap"
                })
            else:
                if presence_count >= self.min_competitor_presence:
                    # امتیاز اولویت داخلی آماری (Heuristic Priority)
                    heuristic_priority = "High (Statistical)" if presence_count >= 3 else "Medium (Statistical)"
                    content_gaps.append({
                        "term": term,
                        "evidence_urls": sorted(evidence[term]),
                        "competitor_domains_count": presence_count,
                        "competitor_domains": comp_domains_list,
                        "keyword": term,
                        "competitors_count": presence_count,
                        "competing_domains": comp_domains_list,
                        "priority": heuristic_priority,
                        "recommended_action": "Review existing coverage before expanding a page or creating content.",
                        "heuristic_priority": heuristic_priority,
                        "recommendation": "Potential content gap identified. Review for new content creation or page expansion."
                    })

        # مرتب‌سازی شکاف‌ها بر اساس تعداد دامنه‌های رقیب (نزولی) و سپس الفبای کلمه
        content_gaps.sort(key=lambda x: (-x["competitors_count"], x["keyword"]))
        overlap_keywords.sort(key=lambda x: (-x["competitors_count"], x["keyword"]))

        return {
            "total_competitor_terms_analyzed": len(competitor_keyword_map),
            "keyword_overlaps_count": len(overlap_keywords),
            "content_gaps_count": len(content_gaps),
            "content_gaps": content_gaps,
            "keyword_overlaps": overlap_keywords
        }
import copy
import math
from typing import Dict, List, Any, Set


class KeywordOpportunityEngine:
    """
    Advanced algorithmic SEO Opportunity Engine (Non-AI).
    Implements robust data type/nan/inf validation, strict immutability,
    consistent coverage thresholds, and cluster structural integrity checks.
    """

    def __init__(
        self,
        min_tf_idf: float = 0.02,
        min_frequency: int = 2,
        max_doc_frequency_ratio: float = 0.85,
        min_coverage_tf_idf: float = 0.01
    ):
        self.min_tf_idf = float(min_tf_idf)
        self.min_frequency = int(min_frequency)
        self.max_doc_frequency_ratio = float(max_doc_frequency_ratio)
        self.min_coverage_tf_idf = float(min_coverage_tf_idf)

    @staticmethod
    def _validate_numeric(val: Any, name: str, allow_float: bool = True, non_negative: bool = True) -> float:
        """Helper to validate numeric inputs against None, types, NaN, and Inf."""
        if val is None:
            raise TypeError(f"Parameter '{name}' cannot be None.")
        
        try:
            if allow_float:
                num = float(val)
            else:
                if isinstance(val, float) and not val.is_integer():
                    raise ValueError(f"Parameter '{name}' must be an integer, got float {val}.")
                num = int(val)
        except (ValueError, TypeError) as e:
            raise TypeError(f"Parameter '{name}' must be a valid number, got {type(val).__name__} ({val}).") from e

        if math.isnan(num) or math.isinf(num):
            raise ValueError(f"Parameter '{name}' cannot be NaN or Infinity.")
        
        if non_negative and num < 0:
            raise ValueError(f"Parameter '{name}' must be non-negative, got {num}.")

        return num

    def filter_noise(
        self,
        prioritized_opportunities: List[Dict[str, Any]],
        total_docs: int
    ) -> List[Dict[str, Any]]:
        """
        1. Noise Filter (Strict Validation & Type Safety):
        Validates total_docs, pages_count, frequencies, and scores explicitly.
        """
        valid_total_docs = int(self._validate_numeric(total_docs, "total_docs", allow_float=False, non_negative=False))
        if valid_total_docs <= 0:
            raise ValueError(f"Invalid total_docs: {valid_total_docs}. Must be greater than 0.")

        filtered = []
        for opp in prioritized_opportunities:
            if not isinstance(opp, dict):
                raise TypeError(f"Opportunity item must be a dict, got {type(opp).__name__}.")

            tf_idf = self._validate_numeric(opp.get("total_tf_idf", 0.0), "total_tf_idf", non_negative=True)
            freq = int(self._validate_numeric(opp.get("total_frequency", 0), "total_frequency", allow_float=False, non_negative=True))
            pages_count = int(self._validate_numeric(opp.get("pages_count", 1), "pages_count", allow_float=False, non_negative=True))

            if pages_count <= 0:
                raise ValueError(f"Invalid pages_count: {pages_count} for keyword '{opp.get('keyword')}'. Must be >= 1.")
            if pages_count > valid_total_docs:
                raise ValueError(f"Data integrity error: pages_count ({pages_count}) cannot exceed total_docs ({valid_total_docs}).")

            if tf_idf < self.min_tf_idf or freq < self.min_frequency:
                continue

            doc_ratio = pages_count / valid_total_docs
            avg_tf_idf_per_doc = tf_idf / pages_count
            
            if doc_ratio > self.max_doc_frequency_ratio and avg_tf_idf_per_doc < self.min_tf_idf:
                continue

            filtered.append(copy.deepcopy(opp))

        return filtered

    @staticmethod
    def score_opportunities(viable_opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        2. Opportunity Scorer (Immutable & Type Safe):
        Computes internal statistical priority score without mutating inputs.
        """
        scored = []
        for opp in viable_opportunities:
            new_opp = copy.deepcopy(opp)
            tf_idf = KeywordOpportunityEngine._validate_numeric(new_opp.get("total_tf_idf", 0.0), "total_tf_idf", non_negative=True)
            pages_count = int(KeywordOpportunityEngine._validate_numeric(new_opp.get("pages_count", 1), "pages_count", allow_float=False, non_negative=True))

            distribution_bonus = min(pages_count, 4) * 0.2
            opportunity_score = tf_idf * (1.0 + distribution_bonus)

            new_opp["opportunity_score"] = round(opportunity_score, 4)
            scored.append(new_opp)

        scored.sort(key=lambda x: x["opportunity_score"], reverse=True)
        return scored

    def detect_content_gaps(
        self,
        tf_idf_results: Dict[int, Dict[str, Dict[str, Any]]],
        top_opportunities: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        3. Content Gap Detector (Review Recommendation):
        Flags potential coverage gaps using token overlap.
        """
        if not isinstance(tf_idf_results, dict):
            raise TypeError("tf_idf_results must be a dictionary.")

        gaps_report = {}

        for page_id, page_keywords in tf_idf_results.items():
            if not isinstance(page_keywords, dict):
                continue

            strong_page_terms = {
                term for term, metrics in page_keywords.items()
                if isinstance(metrics, dict) and self._validate_numeric(metrics.get("tf_idf_score", 0.0), "tf_idf_score", non_negative=True) >= self.min_coverage_tf_idf
            }
            
            page_tokens: Set[str] = set()
            for term in strong_page_terms:
                for token in term.split():
                    if len(token) > 2:
                        page_tokens.add(token)

            page_gaps = []
            for opp in top_opportunities:
                term = opp.get("keyword", "")
                if not term:
                    continue
                term_tokens = {t for t in term.split() if len(t) > 2}

                if term in strong_page_terms:
                    continue

                overlap = term_tokens.intersection(page_tokens)
                if overlap:
                    page_gaps.append({
                        "keyword": term,
                        "gap_type": "Content Review Recommendation / Potential Weak Coverage",
                        "shared_tokens": list(overlap),
                        "opportunity_score": opp.get("opportunity_score", 0.0)
                    })

            gaps_report[str(page_id)] = page_gaps

        return gaps_report

    def detect_new_topics(
        self,
        clusters: List[Dict[str, Any]],
        tf_idf_results: Dict[int, Dict[str, Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        4. New Topic Detector (Strict Cluster Validation & Consistent Threshold):
        Uses min_coverage_tf_idf and validates cluster structural integrity.
        """
        if not isinstance(clusters, list):
            raise TypeError("clusters must be a list.")

        all_strong_terms: Set[str] = set()
        for page_keywords in tf_idf_results.values():
            if not isinstance(page_keywords, dict):
                continue
            for term, metrics in page_keywords.items():
                if isinstance(metrics, dict):
                    score = self._validate_numeric(metrics.get("tf_idf_score", 0.0), "tf_idf_score", non_negative=True)
                    if score >= self.min_coverage_tf_idf:
                        all_strong_terms.add(term)

        new_topic_opportunities = []

        for cluster in clusters:
            if not isinstance(cluster, dict):
                raise TypeError(f"Cluster item must be a dict, got {type(cluster).__name__}.")

            primary_kw = cluster.get("primary_keyword")
            if not primary_kw or not isinstance(primary_kw, str):
                raise ValueError(f"Cluster missing valid string 'primary_keyword': {primary_kw}")

            secondary_kws = cluster.get("secondary_keywords", [])
            if not isinstance(secondary_kws, list):
                raise TypeError(f"Cluster 'secondary_keywords' must be a list, got {type(secondary_kws).__name__}.")
            
            # جلوگیری از تکرار کلمات فرعی و حذف کلمات خالی
            deduplicated_secondary = list(dict.fromkeys([kw for kw in secondary_kws if isinstance(kw, str) and kw.strip()]))

            total_score = self._validate_numeric(cluster.get("total_score", 0.0), "total_score", non_negative=True)

            primary_covered = 1 if primary_kw in all_strong_terms else 0

            if not deduplicated_secondary:
                weighted_coverage = float(primary_covered)
            else:
                secondary_covered = sum(1 for kw in deduplicated_secondary if kw in all_strong_terms)
                total_weight = 2.0 + len(deduplicated_secondary)
                weighted_coverage = (primary_covered * 2.0 + secondary_covered) / total_weight

            if weighted_coverage < 0.4:
                new_topic_opportunities.append({
                    "cluster_name": cluster.get("cluster_name", primary_kw.title()),
                    "primary_keyword": primary_kw,
                    "weighted_coverage": round(weighted_coverage, 2),
                    "recommendation": "Create a new dedicated landing page or content pillar for this cluster.",
                    "total_score": total_score
                })

        new_topic_opportunities.sort(key=lambda x: x["total_score"], reverse=True)
        return new_topic_opportunities
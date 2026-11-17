from typing import Dict, List, Any, Optional
from urllib.parse import urlparse


class ContentGapStrategyEngine:
    """
    Enterprise-grade Content Gap & Strategy Engine (Step 12).
    Identifies content gaps and keyword overlaps between our site and competitors
    using strict algorithmic rules, unique domain counting, and heuristic scoring.
    """

    def __init__(self, min_competitor_presence: int = 2):
        self.min_competitor_presence = self._validate_positive_int(
            min_competitor_presence, "min_competitor_presence"
        )

    @staticmethod
    def _validate_positive_int(val: Any, name: str) -> int:
        """Strict integer validation preventing silent float truncation or bool acceptance."""
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
    def _extract_domain(url: str) -> str:
        """Extracts a clean, normalized domain from a given URL."""
        if not url or not isinstance(url, str):
            return ""
        try:
            parsed = urlparse(url.strip())
            hostname = parsed.hostname or ""
            if not hostname:
                # اگر URL بدون http:// یا طرح باشد
                parsed_fallback = urlparse("http://" + url.strip())
                hostname = parsed_fallback.hostname or ""
            
            hostname = hostname.lower().strip().rstrip(".")
            if hostname.startswith("www."):
                hostname = hostname[4:]
            return hostname
        except Exception:
            return ""

    @staticmethod
    def _normalize_term(term: str) -> str:
        """Normalizes terms/keywords for consistent matching (lowercase, whitespace collapse)."""
        if not term or not isinstance(term, str):
            return ""
        return " ".join(term.strip().lower().split())

    def _extract_site_terms(self, our_tf_idf_results: Any, tf_idf_threshold: float = 0.01) -> set:
        """Extracts terms from our site's TF-IDF analysis meeting the threshold."""
        site_terms = set()
        
        if not our_tf_idf_results:
            return site_terms

        # پشتیبانی از ساختارهای مختلف خروجی TF-IDF (لیست دیکشنری یا دیکشنری کلید-مقدار)
        if isinstance(our_tf_idf_results, list):
            for item in our_tf_idf_results:
                if isinstance(item, dict):
                    term = item.get("term") or item.get("keyword") or item.get("word")
                    score = item.get("score") or item.get("tf_idf") or 0.0
                    if term and score >= tf_idf_threshold:
                        norm = self._normalize_term(term)
                        if norm:
                            site_terms.add(norm)
        elif isinstance(our_tf_idf_results, dict):
            for term, data in our_tf_idf_results.items():
                score = 0.0
                if isinstance(data, (int, float)):
                    score = float(data)
                elif isinstance(data, dict):
                    score = data.get("score") or data.get("tf_idf") or 0.0
                
                if score >= tf_idf_threshold:
                    norm = self._normalize_term(str(term))
                    if norm:
                        site_terms.add(norm)

        return site_terms

    def analyze_gaps(
        self, 
        our_tf_idf_results: Any, 
        competitors_analysis: List[Dict[str, Any]], 
        tf_idf_threshold: float = 0.01
    ) -> Dict[str, Any]:
        """
        Analyzes content gaps and overlaps by comparing our site terms against competitors' terms,
        ensuring unique domain counting and robust heuristic prioritization.
        """
        if not isinstance(competitors_analysis, list):
            raise TypeError("competitors_analysis must be a list of competitor analysis dictionaries.")

        # ۱. استخراج کلمات کلیدی سایت خودی
        our_terms = self._extract_site_terms(our_tf_idf_results, tf_idf_threshold)

        # ۲. تجمیع و نگاشت ترم‌های رقبا به همراه دامنه‌های یکتا و شواهد (URLها)
        # ساختار دیکشنری ترم: { normalized_term: { "display_term": ..., "domains": set(), "evidence_urls": [] } }
        competitor_term_mapping = {}

        for comp in competitors_analysis:
            if not isinstance(comp, dict) or not comp.get("success", False):
                continue

            comp_url = comp.get("final_url") or comp.get("url", "")
            domain = self._extract_domain(comp_url)
            if not domain:
                continue

            # استخراج کلمات کلیدی رقیب (از بخش keywords_analysis یا raw_text در صورت وجود)
            kw_analysis = comp.get("keywords_analysis", [])
            
            # استخراج ترم‌ها از خروجی رقیب
            comp_terms_list = []
            if isinstance(kw_analysis, list):
                for kw_item in kw_analysis:
                    if isinstance(kw_item, dict):
                        t = kw_item.get("term") or kw_item.get("keyword") or kw_item.get("word")
                        if t:
                            comp_terms_list.append(t)
                    elif isinstance(kw_item, str):
                        comp_terms_list.append(kw_item)
            elif isinstance(kw_analysis, dict):
                comp_terms_list.extend(kw_analysis.keys())

            # اگر تحلیل‌گر کلمات کلیدی برای رقیب نبود، از کلمات متن اصلی به عنوان پشتیبان استفاده شود
            if not comp_terms_list:
                raw_text = comp.get("raw_text", "")
                if raw_text and isinstance(raw_text, str):
                    # استخراج ساده واژگان معتبر یا کلمات کلیدی پایه
                    words = [w.strip(".,;:!?()[]{}<>\"'") for w in raw_text.split()]
                    comp_terms_list = [w for w in words if len(w) > 3]

            for raw_term in comp_terms_list:
                norm_term = self._normalize_term(str(raw_term))
                if not norm_term or len(norm_term) < 2:
                    continue

                if norm_term not in competitor_term_mapping:
                    competitor_term_mapping[norm_term] = {
                        "display_term": raw_term.strip(),
                        "domains": set(),
                        "evidence_urls": []
                    }

                # شمارش یکتای دامنه برای هر ترم
                competitor_term_mapping[norm_term]["domains"].add(domain)
                if comp_url and comp_url not in competitor_term_mapping[norm_term]["evidence_urls"]:
                    competitor_term_mapping[norm_term]["evidence_urls"].append(comp_url)

        content_gaps = []
        keyword_overlaps = []

        # ۳. دسته‌بندی به صورت Overlap یا Content Gap
        for norm_term, data in competitor_term_mapping.items():
            unique_competitor_count = len(data["domains"])
            
            item_record = {
                "term": data["display_term"],
                "normalized_term": norm_term,
                "competitor_domains_count": unique_competitor_count,
                "competitor_domains": list(data["domains"]),
                "evidence_urls": data["evidence_urls"]
            }

            # اگر ترم در سایت خودی هم وجود داشته باشد -> هم‌پوشانی (Overlap)
            if norm_term in our_terms:
                keyword_overlaps.append(item_record)
            else:
                # اگر در سایت خودی نباشد و حضور رقبا به حد نصاب رسیده باشد -> شکاف محتوایی (Content Gap)
                if unique_competitor_count >= self.min_competitor_presence:
                    # تعیین اولویت الگوریتمی و پیشنهاد اجرایی بر اساس تعداد رقبا
                    if unique_competitor_count >= 4:
                        priority = "High"
                        recommended_action = "Create dedicated high-priority page or comprehensive guide"
                    elif unique_competitor_count == 3:
                        priority = "Medium"
                        recommended_action = "Create new page or expand existing content section"
                    else:
                        priority = "Low"
                        recommended_action = "Consider covering in relevant supporting articles"

                    item_record["priority"] = priority
                    item_record["recommended_action"] = recommended_action
                    content_gaps.append(item_record)

        # ۴. مرتب‌سازی شکاف‌های محتوایی بر اساس تعداد دامنه‌های رقیب (نزولی) و سپس الفبای ترم
        content_gaps.sort(
            key=lambda x: (-x["competitor_domains_count"], x["term"])
        )

        keyword_overlaps.sort(
            key=lambda x: (-x["competitor_domains_count"], x["term"])
        )

        return {
            "total_competitor_terms_analyzed": len(competitor_term_mapping),
            "our_site_terms_count": len(our_terms),
            "content_gaps_count": len(content_gaps),
            "keyword_overlaps_count": len(keyword_overlaps),
            "content_gaps": content_gaps,
            "keyword_overlaps": keyword_overlaps
        }
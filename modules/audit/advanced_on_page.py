from typing import Dict, List, Any, Set
from urllib.parse import urlparse


class AdvancedOnPageAnalyzer:
    """
    Advanced On-Page SEO Analysis Engine (Step 14).
    Performs keyword cannibalization detection, title-to-content alignment checks,
    and heading structure depth evaluation (Non-AI).
    """

    @staticmethod
    def _normalize_term(term: str) -> str:
        """Normalizes terms for robust matching."""
        if not term or not isinstance(term, str):
            return ""
        return " ".join(term.strip().lower().split())

    def detect_keyword_cannibalization(self, pages_keywords_map: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detects Keyword Cannibalization: identifies when multiple distinct pages 
        on our site are targeting or heavily featuring the exact same keyword/term.
        
        Expected input format per page:
        {
            "url": "https://example.com/page1",
            "keywords": [{"term": "seo tools", "score": 0.05}, ...] or ["seo tools", ...]
        }
        """
        if not isinstance(pages_keywords_map, list):
            raise TypeError("pages_keywords_map must be a list of page keyword data dictionaries.")

        # نگاشت ترم به مجموعه‌ای از URLها و امتیازات آن‌ها
        # { normalized_term: { display_term: str, urls: {url: score} } }
        term_page_registry = {}

        for page_entry in pages_keywords_map:
            if not isinstance(page_entry, dict):
                continue
            
            url = page_entry.get("url") or page_entry.get("final_url")
            if not url:
                continue

            keywords = page_entry.get("keywords", [])
            if not isinstance(keywords, (list, dict)):
                continue

            # استخراج ترم‌ها و امتیازات
            extracted_terms = []
            if isinstance(keywords, list):
                for kw in keywords:
                    if isinstance(kw, dict):
                        t = kw.get("term") or kw.get("keyword") or kw.get("word")
                        s = kw.get("score") or kw.get("tf_idf") or 0.0
                        if t:
                            extracted_terms.append((t, float(s)))
                    elif isinstance(kw, str):
                        extracted_terms.append((kw, 1.0))
            elif isinstance(keywords, dict):
                for t, s in keywords.items():
                    score_val = float(s.get("score", 1.0)) if isinstance(s, dict) else float(s)
                    extracted_terms.append((str(t), score_val))

            for term_str, score in extracted_terms:
                norm = self._normalize_term(term_str)
                if not norm or len(norm) < 3:
                    continue

                if norm not in term_page_registry:
                    term_page_registry[norm] = {
                        "display_term": term_str.strip(),
                        "pages": {}
                    }
                
                term_page_registry[norm]["pages"][url] = score

        cannibalization_issues = []

        # شناسایی مواردی که بیش از یک صفحه روی یک ترم رقابت می‌کنند
        for norm_term, data in term_page_registry.items():
            pages_dict = data["pages"]
            if len(pages_dict) > 1:
                # مرتب‌سازی صفحات بر اساس امتیاز (نزولی)
                sorted_pages = sorted(
                    [{"url": u, "score": sc} for u, sc in pages_dict.items()],
                    key=lambda x: -x["score"]
                )

                cannibalization_issues.append({
                    "rule_id": "KEYWORD_CANNIBALIZATION",
                    "category": "On-Page Cannibalization",
                    "severity": "Medium",
                    "title": f"Keyword Cannibalization Detected: '{data['display_term']}'",
                    "description": f"The term appears with significant weight across {len(pages_dict)} different pages, potentially causing internal competition in SERPs.",
                    "term": data["display_term"],
                    "competing_pages_count": len(pages_dict),
                    "competing_pages": sorted_pages,
                    "recommendation": "Consolidate content, implement canonical tags pointing to the primary landing page, or differentiate target keywords."
                })

        # مرتب‌سازی بر اساس تعداد صفحات رقیب (نزولی)
        cannibalization_issues.sort(key=lambda x: -x["competing_pages_count"])
        return cannibalization_issues

    def analyze_title_content_relevance(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyzes the semantic alignment and overlap between the Page Title, 
        H1 headings, and the body text.
        """
        if not isinstance(page_data, dict):
            return {"relevance_score": 0.0, "issues": []}

        url = page_data.get("url") or page_data.get("final_url", "unknown")
        structure = page_data.get("structure", page_data)
        
        title = structure.get("title", "")
        h1_list = structure.get("h1", [])
        if isinstance(h1_list, str):
            h1_list = [h1_list]
        body_text = structure.get("raw_text", "") or page_data.get("raw_text", "")

        issues = []
        if not title:
            return {"relevance_score": 0.0, "issues": [{"rule_id": "TITLE_MISSING", "message": "Title is missing."}]}

        # استخراج کلمات کلیدی یا واژگان معنادار از Title (کلمات بزرگتر از 3 کاراکتر)
        title_words = {w.strip(".,;:!?()[]{}<>\"'") for w in title.lower().split() if len(w.strip(".,;:!?()[]{}<>\"'")) > 3}
        if not title_words:
            return {"relevance_score": 1.0, "issues": []}

        body_lower = body_text.lower()
        
        # بررسی حضور واژگان Title در بدنه متن یا H1
        matched_words = 0
        h1_text_combined = " ".join([h.lower() for h in h1_list])

        for word in title_words:
            in_body = word in body_lower
            in_h1 = word in h1_text_combined
            if in_body or in_h1:
                matched_words += 1

        relevance_ratio = matched_words / len(title_words) if title_words else 1.0

        if relevance_ratio < 0.4:
            issues.append({
                "rule_id": "TITLE_CONTENT_MISMATCH",
                "category": "On-Page Relevance",
                "severity": "Medium",
                "title": "Low Title-to-Content Relevance",
                "description": f"Key terms from the title have weak representation in the page body or H1 (relevance ratio: {relevance_ratio:.2f}).",
                "url": url,
                "evidence": {"title": title, "relevance_ratio": round(relevance_ratio, 2)},
                "recommendation": "Ensure the core topic mentioned in the title is thoroughly discussed in the H1 and body paragraphs."
            })

        return {
            "url": url,
            "relevance_score": round(relevance_ratio, 2),
            "issues": issues
        }
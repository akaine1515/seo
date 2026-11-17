import math
import re
from typing import Dict, List, Any


class KeywordAnalyzer:
    """
    Analyzes extracted keywords using statistical methods, TF-IDF,
    rule-based search intent detection, and opportunity prioritization (Non-AI).
    """

    @staticmethod
    def normalize_keyword(keyword: str) -> str:
        """
        Normalizes a keyword/phrase by cleaning spaces and standardizing characters.
        """
        if not keyword or not isinstance(keyword, str):
            return ""

        # استانداردسازی حروف عربی و فارسی (ک/ك، ی/ي/ى)
        normalized = keyword.strip().lower()
        normalized = normalized.replace('ك', 'ک').replace('ي', 'ی').replace('ى', 'ی')
        
        # حذف فاصله و خطاهای نگارشی داخلی اضافی
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    @staticmethod
    def detect_search_intent(keyword: str) -> str:
        """
        Rule-based detection of search intent (Transactional, Commercial, Informational, Navigational).
        """
        kw = keyword.lower()

        # نیت خرید / تراکنشی
        transactional_triggers = {"خرید", "فروش", "قیمت", "دانلود", "سفارش", "ارزان", "تعرفه", "استخدام"}
        if any(trigger in kw for trigger in transactional_triggers):
            return "transactional"

        # نیت تجاری / مقایسه‌ای
        commercial_triggers = {"بهترین", "مقایسه", "نقد", "بررسی", "ویژگی", "مدل", "تفاوت"}
        if any(trigger in kw for trigger in commercial_triggers):
            return "commercial"

        # نیت آموزشی / اطلاعاتی
        informational_triggers = {"چگونه", "چیست", "آموزش", "راهنما", "چرا", "روش", "تعریف", "علت"}
        if any(trigger in kw for trigger in informational_triggers) or kw.startswith("چ"):
            return "informational"

        # پیش‌فرض: اطلاعاتی/عمومی
        return "informational"

    def compute_tf_idf(self, extracted_pages_data: Dict[int, Dict[str, Any]]) -> Dict[int, Dict[str, Dict[str, Any]]]:
        """
        Computes Term Frequency (TF) and Inverse Document Frequency (IDF) 
        for keywords across the crawled pages.
        
        extracted_pages_data format:
        {
            page_id: {
                "url": str,
                "unigrams": {word: freq, ...},
                "bigrams": {phrase: freq, ...},
                "total_tokens": int
            }
        }
        """
        total_docs = len(extracted_pages_data)
        if total_docs == 0:
            return {}

        # 1. محاسبه Document Frequency (DF): تعداد اسنادی که هر کلمه در آن‌ها تکرار شده است
        df_counts = {}
        for page_data in extracted_pages_data.values():
            combined_terms = {}
            combined_terms.update(page_data.get("unigrams", {}))
            combined_terms.update(page_data.get("bigrams", {}))

            for term in combined_terms.keys():
                norm_term = self.normalize_keyword(term)
                if norm_term:
                    df_counts[norm_term] = df_counts.get(norm_term, 0) + 1

        # 2. محاسبه TF-IDF برای هر صفحه
        tf_idf_results = {}

        for page_id, page_data in extracted_pages_data.values():
            page_tf_idf = {}
            total_tokens = page_data.get("total_tokens", 1) or 1
            
            combined_terms = {}
            combined_terms.update(page_data.get("unigrams", {}))
            combined_terms.update(page_data.get("bigrams", {}))

            for term, raw_freq in combined_terms.items():
                norm_term = self.normalize_keyword(term)
                if not norm_term:
                    continue

                # محاسبه Term Frequency (TF) = فراوانی خام / کل کلمات سند
                tf = raw_freq / total_tokens

                # محاسبه Inverse Document Frequency (IDF) = log(کل اسناد / تعداد اسناد حاوی کلمه) + 1
                doc_freq = df_counts.get(norm_term, 1)
                idf = math.log((total_docs / doc_freq) + 1) + 1

                # امتیاز نهایی TF-IDF
                score = tf * idf
                page_tf_idf[norm_term] = {
                    "raw_frequency": raw_freq,
                    "tf": tf,
                    "idf": idf,
                    "tf_idf_score": score,
                    "intent": self.detect_search_intent(norm_term)
                }

            tf_idf_results[page_id] = page_tf_idf

        return tf_idf_results

    @staticmethod
    def prioritize_opportunities(tf_idf_results: Dict[int, Dict[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Aggregates and prioritizes keyword opportunities across all pages
        based on TF-IDF scores, raw frequency, and search intent.
        """
        all_opportunities = {}

        for page_id, page_keywords in tf_idf_results.items():
            for term, metrics in page_keywords.items():
                score = metrics.get("tf_idf_score", 0)
                freq = metrics.get("raw_frequency", 0)
                intent = metrics.get("intent", "informational")

                if term not in all_opportunities:
                    all_opportunities[term] = {
                        "keyword": term,
                        "total_tf_idf": score,
                        "total_frequency": freq,
                        "pages_count": 1,
                        "intent": intent
                    }
                else:
                    all_opportunities[term]["total_tf_idf"] += score
                    all_opportunities[term]["total_frequency"] += freq
                    all_opportunities[term]["pages_count"] += 1

        # تبدیل به لیست و مرتب‌سازی بر اساس امتیاز نهایی (اولویت‌بندی فرصت‌ها)
        opportunities_list = list(all_opportunities.values())
        opportunities_list.sort(
            key=lambda x: (x["total_tf_idf"], x["total_frequency"]),
            reverse=True
        )

        return opportunities_list
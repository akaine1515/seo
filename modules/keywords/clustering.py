from typing import Dict, List, Any


class KeywordClustering:
    """
    Groups related keywords into Topic Clusters using token overlap
    and shared root/unigram patterns (Non-AI, Algorithmic).
    """

    @staticmethod
    def cluster_keywords(analyzed_keywords: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clusters a dictionary of analyzed keywords into topic groups.
        
        analyzed_keywords format:
        {
            "keyword_phrase": {
                "raw_frequency": int,
                "tf_idf_score": float,
                "intent": str
            },
            ...
        }
        """
        if not analyzed_keywords:
            return []

        # مرتب‌سازی کلمات بر اساس امتیاز TF-IDF و فراوانی (از زیاد به کم)
        sorted_keywords = sorted(
            analyzed_keywords.items(),
            key=lambda x: (x[1].get("tf_idf_score", 0), x[1].get("raw_frequency", 0)),
            reverse=True
        )

        clusters = []
        assigned_keywords = set()

        for kw, metrics in sorted_keywords:
            if kw in assigned_keywords:
                continue

            # ایجاد یک خوشه جدید با این کلمه به عنوان هسته اصلی (Primary Keyword)
            current_cluster_members = [kw]
            assigned_keywords.add(kw)

            kw_tokens = set(kw.split())

            # جستجو برای یافتن کلمات مرتبط دیگر که کلمات مشترک دارند
            for other_kw, other_metrics in sorted_keywords:
                if other_kw in assigned_keywords:
                    continue

                other_tokens = set(other_kw.split())
                
                # بررسی اشتراک توکن‌ها یا ریشه‌ها
                intersection = kw_tokens.intersection(other_tokens)
                if intersection or any(token in other_kw for token in kw_tokens if len(token) > 2):
                    current_cluster_members.append(other_kw)
                    assigned_keywords.add(other_kw)

            # انتخاب کلمه اصلی خوشه و کلمات فرعی
            primary_keyword = current_cluster_members[0]
            secondary_keywords = current_cluster_members[1:]

            # تعیین نیت جستجوی غالب خوشه
            cluster_intent = analyzed_keywords.get(primary_keyword, {}).get("intent", "informational")

            clusters.append({
                "cluster_name": primary_keyword.title(),
                "primary_keyword": primary_keyword,
                "secondary_keywords": secondary_keywords,
                "cluster_size": len(current_cluster_members),
                "intent": cluster_intent,
                "total_score": sum(analyzed_keywords.get(k, {}).get("tf_idf_score", 0) for k in current_cluster_members)
            })

        # مرتب‌سازی خوشه‌ها بر اساس مجموع امتیازات
        clusters.sort(key=lambda x: x["total_score"], reverse=True)
        return clusters
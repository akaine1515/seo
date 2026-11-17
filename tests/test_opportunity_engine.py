import unittest
import math
from modules.keywords.opportunity import KeywordOpportunityEngine


class TestKeywordOpportunityEngine(unittest.TestCase):

    def setUp(self):
        self.engine = KeywordOpportunityEngine(
            min_tf_idf=0.01,
            min_frequency=1,
            max_doc_frequency_ratio=0.85,
            min_coverage_tf_idf=0.02
        )

    def test_1_total_docs_zero(self):
        """سناریوی ۱: total_docs = 0 باید خطای ValueError بدهد."""
        with self.assertRaises(ValueError):
            self.engine.filter_noise([{"keyword": "gis", "total_tf_idf": 0.05, "total_frequency": 3, "pages_count": 1}], total_docs=0)

    def test_2_pages_count_zero(self):
        """سناریوی ۲: pages_count = 0 باید خطای ValueError بدهد."""
        with self.assertRaises(ValueError):
            self.engine.filter_noise([{"keyword": "gis", "total_tf_idf": 0.05, "total_frequency": 3, "pages_count": 0}], total_docs=10)

    def test_3_pages_count_exceeds_total_docs(self):
        """سناریوی ۳: pages_count > total_docs باید خطای ValueError بدهد."""
        with self.assertRaises(ValueError):
            self.engine.filter_noise([{"keyword": "gis", "total_tf_idf": 0.05, "total_frequency": 3, "pages_count": 15}], total_docs=10)

    def test_4_immutability(self):
        """سناریوی ۴: بررسی عدم تغییر داده ورودی پس از اجرای توابع."""
        original_opps = [
            {"keyword": "gis analysis", "total_tf_idf": 0.08, "total_frequency": 4, "pages_count": 2}
        ]
        # کپی برای مقایسه
        snapshot = [dict(item) for item in original_opps]

        filtered = self.engine.filter_noise(original_opps, total_docs=10)
        scored = self.engine.score_opportunities(filtered)

        # بررسی اینکه دیکشنری‌های ورودی دست‌نخورده باقی مانده‌اند
        self.assertEqual(original_opps, snapshot)

    def test_5_cluster_no_secondary_full_primary(self):
        """سناریوی ۵: خوشه بدون کلمه فرعی با پوشش کامل کلمه اصلی."""
        clusters = [
            {
                "primary_keyword": "python seo",
                "secondary_keywords": [],
                "total_score": 5.0
            }
        ]
        tf_idf_results = {
            1: {"python seo": {"tf_idf_score": 0.05}}  # پوشش قوی (بالاتر از min_coverage_tf_idf=0.02)
        }
        new_topics = self.engine.detect_new_topics(clusters, tf_idf_results)
        # چون پوشش کامل است، نباید به عنوان تاپیک جدید پیشنهاد شود
        self.assertEqual(len(new_topics), 0)

    def test_6_cluster_no_primary_coverage(self):
        """سناریوی ۶: خوشه بدون پوشش کلمه اصلی (باید به عنوان تاپیک جدید شناسایی شود)."""
        clusters = [
            {
                "primary_keyword": "machine learning seo",
                "secondary_keywords": ["ml optimization"],
                "total_score": 8.0
            }
        ]
        tf_idf_results = {
            1: {"unrelated term": {"tf_idf_score": 0.05}}
        }
        new_topics = self.engine.detect_new_topics(clusters, tf_idf_results)
        self.assertEqual(len(new_topics), 1)
        self.assertEqual(new_topics[0]["primary_keyword"], "machine learning seo")

    def test_7_cluster_full_coverage(self):
        """سناریوی ۷: خوشه با پوشش کامل کلمات اصلی و فرعی (نباید پیشنهاد شود)."""
        clusters = [
            {
                "primary_keyword": "gis software",
                "secondary_keywords": ["mapping tool", "spatial analysis"],
                "total_score": 10.0
            }
        ]
        tf_idf_results = {
            1: {
                "gis software": {"tf_idf_score": 0.04},
                "mapping tool": {"tf_idf_score": 0.03},
                "spatial analysis": {"tf_idf_score": 0.03}
            }
        }
        new_topics = self.engine.detect_new_topics(clusters, tf_idf_results)
        self.assertEqual(len(new_topics), 0)

    def test_8_content_gap_detection(self):
        """سناریوی ۸: تشخیص Content Gap برای صفحه مرتبط و عدم پیشنهاد برای صفحه نامرتبط."""
        top_opps = [
            {"keyword": "gis mapping tutorial", "opportunity_score": 1.5}
        ]
        tf_idf_results = {
            1: {"gis basics": {"tf_idf_score": 0.03}},  # مرتبط (دارای توکن مشترک 'gis')
            2: {"cooking recipe": {"tf_idf_score": 0.05}}  # کاملاً نامرتبط
        }
        gaps = self.engine.detect_content_gaps(tf_idf_results, top_opps)
        
        # صفحه 1 باید gap داشته باشد (اشتراک توکن gis)
        self.assertTrue(len(gaps["1"]) > 0)
        # صفحه 2 نباید gap داشته باشد
        self.assertEqual(len(gaps["2"]), 0)

    def test_9_invalid_inputs_and_nans(self):
        """سناریوی ۹: ورودی‌های نامعتبر مانند None، رشته، NaN و Infinity."""
        with self.assertRaises(TypeError):
            self.engine.filter_noise([{"keyword": "test", "total_tf_idf": None, "total_frequency": 2, "pages_count": 1}], total_docs=5)

        with self.assertRaises(ValueError):
            self.engine.filter_noise([{"keyword": "test", "total_tf_idf": float('nan'), "total_frequency": 2, "pages_count": 1}], total_docs=5)

        with self.assertRaises(ValueError):
            self.engine.filter_noise([{"keyword": "test", "total_tf_idf": float('inf'), "total_frequency": 2, "pages_count": 1}], total_docs=5)


if __name__ == "__main__":
    unittest.main()
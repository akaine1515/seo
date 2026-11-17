import unittest
from modules.strategy.content_gap import ContentGapStrategyEngine


class TestContentGapStrategyEngine(unittest.TestCase):

    def setUp(self):
        self.engine = ContentGapStrategyEngine(min_competitor_presence=2)

    def test_init_validation(self):
        """سناریوی ۱: اعتبارسنجی مقادیر اولیه min_competitor_presence."""
        # مقدار معتبر
        engine_valid = ContentGapStrategyEngine(min_competitor_presence=3)
        self.assertEqual(engine_valid.min_competitor_presence, 3)

        # مقادیر نامعتبر (بولی، اعشار، صفر، منفی، رشته نامعتبر)
        with self.assertRaises(TypeError):
            ContentGapStrategyEngine(min_competitor_presence=True)

        with self.assertRaises(ValueError):
            ContentGapStrategyEngine(min_competitor_presence=2.5)

        with self.assertRaises(ValueError):
            ContentGapStrategyEngine(min_competitor_presence=0)

        with self.assertRaises(ValueError):
            ContentGapStrategyEngine(min_competitor_presence=-1)

        with self.assertRaises(ValueError):
            ContentGapStrategyEngine(min_competitor_presence="abc")

    def test_domain_cleaning(self):
        """سناریوی ۲: استخراج امن دامنه."""
        self.assertEqual(ContentGapStrategyEngine._extract_clean_domain("https://www.Competitor.com/path?query=1"), "competitor.com")
        self.assertEqual(ContentGapStrategyEngine._extract_clean_domain("http://sub.rival.co.uk:8080/"), "sub.rival.co.uk")
        self.assertEqual(ContentGapStrategyEngine._extract_clean_domain("invalid-url"), "")
        self.assertEqual(ContentGapStrategyEngine._extract_clean_domain(""), "")

    def test_extract_site_terms(self):
        """سناریوی ۳: استخراج کلمات سایت خودمان بر اساس آستانه TF-IDF."""
        our_data = {
            1: {
                "gis software": {"tf_idf_score": 0.05},
                "mapping tools": {"tf_idf_score": 0.005}  # زیر آستانه 0.01
            }
        }
        terms = ContentGapStrategyEngine._extract_site_terms(our_data, min_threshold=0.01)
        self.assertIn("gis software", terms)
        self.assertNotIn("mapping tools", terms)

    def test_analyze_gaps_and_overlaps(self):
        """سناریوی ۴: تشخیص شکاف‌های محتوایی و هم‌پوشانی‌ها."""
        our_data = {
            1: {
                "gis software": {"tf_idf_score": 0.04},
                "python programming": {"tf_idf_score": 0.03}
            }
        }

        # تحلیل صفحات رقبا
        competitors_analysis = [
            {
                "success": True,
                "url": "https://comp1.com/page1",
                "keywords_analysis": {
                    "gis software": {"tf_idf_score": 0.06},        # در سایت ما هست -> Overlap
                    "spatial analysis": {"tf_idf_score": 0.05}     # در سایت ما نیست (توسط comp1 و comp2 کار شده) -> Gap
                }
            },
            {
                "success": True,
                "url": "https://comp2.com/page1",
                "keywords_analysis": {
                    "spatial analysis": {"tf_idf_score": 0.04},    # حضور دوم برای این کلمه -> Gap معتبر (چون min=2 است)
                    "unique rival term": {"tf_idf_score": 0.03}  # فقط یک رقیب -> نباید Gap باشد
                }
            }
        ]

        result = self.engine.analyze_gaps(our_data, competitors_analysis, min_coverage_threshold=0.01)

        self.assertEqual(result["keyword_overlaps_count"], 1)
        self.assertEqual(result["content_gaps_count"], 1)
        
        # بررسی جزئیات هم‌پوشانی
        overlap_kw = result["keyword_overlaps"][0]["keyword"]
        self.assertEqual(overlap_kw, "gis software")

        # بررسی جزئیات شکاف محتوایی
        gap_item = result["content_gaps"][0]
        self.assertEqual(gap_item["keyword"], "spatial analysis")
        self.assertEqual(gap_item["competitors_count"], 2)

    def test_competitor_domain_deduplication(self):
        """سناریوی ۵: اطمینان از اینکه چند صفحه از یک دامنه، تعداد رقبا را مصنوعی بالا نبرند."""
        our_data = {1: {"python": {"tf_idf_score": 0.05}}}

        # دو صفحه مختلف از یک رقیب (comp1.com) روی یک کلمه کار کرده‌اند
        competitors_analysis = [
            {
                "success": True,
                "url": "https://comp1.com/page-a",
                "keywords_analysis": {"advanced ML": {"tf_idf_score": 0.08}}
            },
            {
                "success": True,
                "url": "https://comp1.com/page-b",
                "keywords_analysis": {"advanced ML": {"tf_idf_score": 0.07}}
            }
        ]

        # با اینکه ۲ صفحه است، اما دامنه یکی است. چون min_competitor_presence = 2 است، نباید به عنوان شکاف ثبت شود.
        result = self.engine.analyze_gaps(our_data, competitors_analysis)
        self.assertEqual(result["content_gaps_count"], 0)


if __name__ == "__main__":
    unittest.main()
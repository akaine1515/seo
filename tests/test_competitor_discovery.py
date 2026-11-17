import unittest
from modules.competitors.discovery import CompetitorDiscovery


class TestCompetitorDiscovery(unittest.TestCase):

    def setUp(self):
        # دامنه هدف برای تست‌ها: example.com
        self.discovery = CompetitorDiscovery(target_domain="https://www.example.com", max_competitors=3)

    def test_init_validation(self):
        """سناریوی ۱: اعتبارسنجی مقادیر اولیه و خطاهای سازنده."""
        with self.assertRaises(ValueError):
            CompetitorDiscovery(target_domain="")
        
        with self.assertRaises(ValueError):
            CompetitorDiscovery(target_domain="example.com", max_competitors=0)
        
        with self.assertRaises(ValueError):
            CompetitorDiscovery(target_domain="example.com", max_competitors=-2)

        with self.assertRaises(ValueError):
            CompetitorDiscovery(target_domain="example.com", max_competitors=5.5)

        with self.assertRaises(TypeError):
            CompetitorDiscovery(target_domain="example.com", max_competitors=True)

    def test_url_and_ip_rejection(self):
        """سناریوی ۲: رد کردن آدرس‌های IP، لوکال‌هست و پروتکل‌های نامعتبر."""
        self.assertFalse(CompetitorDiscovery._is_valid_url("http://127.0.0.1/page"))
        self.assertFalse(CompetitorDiscovery._is_valid_url("http://localhost/path"))
        self.assertFalse(CompetitorDiscovery._is_valid_url("http://192.168.1.1/"))
        self.assertFalse(CompetitorDiscovery._is_valid_url("ftp://example.com/file"))
        self.assertTrue(CompetitorDiscovery._is_valid_url("https://sub.competitor.co.uk/blog?id=1"))

    def test_domain_cleaning_and_multipart_tlds(self):
        """سناریوی ۳: پاک‌سازی دامنه و پشتیبانی از پسوندهای چندبخشی."""
        self.assertEqual(CompetitorDiscovery._clean_domain("https://blog.comp.co.uk/path"), "comp.co.uk")
        self.assertEqual(CompetitorDiscovery._clean_domain("HTTP://WWW.TEST.CO.IR/"), "test.co.ir")
        self.assertEqual(CompetitorDiscovery._clean_domain("example.com."), "example.com")
        self.assertIsNone(CompetitorDiscovery._clean_domain("co.uk"))

    def test_self_domain_exclusion(self):
        """سناریوی ۴: حذف کامل دامنه خودی و ساب‌دامین‌های آن."""
        serp_data = [
            {
                "keyword": "seo tools",
                "organic_results": [
                    {"position": 1, "url": "https://sub.example.com/page1"},
                    {"position": 2, "url": "https://competitor.com/page"},
                    {"position": 3, "url": "https://example.com/"}
                ]
            }
        ]
        results = self.discovery.discover_competitors_per_keyword(serp_data)
        competitors = results.get("seo tools", [])
        domains = [c["domain"] for c in competitors]
        self.assertNotIn("example.com", domains)
        self.assertIn("competitor.com", domains)
        self.assertEqual(len(domains), 1)

    def test_best_position_retention(self):
        """سناریوی ۵: حفظ بهترین (کمترین) رتبه برای یک دامنه در صورت تکرار در یک SERP."""
        serp_data = [
            {
                "keyword": "python seo",
                "organic_results": [
                    {"position": 8, "url": "https://rival.com/page-b"},
                    {"position": 3, "url": "https://rival.com/page-a"}
                ]
            }
        ]
        results = self.discovery.discover_competitors_per_keyword(serp_data)
        competitors = results.get("python seo", [])
        self.assertEqual(len(competitors), 1)
        self.assertEqual(competitors[0]["domain"], "rival.com")
        self.assertEqual(competitors[0]["position"], 3)

    def test_aggregate_project_competitors(self):
        """سناریوی ۶: تجمیع کلان پروژه‌ای و اعمال محدودیت max_competitors."""
        serp_data = [
            {
                "keyword": "keyword one",
                "organic_results": [
                    {"position": 1, "url": "https://comp-a.com"},
                    {"position": 2, "url": "https://comp-b.com"}
                ]
            },
            {
                "keyword": "keyword two",
                "organic_results": [
                    {"position": 1, "url": "https://comp-a.com"},
                    {"position": 3, "url": "https://comp-c.com"}
                ]
            }
        ]
        ranked = self.discovery.aggregate_project_competitors(serp_data)
        self.assertEqual(ranked[0]["domain"], "comp-a.com")
        self.assertEqual(ranked[0]["appearance_count"], 2)
        self.assertLessEqual(len(ranked), 3)

    def test_invalid_positions_and_inputs(self):
        """سناریوی ۷: رفتار در مواجهه با پوزیشن‌های نامعتبر، اعشار و ورودی‌های معیوب."""
        serp_data = [
            {
                "keyword": "test kw",
                "organic_results": [
                    {"position": -1, "url": "https://rival.com"},
                    {"position": 2.5, "url": "https://rival2.com"},
                    {"position": "abc", "url": "https://rival3.com"},
                    {"position": 4, "url": "invalid-url-format"}
                ]
            }
        ]
        results = self.discovery.discover_competitors_per_keyword(serp_data)
        self.assertEqual(len(results.get("test kw", [])), 0)


if __name__ == "__main__":
    unittest.main()
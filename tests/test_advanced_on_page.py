import unittest
from modules.audit.advanced_on_page import AdvancedOnPageAnalyzer


class TestAdvancedOnPageAnalyzer(unittest.TestCase):
    """Unit tests for Advanced On-Page SEO Analysis Engine (Step 14)."""

    def setUp(self):
        self.analyzer = AdvancedOnPageAnalyzer()

    def test_keyword_cannibalization_detection(self):
        pages_data = [
            {
                "url": "https://example.com/page1",
                "keywords": [{"term": "python seo tools", "score": 0.08}]
            },
            {
                "url": "https://example.com/page2",
                "keywords": [{"term": "python seo tools", "score": 0.06}]
            }
        ]
        issues = self.analyzer.detect_keyword_cannibalization(pages_data)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["rule_id"], "KEYWORD_CANNIBALIZATION")
        self.assertEqual(issues[0]["competing_pages_count"], 2)

    def test_title_content_relevance(self):
        page_data = {
            "url": "https://example.com/guide",
            "structure": {
                "title": "Complete Python Guide for Data Analysis",
                "h1": ["Python Programming"],
                "raw_text": "Python is a great language for data science and analytics."
            }
        }
        result = self.analyzer.analyze_title_content_relevance(page_data)
        self.assertIn("relevance_score", result)
        self.assertIsInstance(result["issues"], list)


if __name__ == "__main__":
    unittest.main()
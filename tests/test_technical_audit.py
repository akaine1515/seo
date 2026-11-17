import unittest
from modules.audit.engine import TechnicalSEOAuditEngine


class TestTechnicalSEOAudit(unittest.TestCase):
    """Unit tests for Technical SEO Audit Engine and Page Rules (Step 13)."""

    def setUp(self):
        self.audit_engine = TechnicalSEOAuditEngine()

    def test_http_error_status(self):
        page = {
            "url": "https://example.com/broken",
            "status_code": 500,
            "structure": {}
        }
        result = self.audit_engine.audit_pages_batch([page])
        self.assertEqual(result["total_issues_found"], 1)
        self.assertEqual(result["issues"][0]["rule_id"], "HTTP_ERROR_STATUS")
        self.assertEqual(result["issues"][0]["severity"], "Critical")

    def test_missing_and_malformed_title(self):
        # 1. Missing Title
        page_no_title = {
            "url": "https://example.com/no-title",
            "status_code": 200,
            "structure": {"title": "", "word_count": 300}
        }
        res1 = self.audit_engine.audit_pages_batch([page_no_title])
        rule_ids1 = [i["rule_id"] for i in res1["issues"]]
        self.assertIn("PAGE_TITLE_MISSING", rule_ids1)

        # 2. Too Short Title
        page_short_title = {
            "url": "https://example.com/short-title",
            "status_code": 200,
            "structure": {"title": "SEO", "word_count": 300}
        }
        res2 = self.audit_engine.audit_pages_batch([page_short_title])
        rule_ids2 = [i["rule_id"] for i in res2["issues"]]
        self.assertIn("PAGE_TITLE_TOO_SHORT", rule_ids2)

    def test_h1_rules(self):
        # 1. Missing H1
        page_no_h1 = {
            "url": "https://example.com/no-h1",
            "status_code": 200,
            "structure": {"title": "A Valid Page Title Here", "h1": [], "word_count": 300}
        }
        res = self.audit_engine.audit_pages_batch([page_no_h1])
        rule_ids = [i["rule_id"] for i in res["issues"]]
        self.assertIn("H1_MISSING", rule_ids)

        # 2. Multiple H1s
        page_multi_h1 = {
            "url": "https://example.com/multi-h1",
            "status_code": 200,
            "structure": {"title": "A Valid Page Title Here", "h1": ["H1 One", "H1 Two"], "word_count": 300}
        }
        res2 = self.audit_engine.audit_pages_batch([page_multi_h1])
        rule_ids2 = [i["rule_id"] for i in res2["issues"]]
        self.assertIn("H1_MULTIPLE", rule_ids2)

    def test_thin_content(self):
        page_thin = {
            "url": "https://example.com/thin",
            "status_code": 200,
            "structure": {"title": "A Valid Page Title Here", "h1": ["Main Heading"], "word_count": 50}
        }
        res = self.audit_engine.audit_pages_batch([page_thin])
        rule_ids = [i["rule_id"] for i in res["issues"]]
        self.assertIn("THIN_CONTENT", rule_ids)


if __name__ == "__main__":
    unittest.main()
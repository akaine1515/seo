import os
import tempfile
import unittest
import pandas as pd
from modules.reporting.excel_reporter import ExcelReportGenerator
from modules.reporting.html_reporter import HTMLReportGenerator


class TestReportingEngine(unittest.TestCase):
    """Unit tests for Excel and Interactive HTML Report Generators (Step 18 - Phase G)."""

    def setUp(self):
        self.sample_project_data = {
            "meta": {
                "target_domain": "example.com"
            },
            "audit_summary": {
                "total_pages_audited": 15,
                "total_issues_found": 2,
                "severity_distribution": {
                    "Critical": 1,
                    "High": 1,
                    "Medium": 0,
                    "Low": 0
                },
                "issues": [
                    {
                        "rule_id": "HTTP_ERROR_STATUS",
                        "severity": "Critical",
                        "category": "Technical",
                        "title": "HTTP Error 500",
                        "url": "https://example.com/error-page",
                        "description": "Server returned 500 error.",
                        "recommendation": "Check server logs."
                    },
                    {
                        "rule_id": "H1_MISSING",
                        "severity": "High",
                        "category": "On-Page",
                        "title": "Missing H1 Heading",
                        "url": "https://example.com/about",
                        "description": "No H1 tag found.",
                        "recommendation": "Add a descriptive H1 tag."
                    }
                ]
            },
            "cannibalization_issues": [
                {
                    "term": "gis web development",
                    "competing_pages_count": 2,
                    "competing_pages": [
                        {"url": "https://example.com/gis-web", "score": 0.08},
                        {"url": "https://example.com/webgis-guide", "score": 0.06}
                    ],
                    "severity": "Medium",
                    "recommendation": "Consolidate pages or set canonical."
                }
            ],
            "project_competitors": [
                {
                    "domain": "competitor1.com",
                    "competitiveness_score": 12.5,
                    "keywords_count": 4,
                    "appearance_count": 5,
                    "best_position": 1,
                    "average_position": 2.4
                }
            ],
            "content_gap_analysis": {
                "content_gaps": [
                    {
                        "term": "spatial data pipeline",
                        "priority": "High",
                        "competitor_domains_count": 4,
                        "competitor_domains": ["competitor1.com", "competitor2.com", "competitor3.com", "competitor4.com"],
                        "evidence_urls": ["https://competitor1.com/spatial-pipeline"],
                        "recommended_action": "Create dedicated high-priority guide"
                    }
                ],
                "keyword_overlaps": [
                    {
                        "term": "geoserver styling",
                        "competitor_domains_count": 2,
                        "competitor_domains": ["competitor1.com", "competitor2.com"],
                        "evidence_urls": ["https://competitor1.com/sld-guide"]
                    }
                ]
            }
        }

    def test_excel_report_generation(self):
        generator = ExcelReportGenerator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = os.path.join(tmp_dir, "seo_report.xlsx")
            generated_path = generator.generate_report(output_file, self.sample_project_data)

            self.assertTrue(os.path.exists(generated_path))

            # بررسی شیت‌های موجود در فایل اکسل با استفاده از Context Manager برای بستن ایمن فایل
            with pd.ExcelFile(generated_path) as excel_file:
                expected_sheets = [
                    "Project Overview",
                    "Technical Audit",
                    "Cannibalization",
                    "Competitors",
                    "Content Gaps",
                    "Keyword Overlaps",
                    "Run Metadata"
                ]
                self.assertEqual(excel_file.sheet_names, expected_sheets)

            # بررسی صحت داده‌ها در شیت نمای کلی و ممیزی
            df_overview = pd.read_excel(generated_path, sheet_name="Project Overview")
            self.assertIn("example.com", df_overview["Value"].astype(str).values)

            df_audit = pd.read_excel(generated_path, sheet_name="Technical Audit")
            self.assertEqual(len(df_audit), 2)
            self.assertEqual(df_audit.iloc[0]["Rule ID"], "HTTP_ERROR_STATUS")
            metadata = pd.read_excel(generated_path, sheet_name="Run Metadata")
            self.assertEqual(metadata.iloc[0]['target_domain'], self.sample_project_data['meta']['target_domain'])

    def test_html_report_generation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_file = os.path.join(tmp_dir, "seo_report.html")
            generated_path = HTMLReportGenerator.generate_report(output_file, self.sample_project_data)

            self.assertTrue(os.path.exists(generated_path))

            with open(generated_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("SEO Intelligence V2 - Audit Dashboard", content)
            self.assertIn("example.com", content)
            self.assertIn("HTTP_ERROR_STATUS", content)
            self.assertIn("competitor1.com", content)
            self.assertIn("spatial data pipeline", content)
            self.assertIn("filterTable", content)

    def test_empty_data_handling(self):
        generator = ExcelReportGenerator()
        with tempfile.TemporaryDirectory() as tmp_dir:
            xlsx_path = os.path.join(tmp_dir, "empty.xlsx")
            html_path = os.path.join(tmp_dir, "empty.html")

            generator.generate_report(xlsx_path, {})
            HTMLReportGenerator.generate_report(html_path, {})

            self.assertTrue(os.path.exists(xlsx_path))
            self.assertTrue(os.path.exists(html_path))

    def test_invalid_inputs(self):
        generator = ExcelReportGenerator()
        with self.assertRaises(ValueError):
            generator.generate_report("", self.sample_project_data)
        with self.assertRaises(TypeError):
            generator.generate_report("report.xlsx", "not_a_dict")  # type: ignore
        with self.assertRaises(ValueError):
            HTMLReportGenerator.generate_report("", self.sample_project_data)
        with self.assertRaises(TypeError):
            HTMLReportGenerator.generate_report("report.html", [])  # type: ignore


if __name__ == "__main__":
    unittest.main()
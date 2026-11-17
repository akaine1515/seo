import tempfile
import unittest
import uuid
from pathlib import Path

import database.connection as connection_module
from database.repository import (
    ProjectRepository,
    AnalysisRepository,
    PageRepository,
    PageContentRepository,
)


class TestPageContentRepository(unittest.TestCase):
    """
    Isolated unit and integration tests for PageContentRepository.
    """

    @classmethod
    def setUpClass(cls):
        cls.original_db_path = connection_module.DB_PATH
        cls.temp_directory = tempfile.TemporaryDirectory()
        cls.test_db_path = (
            Path(cls.temp_directory.name)
            / "page_content_repo_test.db"
        )

        connection_module.DB_PATH = cls.test_db_path
        connection_module.initialize_database()

    @classmethod
    def tearDownClass(cls):
        try:
            connection_module.DB_PATH = cls.original_db_path
            cls.temp_directory.cleanup()
        except Exception:
            pass

    def setUp(self):
        unique_id = uuid.uuid4().hex[:10]
        self.website_url = f"https://content-{unique_id}.example.com"
        self.domain = f"content-{unique_id}.example.com"

        self.project_id = ProjectRepository.create_project(
            name="PageContent Repository Test",
            website_url=self.website_url,
            domain=self.domain,
            description="Temporary test project"
        )

        self.run_id = AnalysisRepository.create_analysis_run(
            self.project_id,
            max_pages=10
        )

        self.page_id = PageRepository.save_page(
            self.run_id,
            {
                "url": self.website_url + "/test-page",
                "title": "Test Page",
                "status_code": 200,
                "word_count": 50
            }
        )

    def tearDown(self):
        if self.project_id:
            ProjectRepository.delete_project(self.project_id)

    def test_save_and_get_page_content(self):
        content_id = PageContentRepository.save_page_content(
            page_id=self.page_id,
            text_content="Sample extracted main content.",
            h1_list=["Main Heading"],
            h2_list=["Subheading 1", "Subheading 2"],
            h3_list=["Detail Heading"],
            content_hash="abc123hash"
        )

        self.assertIsNotNone(content_id)

        content = PageContentRepository.get_page_content(
            self.page_id
        )

        self.assertIsNotNone(content)
        self.assertEqual(content["page_id"], self.page_id)
        self.assertEqual(
            content["text_content"],
            "Sample extracted main content."
        )
        self.assertEqual(content["h1_list"], ["Main Heading"])
        self.assertEqual(
            content["h2_list"],
            ["Subheading 1", "Subheading 2"]
        )
        self.assertEqual(content["h3_list"], ["Detail Heading"])
        self.assertEqual(content["content_hash"], "abc123hash")
        self.assertEqual(
            content["content_length"],
            len("Sample extracted main content.")
        )

        print("[PASS] Page content save and retrieval")

    def test_update_page_content_prevents_duplicates(self):
        first_id = PageContentRepository.save_page_content(
            page_id=self.page_id,
            text_content="Original content",
            h1_list=["Original Heading"],
            content_hash="original-hash"
        )

        second_id = PageContentRepository.save_page_content(
            page_id=self.page_id,
            text_content="Updated content",
            h1_list=["Updated Heading"],
            content_hash="updated-hash"
        )

        self.assertEqual(first_id, second_id)

        content = PageContentRepository.get_page_content(
            self.page_id
        )

        self.assertEqual(
            content["text_content"],
            "Updated content"
        )
        self.assertEqual(
            content["h1_list"],
            ["Updated Heading"]
        )
        self.assertEqual(
            content["content_hash"],
            "updated-hash"
        )
        self.assertEqual(
            PageContentRepository.count_run_contents(self.run_id),
            1
        )

        print("[PASS] Page content update and duplicate prevention")

    def test_get_run_contents(self):
        PageContentRepository.save_page_content(
            page_id=self.page_id,
            text_content="Run content",
            h1_list=["Run Heading"]
        )

        contents = PageContentRepository.get_run_contents(
            self.run_id
        )

        self.assertEqual(len(contents), 1)
        self.assertEqual(
            contents[0]["analysis_run_id"],
            self.run_id
        )
        self.assertEqual(
            contents[0]["url"],
            self.website_url + "/test-page"
        )
        self.assertEqual(
            contents[0]["text_content"],
            "Run content"
        )

        print("[PASS] Analysis run content retrieval")

    def test_empty_content_filter(self):
        PageContentRepository.save_page_content(
            page_id=self.page_id,
            text_content="   ",
            h1_list=["Empty Text Page"]
        )

        non_empty = PageContentRepository.get_run_contents(
            self.run_id,
            non_empty_only=True
        )
        self.assertEqual(len(non_empty), 0)

        all_contents = PageContentRepository.get_run_contents(
            self.run_id,
            non_empty_only=False
        )
        self.assertEqual(len(all_contents), 1)

        print("[PASS] Empty content filtering")

    def test_validation_errors(self):
        with self.assertRaises(TypeError):
            PageContentRepository.save_page_content(
                page_id=self.page_id,
                text_content="Valid text",
                content_hash=12345
            )

        with self.assertRaises(TypeError):
            PageContentRepository.save_page_content(
                page_id=self.page_id,
                text_content="Valid text",
                h1_list=["Valid", 999]
            )

        with self.assertRaises(TypeError):
            PageContentRepository.get_run_contents(
                self.run_id,
                non_empty_only=1
            )

        with self.assertRaises(ValueError):
            PageContentRepository.save_page_content(
                page_id=9999999,
                text_content="Orphan page"
            )

        print("[PASS] Input validation checks")

    def test_cascade_delete_on_project_removal(self):
        PageContentRepository.save_page_content(
            page_id=self.page_id,
            text_content="Cascade delete test"
        )

        self.assertIsNotNone(
            PageContentRepository.get_page_content(self.page_id)
        )

        ProjectRepository.delete_project(self.project_id)
        self.project_id = None

        self.assertIsNone(
            PageContentRepository.get_page_content(self.page_id)
        )

        print("[PASS] Foreign key cascade deletion")


if __name__ == "__main__":
    unittest.main(verbosity=2)
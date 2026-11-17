
import unittest
import tempfile

from pathlib import Path
from unittest.mock import patch

import database.connection as connection_module

from database.repository import (
    ProjectRepository,
    AnalysisRepository,
    PageRepository,
    CrawlQueueRepository,
    PageLinkRepository,
)


class FakeResponse:
    """Simulated HTTP response."""

    def __init__(self, url, html):

        self.url = url
        self.text = html
        self.status_code = 200

        self.headers = {
            "Content-Type": "text/html; charset=utf-8"
        }

        self.closed = False

    def raise_for_status(self):
        return None

    def close(self):
        self.closed = True


class FakeSession:
    """Simulated requests.Session."""

    def __init__(self):

        self.headers = {}
        self.closed = False
        self.responses = []

    def get(self, url, **kwargs):

        if not kwargs.get("allow_redirects") is False:
            raise AssertionError(
                "Crawler must handle redirects manually."
            )

        if url.endswith("/about"):
            html = """
            <html>
                <head>
                    <title>About Page</title>
                    <meta name="description"
                          content="About our company">
                </head>
                <body>
                    <h1>About Us</h1>
                    <p>Information about our company.</p>
                </body>
            </html>
            """

        else:
            html = """
            <html>
                <head>
                    <title>Test Website</title>
                    <meta name="description"
                          content="Test website description">
                </head>
                <body>
                    <h1>Welcome</h1>

                    <p>
                        This is a test website with useful content.
                    </p>

                    <a href="/about">About Us</a>

                    <a href="https://external.example.org/">
                        External Website
                    </a>
                </body>
            </html>
            """

        response = FakeResponse(url, html)

        self.responses.append(response)

        return response

    def close(self):
        self.closed = True


class FakeRobotsManager:
    """Allow all test URLs without network access."""

    def __init__(self, base_url, user_agent=None, request_policy=None):
        self.base_url = base_url
        self.user_agent = user_agent

    def can_fetch(self, url):
        return True


class FakeSitemapManager:
    """Return no sitemap URLs during testing."""

    def __init__(self, **kwargs):
        self.closed = False

    def discover(self, base_url, robots_manager=None):
        return []

    def close(self):
        self.closed = True


class TestCrawlerEngineIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.original_db_path = connection_module.DB_PATH

        cls.temp_directory = tempfile.TemporaryDirectory()

        cls.test_db_path = (
            Path(cls.temp_directory.name)
            / "crawler_test.db"
        )

        # Isolate all repository operations from the real database.
        connection_module.DB_PATH = cls.test_db_path

        connection_module.initialize_database()

        cls.website_url = "https://crawler-test.example.com"

        cls.project_id = ProjectRepository.create_project(
            name="Crawler Engine Integration Test",
            website_url=cls.website_url,
            domain="crawler-test.example.com",
            description="Temporary crawler test"
        )

        cls.run_id = AnalysisRepository.create_analysis_run(
            cls.project_id,
            max_pages=2
        )

    @classmethod
    def tearDownClass(cls):

        try:
            if getattr(cls, "project_id", None):
                ProjectRepository.delete_project(
                    cls.project_id
                )

        finally:
            connection_module.DB_PATH = cls.original_db_path
            cls.temp_directory.cleanup()

    def test_crawler_engine_workflow(self):

        from modules.crawler import engine as engine_module

        fake_session = FakeSession()

        with (
            patch.object(
                engine_module,
                "RobotsManager",
                FakeRobotsManager
            ),
            patch.object(
                engine_module,
                "SitemapManager",
                FakeSitemapManager
            ),
            patch.object(
                engine_module.requests,
                "Session",
                return_value=fake_session
            )
        ):

            crawler = engine_module.CrawlerEngine(
                analysis_run_id=self.run_id,
                max_pages=2,
                timeout=5
            )

            stats = crawler.run(self.website_url)

        # ---------------------------------------------
        # 1. Verify crawl statistics
        # ---------------------------------------------

        self.assertEqual(stats["attempted"], 2)
        self.assertEqual(stats["crawled"], 2)
        self.assertEqual(stats["saved"], 2)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(stats["blocked"], 0)
        self.assertEqual(stats["links_saved"], 2)

        print("[PASS] Crawler execution statistics")

        # ---------------------------------------------
        # 2. Verify session cleanup
        # ---------------------------------------------

        self.assertTrue(fake_session.closed)

        self.assertTrue(
            all(
                response.closed
                for response in fake_session.responses
            )
        )

        print("[PASS] HTTP session and response cleanup")

        # ---------------------------------------------
        # 3. Verify page storage
        # ---------------------------------------------

        pages = PageRepository.get_run_pages(
            self.run_id
        )

        self.assertEqual(len(pages), 2)

        page_urls = {
            page["url"]
            for page in pages
        }

        self.assertIn(
            self.website_url + "/",
            page_urls
        )

        self.assertIn(
            self.website_url + "/about",
            page_urls
        )

        print("[PASS] Database page storage")

        # ---------------------------------------------
        # 4. Verify page depth
        # ---------------------------------------------

        about_page = next(
            page for page in pages
            if page["url"].endswith("/about")
        )

        self.assertEqual(
            about_page["depth"],
            1
        )

        self.assertEqual(
            about_page["parent_url"],
            self.website_url + "/"
        )

        print("[PASS] Page depth and parent URL")

        # ---------------------------------------------
        # 5. Verify link storage
        # ---------------------------------------------

        links = PageLinkRepository.get_run_links(
            self.run_id
        )

        self.assertEqual(len(links), 2)

        internal_links = [
            link for link in links
            if link["is_internal"]
        ]

        external_links = [
            link for link in links
            if not link["is_internal"]
        ]

        self.assertEqual(len(internal_links), 1)
        self.assertEqual(len(external_links), 1)

        print("[PASS] Internal and external link storage")

        # ---------------------------------------------
        # 6. Verify queue completion
        # ---------------------------------------------

        queue_stats = CrawlQueueRepository.get_queue_stats(
            self.run_id
        )

        self.assertEqual(
            queue_stats["completed"],
            2
        )

        self.assertEqual(
            queue_stats["total"],
            2
        )

        print("[PASS] Persistent crawl queue")

        # ---------------------------------------------
        # 7. Verify maximum page limit
        # ---------------------------------------------

        self.assertLessEqual(
            stats["attempted"],
            2
        )

        print("[PASS] Maximum attempted URL limit")

        # ---------------------------------------------
        # 8. Verify redirect policy
        # ---------------------------------------------

        self.assertTrue(
            all(
                response.status_code == 200
                for response in fake_session.responses
            )
        )

        print("[PASS] HTTP responses processed successfully")


if __name__ == "__main__":
    unittest.main(verbosity=2)


import tempfile
import unittest
import uuid

from pathlib import Path
from unittest.mock import patch

import requests

import database.connection as connection_module

from database.repository import (
    ProjectRepository,
    AnalysisRepository,
    PageRepository,
    CrawlQueueRepository,
)


# =====================================================
# FAKE HTTP RESPONSE
# =====================================================

class FakeResponse:

    def __init__(
        self,
        url,
        status_code=200,
        html=None,
        headers=None
    ):

        self.url = url
        self.status_code = status_code

        self.text = html or """
        <html>
            <head>
                <title>Edge Case Test</title>
                <meta name="description" content="Test description">
            </head>
            <body>
                <h1>Test Page</h1>
                <p>Testing crawler behavior.</p>
            </body>
        </html>
        """

        self.headers = headers or {
            "Content-Type": "text/html; charset=utf-8"
        }

        self.closed = False

    def raise_for_status(self):

        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"HTTP {self.status_code}",
                response=self
            )

    def close(self):
        self.closed = True


# =====================================================
# FAKE HTTP SESSION
# =====================================================

class FakeSession:

    def __init__(self, routes=None):

        self.headers = {}
        self.routes = routes or {}
        self.calls = []
        self.responses = []
        self.closed = False

    def get(self, url, **kwargs):

        self.calls.append(url)

        if kwargs.get("allow_redirects") is not False:
            raise AssertionError(
                "Redirects must be handled manually."
            )

        route = self.routes.get(url)

        if isinstance(route, Exception):
            raise route

        if route is None:
            route = FakeResponse(url)

        self.responses.append(route)

        return route

    def close(self):
        self.closed = True


# =====================================================
# FAKE ROBOTS MANAGER
# =====================================================

class FakeRobotsManager:

    def __init__(
        self,
        base_url,
        user_agent=None,
        blocked_urls=None,
        request_policy=None
    ):

        self.base_url = base_url
        self.blocked_urls = blocked_urls or set()

    def can_fetch(self, url):
        return url not in self.blocked_urls


# =====================================================
# FAKE SITEMAP MANAGER
# =====================================================

class FakeSitemapManager:

    def __init__(self, **kwargs):
        self.closed = False

    def discover(self, base_url, robots_manager=None):
        return []

    def close(self):
        self.closed = True


# =====================================================
# TEST CLASS
# =====================================================

class TestCrawlerEdgeCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.original_db_path = connection_module.DB_PATH

        cls.temp_directory = tempfile.TemporaryDirectory()

        cls.test_db_path = (
            Path(cls.temp_directory.name)
            / "edge_cases_test.db"
        )

        connection_module.DB_PATH = cls.test_db_path

        connection_module.initialize_database()

        from modules.crawler import engine as engine_module

        cls.engine_module = engine_module

    @classmethod
    def tearDownClass(cls):

        try:
            connection_module.DB_PATH = cls.original_db_path

            cls.temp_directory.cleanup()

        except Exception:
            pass

    def setUp(self):

        unique_id = uuid.uuid4().hex[:10]

        self.website_url = (
            f"https://edge-{unique_id}.example.com"
        )

        self.domain = f"edge-{unique_id}.example.com"

        self.project_id = ProjectRepository.create_project(
            name="Crawler Edge Case Test",
            website_url=self.website_url,
            domain=self.domain,
            description="Temporary edge case test"
        )

        self.run_id = AnalysisRepository.create_analysis_run(
            self.project_id,
            max_pages=10
        )

    def tearDown(self):

        if self.project_id:
            ProjectRepository.delete_project(
                self.project_id
            )

    # -------------------------------------------------
    # HELPER
    # -------------------------------------------------

    def create_crawler(
        self,
        routes=None,
        blocked_urls=None,
        max_pages=10
    ):

        crawler = self.engine_module.CrawlerEngine(
            analysis_run_id=self.run_id,
            max_pages=max_pages,
            timeout=5
        )

        crawler.base_url = self.website_url
        crawler.base_domain = self.domain

        crawler.robots = FakeRobotsManager(
            self.website_url,
            blocked_urls=blocked_urls
        )

        crawler.session = FakeSession(
            routes=routes
        )

        return crawler

    # -------------------------------------------------
    # 1. HTTP 404
    # -------------------------------------------------

    def test_http_404(self):

        url = self.website_url + "/missing"

        response = FakeResponse(
            url,
            status_code=404
        )

        crawler = self.create_crawler({
            url: response
        })

        try:

            result = crawler.crawl_page(url)

            self.assertEqual(result, "failed")
            self.assertEqual(crawler.stats["attempted"], 1)
            self.assertEqual(crawler.stats["failed"], 1)
            self.assertEqual(crawler.stats["saved"], 0)

            self.assertTrue(response.closed)

            print("[PASS] HTTP 404 handling")

        finally:
            crawler.close()

    # -------------------------------------------------
    # 2. HTTP 500
    # -------------------------------------------------

    def test_http_500(self):

        url = self.website_url + "/server-error"

        response = FakeResponse(
            url,
            status_code=500
        )

        crawler = self.create_crawler({
            url: response
        })

        try:

            result = crawler.crawl_page(url)

            self.assertEqual(result, "failed")
            self.assertEqual(crawler.stats["failed"], 1)
            self.assertEqual(crawler.stats["saved"], 0)

            self.assertTrue(response.closed)

            print("[PASS] HTTP 500 handling")

        finally:
            crawler.close()

    # -------------------------------------------------
    # 3. TIMEOUT
    # -------------------------------------------------

    def test_request_timeout(self):

        url = self.website_url + "/timeout"

        crawler = self.create_crawler({
            url: requests.exceptions.Timeout(
                "Simulated connection timeout"
            )
        })

        try:

            result = crawler.crawl_page(url)

            self.assertEqual(result, "failed")
            self.assertEqual(crawler.stats["failed"], 1)
            self.assertEqual(crawler.stats["saved"], 0)

            print("[PASS] Request timeout handling")

        finally:
            crawler.close()

    # -------------------------------------------------
    # 4. INTERNAL REDIRECT
    # -------------------------------------------------

    def test_internal_redirect(self):

        source_url = self.website_url + "/old"
        destination_url = self.website_url + "/new"

        redirect_response = FakeResponse(
            source_url,
            status_code=301,
            headers={
                "Content-Type": "text/html",
                "Location": "/new"
            }
        )

        final_response = FakeResponse(
            destination_url,
            status_code=200
        )

        crawler = self.create_crawler({
            source_url: redirect_response,
            destination_url: final_response
        })

        try:

            result = crawler.crawl_page(source_url)

            self.assertEqual(result, "completed")

            self.assertEqual(
                crawler.stats["saved"],
                1
            )

            self.assertEqual(
                crawler.stats["crawled"],
                1
            )

            self.assertEqual(
                crawler.session.calls,
                [source_url, destination_url]
            )

            page = PageRepository.get_page_by_url(
                self.run_id,
                destination_url
            )

            self.assertIsNotNone(page)

            redirect_chain = page["redirect_chain_json"]

            self.assertIn(source_url, redirect_chain)
            self.assertIn(destination_url, redirect_chain)

            self.assertTrue(redirect_response.closed)
            self.assertTrue(final_response.closed)

            print("[PASS] Internal redirect handling")

        finally:
            crawler.close()

    # -------------------------------------------------
    # 5. EXTERNAL REDIRECT
    # -------------------------------------------------

    def test_external_redirect(self):

        source_url = self.website_url + "/external"

        external_url = "https://external.example.org/page"

        redirect_response = FakeResponse(
            source_url,
            status_code=302,
            headers={
                "Content-Type": "text/html",
                "Location": external_url
            }
        )

        crawler = self.create_crawler({
            source_url: redirect_response
        })

        try:

            result = crawler.crawl_page(source_url)

            self.assertEqual(result, "completed")

            self.assertEqual(
                crawler.stats["skipped"],
                1
            )

            self.assertEqual(
                crawler.stats["saved"],
                0
            )

            self.assertEqual(
                crawler.session.calls,
                [source_url]
            )

            self.assertNotIn(
                external_url,
                crawler.session.calls
            )

            self.assertTrue(redirect_response.closed)

            print("[PASS] External redirect protection")

        finally:
            crawler.close()

    # -------------------------------------------------
    # 6. ROBOTS BLOCKED REDIRECT DESTINATION
    # -------------------------------------------------

    def test_blocked_redirect_destination(self):

        source_url = self.website_url + "/redirect"

        destination_url = self.website_url + "/private"

        redirect_response = FakeResponse(
            source_url,
            status_code=302,
            headers={
                "Content-Type": "text/html",
                "Location": "/private"
            }
        )

        crawler = self.create_crawler(
            routes={
                source_url: redirect_response
            },
            blocked_urls={
                destination_url
            }
        )

        try:

            result = crawler.crawl_page(source_url)

            self.assertEqual(result, "blocked")

            self.assertEqual(
                crawler.stats["blocked"],
                1
            )

            self.assertEqual(
                crawler.stats["saved"],
                0
            )

            self.assertEqual(
                crawler.session.calls,
                [source_url]
            )

            self.assertTrue(redirect_response.closed)

            print("[PASS] Robots blocked redirect destination")

        finally:
            crawler.close()

    # -------------------------------------------------
    # 7. MAXIMUM ATTEMPTED URL LIMIT
    # -------------------------------------------------

    def test_maximum_attempted_url_limit(self):

        html = """
        <html>
            <head>
                <title>Root Page</title>
                <meta name="description" content="Root page">
            </head>
            <body>
                <h1>Root</h1>
                <a href="/page-2">Page 2</a>
                <a href="/page-3">Page 3</a>
            </body>
        </html>
        """

        fake_session = FakeSession({
            self.website_url + "/": FakeResponse(
                self.website_url + "/",
                html=html
            )
        })

        with (
            patch.object(
                self.engine_module,
                "RobotsManager",
                FakeRobotsManager
            ),
            patch.object(
                self.engine_module,
                "SitemapManager",
                FakeSitemapManager
            ),
            patch.object(
                self.engine_module.requests,
                "Session",
                return_value=fake_session
            )
        ):

            crawler = self.engine_module.CrawlerEngine(
                analysis_run_id=self.run_id,
                max_pages=1,
                timeout=5
            )

            stats = crawler.run(
                self.website_url
            )

        self.assertEqual(stats["attempted"], 1)

        self.assertLessEqual(
            stats["attempted"],
            1
        )

        self.assertEqual(stats["saved"], 1)

        queue_stats = CrawlQueueRepository.get_queue_stats(
            self.run_id
        )

        self.assertGreaterEqual(
            queue_stats["queued"],
            1
        )

        self.assertTrue(fake_session.closed)

        print("[PASS] Maximum attempted URL limit")

    # -------------------------------------------------
    # 8. RECOVER INTERRUPTED QUEUE
    # -------------------------------------------------

    def test_interrupted_queue_recovery(self):

        url = self.website_url + "/recovery"

        queue_id = CrawlQueueRepository.add_url(
            analysis_run_id=self.run_id,
            url=url,
            normalized_url=url,
            depth=0
        )

        claimed = CrawlQueueRepository.get_next_url(
            self.run_id
        )

        self.assertEqual(
            claimed["id"],
            queue_id
        )

        self.assertEqual(
            claimed["status"],
            "processing"
        )

        recovered = CrawlQueueRepository.recover_processing_items(
            self.run_id
        )

        self.assertEqual(recovered, 1)

        pending = CrawlQueueRepository.get_pending_urls(
            self.run_id
        )

        self.assertEqual(len(pending), 1)

        self.assertEqual(
            pending[0]["id"],
            queue_id
        )

        print("[PASS] Interrupted queue recovery")


if __name__ == "__main__":
    unittest.main(verbosity=2)


import unittest
import uuid
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
    CrawlEventRepository,
    CrawlSummaryRepository,
)


class TestRepositoryIntegration(unittest.TestCase):
    """
    Integration tests for SEO Intelligence V2 repositories.

    All test data belongs to a temporary project.
    The temporary project is deleted after the test.
    Existing projects and analysis data remain untouched.
    """

    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.db_patch = patch.object(connection_module, "DB_PATH", Path(self.temp_directory.name) / "test.db")
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        connection_module.initialize_database()
        unique_id = uuid.uuid4().hex[:12]

        self.website_url = (
            f"https://repository-test-{unique_id}.example.com"
        )

        self.project_id = ProjectRepository.create_project(
            name="Repository Integration Test",
            website_url=self.website_url,
            domain=f"repository-test-{unique_id}.example.com",
            description="Temporary test project"
        )

        self.run_id = AnalysisRepository.create_analysis_run(
            self.project_id,
            max_pages=10
        )

    def tearDown(self):
        """
        Delete only the temporary test project.
        Related records are removed through foreign keys.
        """

        if self.project_id:
            ProjectRepository.delete_project(self.project_id)

    def test_repository_workflow(self):

        # -------------------------------------------------
        # 1. Verify project creation
        # -------------------------------------------------

        project = ProjectRepository.get_project(
            self.project_id
        )

        self.assertIsNotNone(project)
        self.assertEqual(
            project["website_url"],
            self.website_url
        )

        print("[PASS] Project creation and retrieval")

        # -------------------------------------------------
        # 2. Verify analysis run lifecycle
        # -------------------------------------------------

        run = AnalysisRepository.get_analysis_run(
            self.run_id
        )

        self.assertIsNotNone(run)
        self.assertEqual(run["project_id"], self.project_id)
        self.assertEqual(run["status"], "pending")

        started = AnalysisRepository.start_analysis_run(
            self.run_id
        )

        self.assertTrue(started)

        run = AnalysisRepository.get_analysis_run(
            self.run_id
        )

        self.assertEqual(run["status"], "running")

        print("[PASS] Analysis run creation and startup")

        # -------------------------------------------------
        # 3. Add URL to crawl queue
        # -------------------------------------------------

        test_url = self.website_url + "/test-page"

        queue_id = CrawlQueueRepository.add_url(
            analysis_run_id=self.run_id,
            url=test_url,
            normalized_url=test_url,
            depth=1,
            parent_url=self.website_url,
            discovered_from="integration_test",
            priority=10
        )

        self.assertIsNotNone(queue_id)

        print("[PASS] Crawl queue URL insertion")

        # -------------------------------------------------
        # 4. Prevent duplicate URL insertion
        # -------------------------------------------------

        duplicate_id = CrawlQueueRepository.add_url(
            analysis_run_id=self.run_id,
            url=test_url,
            normalized_url=test_url,
            depth=1
        )

        self.assertEqual(queue_id, duplicate_id)

        queue_stats = CrawlQueueRepository.get_queue_stats(
            self.run_id
        )

        self.assertEqual(queue_stats["queued"], 1)
        self.assertEqual(queue_stats["total"], 1)

        print("[PASS] Duplicate URL prevention")

        # -------------------------------------------------
        # 5. Claim next URL
        # -------------------------------------------------

        next_url = CrawlQueueRepository.get_next_url(
            self.run_id
        )

        self.assertIsNotNone(next_url)
        self.assertEqual(next_url["id"], queue_id)
        self.assertEqual(next_url["status"], "processing")
        self.assertEqual(next_url["attempt_count"], 1)

        print("[PASS] Queue URL claiming")

        # -------------------------------------------------
        # 6. Update queue status
        # -------------------------------------------------

        updated = CrawlQueueRepository.update_status(
            queue_id,
            "completed"
        )

        self.assertTrue(updated)

        queue_stats = CrawlQueueRepository.get_queue_stats(
            self.run_id
        )

        self.assertEqual(queue_stats["completed"], 1)

        print("[PASS] Queue status update")

        # -------------------------------------------------
        # 7. Save crawled page
        # -------------------------------------------------

        page_data = {
            "url": test_url,
            "canonical_url": test_url,
            "title": "Repository Test Page",
            "meta_description": "Integration test page",
            "h1": "Test Heading",
            "status_code": 200,
            "content_type": "text/html",
            "word_count": 120,
            "depth": 1,
            "is_indexable": 1,
            "robots_directive": "index, follow",
            "canonical_status": "valid",
            "content_hash": "test-content-hash",
            "title_length": 21,
            "meta_description_length": 22,
            "h1_count": 1,
            "h2_count": 2,
            "h3_count": 0,
            "headings_json": None,
            "image_count": 2,
            "images_without_alt": 0,
            "internal_links_count": 1,
            "external_links_count": 0,
            "x_robots_tag": None,
            "is_nofollow": 0,
            "parent_url": self.website_url,
            "final_url": test_url,
            "redirect_chain_json": None,
            "crawl_status": "success",
            "crawl_error": None,
            "duplicate_of_url": None,
            "duplicate_type": None,
            "unique_internal_links_count": 1,
            "unique_external_links_count": 0,
            "nofollow_links_count": 0
        }

        page_id = PageRepository.save_page(
            self.run_id,
            page_data
        )

        self.assertIsNotNone(page_id)

        saved_page = PageRepository.get_page(page_id)

        self.assertIsNotNone(saved_page)
        self.assertEqual(saved_page["url"], test_url)
        self.assertEqual(saved_page["status_code"], 200)

        print("[PASS] Page insertion and retrieval")

        # -------------------------------------------------
        # 8. Verify page update instead of duplication
        # -------------------------------------------------

        updated_page_data = dict(page_data)
        updated_page_data["title"] = "Updated Test Page"

        updated_page_id = PageRepository.save_page(
            self.run_id,
            updated_page_data
        )

        self.assertEqual(page_id, updated_page_id)

        saved_page = PageRepository.get_page(page_id)

        self.assertEqual(
            saved_page["title"],
            "Updated Test Page"
        )

        self.assertEqual(
            PageRepository.count_run_pages(self.run_id),
            1
        )

        print("[PASS] Page upsert and duplicate prevention")

        # -------------------------------------------------
        # 9. Save page links
        # -------------------------------------------------

        links = [
            {
                "target_url": self.website_url + "/another-page",
                "source_url": test_url,
                "anchor_text": "Another page",
                "rel": None,
                "is_internal": True,
                "link_type": "html",
                "link_position": 0
            },
            {
                "target_url": "https://external.example.org/",
                "source_url": test_url,
                "anchor_text": "External website",
                "rel": "nofollow",
                "is_internal": False,
                "link_type": "html",
                "link_position": 1
            }
        ]

        saved_links = PageLinkRepository.save_links(
            self.run_id,
            page_id,
            links
        )

        self.assertEqual(saved_links, 2)

        retrieved_links = PageLinkRepository.get_page_links(
            page_id
        )

        self.assertEqual(len(retrieved_links), 2)

        print("[PASS] Page links insertion and retrieval")

        # -------------------------------------------------
        # 10. Verify inbound link count
        # -------------------------------------------------

        inbound_count = PageLinkRepository.count_inbound_links(
            self.run_id,
            self.website_url + "/another-page"
        )

        self.assertEqual(inbound_count, 1)

        print("[PASS] Internal inbound link counting")

        # -------------------------------------------------
        # 11. Verify broken link candidates
        # -------------------------------------------------

        broken_candidates = (
            PageLinkRepository.get_broken_link_candidates(
                self.run_id
            )
        )

        self.assertEqual(len(broken_candidates), 1)

        self.assertEqual(
            broken_candidates[0]["target_url"],
            self.website_url + "/another-page"
        )

        print("[PASS] Broken internal link candidates")

        # -------------------------------------------------
        # 12. Record crawl event
        # -------------------------------------------------

        event_id = CrawlEventRepository.log_event(
            analysis_run_id=self.run_id,
            event_type="integration_test",
            message="Repository integration test completed",
            url=test_url,
            severity="info",
            details_json='{"test": true}'
        )

        self.assertIsNotNone(event_id)

        events = CrawlEventRepository.get_run_events(
            self.run_id
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0]["event_type"],
            "integration_test"
        )

        print("[PASS] Crawl event logging")

        # -------------------------------------------------
        # 13. Verify crawl summary
        # -------------------------------------------------

        summary = CrawlSummaryRepository.get_run_summary(
            self.run_id
        )

        self.assertEqual(
            summary["pages"]["total_pages"],
            1
        )

        self.assertEqual(
            summary["pages"]["successful_pages"],
            1
        )

        self.assertEqual(
            summary["queue"]["completed"],
            1
        )

        self.assertEqual(
            summary["links"]["total_links"],
            2
        )

        self.assertEqual(
            summary["links"]["internal_links"],
            1
        )

        self.assertEqual(
            summary["links"]["external_links"],
            1
        )

        print("[PASS] Crawl summary aggregation")

        # -------------------------------------------------
        # 14. Finish analysis run
        # -------------------------------------------------

        finished = AnalysisRepository.finish_analysis_run(
            self.run_id,
            status="completed"
        )

        self.assertTrue(finished)

        finished_run = AnalysisRepository.get_analysis_run(
            self.run_id
        )

        self.assertEqual(
            finished_run["status"],
            "completed"
        )

        self.assertIsNotNone(
            finished_run["finished_at"]
        )

        print("[PASS] Analysis run completion")

    def test_queue_recovery(self):
        """
        Verify that interrupted processing items can be recovered.
        """

        started = AnalysisRepository.start_analysis_run(
            self.run_id
        )

        self.assertTrue(started)

        test_url = self.website_url + "/recovery-test"

        queue_id = CrawlQueueRepository.add_url(
            analysis_run_id=self.run_id,
            url=test_url,
            normalized_url=test_url
        )

        claimed = CrawlQueueRepository.get_next_url(
            self.run_id
        )

        self.assertEqual(claimed["id"], queue_id)
        self.assertEqual(claimed["status"], "processing")

        recovered = CrawlQueueRepository.recover_processing_items(
            self.run_id
        )

        self.assertEqual(recovered, 1)

        pending = CrawlQueueRepository.get_pending_urls(
            self.run_id
        )

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], queue_id)

        print("[PASS] Interrupted queue recovery")


if __name__ == "__main__":
    unittest.main(verbosity=2)

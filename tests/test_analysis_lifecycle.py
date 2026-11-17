
import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from database import repository


class AnalysisLifecycleTests(unittest.TestCase):
    """
    Isolated tests for the analysis lifecycle.

    All tests use a temporary SQLite database.
    The production database is never modified.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

        self.db_path = os.path.join(
            self.temp_dir.name,
            "test_analysis.db"
        )

        self._create_test_database()

        self.database_patch = patch(
            "database.repository.database_connection",
            self._test_database_connection
        )

        self.database_patch.start()

        self.project_id = repository.ProjectRepository.create_project(
            name="Lifecycle Test",
            website_url="https://example.com",
            domain="example.com"
        )

    def tearDown(self):
        self.database_patch.stop()
        self.temp_dir.cleanup()

    @contextmanager
    def _test_database_connection(self):
        connection = sqlite3.connect(
            self.db_path,
            timeout=10
        )

        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        try:
            yield connection
            connection.commit()

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()

    def _create_test_database(self):
        connection = sqlite3.connect(self.db_path)

        try:
            connection.executescript(
                """
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    website_url TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE analysis_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK (
                        status IN (
                            'pending',
                            'running',
                            'completed',
                            'failed',
                            'cancelled',
                            'interrupted'
                        )
                    ),
                    max_pages INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    started_at TEXT,
                    finished_at TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_heartbeat_at TEXT,
                    completion_reason TEXT,
                    error_message TEXT,
                    summary_json TEXT,
                    FOREIGN KEY (project_id)
                        REFERENCES projects(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_run_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    status_code INTEGER,
                    is_indexable INTEGER DEFAULT 1,
                    word_count INTEGER DEFAULT 0,
                    FOREIGN KEY (analysis_run_id)
                        REFERENCES analysis_runs(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE crawl_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_run_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (analysis_run_id)
                        REFERENCES analysis_runs(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE page_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_run_id INTEGER NOT NULL,
                    is_internal INTEGER DEFAULT 1,
                    FOREIGN KEY (analysis_run_id)
                        REFERENCES analysis_runs(id)
                        ON DELETE CASCADE
                );
                """
            )

            connection.commit()

        finally:
            connection.close()

    def _create_running_analysis(self):
        run_id = repository.AnalysisRepository.create_analysis_run(
            self.project_id,
            max_pages=50
        )

        started = repository.AnalysisRepository.start_analysis_run(
            run_id
        )

        self.assertTrue(started)

        return run_id

    def test_create_analysis_starts_as_pending(self):
        run_id = repository.AnalysisRepository.create_analysis_run(
            self.project_id
        )

        run = repository.AnalysisRepository.get_analysis_run(run_id)

        self.assertIsNotNone(run)
        self.assertEqual(run["status"], "pending")
        self.assertIsNone(run["started_at"])
        self.assertIsNone(run["finished_at"])

    def test_start_analysis_changes_status_to_running(self):
        run_id = repository.AnalysisRepository.create_analysis_run(
            self.project_id
        )

        result = repository.AnalysisRepository.start_analysis_run(
            run_id
        )

        run = repository.AnalysisRepository.get_analysis_run(run_id)

        self.assertTrue(result)
        self.assertEqual(run["status"], "running")
        self.assertIsNotNone(run["started_at"])
        self.assertIsNotNone(run["last_heartbeat_at"])

    def test_analysis_cannot_be_started_twice(self):
        run_id = self._create_running_analysis()

        result = repository.AnalysisRepository.start_analysis_run(
            run_id
        )

        self.assertFalse(result)

        run = repository.AnalysisRepository.get_analysis_run(run_id)

        self.assertEqual(run["status"], "running")

    def test_heartbeat_updates_running_analysis(self):
        run_id = self._create_running_analysis()

        result = repository.AnalysisRepository.heartbeat_analysis_run(
            run_id
        )

        run = repository.AnalysisRepository.get_analysis_run(run_id)

        self.assertTrue(result)
        self.assertIsNotNone(run["last_heartbeat_at"])
        self.assertIsNotNone(run["updated_at"])

    def test_successful_completion_saves_summary(self):
        run_id = self._create_running_analysis()

        with repository.database_connection() as connection:
            connection.execute(
                """
                INSERT INTO pages (
                    analysis_run_id,
                    url,
                    status_code,
                    is_indexable,
                    word_count
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    "https://example.com/",
                    200,
                    1,
                    500
                )
            )

        result = repository.AnalysisRepository.finish_analysis_run(
            run_id,
            status="completed",
            completion_reason="normal_completion"
        )

        run = repository.AnalysisRepository.get_analysis_run(run_id)

        self.assertTrue(result)
        self.assertEqual(run["status"], "completed")
        self.assertIsNotNone(run["finished_at"])
        self.assertEqual(
            run["completion_reason"],
            "normal_completion"
        )
        self.assertIsNotNone(run["summary_json"])

        import json

        summary = json.loads(run["summary_json"])

        self.assertEqual(summary["analysis_run_id"], run_id)
        self.assertEqual(summary["pages"]["total_pages"], 1)
        self.assertEqual(summary["pages"]["successful_pages"], 1)
        self.assertEqual(summary["pages"]["total_words"], 500)

    def test_failed_and_cancelled_statuses(self):
        for status in ("failed", "cancelled"):
            with self.subTest(status=status):
                run_id = self._create_running_analysis()

                result = repository.AnalysisRepository.finish_analysis_run(
                    run_id,
                    status=status,
                    error_message=(
                        "Test error" if status == "failed" else None
                    )
                )

                run = repository.AnalysisRepository.get_analysis_run(
                    run_id
                )

                self.assertTrue(result)
                self.assertEqual(run["status"], status)
                self.assertIsNotNone(run["finished_at"])

    def test_terminal_status_cannot_be_changed(self):
        run_id = self._create_running_analysis()

        first_result = (
            repository.AnalysisRepository.finish_analysis_run(
                run_id,
                status="completed"
            )
        )

        second_result = (
            repository.AnalysisRepository.finish_analysis_run(
                run_id,
                status="failed",
                error_message="Should not overwrite"
            )
        )

        run = repository.AnalysisRepository.get_analysis_run(run_id)

        self.assertTrue(first_result)
        self.assertFalse(second_result)
        self.assertEqual(run["status"], "completed")
        self.assertIsNone(run["error_message"])

    def test_heartbeat_fails_after_completion(self):
        run_id = self._create_running_analysis()

        repository.AnalysisRepository.finish_analysis_run(
            run_id,
            status="completed"
        )

        result = repository.AnalysisRepository.heartbeat_analysis_run(
            run_id
        )

        self.assertFalse(result)

    def test_pending_analysis_cannot_be_finished(self):
        run_id = repository.AnalysisRepository.create_analysis_run(
            self.project_id
        )

        result = repository.AnalysisRepository.finish_analysis_run(
            run_id,
            status="completed"
        )

        run = repository.AnalysisRepository.get_analysis_run(run_id)

        self.assertFalse(result)
        self.assertEqual(run["status"], "pending")
        self.assertIsNone(run["finished_at"])

    def test_stale_analysis_is_marked_interrupted(self):
        run_id = self._create_running_analysis()

        with repository.database_connection() as connection:
            connection.execute(
                """
                UPDATE analysis_runs
                SET
                    last_heartbeat_at = datetime(
                        'now',
                        '-60 minutes'
                    ),
                    updated_at = datetime(
                        'now',
                        '-60 minutes'
                    )
                WHERE id = ?
                """,
                (run_id,)
            )

        interrupted_count = (
            repository.AnalysisRepository
            .mark_stale_analysis_runs_interrupted(
                timeout_minutes=30
            )
        )

        run = repository.AnalysisRepository.get_analysis_run(run_id)

        self.assertEqual(interrupted_count, 1)
        self.assertEqual(run["status"], "interrupted")
        self.assertEqual(
            run["completion_reason"],
            "stale_heartbeat_timeout"
        )
        self.assertIsNotNone(run["finished_at"])
        self.assertIsNotNone(run["summary_json"])

    def test_recent_analysis_is_not_marked_interrupted(self):
        run_id = self._create_running_analysis()

        interrupted_count = (
            repository.AnalysisRepository
            .mark_stale_analysis_runs_interrupted(
                timeout_minutes=30
            )
        )

        run = repository.AnalysisRepository.get_analysis_run(run_id)

        self.assertEqual(interrupted_count, 0)
        self.assertEqual(run["status"], "running")

    def test_invalid_timeout_is_rejected(self):
        with self.assertRaises(ValueError):
            (
                repository.AnalysisRepository
                .mark_stale_analysis_runs_interrupted(
                    timeout_minutes=0
                )
            )

    def test_invalid_terminal_status_is_rejected(self):
        run_id = self._create_running_analysis()

        with self.assertRaises(ValueError):
            repository.AnalysisRepository.finish_analysis_run(
                run_id,
                status="pending"
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)

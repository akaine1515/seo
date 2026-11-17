"""P0 acceptance: actual pipeline and Qt worker, with controlled HTTP and local SQLite."""
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import test_pipeline as pipeline_fixtures
from tests.test_crawler_engine import FakeSession
from core.engine import SEOOrchestrator
from database.connection import database_connection
from database.sites import SiteRepository, validate_settings
from database.repository import ProjectRepository, AnalysisRepository
from modules.crawler.engine import CrawlerEngine


class ProductP0Tests(unittest.TestCase):
    # Reuse fixture setup without inheriting unrelated tests.
    setUp = pipeline_fixtures.PipelineTests.setUp

    def test_five_sites_duplicate_inactive_and_preserved_history(self):
        from database.connection import initialize_database
        initialize_database()
        ids = [SiteRepository.register(f'Site {i}', f'https://site{i}.com') for i in range(5)]
        with self.assertRaisesRegex(ValueError, 'already registered'):
            SiteRepository.register('Duplicate', 'https://www.site0.com/path#fragment')
        with self.assertRaisesRegex(ValueError, 'at most five'):
            SiteRepository.register('Sixth', 'https://sixth.com')
        run = AnalysisRepository.create_analysis_run(ids[0])
        SiteRepository.configure(ids[0], name='Renamed', active=False, settings={'max_depth': 1, 'excluded_paths': ['/cart']})
        site = SiteRepository.list_sites()[0]
        self.assertEqual(site['name'], 'Renamed')
        self.assertFalse(site['is_active'])
        self.assertEqual(site['settings']['excluded_paths'], ['/cart'])
        self.assertEqual(AnalysisRepository.get_analysis_run(run)['project_id'], ids[0])
        with self.assertRaisesRegex(ValueError, 'inactive'):
            SEOOrchestrator().run_full_pipeline('', {'project_id': ids[0]})
        ProjectRepository.delete_project(ids[0])
        self.assertIsNone(AnalysisRepository.get_analysis_run(run))
        with database_connection() as conn:
            self.assertIsNone(conn.execute('SELECT * FROM site_settings WHERE project_id=?', (ids[0],)).fetchone())
        self.assertTrue(SiteRepository.register('Sixth', 'https://sixth.com'))

    def test_max_pages_is_partial_and_settings_are_saved_in_snapshot(self):
        engine = SEOOrchestrator()
        result = engine.run_full_pipeline('https://example.com', {'max_pages': 1, 'request_interval': 0})
        self.assertEqual(result['meta']['pipeline_status'], 'partial')
        self.assertEqual(result['meta']['crawl_status'], 'partial')
        self.assertEqual(result['meta']['coverage']['attempted'], 1)
        self.assertEqual(result['meta']['coverage']['discovered'], 2)
        self.assertEqual(result['meta']['coverage']['queued_remaining'], 1)
        self.assertEqual(result['meta']['settings']['max_pages'], 1)
        self.assertTrue(result['meta']['algorithm_version'])
        self.assertEqual(engine.load_result(result['meta']['analysis_run_id'])['meta']['pipeline_status'], 'partial')
        rerun = engine.run_full_pipeline('https://example.com', {'max_pages': 2, 'request_interval': 0})
        self.assertEqual(rerun['meta']['crawl_status'], 'completed')
        self.assertEqual(rerun['meta']['pipeline_status'], 'partial')  # No competitor source.
        self.assertIsNotNone(engine.load_result(result['meta']['analysis_run_id']))

    def test_excluded_paths_and_depth_are_applied_before_requests(self):
        for settings in [{'excluded_paths': ['/about']}, {'max_depth': 0}]:
            result = SEOOrchestrator().run_full_pipeline('https://example.com', {**settings, 'request_interval': 0})
            self.assertEqual(len(result['crawled_pages']), 1)
            self.assertEqual(result['meta']['coverage']['scope_excluded'], 1)
            self.assertEqual(result['meta']['coverage']['queued_remaining'], 0)
        with CrawlerEngine(1) as crawler:
            crawler.base_domain = 'example.com'
            self.assertFalse(crawler.is_internal_url('https://external.com'))
            crawler.excluded_paths = ['/cart']
            self.assertEqual(crawler.request_page('https://example.com/cart')['status'], 'excluded')

    def test_cancel_preserves_pages_and_never_claims_completed(self):
        event = threading.Event()
        original_get = FakeSession.get
        def get(session, url, **kwargs):
            response = original_get(session, url, **kwargs)
            event.set()  # Stop during a bounded operation: preserve the response/page already received.
            return response
        with patch.object(FakeSession, 'get', get):
            result = SEOOrchestrator().run_full_pipeline('https://example.com', {'request_interval': 0}, cancel_event=event)
        self.assertEqual(result['meta']['pipeline_status'], 'cancelled')
        self.assertEqual(result['meta']['crawl_status'], 'cancelled')
        self.assertEqual(len(result['crawled_pages']), 1)
        self.assertEqual(AnalysisRepository.get_analysis_run(result['meta']['analysis_run_id'])['status'], 'cancelled')
        self.assertIsNotNone(SEOOrchestrator.load_result(result['meta']['analysis_run_id']))

    def test_invalid_settings_are_rejected(self):
        for settings in [{'max_depth': True}, {'excluded_paths': ['cart']}, {'request_interval': float('nan')}, {'unknown': 1}]:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                validate_settings(settings)

    def test_site_settings_used_by_registered_run(self):
        from database.connection import initialize_database
        initialize_database()
        project_id = SiteRepository.register('Owned site', 'https://example.com')
        SiteRepository.configure(project_id, settings={'max_pages': 1, 'request_interval': 0})
        result = SEOOrchestrator().run_full_pipeline('', {'project_id': project_id})
        self.assertEqual(result['meta']['coverage']['attempted'], 1)
        self.assertEqual(result['meta']['project_id'], project_id)

    def test_export_metadata_matches_persisted_status_and_settings(self):
        import pandas as pd
        from openpyxl import load_workbook
        from modules.reporting.excel_reporter import ExcelReportGenerator
        from modules.reporting.html_reporter import HTMLReportGenerator
        result = SEOOrchestrator().run_full_pipeline('https://example.com', {'max_pages': 1, 'request_interval': 0})
        path = Path(self.temp.name) / 'report.xlsx'
        ExcelReportGenerator().generate_report(str(path), result)
        metadata = pd.read_excel(path, sheet_name='Run Metadata').iloc[0]
        saved = SEOOrchestrator.load_result(result['meta']['analysis_run_id'])['meta']
        self.assertEqual(metadata['pipeline_status'], saved['pipeline_status'])
        self.assertEqual(json.loads(metadata['settings']), saved['settings'])
        self.assertEqual(json.loads(metadata['coverage']), saved['coverage'])
        book = load_workbook(path)
        self.assertTrue(book['Run Metadata'].auto_filter.ref)
        book.close()
        html_path = Path(self.temp.name) / 'report.html'
        HTMLReportGenerator.generate_report(str(html_path), result)
        self.assertIn('Analysis: partial', html_path.read_text())
        self.assertIn('Observed coverage:', html_path.read_text())

    def test_desktop_registration_settings_and_background_flow(self):
        import os
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PySide6.QtWidgets import QApplication, QMessageBox
        import time
        from modules.ui.main_window import MainWindow
        app = QApplication.instance() or QApplication([])
        with patch('modules.ui.main_window.QInputDialog.getText', return_value=('My site', True)), \
                patch.object(QMessageBox, 'information'), patch.object(QMessageBox, 'warning') as warning, \
                patch.object(QMessageBox, 'critical') as critical:
            window = MainWindow(SEOOrchestrator())
            try:
                window.url_input.setText('https://example.com')
                window.register_site()
                self.assertEqual(window.site_selector.currentText(), 'My site')
                window.max_pages_input.setValue(1)
                window.interval_input.setValue(0)
                window.save_site_settings()
                self.assertEqual(SiteRepository.list_sites()[0]['settings']['max_pages'], 1)
                window.start_analysis()
                deadline = time.monotonic() + 10
                while window.worker.isRunning() and time.monotonic() < deadline:
                    app.processEvents()
                    time.sleep(0.01)  # Release the GIL for Python code inside QThread.
                self.assertFalse(window.worker.isRunning())
                app.processEvents()
                self.assertEqual(window.last_result_data['meta']['pipeline_status'], 'partial')
                self.assertEqual(window.kpi_label.text(), 'نتایج ناقص')
                self.assertFalse(window.stop_btn.isEnabled())
                self.assertTrue(window.run_btn.isEnabled())
                warning.assert_not_called()
                critical.assert_not_called()
            finally:
                if window.worker and window.worker.isRunning():
                    window.worker.cancel()
                    window.worker.wait(10000)
                window.close()

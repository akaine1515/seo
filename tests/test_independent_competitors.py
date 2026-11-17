"""V3: independent execution must preserve the own-site run and data lineage."""
import json
import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from openpyxl import load_workbook
from tests import test_pipeline as fixtures
from tests import test_keyword_plan as keyword_fixtures
from tests.test_crawler_engine import FakeSession, FakeResponse
from core.engine import SEOOrchestrator
from database.connection import initialize_database, database_connection
from database.results import AnalysisResultRepository
from database.stages import StageResultRepository
from database.sites import SiteRepository
from database.competitors import CompetitorChoiceRepository
from database.repository import ProjectRepository, AnalysisRepository
from modules.crawler.engine import CrawlerEngine
from modules.reporting.excel_reporter import ExcelReportGenerator
from modules.reporting.html_reporter import HTMLReportGenerator
from modules.serp.google_search import FileSERPProvider


class IndependentCompetitorTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp
    pipeline = keyword_fixtures.KeywordPlanTests.pipeline

    def fetch_only_competitors(self, seen, status=200, cancel=None):
        def get(session, url, **kwargs):
            self.assertNotIn('example.com', url, 'Independent stage fetched the own site')
            seen.append(url)
            response = FakeResponse(url, keyword_fixtures.RIVAL)
            response.status_code = status
            if cancel is not None:
                cancel.set()
            return response
        return get

    def source_rows(self, run_id):
        with database_connection() as conn:
            rows = {table: [tuple(r) for r in conn.execute(f'SELECT * FROM {table} WHERE {column}=? ORDER BY rowid', (run_id,))]
                    for table, column in [('analysis_runs','id'), ('pages','analysis_run_id'),
                        ('analysis_results', 'analysis_run_id'), ('crawl_queue','analysis_run_id'),
                        ('crawl_events','analysis_run_id'), ('page_links','analysis_run_id')]}
            rows['page_contents'] = [tuple(r) for r in conn.execute('SELECT * FROM page_contents '
                'WHERE page_id IN (SELECT id FROM pages WHERE analysis_run_id=?) ORDER BY id', (run_id,))]
            return rows

    def test_independent_result_is_append_only_and_no_own_network_or_crawl(self):
        source = self.pipeline()
        run_id, project_id = source['meta']['analysis_run_id'], source['meta']['project_id']
        original = AnalysisResultRepository.load(run_id)
        rows = self.source_rows(run_id)
        seen = []
        engine = SEOOrchestrator()  # Reuse dated SERP from source; no provider required.
        with patch.object(FakeSession, 'get', self.fetch_only_competitors(seen)), patch.object(CrawlerEngine, 'run', side_effect=AssertionError('Must not crawl')):
            first = engine.run_competitor_stage(run_id, {'competitors_by_keyword': {'طراحی سایت': ['rival.com']}})
            second = engine.run_competitor_stage(run_id, {'competitors_by_keyword': {'آموزش': ['other.com']}})
        self.assertEqual(len(seen), 2)
        self.assertEqual(AnalysisResultRepository.load(run_id), original)
        self.assertEqual(self.source_rows(run_id), rows)
        self.assertEqual(len(AnalysisRepository.get_project_analysis_runs(project_id)), 1)
        self.assertNotEqual(first['meta']['stage_result_id'], second['meta']['stage_result_id'])
        self.assertEqual(first['meta']['analysis_run_id'], run_id)
        self.assertEqual(first['meta']['source_analysis_run_id'], run_id)
        self.assertEqual(first['meta']['stage_status'], 'completed')
        self.assertEqual(first['meta']['finished_at'], source['meta']['finished_at'])
        self.assertEqual(first['serp'], source['serp'])  # Original SERP observation/import timestamps.
        self.assertEqual(first['audit_summary'], source['audit_summary'])
        self.assertEqual(first['keyword_analysis'], original['keyword_analysis'])
        plan = next(p for p in first['keyword_strategies'] if p['keyword'] == 'طراحی سایت')
        self.assertEqual([p['domain'] for p in plan['competitor_patterns']], ['rival.com'])
        saved = StageResultRepository.load(first['meta']['stage_result_id'])
        self.assertEqual(saved['keyword_strategies'], first['keyword_strategies'])
        self.assertNotIn('raw_text', saved['competitor_analysis'][0])
        self.assertIn('raw_text', first['competitor_analysis'][0])
        self.assertEqual(len(StageResultRepository.list_for_project(project_id)), 2)
        with self.assertRaises(ValueError):
            StageResultRepository.finish(first['meta']['stage_result_id'], 'completed', first)
        ProjectRepository.delete_project(project_id)
        self.assertIsNone(StageResultRepository.load(first['meta']['stage_result_id']))
        with database_connection() as conn:
            self.assertFalse(conn.execute('PRAGMA foreign_key_check').fetchall())

    def test_fresh_dated_import_without_recrawl_and_exports_show_source(self):
        source = self.pipeline()
        run_id = source['meta']['analysis_run_id']
        directory = Path(self.temp.name)
        path = directory / 'serp.json'
        payload = {'source': 'new authorized export', 'retrieved_at': '2026-11-18T00:00:00Z',
                   'results': [{'keyword': 'طراحی سایت', 'organic_results': [{'url': 'https://fresh.com/guide', 'position': 2}]}]}
        path.write_text(json.dumps(payload))
        with patch.object(FakeSession, 'get', self.fetch_only_competitors([])):
            result = SEOOrchestrator(FileSERPProvider(str(path))).run_competitor_stage(run_id,
                {'competitors_by_keyword': {'طراحی سایت': ['fresh.com']}, 'retain_competitor_text': True})
        self.assertEqual(result['serp']['retrieved_at'], payload['retrieved_at'])
        self.assertEqual(result['serp']['source'], payload['source'])
        self.assertEqual(result['meta']['finished_at'], source['meta']['finished_at'])
        self.assertIn('raw_text', StageResultRepository.load(result['meta']['stage_result_id'])['competitor_analysis'][0])
        ExcelReportGenerator().generate_report(str(directory/'stage.xlsx'), result)
        HTMLReportGenerator.generate_report(str(directory/'stage.html'), result)
        book = load_workbook(directory/'stage.xlsx')
        metadata = list(book['Run Metadata'].values)
        self.assertIn('source_analysis_run_id', metadata[0])
        self.assertEqual(metadata[1][metadata[0].index('stage_result_id')], result['meta']['stage_result_id'])
        book.close()
        html = (directory/'stage.html').read_text()
        self.assertIn(f"Independent competitor stage #{result['meta']['stage_result_id']}", html)
        self.assertIn('Own-site crawl evidence reused', html)
        self.assertIn(payload['retrieved_at'], html)
        self.assertIn(source['meta']['finished_at'], html)

    def test_budget_failure_and_stop_never_report_complete(self):
        source = self.pipeline()
        run_id = source['meta']['analysis_run_id']
        seen = []
        choices = {'طراحی سایت': ['rival.com'], 'آموزش': ['rival.com']}
        class BudgetProvider:
            source = 'controlled dated observations'
            retrieved_at = '2026-11-17T00:00:00Z'
            def search(self, keywords):
                return [{'keyword': term, 'organic_results': [{'url': f'https://rival.com/{index}', 'position': 1}]}
                        for index, term in enumerate(choices)]
        with patch.object(FakeSession, 'get', self.fetch_only_competitors(seen)):
            budget = SEOOrchestrator(BudgetProvider()).run_competitor_stage(run_id,
                {'competitors_by_keyword': choices, 'competitor_max_pages': 1})
        self.assertEqual(len(seen), 1)
        self.assertEqual(budget['meta']['stage_status'], 'partial')
        self.assertEqual(budget['content_gap_analysis']['status'], 'partial')
        plan = next(p for p in budget['keyword_strategies'] if p['keyword'] == 'آموزش')
        self.assertEqual(plan['competitor_patterns'][0]['status'], 'not_analyzed')
        with patch.object(FakeSession, 'get', self.fetch_only_competitors([], status=503)):
            failed_pages = SEOOrchestrator().run_competitor_stage(run_id, {'competitors_by_keyword': choices})
        self.assertEqual(failed_pages['meta']['stage_status'], 'partial')
        self.assertFalse(failed_pages['content_gap_analysis']['content_gaps'])
        cancel = threading.Event()
        cancel.set()
        with patch.object(FakeSession, 'get', side_effect=AssertionError('Stopped stage made HTTP call')):
            stopped = SEOOrchestrator().run_competitor_stage(run_id, cancel_event=cancel)
        self.assertEqual(stopped['meta']['stage_status'], 'cancelled')
        self.assertEqual(stopped['meta']['pipeline_status'], 'cancelled')
        self.assertEqual(StageResultRepository.list_for_project(source['meta']['project_id'])[0]['status'], 'cancelled')
        during_fetch = threading.Event()
        with patch.object(FakeSession, 'get', self.fetch_only_competitors([], cancel=during_fetch)):
            stopped_later = SEOOrchestrator(BudgetProvider()).run_competitor_stage(run_id,
                {'competitors_by_keyword': choices}, cancel_event=during_fetch)
        self.assertEqual(stopped_later['meta']['stage_status'], 'cancelled')
        self.assertLessEqual(len(stopped_later['competitor_analysis']), 1)

    def test_invalid_choices_record_failure_without_touching_source(self):
        source = self.pipeline()
        run_id, project_id = source['meta']['analysis_run_id'], source['meta']['project_id']
        for mapping in [{'طراحی سایت': ['unknown.com']}, {'طراحی سایت': ['rival.com']*6}]:
            with self.subTest(mapping=mapping), patch.object(FakeSession, 'get', side_effect=AssertionError('Invalid choice fetched')):
                with self.assertRaises(ValueError):
                    SEOOrchestrator().run_competitor_stage(run_id, {'competitors_by_keyword': mapping})
        history = StageResultRepository.list_for_project(project_id)
        self.assertEqual([r['status'] for r in history], ['failed', 'failed'])
        self.assertTrue(all(StageResultRepository.load(r['id']) is None for r in history))
        self.assertEqual(AnalysisResultRepository.load(run_id)['keyword_inventory'], source['keyword_inventory'])
        self.assertEqual(CompetitorChoiceRepository.load(project_id), {})

    def test_missing_serp_and_missing_selection_are_explicitly_partial(self):
        source = self.pipeline()
        run_id = source['meta']['analysis_run_id']
        with patch.object(FakeSession, 'get', side_effect=AssertionError('No selection must not fetch')):
            waiting = SEOOrchestrator().run_competitor_stage(run_id)
        self.assertEqual(waiting['competitor_status'], 'awaiting_selection')
        self.assertEqual(waiting['meta']['stage_status'], 'partial')
        self.assertEqual(waiting['content_gap_analysis']['status'], 'unavailable')
        without_serp = SEOOrchestrator().run_full_pipeline('https://example.com', {'max_pages': 1, 'request_interval': 0})
        with patch.object(FakeSession, 'get', side_effect=AssertionError('Unavailable source must not fetch')):
            unavailable = SEOOrchestrator().run_competitor_stage(without_serp['meta']['analysis_run_id'])
        self.assertEqual(unavailable['competitor_status'], 'unavailable')
        self.assertEqual(unavailable['meta']['stage_status'], 'partial')
        self.assertFalse(unavailable['competitor_analysis'])
        self.assertFalse(unavailable['content_gap_analysis']['content_gaps'])

    def test_scope_and_readable_source_are_required_before_stage_creation(self):
        source = self.pipeline()
        run_id, project_id = source['meta']['analysis_run_id'], source['meta']['project_id']
        for options in [{'project_id': project_id+1}, {'competitor_max_pages': True}, {'request_interval': -1}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                SEOOrchestrator().run_competitor_stage(run_id, options)
        SiteRepository.configure(project_id, active=False)
        with self.assertRaises(ValueError):
            SEOOrchestrator().run_competitor_stage(run_id)
        SiteRepository.configure(project_id, active=True)
        with database_connection() as conn:
            conn.execute('DELETE FROM page_contents')
        with self.assertRaises(ValueError):
            SEOOrchestrator().run_competitor_stage(run_id)
        self.assertEqual(StageResultRepository.list_for_project(project_id), [])

    def test_v9_migration_preserves_snapshot_and_enforces_fk(self):
        source = self.pipeline()
        run_id = source['meta']['analysis_run_id']
        original = AnalysisResultRepository.load(run_id)
        with database_connection() as conn:
            conn.execute('DROP TABLE analysis_stage_results')
            conn.execute('DELETE FROM schema_versions WHERE version>=10')
        initialize_database()
        initialize_database()
        self.assertEqual(AnalysisResultRepository.load(run_id), original)
        stage_id = StageResultRepository.start(run_id, 'fixture')
        StageResultRepository.finish(stage_id, 'cancelled')
        with database_connection() as conn:
            self.assertEqual(conn.execute('SELECT MAX(version) FROM schema_versions').fetchone()[0], 10)
            self.assertFalse(conn.execute('PRAGMA foreign_key_check').fetchall())
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            StageResultRepository.start(run_id+1000, 'fixture')

    def test_native_button_runs_background_stage_and_history_reopens(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication, QInputDialog
        from PySide6.QtCore import Qt
        from modules.ui.main_window import MainWindow
        source = self.pipeline()
        app = QApplication.instance() or QApplication([])
        errors, calls = [], []
        with patch.object(sys, 'excepthook', lambda *args: errors.append(args)), patch.object(FakeSession, 'get', self.fetch_only_competitors(calls)):
            window = MainWindow(SEOOrchestrator())
            try:
                window.on_analysis_finished(source)
                selection = window.competitor_selection
                selection.term.setCurrentText('طراحی سایت')
                selection.list.item(0).setCheckState(Qt.CheckState.Checked)
                selection.run_stage_btn.click()
                self.assertIsNotNone(window.worker)
                deadline = time.monotonic()+10
                while window.worker.isRunning() and time.monotonic()<deadline:
                    app.processEvents()
                    time.sleep(.005)
                self.assertFalse(window.worker.isRunning())
                app.processEvents()
                self.assertEqual(len(calls), 1)
                self.assertTrue(window.last_result_data['meta']['stage_result_id'])
                self.assertTrue(window.run_btn.isEnabled())
                self.assertFalse(window.stage_banner.isHidden())
                with patch.object(QInputDialog, 'getItem', side_effect=lambda parent,title,prompt,items,*args: (items[0], True)):
                    window.open_competitor_history()
                self.assertEqual(window.last_result_data['meta']['source_analysis_run_id'], source['meta']['analysis_run_id'])
                self.assertEqual(errors, [])
                window.site_selector.setCurrentIndex(0)
                self.assertTrue(window.stage_banner.isHidden())
            finally:
                if window.worker and window.worker.isRunning():
                    window.worker.cancel()
                    while window.worker.isRunning():
                        app.processEvents()
                        time.sleep(.005)
                window.close()

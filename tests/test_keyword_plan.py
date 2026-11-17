"""Acceptance of keyword-specific evidence, choices, strategies, maps and exports."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_pipeline as fixtures
from tests.test_crawler_engine import FakeSession, FakeResponse
from core.engine import SEOOrchestrator
from database.connection import initialize_database, database_connection
from database.competitors import CompetitorChoiceRepository, validate_choices
from database.repository import ProjectRepository
from modules.crawler.parser import PageParser
from modules.crawler.transport import RequestPolicy
from modules.strategy.keyword_plan import keyword_inventory, build_keyword_plans
from modules.audit.technical_rules import page_checks
from modules.reporting.excel_reporter import ExcelReportGenerator
from modules.reporting.html_reporter import HTMLReportGenerator
from openpyxl import load_workbook

OWN = '''<html lang="fa"><head><title>طراحی سایت</title><meta name="description" content="آموزش طراحی سایت"><meta name="viewport" content="width=device-width"><script type="application/ld+json">{"@type":"Article"}</script></head><body><h1>طراحی سایت</h1><h4>طراحی سایت فروشگاهی</h4><h6>آموزش طراحی سایت</h6><article><p>طراحی سایت طراحی سایت آموزش طراحی سایت</p></article><img src="/hero.png" alt="طراحی سایت" width="640" height="480"><img src="/missing.png"></body></html>'''
RIVAL = '''<html><head><title>طراحی سایت</title></head><body><h1>طراحی سایت حرفه‌ای</h1><article><p>طراحی سایت ارزان طراحی سایت ارزان طراحی سایت ارزان</p></article><a href="/guide">راهنما</a></body></html>'''


class Provider:
    source = 'Synthetic authorized fixture'
    retrieved_at = '2026-11-17T00:00:00+00:00'
    def search(self, keywords):
        return [{'keyword': term, 'organic_results': [{'url': f'https://{domain}/{i}', 'position': i+1}
                  for i, domain in enumerate(['rival.com', 'other.com'])]}
                for term in ['طراحی سایت', 'آموزش'] if term in keywords]


class KeywordPlanTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp

    def pipeline(self, **options):
        def get(session, url, **kwargs):
            response = FakeResponse(url, OWN if 'example.com' in url else RIVAL)
            session.responses.append(response)
            return response
        with patch.object(FakeSession, 'get', get):
            return SEOOrchestrator(Provider()).run_full_pipeline('https://example.com', {'max_pages': 1, 'request_interval': 0, **options})

    def test_parser_inventory_images_and_timing_are_measured_not_vitals(self):
        parsed = PageParser.parse(OWN, 'https://example.com/', 200)
        self.assertEqual([h['level'] for h in parsed['headings']], [1, 4, 6])
        self.assertEqual(parsed['tag_counts']['img'], 2)
        self.assertEqual(parsed['images'][0]['url'], 'https://example.com/hero.png')
        self.assertIsNone(parsed['images'][0]['file_bytes'])
        self.assertTrue(parsed['structured_data'][0]['valid_json'])
        codes = {r['rule_id'] for r in page_checks(parsed)}
        self.assertTrue({'HEADING_ORDER', 'IMAGE_SIZE_UNDECLARED', 'IMAGE_ALT_MISSING'} <= codes)
        session = FakeSession()
        with patch('modules.crawler.transport.time.perf_counter', side_effect=[1.0, 1.05, 1.25]):
            response = RequestPolicy(interval=0).get(session, 'https://example.com', allow_redirects=False)
        self.assertEqual(response.seo_metrics['html_fetch_ms'], 250)
        self.assertEqual(response.seo_metrics['headers_ms'], 50)
        self.assertIsNone(response.seo_metrics['core_web_vitals'])

    def test_children_are_observed_with_sources_and_contiguous_parent(self):
        parsed = PageParser.parse(OWN, 'https://example.com/', 200)
        rows = {r['term']: r for r in keyword_inventory([parsed])}
        self.assertIn('طراحی سایت', rows['طراحی']['children'])
        self.assertIn('طراحی سایت فروشگاهی', rows['طراحی سایت']['children'])
        self.assertNotIn('فروشگاه اینترنتی', rows)
        self.assertEqual(rows['طراحی سایت']['source_pages'], ['https://example.com/'])
        self.assertGreater(rows['طراحی سایت']['locations']['title'], 0)

    def test_query_isolation_persistence_and_failed_evidence(self):
        result = self.pipeline(competitors_by_keyword={'طراحی سایت': ['rival.com'], 'آموزش': ['other.com']})
        plans = {p['keyword']: p for p in result['keyword_strategies']}
        self.assertEqual([p['domain'] for p in plans['طراحی سایت']['competitor_patterns']], ['rival.com'])
        self.assertEqual([p['domain'] for p in plans['آموزش']['competitor_patterns']], ['other.com'])
        pattern = plans['طراحی سایت']['competitor_patterns'][0]
        self.assertEqual(pattern['keyword_locations']['title'], 1)
        self.assertTrue(any(a['kind'] == 'expand_topic' and 'ارزان' in a['topic'] for a in plans['طراحی سایت']['actions']))
        self.assertEqual(CompetitorChoiceRepository.load(result['meta']['project_id']), result['competitor_selections'])
        loaded = SEOOrchestrator.load_result(result['meta']['analysis_run_id'])
        self.assertEqual(loaded['keyword_strategies'], result['keyword_strategies'])
        second = self.pipeline()
        self.assertEqual(second['competitor_selections'], result['competitor_selections'])
        self.assertIsNotNone(SEOOrchestrator.load_result(result['meta']['analysis_run_id']))
        self.assertEqual(len(second['keyword_mindmaps']), len(second['keyword_strategies']))
        self.assertTrue(second['page_details'][0]['performance']['html_fetch_ms'] >= 0)
        ProjectRepository.delete_project(result['meta']['project_id'])
        self.assertEqual(CompetitorChoiceRepository.load(result['meta']['project_id']), {})

    def test_choices_five_per_keyword_and_unknown_domain_rejected(self):
        candidates = {k: [{'domain': f'site{i}.com'} for i in range(7)] for k in ['alpha','beta']}
        choice = {'alpha': [f'site{i}.com' for i in range(5)], 'beta': ['site5.com','site6.com']}
        self.assertEqual(validate_choices(choice, candidates), choice)  # union may exceed five
        with self.assertRaises(ValueError):
            validate_choices({'alpha': [f'site{i}.com' for i in range(6)]}, candidates)
        with self.assertRaises(ValueError):
            validate_choices({'alpha': ['unseen.com']}, candidates)
        result = self.pipeline()
        with self.assertRaises(ValueError):
            self.pipeline(competitors_by_keyword={'طراحی سایت': ['absent.com']})
        self.assertEqual(CompetitorChoiceRepository.load(result['meta']['project_id']), {})

    def test_unavailable_or_failed_competitor_does_not_become_no_gap_success(self):
        parsed = PageParser.parse(OWN, 'https://example.com/', 200)
        candidates = {'طراحی سایت': [{'domain': 'rival.com', 'url': 'https://rival.com/x', 'position': 1}]}
        _, plans = build_keyword_plans([parsed], candidates, {'طراحی سایت':['rival.com']},
            [{'url':'https://rival.com/x','success':False,'error':'robots blocked'}], {'issues':[]})
        plan = next(p for p in plans if p['keyword'] == 'طراحی سایت')
        self.assertEqual(plan['competitor_status'], 'partial')
        self.assertEqual(plan['competitor_patterns'][0]['status'], 'failed')
        self.assertFalse(any(a['kind'] == 'expand_topic' for a in plan['actions']))

    def test_v8_migration_preserves_existing_site_and_choices_cascade(self):
        initialize_database()
        project = ProjectRepository.create_project('old', 'https://example.com', 'example.com')
        with database_connection() as conn:
            conn.execute('DROP TABLE keyword_competitor_choices')
            conn.execute('DROP TABLE analysis_stage_results')
            conn.execute('DELETE FROM schema_versions WHERE version>=9')
        initialize_database()
        CompetitorChoiceRepository.save(project, {'alpha': []}, {'alpha': []})
        self.assertIsNotNone(ProjectRepository.get_project(project))
        self.assertEqual(CompetitorChoiceRepository.load(project), {'alpha': []})
        with database_connection() as conn:
            self.assertFalse(conn.execute('PRAGMA foreign_key_check').fetchall())

    def test_exports_preserve_keyword_strategies_and_escape_sources(self):
        result = self.pipeline(competitors_by_keyword={'طراحی سایت':['rival.com']})
        result['keyword_mindmaps'][0]['children'].append({'label':'<script>alert(1)</script>', 'url':'javascript:alert(1)'})
        directory = Path(self.temp.name)
        ExcelReportGenerator().generate_report(str(directory/'plan.xlsx'), result)
        HTMLReportGenerator.generate_report(str(directory/'plan.html'), result)
        book = load_workbook(directory/'plan.xlsx')
        for sheet in ['Keyword Children','Keyword Strategy','Competitor Patterns','Keyword Mindmaps','HTML Tags','Images','HTTP Performance']:
            self.assertIn(sheet, book.sheetnames)
        self.assertEqual(book['Keyword Children'].max_row-1, len(result['keyword_inventory']))
        book.close()
        html = (directory/'plan.html').read_text()
        self.assertIn('طراحی سایت', html)
        self.assertIn('مایندمپ', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('href="javascript:', html)

    def test_native_keyword_selection_cap_strategy_and_site_reset(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt
        from modules.ui.main_window import MainWindow
        result = self.pipeline()
        app = QApplication.instance() or QApplication([])
        errors = []
        with patch.object(sys, 'excepthook', lambda *args: errors.append(args)):
            window = MainWindow(SEOOrchestrator())
            try:
                window.on_analysis_finished(result)
                selection = window.competitor_selection
                self.assertEqual(window.keyword_evidence.table.rowCount(), len(result['keyword_inventory']))
                selection.candidates = {'طراحی سایت': [{'domain':f'site{i}.com', 'url':f'https://site{i}.com/', 'position':i+1} for i in range(6)]}
                selection.term.clear()
                selection.term.addItem('طراحی سایت')
                for i in range(6):
                    selection.list.item(i).setCheckState(Qt.CheckState.Checked)
                self.assertEqual(len(selection.selected()), 5)
                selection.save()
                self.assertEqual(len(CompetitorChoiceRepository.load(result['meta']['project_id'])['طراحی سایت']), 5)
                self.assertTrue(window.strategy_map.tree.topLevelItemCount())
                window.site_selector.setCurrentIndex(0)
                self.assertFalse(window.strategy_map.tree.topLevelItemCount())
                self.assertEqual(window.keyword_evidence.table.rowCount(), 0)
                self.assertEqual(errors, [])
            finally:
                window.close()

    def test_existing_domain_page_budget_remains_partial_for_unfetched_query(self):
        class BudgetProvider:
            source = 'budget fixture'
            def search(self, keywords):
                return [{'keyword': term, 'organic_results': [{'url': f'https://rival.com/{i}', 'position':1}]} for i,term in enumerate(['طراحی سایت','آموزش'])]
        def get(session, url, **kwargs):
            return FakeResponse(url, OWN if 'example.com' in url else RIVAL)
        with patch.object(FakeSession, 'get', get):
            result = SEOOrchestrator(BudgetProvider()).run_full_pipeline('https://example.com',
                {'max_pages':1, 'request_interval':0, 'competitor_max_pages':1,
                 'competitors_by_keyword': {'طراحی سایت':['rival.com'],'آموزش':['rival.com']}})
        self.assertEqual(len(result['competitor_analysis']), 1)
        self.assertEqual(result['competitor_status'], 'partial')
        plan = next(p for p in result['keyword_strategies'] if p['keyword']=='آموزش')
        self.assertEqual(plan['competitor_patterns'][0]['status'], 'not_analyzed')

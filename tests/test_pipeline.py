"""Offline integration across actual crawler, parser, analyzers, DB and exports."""
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database.connection as connection_module
from core.engine import SEOOrchestrator
from modules.keywords.analyzer import KeywordAnalyzer
from modules.keywords.extractor import KeywordExtractor
from modules.competitors.analyzer import CompetitorAnalyzer
from modules.competitors.discovery import CompetitorDiscovery
from modules.strategy.content_gap import ContentGapStrategyEngine
from modules.serp.google_search import FileSERPProvider
from modules.crawler.engine import CrawlerEngine
from modules.crawler.parser import PageParser
from modules.reporting.excel_reporter import ExcelReportGenerator
from modules.reporting.html_reporter import HTMLReportGenerator
from tests.test_crawler_engine import FakeSession, FakeResponse, FakeRobotsManager, FakeSitemapManager


class PipelineTests(unittest.TestCase):
    def setUp(self):
        # Load the bundled offline PSL before globally replacing requests.Session.
        # tldextract constructs a real Session to mount its file adapter even with no URLs.
        from core.domains import site_domain
        site_domain('https://example.com')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        for target, value in [
            ('database.connection.DB_PATH', Path(self.temp.name) / 'test.db'),
            ('modules.crawler.engine.requests.Session', FakeSession),
            ('modules.crawler.engine.RobotsManager', FakeRobotsManager),
            ('modules.competitors.analyzer.RobotsManager', FakeRobotsManager),
            ('modules.crawler.engine.SitemapManager', FakeSitemapManager),
        ]:
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_actual_tf_idf_formula(self):
        data = {10: {'unigrams': {'alpha': 2}, 'total_tokens': 4},
                20: {'unigrams': {'beta': 1}, 'total_tokens': 2}}
        actual = KeywordAnalyzer().compute_tf_idf(data)
        self.assertAlmostEqual(actual[10]['alpha']['tf_idf_score'], .5 * (math.log(3) + 1))
        self.assertEqual(actual[20]['beta']['raw_frequency'], 1)

    def test_no_provider_saves_real_pages_without_fake_competitors(self):
        engine = SEOOrchestrator()
        result = engine.run_full_pipeline('https://example.com', {'max_pages': 1})
        self.assertEqual(len(result['crawled_pages']), 1)
        self.assertTrue(result['keyword_analysis']['keywords'])
        self.assertEqual(result['project_competitors'], [])
        self.assertEqual(result['competitor_status'], 'unavailable')
        self.assertEqual(result['content_gap_analysis']['content_gaps'], [])
        self.assertTrue(result['meta']['warnings'])
        saved = engine.load_result(result['meta']['analysis_run_id'])
        self.assertEqual(saved['keyword_analysis']['keywords'], result['keyword_analysis']['keywords'])
        self.assertFalse(any(i['rule_id'] == 'H1_MISSING' for i in result['audit_summary']['issues']))
        second = engine.run_full_pipeline('https://example.com', {'max_pages': 1})
        self.assertNotEqual(second['meta']['analysis_run_id'], result['meta']['analysis_run_id'])
        self.assertIsNotNone(engine.load_result(result['meta']['analysis_run_id']))
        ExcelReportGenerator().generate_report(str(Path(self.temp.name) / 'report.xlsx'), result)
        report_path = Path(self.temp.name) / 'report.html'
        result['meta']['warnings'].append('<script>alert(1)</script>')
        HTMLReportGenerator.generate_report(str(report_path), result)
        html = report_path.read_text()
        self.assertIn('Content gap analysis unavailable or incomplete', html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_serp_discovery_selected_pages_gap_and_evidence(self):
        class Provider:
            source = 'offline fixture'
            def search(self, keywords):
                self.keywords = keywords
                return [{'keyword': keywords[0], 'organic_results': [
                    {'url': 'https://rival.com/article', 'position': 1},
                    {'url': 'https://other.com/article', 'position': 2}]}]
        original_get = FakeSession.get
        def get(session, url, **kwargs):
            if 'example.com' in url:
                return original_get(session, url, **kwargs)
            return FakeResponse(url, '<html><title>Rival guide</title><h1>Guide</h1>'
                                '<article><p>cartography cartography cartography maps maps</p>'
                                '<a href="/guide">Guide</a><a href="/guide#x">Guide</a>'
                                '<a href="mailto:a@rival.com">Email</a></article></html>')
        provider = Provider()
        with patch.object(FakeSession, 'get', get):
            result = SEOOrchestrator(provider).run_full_pipeline('https://example.com', {
                'max_pages': 1, 'selected_competitors': ['rival.com', 'other.com']})
        self.assertTrue(provider.keywords)
        self.assertEqual(result['competitor_status'], 'completed')
        self.assertEqual(len(result['competitor_analysis']), 2)
        self.assertTrue(all(item['success'] for item in result['competitor_analysis']))
        self.assertEqual(result['competitor_analysis'][0]['linking']['internal_links_count'], 1)
        gap = next(item for item in result['content_gap_analysis']['content_gaps'] if item['term'] == 'cartography')
        self.assertEqual(gap['competitor_domains_count'], 2)
        self.assertEqual(len(gap['evidence_urls']), 2)
        self.assertEqual(result['serp']['source'], 'offline fixture')

    def test_competitor_failures_are_isolated_and_responses_closed(self):
        connection_module.initialize_database()
        with CrawlerEngine(1) as crawler:
            response = FakeResponse('https://rival.com/', '')
            with patch.object(crawler, 'request_page', return_value={
                    'status': 'success', 'response': response, 'final_url': response.url}):
                results = CompetitorAnalyzer(crawler, PageParser()).analyze_batch([None, response.url])
            self.assertEqual([item['success'] for item in results], [False, False])
            self.assertTrue(response.closed)
        with CrawlerEngine(1) as crawler:
            with patch.object(crawler, 'request_page', side_effect=TimeoutError('timeout')):
                self.assertFalse(CompetitorAnalyzer(crawler, PageParser()).analyze_competitor_page('https://rival.com')['success'])

    def test_gap_domain_normalization_and_invalid_ports(self):
        self.assertEqual(ContentGapStrategyEngine._extract_clean_domain('https://www.web.com'), 'web.com')
        for url in ['https://', 'https://bad.com:abc', 'https://bad.com:99999', 'https://-bad.com', 'https://bad..com']:
            self.assertFalse(CompetitorDiscovery._is_valid_url(url), url)
        result = ContentGapStrategyEngine().analyze_gaps({1: {'كتاب': {'tf_idf_score': .5}}}, [
            {'success': True, 'url': 'https://rival.com', 'keywords_analysis': {'کتاب': {'tf_idf_score': .5}}}])
        self.assertEqual(result['keyword_overlaps_count'], 1)

    def test_file_provider_retains_source_and_filters_keywords(self):
        path = Path(self.temp.name) / 'serp.json'
        path.write_text(json.dumps({'source': 'fixture', 'retrieved_at': '2026-11-17T00:00:00Z',
            'results': [{'keyword': 'Software', 'organic_results': []}, {'keyword': 'other', 'organic_results': []}]}))
        provider = FileSERPProvider(str(path))
        self.assertEqual(len(provider.search(['software'])), 1)
        self.assertEqual(provider.source, 'fixture')

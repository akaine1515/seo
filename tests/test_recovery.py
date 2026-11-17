import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import requests
import database.connection as db
from database.repository import ProjectRepository, AnalysisRepository, CrawlEventRepository
from database.results import AnalysisResultRepository
from core.domains import site_domain
from modules.crawler.transport import RequestPolicy
from modules.competitors.discovery import CompetitorDiscovery
from modules.strategy.content_gap import ContentGapStrategyEngine
from modules.serp.google_search import FileSERPProvider
from modules.audit.engine import TechnicalSEOAuditEngine
from modules.crawler.parser import PageParser


class RecoveryTests(unittest.TestCase):
    def test_psl_private_and_multilevel_suffixes(self):
        self.assertEqual(site_domain('https://blog.example.co.uk'), 'example.co.uk')
        self.assertNotEqual(site_domain('https://a.github.io'), site_domain('https://b.github.io'))
        self.assertEqual(CompetitorDiscovery._clean_domain('https://a.example.com.au'), 'example.com.au')
        self.assertIsNone(CompetitorDiscovery._clean_domain('https://co.uk'))

    def test_gap_counts_registered_sites_not_hosts(self):
        records = [{'url': url, 'success': True, 'keywords_analysis': {'cartography': {'tf_idf_score': .5}}}
                   for url in ['https://blog.rival.co.uk/a', 'https://shop.rival.co.uk/b']]
        self.assertEqual(ContentGapStrategyEngine().analyze_gaps({}, records)['content_gaps_count'], 0)
        records[1]['url'] = 'https://other.co.uk/b'
        self.assertEqual(ContentGapStrategyEngine().analyze_gaps({}, records)['content_gaps_count'], 1)

    @staticmethod
    def response(body, code=200):
        response = requests.Response()
        response.status_code = code
        response.raw = io.BytesIO(body)
        return response

    def test_stream_limit_closes_response(self):
        response = self.response(b'x' * 20)
        session = Mock()
        session.get.return_value = response
        with self.assertRaisesRegex(ValueError, 'exceeds'):
            RequestPolicy(interval=0, max_bytes=10).get(session, 'https://example.com')
        self.assertTrue(response.raw.closed)

    def test_rate_limit_is_per_origin_and_429_stops_origin(self):
        session = Mock()
        session.get.side_effect = [self.response(b'ok'), self.response(b'ok'), self.response(b'limit', 429)]
        policy = RequestPolicy(interval=.5)
        with patch('modules.crawler.transport.time.monotonic', return_value=10), patch('modules.crawler.transport.time.sleep') as sleep:
            policy.get(session, 'https://a.com')
            policy.get(session, 'https://a.com/b')
            sleep.assert_called_once_with(.5)
            policy.get(session, 'https://b.com')
            with self.assertRaisesRegex(ValueError, '429'):
                policy.get(session, 'https://b.com/c')
        self.assertEqual(session.get.call_count, 3)

    def test_serp_rejects_invalid_records_and_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'serp.json'
            for values in [dict(retrieved_at='yesterday'), dict(results=[None]),
                           dict(results=[{'keyword': 'x', 'organic_results': [{'url': 'https://bad.com', 'position': True}]}])]:
                payload = dict(source='fixture', retrieved_at='2026-11-17T00:00:00Z', results=[])
                payload.update(values)
                path.write_text(json.dumps(payload))
                with self.subTest(values=values), self.assertRaises(ValueError):
                    FileSERPProvider(str(path))

    def test_migration_v6_preserves_data_and_legacy_snapshots(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(db, 'DB_PATH', Path(directory) / 'test.db'):
            db.initialize_database()
            project = ProjectRepository.create_project('test', 'https://example.com', 'example.com')
            run = AnalysisRepository.create_analysis_run(project)
            old = {'meta': {'project_id': project}, 'competitor_analysis': [{'raw_text': 'private content'}],
                   'audit_summary': {'issues': []}}
            with db.database_connection() as conn:
                conn.execute('DROP TABLE analysis_results')
                conn.execute('DROP TABLE site_settings')
                conn.execute('DROP TABLE keyword_competitor_choices')
                conn.execute('DELETE FROM schema_versions WHERE version>=7')
            CrawlEventRepository.log_event(run, 'pipeline_completed', details_json=json.dumps(old))
            db.initialize_database()
            db.initialize_database()  # Idempotence.
            self.assertIsNotNone(ProjectRepository.get_project(project))
            self.assertEqual(AnalysisResultRepository.load(run), old)
            AnalysisResultRepository.save(run, old)
            self.assertNotIn('raw_text', AnalysisResultRepository.load(run)['competitor_analysis'][0])
            self.assertIn('raw_text', old['competitor_analysis'][0])
            with db.database_connection() as conn:
                self.assertEqual(conn.execute('SELECT MAX(version) FROM schema_versions').fetchone()[0], 9)
                self.assertFalse(conn.execute('PRAGMA foreign_key_check').fetchall())
            ProjectRepository.delete_project(project)
            self.assertIsNone(AnalysisResultRepository.load(run))

    def test_page_rules_observe_canonical_robots_images_and_mixed_content(self):
        html = '<link rel="canonical" href="/other"><meta name="robots" content="noindex"><img src="http://assets.com/x"><h3>Heading</h3>'
        parsed = PageParser.parse(html, 'https://example.com', 200)
        result = TechnicalSEOAuditEngine().audit_pages_batch([parsed])
        rules = {item['rule_id'] for item in result['issues']}
        self.assertTrue({'CANONICAL_MISMATCH', 'PAGE_NOINDEX', 'IMAGE_ALT_MISSING', 'MIXED_CONTENT', 'HEADING_LEVEL_SKIPPED'} <= rules)
        for item in result['issues']:
            self.assertTrue({'rule_id', 'title', 'severity', 'evidence', 'recommendation', 'url'} <= item.keys())

    def test_site_audit_http_errors_and_partial_crawl(self):
        result = TechnicalSEOAuditEngine().audit_pages_batch([], observations=[{
            'url': 'https://example.com/missing', 'final_url': 'https://example.com/missing', 'status_code': 404}],
            links=[{'source_url': 'https://example.com/', 'target_url': 'https://example.com/missing', 'is_internal': True}],
            sitemap_urls=['https://example.com/unseen'], complete=False)
        rules = {item['rule_id'] for item in result['issues']}
        self.assertTrue({'HTTP_ERROR_STATUS', 'INTERNAL_LINK_BROKEN', 'SITE_SITEMAP_URLS_NOT_CRAWLED'} <= rules)
        self.assertFalse(any('ORPHAN' in rule for rule in rules))
        self.assertEqual(sum(result['severity_distribution'].values()), result['total_issues_found'])

    def test_redirect_and_duplicate_content(self):
        pages = [dict(url='https://example.com/'+suffix, word_count=300, content_hash='same',
                      redirect_chain=[{'from': '/x', 'to': '/y'}, {'from': '/y', 'to': '/z'}]) for suffix in ['a', 'b']]
        result = TechnicalSEOAuditEngine().audit_pages_batch(pages)
        self.assertTrue({'REDIRECT_CHAIN', 'DUPLICATE_CONTENT'} <= {i['rule_id'] for i in result['issues']})

    def test_competitor_http_content_type_block_and_parse_failures(self):
        from modules.competitors.analyzer import CompetitorAnalyzer
        from modules.crawler.engine import CrawlerEngine
        from tests.test_crawler_engine import FakeResponse, FakeRobotsManager
        with patch('modules.competitors.analyzer.RobotsManager', FakeRobotsManager), CrawlerEngine(1) as crawler:
            crawler.request_policy.interval = 0
            for status, content_type, body in [(404, 'text/html', 'missing'), (200, 'application/pdf', 'pdf'), (200, 'text/html', '')]:
                response = FakeResponse('https://rival.com/', body)
                response.status_code = status
                response.headers['Content-Type'] = content_type
                with patch.object(crawler, 'request_page', return_value={'status': 'success', 'response': response}):
                    result = CompetitorAnalyzer(crawler, PageParser()).analyze_competitor_page('https://rival.com/')
                self.assertFalse(result['success'])
                self.assertTrue(response.closed)
            with patch.object(crawler, 'request_page', return_value={'status': 'blocked'}):
                result = CompetitorAnalyzer(crawler, PageParser()).analyze_competitor_page('https://rival.com/')
                self.assertIn('blocked', result['error'])
            parser = Mock()
            parser.parse.side_effect = ValueError('parse failure')
            response = FakeResponse('https://rival.com/', '<p>text</p>')
            with patch.object(crawler, 'request_page', return_value={'status': 'success', 'response': response}):
                result = CompetitorAnalyzer(crawler, parser).analyze_competitor_page('https://rival.com/')
                self.assertIn('parse failure', result['error'])
                self.assertTrue(response.closed)

    def test_comparison_does_not_call_unobserved_issues_resolved(self):
        before = {'meta': {'project_id': 1}, 'audit_summary': {'issues': [
            {'rule_id': 'A', 'url': 'https://example.com/a'}, {'rule_id': 'B', 'url': 'https://example.com/b'}]}}
        after = {'meta': {'project_id': 1}, 'audit_summary': {'issues': []},
                 'crawled_pages': [{'url': 'https://example.com/a'}]}
        with patch.object(AnalysisResultRepository, 'load', side_effect=[before, after]):
            result = AnalysisResultRepository.compare(1, 2)
        self.assertEqual(result['resolved'], [{'rule_id': 'A', 'url': 'https://example.com/a'}])
        self.assertEqual(result['unobserved'], [{'rule_id': 'B', 'url': 'https://example.com/b'}])

    def test_strategy_actions_keep_evidence_and_explainable_scores(self):
        from modules.strategy.prioritization import build_roadmap
        actions = build_roadmap({'issues': [{'url': 'https://example.com/a', 'rule_id': 'HTTP_ERROR_STATUS',
            'severity': 'Critical', 'recommendation': 'Repair HTTP error', 'evidence': {'status': 500}}]}, {'content_gaps': []})
        self.assertEqual(actions[0]['priority_score'], actions[0]['impact']/actions[0]['effort'])
        self.assertEqual(actions[0]['evidence'], {'status': 500})

    def test_robots_uses_origin_and_closes_denied_response(self):
        from modules.crawler.robots import RobotsManager
        response = self.response(b'denied', 403)
        with patch.object(response, 'close', wraps=response.close) as close, patch('modules.crawler.robots.requests.get', return_value=response) as get:
            manager = RobotsManager('https://example.com/nested/page')
        self.assertEqual(get.call_args.args[0], 'https://example.com/robots.txt')
        self.assertFalse(manager.can_fetch('https://example.com/'))
        close.assert_called_once()

    def test_canonical_link_is_not_embedded_mixed_content(self):
        parsed = PageParser.parse('<link rel="canonical" href="http://example.com">', 'https://example.com')
        self.assertEqual(parsed['mixed_content_urls'], [])

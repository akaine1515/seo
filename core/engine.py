"""Application pipeline. Network and persistence use the existing modules."""
import json
import threading
from database.sites import SiteRepository, validate_settings
from datetime import datetime, timezone
from urllib.parse import urlparse

from database.connection import initialize_database, database_connection
from database.results import AnalysisResultRepository
from modules.strategy.keyword_plan import build_keyword_plans, keyword_inventory, mindmap, VERSION, LIMITATION
from modules.crawler.transport import RequestPolicy
from database.repository import (ProjectRepository, AnalysisRepository, PageRepository,
                                 PageContentRepository, CrawlEventRepository, PageLinkRepository, CrawlQueueRepository)
from modules.crawler.engine import CrawlerEngine
from modules.keywords.extractor import KeywordExtractor
from modules.keywords.analyzer import KeywordAnalyzer
from modules.keywords.clustering import KeywordClustering
from modules.keywords.opportunity import KeywordOpportunityEngine
from modules.competitors.discovery import CompetitorDiscovery
from modules.audit.engine import TechnicalSEOAuditEngine
from modules.audit.advanced_on_page import AdvancedOnPageAnalyzer
from modules.strategy.prioritization import build_roadmap


class SEOOrchestrator:
    """SERP provider: source, search(keywords) -> discovery input list.

    Without a provider, competitor/gap stages are explicitly unavailable.
    Selected domains are supplied through options['selected_competitors']; no
    competitor pages are fetched until the caller supplies this selection.
    Crawl lifecycle remains owned by CrawlerEngine; pipeline events separately
    record completed/failed processing under the same run ID (schema 6).
    """

    def __init__(self, serp_provider=None):
        self.serp_provider = serp_provider

    @staticmethod
    def _positive(options, key, default):
        value = options.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{key} must be a positive integer")
        return value

    @staticmethod
    def load_result(run_id: int):
        """Retrieve a completed snapshot; crawl completion alone is insufficient."""
        return AnalysisResultRepository.load(run_id)

    @staticmethod
    def preview_serp(path, target_url, project_id):
        from modules.serp.google_search import FileSERPProvider
        provider = FileSERPProvider(path)
        if not project_id:
            raise ValueError('ابتدا یک سایت ثبت‌شده انتخاب کنید.')
        return {'meta': {'project_id': project_id},
                'competitors_per_keyword': CompetitorDiscovery(target_url).discover_competitors_per_keyword(provider.payload['results'], max_per_keyword=100),
                'serp': {'source': provider.source, 'retrieved_at': provider.retrieved_at}}

    def run_competitor_stage(self, source_run_id, options=None, progress_callback=None, cancel_event=None):
        """Reanalyze selected competitors against an immutable saved own-site crawl."""
        from core.stages import run_competitor_stage
        return run_competitor_stage(source_run_id, options, progress_callback, cancel_event,
                                    serp_provider=self.serp_provider)

    def run_full_pipeline(self, target_url: str, options: dict, progress_callback=None, cancel_event=None) -> dict:
        progress = progress_callback or (lambda message, value: None)
        cancel_event = cancel_event if cancel_event is not None else threading.Event()
        if not isinstance(options, dict):
            raise ValueError('options must be a dictionary')
        initialize_database()
        selected_site = None
        if options.get('project_id') is not None:
            self._positive(options, 'project_id', 1)
            selected_site = next((s for s in SiteRepository.list_sites() if s['id'] == options['project_id']), None)
            if selected_site is None or not selected_site['is_active']:
                raise ValueError('Site does not exist or is inactive')
            options = {**selected_site['settings'], **options}
            target_url = selected_site['website_url']
        settings = validate_settings({k: options[k] for k in ('max_pages', 'max_depth', 'timeout',
            'request_interval', 'max_response_bytes', 'excluded_paths') if k in options})
        options = {**settings, **options}
        max_pages = self._positive(options, 'max_pages', 50)
        max_competitors = self._positive(options, 'max_competitors', 5)
        competitor_limit = self._positive(options, 'competitor_max_pages', 5)
        timeout = self._positive(options, 'timeout', 15)
        max_bytes = self._positive(options, 'max_response_bytes', 5 * 1024 * 1024)
        interval = options.get('request_interval', 0.5)
        if isinstance(interval, bool) or not isinstance(interval, (int, float)) or not 0 <= interval <= 60:
            raise ValueError('request_interval must be between 0 and 60 seconds')
        if not isinstance(options.get('retain_competitor_text', False), bool):
            raise ValueError('retain_competitor_text must be boolean')
        policy = RequestPolicy(interval=interval, max_bytes=max_bytes)
        if not isinstance(target_url, str) or not target_url.strip():
            raise ValueError('Target URL is required')
        target_url = target_url.strip()
        if '://' not in target_url:
            target_url = 'https://' + target_url
        if not CompetitorDiscovery._is_valid_url(target_url):
            raise ValueError('Invalid target HTTP URL')
        target_url = CrawlerEngine.normalize_url(target_url)
        if selected_site is None:
            from core.domains import site_domain
            selected_site = next((s for s in SiteRepository.list_sites()
                                  if site_domain(s['website_url']) == site_domain(target_url)), None)
            if selected_site and not selected_site['is_active']:
                raise ValueError('Site is inactive')
        project_id = selected_site['id'] if selected_site else SiteRepository.register(urlparse(target_url).hostname, target_url)
        run_id = AnalysisRepository.create_analysis_run(project_id, max_pages=max_pages)
        try:
            progress('Crawling and saving pages with the configured limit...', 10)
            with CrawlerEngine(run_id, max_pages=max_pages, timeout=timeout) as crawler:
                crawler.request_policy = policy
                crawler.max_depth = settings['max_depth']
                crawler.excluded_paths = settings['excluded_paths']
                crawler.cancel_event = cancel_event
                crawler.progress_callback = progress
                crawler.run(target_url)
                observations = list(crawler.http_results)
                sitemap_urls = list(crawler.sitemap_urls)
                crawl_stats = dict(crawler.stats)
                scope_excluded = len(crawler.scope_skipped)
                queue_stats = CrawlQueueRepository.get_queue_stats(run_id)
                crawl_complete = (not cancel_event.is_set() and not queue_stats.get('queued', 0)
                                  and not any(crawl_stats.get(k, 0) for k in ('failed', 'blocked', 'skipped'))
                                  and len(observations) > 0)
            pages = PageRepository.get_run_pages(run_id)
            contents = PageContentRepository.get_run_contents(run_id)

            evidence = {}
            for event in CrawlEventRepository.get_run_events(run_id, limit=100000):
                if event['event_type'] == 'page_observation':
                    evidence[event['url']] = json.loads(event['details_json'])
            detailed_pages = [{**evidence.get(item['url'], {}), 'url': item['url'], 'text_content': item['text_content']}
                              for item in contents]
            site_inventory = keyword_inventory(detailed_pages)
            progress('Computing actual keyword frequencies and TF-IDF...', 45)
            extractor, analyzer = KeywordExtractor(), KeywordAnalyzer()
            extracted = extractor.extract_run_keywords(contents)
            own_metrics = analyzer.compute_tf_idf(extracted)
            opportunities = analyzer.prioritize_opportunities(own_metrics)
            opportunity_engine = KeywordOpportunityEngine()
            scored = opportunity_engine.score_opportunities(
                opportunity_engine.filter_noise(opportunities, len(extracted)) if extracted else [])
            aggregate = {item['keyword']: {'tf_idf_score': item['total_tf_idf'],
                         'raw_frequency': item['total_frequency'], 'intent': item['intent']}
                         for item in opportunities}
            clusters = KeywordClustering.cluster_keywords(aggregate)
            cluster_names = {kw: cluster['cluster_name'] for cluster in clusters
                             for kw in [cluster['primary_keyword'], *cluster['secondary_keywords']]}
            warnings = []
            if not crawl_complete:
                warnings.append('Crawl coverage is incomplete; inspect failures, remaining URLs and configured limits.')
            if cancel_event.is_set():
                warnings.append('Analysis was stopped. Saved pages and partial results are preserved.')
            if not contents:
                warnings.append("No readable pages: keyword coverage and gap analysis are unavailable.")
            from core.competitor_stage import analyze_competitors
            competitor_data = analyze_competitors(target_url, project_id, run_id,
                contents, site_inventory, options, policy, progress, cancel_event,
                serp_provider=self.serp_provider)
            warnings.extend(competitor_data.pop('warnings'))
            competitor_status = competitor_data['competitor_status']
            gaps = competitor_data['content_gap_analysis']
            content_map = {item["page_id"]: item for item in contents}
            audit_pages = []
            for page in pages:
                headings = content_map.get(page["id"], {})
                audit_pages.append({**page, **evidence.get(page['url'], {}), 'structure': {**page,
                    'h1': headings.get('h1_list', []), 'raw_text': headings.get('text_content', '')}})
            progress('Auditing persisted pages and saving analysis snapshot...', 90)
            result = {
                'meta': {'target_domain': target_url, 'analysis_run_id': run_id,
                         'project_id': project_id, 'generated_at': datetime.now(timezone.utc).isoformat(),
                         'warnings': warnings, 'pipeline_status': ('cancelled' if cancel_event.is_set() else
                             'failed' if not contents else 'partial' if not crawl_complete or competitor_status != 'completed' else 'completed'),
                         'crawl_status': ('cancelled' if cancel_event.is_set() else 'completed' if crawl_complete else 'partial'),
                         'settings': {**settings, 'competitor_max_pages': competitor_limit}, 'algorithm_version': 'seo-intelligence-1.1', 'keyword_plan_version': VERSION,
                         'coverage': {**crawl_stats, 'queued_remaining': queue_stats.get('queued', 0),
                                      'scope_excluded': scope_excluded, 'readable_pages': len(contents),
                                      'discovered': queue_stats.get('total', 0)},
                         'started_at': AnalysisRepository.get_analysis_run(run_id)['started_at']},
                'crawled_pages': pages,
                'keyword_analysis': {'keywords': [dict(term=item['keyword'],
                    frequency=item['total_frequency'], tfidf=item['total_tf_idf'],
                    cluster=cluster_names.get(item['keyword'], '')) for item in opportunities],
                    'clusters': clusters, 'opportunities': scored, 'tf_idf': own_metrics},
                'audit_summary': TechnicalSEOAuditEngine().audit_pages_batch(audit_pages,
                    links=PageLinkRepository.get_run_links(run_id), observations=observations,
                    sitemap_urls=sitemap_urls, complete=crawl_complete),
                'crawl_observations': observations,
                **competitor_data,
                'page_details': [dict(data, url=url) for url, data in evidence.items()],
            }
            on_page = AdvancedOnPageAnalyzer()
            result['on_page_analysis'] = [on_page.analyze_title_content_relevance(page) for page in audit_pages]
            result['cannibalization_issues'] = on_page.detect_keyword_cannibalization([
                {'url': item['url'], 'keywords': [{'term': term, 'score': metrics['tf_idf_score']}
                    for term, metrics in own_metrics.get(item['page_id'], {}).items()
                    if metrics['tf_idf_score'] >= 0.01]} for item in contents])
            result['seo_roadmap'] = build_roadmap(result['audit_summary'], gaps)
            result['strategy_method'] = 'Heuristic impact 1–4 / assumed effort 2 (technical) or 3 (content); requires human review, not traffic estimates.'
            inventory, plans = build_keyword_plans(detailed_pages, competitor_data['competitors_per_keyword'], competitor_data['competitor_selections'], competitor_data['competitor_analysis'], result['audit_summary'], inventory=site_inventory)
            result['keyword_inventory'] = inventory
            result['keyword_strategies'] = plans
            result['keyword_mindmaps'] = [mindmap(plan) for plan in plans]
            result['analysis_limitations'] = [LIMITATION,
                'سرعت ثبت‌شده فقط یک دریافت HTTP از این دستگاه است؛ Core Web Vitals و سرعت رندر مرورگر اندازه‌گیری نشده‌اند.',
                'ابعاد تصاویر از HTML هستند؛ حجم فایل و ابعاد واقعی تصویر، بک‌لینک‌ها و داده خصوصی رقبا بررسی نشده‌اند.',
                'ممیزی به صفحات HTML قابل دریافت در محدوده خزش محدود است؛ همه عوامل رتبه‌بندی قابل مشاهده نیستند.']
            result['meta']['finished_at'] = datetime.now(timezone.utc).isoformat()
            AnalysisResultRepository.save(run_id, result, retain_text=options.get('retain_competitor_text', False))
            CrawlEventRepository.log_event(run_id, 'pipeline_' + result['meta']['pipeline_status'],
                message='Analysis snapshot; crawl lifecycle is tracked separately.',
                details_json=json.dumps({"snapshot_format": 1, "stored_in": "analysis_results"}))
            progress('Analysis saved. Review availability warnings before using results.', 100)
            return result
        except Exception as error:
            CrawlEventRepository.log_event(run_id, 'pipeline_failed', message=str(error), severity='high')
            raise

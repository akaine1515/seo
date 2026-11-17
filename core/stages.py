"""Independent stage execution over immutable, run-scoped own-site evidence."""
import copy
import threading
from datetime import datetime, timezone
from database.connection import initialize_database
from database.repository import AnalysisRepository, PageContentRepository
from database.results import AnalysisResultRepository
from database.competitors import validate_choices
from database.sites import SiteRepository, validate_settings
from database.stages import StageResultRepository
from core.competitor_stage import analyze_competitors
from modules.crawler.transport import RequestPolicy
from modules.strategy.keyword_plan import keyword_inventory, build_keyword_plans, mindmap
from modules.strategy.prioritization import build_roadmap

VERSION = 'competitor-stage-1.0'
REUSED_NOTICE = 'داده سایت از خزش ذخیره‌شده استفاده شده است؛ این مرحله سایت شما را دوباره خزش نمی‌کند. تاریخ SERP مستقل از زمان دریافت صفحات رقباست.'


def run_competitor_stage(source_run_id, options=None, progress_callback=None,
                         cancel_event=None, serp_provider=None):
    initialize_database()
    run = AnalysisRepository.get_analysis_run(source_run_id)
    source = AnalysisResultRepository.load(source_run_id)
    if run is None or source is None:
        raise ValueError('ابتدا یک تحلیل ذخیره‌شده با محتوای سایت باز کنید.')
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise ValueError('options must be a dictionary')
    project_id = run['project_id']
    if options.get('project_id', project_id) != project_id:
        raise ValueError('اجرای منبع به سایت فعال تعلق ندارد.')
    site = next((s for s in SiteRepository.list_sites() if s['id'] == project_id), None)
    if site is None or not site['is_active']:
        raise ValueError('سایت منبع موجود نیست یا غیرفعال است.')
    contents = PageContentRepository.get_run_contents(source_run_id)
    if not contents:
        raise ValueError('خزش منبع متن قابل تحلیل ندارد؛ ابتدا خزش سایت را انجام دهید.')
    options = {**source.get('meta', {}).get('settings', {}), **options}
    settings = validate_settings({k: options[k] for k in ('timeout', 'request_interval', 'max_response_bytes') if k in options})
    options = {**options, **{k: settings[k] for k in ('timeout', 'request_interval', 'max_response_bytes')}}
    for key, default in [('competitor_max_pages', 5), ('max_competitors', 5)]:
        value = options.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f'{key} must be a positive integer')
        options[key] = value
    if not isinstance(options.get('retain_competitor_text', False), bool):
        raise ValueError('retain_competitor_text must be boolean')
    progress = progress_callback or (lambda message, value: None)
    cancel_event = cancel_event if cancel_event is not None else threading.Event()
    evidence = {p['url']: p for p in source.get('page_details', [])}
    pages = [{**evidence.get(p['url'], {}), 'url': p['url'], 'text_content': p['text_content']} for p in contents]
    inventory = keyword_inventory(pages)
    saved_serp = source.get('serp', {})
    if not saved_serp.get('source') or not saved_serp.get('retrieved_at'):
        saved_serp = None
    stage_id = StageResultRepository.start(source_run_id, VERSION)
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        if 'competitors_by_keyword' in options:
            validate_choices(options['competitors_by_keyword'])
        progress('Reusing saved own-site crawl; only selected competitor pages will be fetched.', 10)
        data = analyze_competitors(site['website_url'], project_id, source_run_id,
            contents, inventory, options,
            RequestPolicy(interval=settings['request_interval'], max_bytes=settings['max_response_bytes']),
            progress, cancel_event, serp_provider=serp_provider, saved_serp=saved_serp)
        warnings = data.pop('warnings')
        stage_status = ('cancelled' if cancel_event.is_set() else
                        'completed' if data['competitor_status'] == 'completed' else 'partial')
        result = copy.deepcopy(source)
        result.update(data)
        result['keyword_inventory'], result['keyword_strategies'] = build_keyword_plans(
            pages, data['competitors_per_keyword'], data['competitor_selections'],
            data['competitor_analysis'], source['audit_summary'], inventory=inventory)
        result['keyword_mindmaps'] = [mindmap(p) for p in result['keyword_strategies']]
        result['seo_roadmap'] = build_roadmap(source['audit_summary'], data['content_gap_analysis'])
        finished_at = datetime.now(timezone.utc).isoformat()
        result['meta'].update(stage_result_id=stage_id, source_analysis_run_id=source_run_id,
            execution_scope='competitors', stage_status=stage_status, stage_algorithm_version=VERSION,
            stage_started_at=started_at, stage_finished_at=finished_at, generated_at=finished_at,
            source_pipeline_status=source['meta'].get('pipeline_status'),
            source_warnings=source['meta'].get('warnings', []),
            stage_settings={k: options[k] for k in ('timeout', 'request_interval', 'max_response_bytes', 'competitor_max_pages')},
            pipeline_status=('cancelled' if stage_status == 'cancelled' else 'completed'
                if stage_status == 'completed' and source['meta'].get('crawl_status') == 'completed' else 'partial'),
            warnings=[REUSED_NOTICE, *(['Source crawl coverage is incomplete.']
                if source['meta'].get('crawl_status') != 'completed' else []), *warnings])
        result['analysis_limitations'] = [*source.get('analysis_limitations', []), REUSED_NOTICE]
        StageResultRepository.finish(stage_id, stage_status, result,
                                     retain_text=options.get('retain_competitor_text', False))
        progress('Independent competitor result saved; source crawl history preserved.', 100)
        return result
    except Exception as error:
        StageResultRepository.finish(stage_id, 'failed', error_type=type(error).__name__)
        raise

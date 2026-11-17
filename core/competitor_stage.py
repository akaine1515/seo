"""Reusable competitor stage shared by full analysis and saved-run reanalysis."""
from datetime import datetime, timezone
from database.competitors import CompetitorChoiceRepository, validate_choices
from modules.crawler.engine import CrawlerEngine
from modules.crawler.parser import PageParser
from modules.competitors.discovery import CompetitorDiscovery
from modules.competitors.analyzer import CompetitorAnalyzer
from modules.keywords.extractor import KeywordExtractor
from modules.keywords.analyzer import KeywordAnalyzer
from modules.strategy.content_gap import ContentGapStrategyEngine


def analyze_competitors(target_url, project_id, run_id, contents, site_inventory,
                        options, policy, progress, cancel_event, serp_provider=None,
                        saved_serp=None):
    """Return observed competitor data without modifying any own-site crawl rows."""
    max_competitors = options.get('max_competitors', 5)
    competitor_limit = options.get('competitor_max_pages', 5)
    timeout = options.get('timeout', 15)
    discovery = CompetitorDiscovery(target_url, max_competitors)
    extractor, analyzer = KeywordExtractor(), KeywordAnalyzer()
    extracted = extractor.extract_run_keywords(contents)
    competitors, per_keyword, analyses, serp = [], {}, [], []
    selections, warnings = {}, []
    source = None
    retrieved_at = None
    if (serp_provider is None and not saved_serp) or cancel_event.is_set():
        competitor_status = 'unavailable'
        warnings.append('SERP provider is not configured. Competitors and content gaps are unavailable.')
    else:
        progress('Discovering competitors from sourced SERP data...', 65)
        if serp_provider is None:
            source = saved_serp.get('source')
            retrieved_at = saved_serp.get('imported_at')
            serp = saved_serp.get('results', [])
        else:
            source = serp_provider.source
            retrieved_at = datetime.now(timezone.utc).isoformat()
            serp = serp_provider.search(list(dict.fromkeys(
                [item['term'] for item in site_inventory]
                + list(CompetitorChoiceRepository.load(project_id))
                + list(validate_choices(options.get('competitors_by_keyword', {}))))))
        competitors = discovery.aggregate_project_competitors(serp)
        per_keyword = discovery.discover_competitors_per_keyword(serp, max_per_keyword=100)
        requested = options.get('competitors_by_keyword')
        if requested is None:
            persisted = CompetitorChoiceRepository.load(project_id)
            # Stale observations cannot authorize fetching a domain in a new query.
            selections = {term: [d for d in domains if d in {r['domain'] for r in per_keyword.get(term, [])}]
                          for term, domains in persisted.items() if term in per_keyword}
        else:
            selections = validate_choices(requested, per_keyword)
        selected = options.get('selected_competitors', [])
        if not isinstance(selected, list) or len(selected) > min(max_competitors, 5):
            raise ValueError('selected_competitors must be a list within max_competitors (up to 5)')
        available = {r['domain'] for rows in per_keyword.values() for r in rows}
        if any(domain not in available for domain in selected):
            raise ValueError('Selected competitor was not discovered in SERP')
        if selected and requested is None and not selections:
            selections = {term: [d for d in selected if d in {r['domain'] for r in rows}]
                          for term, rows in per_keyword.items()}
        selections = validate_choices(selections, per_keyword)
        if requested is not None:
            CompetitorChoiceRepository.save(project_id, selections, per_keyword)
        required_urls = list(dict.fromkeys(r['url'] for term, rows in per_keyword.items()
            for r in rows if r['domain'] in selections.get(term, [])))
        competitor_status = 'awaiting_selection' if not required_urls else 'completed'
        domain_by_url = {r['url']: r['domain'] for term, rows in per_keyword.items()
                         for r in rows if r['domain'] in selections.get(term, [])}
        fetched_per_domain = {}
        for url in required_urls:
            domain = domain_by_url[url]
            if fetched_per_domain.get(domain, 0) >= competitor_limit:
                competitor_status = 'partial'
                warnings.append('Competitor page budget reached for ' + domain + '; some query comparisons remain unavailable.')
                continue
            fetched_per_domain[domain] = fetched_per_domain.get(domain, 0) + 1
            if cancel_event.is_set():
                competitor_status = 'partial'
                break
            with CrawlerEngine(run_id, max_pages=1, timeout=timeout) as crawler:
                crawler.request_policy = policy
                crawler.cancel_event = cancel_event
                analyses.extend(CompetitorAnalyzer(crawler, PageParser()).analyze_batch([url]))
    # Both sites are evaluated using the same document corpus and formula.
    combined = dict(extracted)
    for index, analysis in enumerate(analyses):
        if analysis['success']:
            combined[f'competitor-{index}'] = extractor.extract_page_keywords(analysis['raw_text'])
    shared_metrics = analyzer.compute_tf_idf(combined)
    for index, analysis in enumerate(analyses):
        if analysis['success']:
            analysis['keywords_analysis'] = shared_metrics[f'competitor-{index}']
    gaps = ContentGapStrategyEngine().analyze_gaps(
        {key: shared_metrics[key] for key in extracted}, analyses)
    gaps['status'] = ('completed' if contents and any(a['success'] for a in analyses)
                      else 'unavailable')
    if any(not a['success'] for a in analyses):
        competitor_status = 'partial'
        warnings.append('Some competitor pages failed; gap evidence is incomplete.')
    if not contents:
        gaps['content_gaps'] = []
        gaps['content_gaps_count'] = 0
    if contents and competitor_status == 'partial':
        gaps['status'] = 'partial'
    return {
        'project_competitors': competitors, 'competitors_per_keyword': per_keyword,
        'competitor_analysis': analyses, 'competitor_status': competitor_status,
        'competitor_selections': selections, 'content_gap_analysis': gaps,
        'serp': {'source': source,
                 'retrieved_at': (saved_serp or {}).get('retrieved_at') if serp_provider is None
                                  else getattr(serp_provider, 'retrieved_at', retrieved_at),
                 'imported_at': retrieved_at, 'results': serp},
        'warnings': warnings,
    }

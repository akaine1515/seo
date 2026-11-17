"""Rules use observed HTTP/HTML only; no claim of browser rendering or indexing."""
import json
from urllib.parse import urldefrag


def issue(rule, url, title, evidence, recommendation, severity='Medium', category='Technical'):
    return dict(rule_id=rule, url=url, title=title, description=title,
                evidence=evidence, recommendation=recommendation, severity=severity, category=category)


def page_checks(page):
    url = page.get('final_url') or page.get('url', '')
    found = []
    def add(rule, title, evidence, recommendation, severity='Medium'):
        found.append(issue(rule, url, title, evidence, recommendation, severity))
    chain = page.get('redirect_chain', []) or json.loads(page.get('redirect_chain_json') or '[]')
    if chain:
        add('REDIRECT_CHAIN' if len(chain) > 1 else 'PAGE_REDIRECT', 'Observed HTTP redirect',
            {'chain': chain}, 'Link directly to the intended final URL.', 'Low')
    canonical = page.get('canonical_url')
    if canonical and urldefrag(canonical)[0] != urldefrag(url)[0]:
        add('CANONICAL_MISMATCH', 'Canonical points to a different URL',
            {'canonical': canonical, 'final_url': url}, 'Verify the intended canonical; do not change it automatically.')
    if page.get('canonical_status') in ('invalid', 'multiple'):
        add('CANONICAL_INVALID', 'Invalid or multiple canonical tags',
            {'status': page['canonical_status']}, 'Declare one valid canonical URL.')
    if page.get('is_indexable') == 0:
        add('PAGE_NOINDEX', 'Page declares noindex',
            {'robots': page.get('robots_directive'), 'header': page.get('x_robots_tag')},
            'Verify whether exclusion from indexing is intentional.', 'Low')
    if page.get('images_without_alt', 0):
        add('IMAGE_ALT_MISSING', 'Images with missing or empty alt text',
            {'count': page['images_without_alt']}, 'Review informative images; decorative images may use empty alt.', 'Low')
    if page.get('h3_count', 0) and not page.get('h2_count', 0):
        add('HEADING_LEVEL_SKIPPED', 'H3 headings without H2', {}, 'Review heading hierarchy.', 'Low')
    if page.get('mixed_content_urls'):
        add('MIXED_CONTENT', 'HTTP resources embedded in an HTTPS page',
            {'urls': page['mixed_content_urls']}, 'Use HTTPS for embedded resources.')
    if url.startswith('http://'):
        add('PAGE_HTTP', 'Page served over HTTP', {}, 'Check HTTPS availability before updating links.', 'Low')
    headings = page.get('headings', [])
    skipped = [[a['level'], b['level']] for a, b in zip(headings, headings[1:]) if b['level'] > a['level'] + 1]
    if skipped:
        add('HEADING_ORDER', 'Observed skipped heading levels H1–H6', {'jumps': skipped}, 'Review section hierarchy.', 'Low')
    if 'viewport' in page and not page['viewport']:
        add('VIEWPORT_MISSING', 'Viewport meta absent', {}, 'Review mobile viewport configuration.', 'Low')
    if 'language' in page and not page['language']:
        add('LANGUAGE_MISSING', 'HTML language absent', {}, 'Declare the page language.', 'Low')
    if any(not item['valid_json'] for item in page.get('structured_data', [])):
        add('JSON_LD_INVALID', 'Structured data contains invalid JSON', {}, 'Repair JSON syntax; semantic schema eligibility is not verified.')
    missing_size = [im.get('url') for im in page.get('images', []) if not im.get('width') or not im.get('height')]
    if missing_size:
        add('IMAGE_SIZE_UNDECLARED', 'Images without declared dimensions', {'urls': missing_size}, 'Review explicit dimensions/aspect ratio to reduce layout shift.', 'Low')
    perf = page.get('performance', {})
    if perf.get('html_fetch_ms', 0) > 2000:
        add('HTML_FETCH_SLOW', 'Observed HTML fetch exceeded 2000 ms', perf,
            'Repeat measurements and inspect server/network latency. This is not a Core Web Vitals result.')
    return found


def site_checks(pages, links, observations, sitemap_urls, complete=False):
    findings, seen_errors = [], set()
    inbound = {}
    for link in links:
        if link.get('is_internal'):
            inbound.setdefault(link['target_url'], set()).add(link.get('source_url'))
    statuses = {row.get('final_url', row.get('url')): row.get('status_code') for row in observations}
    for row in observations:
        status = row.get('status_code')
        key = (row.get('final_url'), status)
        if isinstance(status, int) and status >= 400 and key not in seen_errors:
            seen_errors.add(key)
            findings.append(issue('HTTP_ERROR_STATUS', row.get('final_url', row['url']),
                f'HTTP error {status}', {'status_code': status}, 'Repair the URL or its incoming links.',
                'Critical' if status >= 500 else 'High'))
    for link in links:
        status = statuses.get(link['target_url'])
        if link.get('is_internal') and status is not None and status >= 400:
            findings.append(issue('INTERNAL_LINK_BROKEN', link.get('source_url', ''),
                'Internal link returns an HTTP error', {'target_url': link['target_url'], 'status_code': status},
                'Update or remove the broken internal link.'))
    hashes = {}
    for page in pages:
        url = page['url']
        content_hash = page.get('content_hash')
        if content_hash and page.get('word_count', 0):
            hashes.setdefault(content_hash, []).append(url)
        if page.get('depth', 0) > 3:
            findings.append(issue('CLICK_DEPTH_HIGH', url, 'Page deeper than three observed clicks',
                {'depth': page['depth']}, 'Review relevant navigation paths.', 'Low', 'Architecture'))
        if page.get('depth', 0) > 0 and len(inbound.get(url, set())) <= 1:
            findings.append(issue('FEW_OBSERVED_INLINKS', url, 'Few incoming links in observed crawl',
                {'inbound_count': len(inbound.get(url, set())), 'crawl_complete': complete},
                'Review internal links; partial crawls do not establish orphan status.', 'Low', 'Architecture'))
    for urls in hashes.values():
        if len(urls) > 1:
            findings.append(issue('DUPLICATE_CONTENT', sorted(urls)[0], 'Identical extracted content',
                {'urls': sorted(urls)}, 'Review duplication and intended canonicalization.'))
    missing = sorted(set(sitemap_urls) - {p['url'] for p in pages})
    if missing:
        findings.append(issue('SITE_SITEMAP_URLS_NOT_CRAWLED', 'sitemap.xml',
            'Sitemap URLs not observed in saved pages', {'urls': missing, 'crawl_complete': complete},
            'Check crawl limits, robots and HTTP results; absence does not prove an orphan.', 'Low', 'Architecture'))
    return findings

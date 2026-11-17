"""Evidence based lexical keyword trees and per-query observable competitor plans.

No private competitor algorithm is inferred. Child means a longer observed
1–3 gram containing the parent after the documented tokenizer/stopword filter.
"""
from collections import Counter, defaultdict
from modules.keywords.extractor import KeywordExtractor
from modules.keywords.analyzer import KeywordAnalyzer

VERSION = 'keyword-plan-1.0'
LIMITATION = ('الگوی صفحات عمومی مشاهده‌شده؛ علت رتبه یا الگوریتم داخلی رقیب قابل استنتاج قطعی نیست. '
              'کلمات فرزند، عبارت‌های طولانی‌تر مشاهده‌شده پس از پاک‌سازی و حذف واژه‌های عمومی‌اند؛ رابطه معنایی قطعی نیست.')


def phrases(text):
    data = KeywordExtractor().extract_page_keywords(KeywordAnalyzer.normalize_keyword(text))
    return Counter({term: count for key in ('unigrams', 'bigrams', 'trigrams') for term, count in data[key].items()
                    if any(ch.isalpha() for ch in term)})


def fields(page):
    return {'title': page.get('title') or '', 'description': page.get('meta_description') or '',
            'headings': ' '.join(h['text'] for h in page.get('headings', [])),
            'body': page.get('text_content') or ''}


def keyword_inventory(pages):
    inventory = {}
    for page in pages:
        for location, text in fields(page).items():
            for term, count in phrases(text).items():
                row = inventory.setdefault(term, {'term': term, 'ngram': len(term.split()),
                    'frequency': 0, 'source_pages': [], 'locations': {}, 'children': [], 'parents': []})
                row['frequency'] += count
                row['locations'][location] = row['locations'].get(location, 0) + count
                if page['url'] not in row['source_pages']:
                    row['source_pages'].append(page['url'])
    for term, row in inventory.items():
        tokens = term.split()
        if len(tokens) < 2 or len(set(tokens)) != len(tokens):
            continue
        for start in range(2):
            parent = ' '.join(tokens[start:start + len(tokens)-1])
            if parent in inventory and parent not in row['parents']:
                row['parents'].append(parent)
                inventory[parent]['children'].append(term)
    return sorted(inventory.values(), key=lambda r: (-r['frequency'], r['term']))


def build_keyword_plans(pages, candidates, selections, analyses, audit, target_terms=None, inventory=None):
    inventory = keyword_inventory(pages) if inventory is None else inventory
    own = {r['term']: r for r in inventory}
    by_url = {a['url']: a for a in analyses}
    prepared = {}
    for url, analysis in by_url.items():
        if not analysis.get('success'):
            continue
        seo = analysis.get('seo', {})
        prepared[url] = {k: phrases(v) for k, v in fields({**seo, 'text_content': analysis.get('raw_text', '')}).items()}
    issues_by_url = defaultdict(list)
    for issue in audit.get('issues', []):
        issues_by_url[issue['url']].append(issue)
    plans = []
    # Every observed phrase gets a plan; query-only entries from SERP stay explicit.
    terms = list(dict.fromkeys([*(r['term'] for r in inventory), *candidates, *(target_terms or [])]))
    for term in terms:
        row = own.get(term, {})
        patterns, missing = [], defaultdict(set)
        selected_rows = [r for r in candidates.get(term, []) if r['domain'] in selections.get(term, [])]
        for candidate in selected_rows:
            url = candidate['url']
            analysis = by_url.get(url, {})
            observed = prepared.get(url)
            if observed is None:
                patterns.append({'domain': candidate['domain'], 'url': url, 'status': 'failed' if analysis else 'not_analyzed',
                                 'error': analysis.get('error'), 'keyword': term})
                continue
            counts = {loc: counts.get(term, 0) for loc, counts in observed.items()}
            # Related topics must contain the query token sequence, not unrelated sitewide terms.
            related = sorted(t for t in observed['body'] if term != t and f' {term} ' in f' {t} ')
            for topic in related:
                if topic not in own:
                    missing[topic].add(url)
            patterns.append({'keyword': term, 'domain': candidate['domain'], 'url': url, 'status': 'observed',
                'position': candidate['position'], 'retrieved_at': analysis.get('retrieved_at'),
                'keyword_locations': counts, 'headings': analysis.get('seo', {}).get('headings', []),
                'related_phrases': related, 'word_count': analysis.get('structure', {}).get('word_count'),
                'internal_links': analysis.get('linking', {}).get('internal_links', []),
                'images': analysis.get('seo', {}).get('images', []), 'performance': analysis.get('performance', {}),
                'interpretation': 'فراوانی و جایگاه مشاهده‌شده؛ علت رتبه‌گرفتن اثبات نمی‌شود.'})
        relevant_issues = [issue for url in row.get('source_pages', []) for issue in issues_by_url[url]]
        actions = [{'kind': 'technical', 'action': i['recommendation'], 'url': i['url'],
                    'reason': i['title'], 'evidence': i.get('evidence', {}), 'rule_id': i['rule_id']}
                   for i in relevant_issues]
        if row:
            actions.append({'kind': 'review_existing', 'action': 'پوشش عبارت و نیاز کاربر را در صفحه موجود بازبینی کنید.',
                'url': row['source_pages'][0], 'reason': 'عبارت در محتوای استخراج‌شده وجود دارد.',
                'evidence': {'locations': row['locations'], 'source_pages': row['source_pages']}})
        for topic, urls in sorted(missing.items()):
            actions.append({'kind': 'expand_topic', 'topic': topic,
                'action': 'مرتبط‌بودن را تأیید و سپس پوشش این زیرموضوع را به صفحه مرتبط اضافه کنید.',
                'reason': 'عبارت فرزند در صفحه منتخب رقیب دیده شد و در داده سایت ما مشاهده نشد.',
                'evidence': {'competitor_urls': sorted(urls), 'own_crawl_may_be_incomplete': True}})
        if len(row.get('source_pages', [])) > 1:
            actions.append({'kind': 'review_overlap', 'action': 'هدف صفحات هم‌پوشان را بررسی کنید؛ ادغام خودکار توصیه نمی‌شود.',
                'reason': 'وجود عبارت در چند صفحه به‌تنهایی اثبات هم‌نوع‌خواری نیست.',
                'evidence': {'urls': row['source_pages']}})
        plans.append({'keyword': term, 'own_pages': row.get('source_pages', []), 'children': row.get('children', []),
            'competitor_status': 'unavailable' if not candidates.get(term) else
                                 'awaiting_selection' if not selected_rows else
                                 'observed' if patterns and all(p['status'] == 'observed' for p in patterns) else 'partial',
            'competitor_patterns': patterns, 'actions': actions, 'method_version': VERSION,
            'limitation': LIMITATION})
    return inventory, plans


def mindmap(plan):
    return {'label': plan['keyword'], 'kind': 'keyword', 'children': [
        {'label': 'صفحات سایت ما', 'children': [{'label': u, 'url': u} for u in plan['own_pages']]},
        {'label': 'عبارت‌های فرزند مشاهده‌شده', 'children': [{'label': t} for t in plan['children']]},
        {'label': 'الگوهای قابل مشاهده رقبا', 'children': [
            {'label': p['domain'] + ' · ' + p['status'], 'url': p['url'], 'children': [
                {'label': 'رتبه ثبت‌شده: ' + str(p.get('position', 'نامشخص')) + ' · تاریخ: ' + str(p.get('retrieved_at', 'نامشخص'))},
                {'label': 'جایگاه عبارت: ' + str(p.get('keyword_locations', {}))},
                *[{'label': t} for t in p.get('related_phrases', [])]]} for p in plan['competitor_patterns']]},
        {'label': 'اقدام‌های پیشنهادی', 'children': [{'label': (a.get('topic', '') + ' · ' if a.get('topic') else '') + a['action'], 'children':
            [{'label': a['reason']}, {'label': str(a['evidence'])}]} for a in plan['actions']]},
    ]}

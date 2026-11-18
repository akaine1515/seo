"""Bounded, explainable keyword expansion. No search-demand estimates or network calls."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from modules.keywords.analyzer import KeywordAnalyzer

VERSION = 'keyword-research-1.1'
MAX_RESULTS = 1000


def _terms(values, name, limit, required=False):
    if not isinstance(values, list) or len(values) > limit:
        raise ValueError(f'{name}: تعداد ورودی بیش از حد مجاز است.')
    result = []
    for value in values:
        if not isinstance(value, str) or len(value) > 200 or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
            raise ValueError(f'{name}: هر عبارت باید متن و حداکثر ۲۰۰ نویسه باشد.')
        word = KeywordAnalyzer.normalize_keyword(value)
        if word and word not in result:
            result.append(word)
    if required and not result:
        raise ValueError('حداقل یک عبارت پایه وارد کنید.')
    return result


def load_suggestions(path):
    """Load a dated export supplied by the user; no direct Google access is implied."""
    with Path(path).open('rb') as file:
        raw = file.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError('حجم فایل پیشنهادها نباید از ۱ مگابایت بیشتر باشد.')
    try:
        payload = json.loads(raw.decode('utf-8-sig'))
    except (ValueError, UnicodeError) as error:
        raise ValueError('فایل پیشنهادها JSON معتبر نیست.') from error
    if not isinstance(payload, dict):
        raise ValueError('ساختار فایل پیشنهادها معتبر نیست.')
    source, stamp, rows = payload.get('source'), payload.get('retrieved_at'), payload.get('results')
    if not isinstance(source, str) or not source.strip() or len(source) > 200:
        raise ValueError('نام منبع پیشنهادها لازم است.')
    if not isinstance(stamp, str) or len(stamp) > 64:
        raise ValueError('تاریخ دریافت معتبر و دارای منطقه زمانی لازم است.')
    try:
        date = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        if date.utcoffset() is None:
            raise ValueError('timezone missing')
    except ValueError as error:
        raise ValueError('تاریخ دریافت معتبر و دارای منطقه زمانی لازم است.') from error
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError('فهرست نتایج پیشنهادها معتبر نیست.')
    normalized = []
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('هر نتیجه باید عبارت پایه و فهرست پیشنهادها داشته باشد.')
        seed = _terms([row.get('seed')], 'عبارت پایه فایل', 1, True)[0]
        suggestions = _terms(row.get('suggestions'), 'پیشنهادها', MAX_RESULTS)
        total += len(suggestions)
        if total > MAX_RESULTS:
            raise ValueError('تعداد پیشنهادهای فایل بیش از حد مجاز است.')
        normalized.append({'seed': seed, 'suggestions': suggestions})
    for key in ('country', 'language'):
        if payload.get(key) is not None and (not isinstance(payload[key], str) or len(payload[key]) > 100):
            raise ValueError('کشور یا زبان منبع معتبر نیست.')
    return {'source': source.strip(), 'retrieved_at': stamp, 'country': payload.get('country'),
            'language': payload.get('language'), 'results': normalized}


def research(seeds, prefixes=None, suffixes=None, *, site_keywords=None, site_run_id=None, suggestions=None):
    """Deduplicate phrases while preserving each input seed and source as evidence."""
    seeds = _terms(seeds, 'عبارت پایه', 20, True)
    prefixes = _terms(prefixes or [], 'پیشوند', 10)
    suffixes = _terms(suffixes or [], 'پسوند', 10)
    if len(seeds) * (1 + len(prefixes)) * (1 + len(suffixes)) > MAX_RESULTS:
        raise ValueError('تعداد ترکیب‌ها بیش از ۱۰۰۰ است؛ ورودی‌ها را کمتر کنید.')
    if site_keywords is not None and (not isinstance(site_run_id, int) or isinstance(site_run_id, bool) or site_run_id < 1):
        raise ValueError('برای عبارت‌های سایت، شناسه خزش منبع لازم است.')
    results = {}
    skipped = set()
    def add(phrase, kind, seed, detail=None):
        phrase = KeywordAnalyzer.normalize_keyword(phrase)
        if len(phrase) > 200:
            skipped.add(phrase)
            return
        if phrase not in results:
            if len(results) >= MAX_RESULTS:
                raise ValueError('تعداد کل نتایج بیش از ۱۰۰۰ است؛ ورودی‌ها را کمتر کنید.')
            results[phrase] = {'phrase': phrase, 'seeds': [], 'types': [], 'evidence': [],
                               'word_count': len(phrase.split())}
        row = results[phrase]
        if seed not in row['seeds']:
            row['seeds'].append(seed)
        if kind not in row['types']:
            row['types'].append(kind)
        evidence = {'type': kind, 'seed': seed, **(detail or {})}
        if evidence not in row['evidence']:
            row['evidence'].append(evidence)
    for seed in seeds:
        add(seed, 'seed', seed)
        for prefix in prefixes:
            add(f'{prefix} {seed}', 'prefix', seed, {'prefix': prefix})
        for suffix in suffixes:
            add(f'{seed} {suffix}', 'suffix', seed, {'suffix': suffix})
        for prefix in prefixes:
            for suffix in suffixes:
                add(f'{prefix} {seed} {suffix}', 'prefix_suffix', seed, {'prefix': prefix, 'suffix': suffix})
    # Site terms are observed lexical matches, not inferred synonyms.
    for item in site_keywords or []:
        phrase = KeywordAnalyzer.normalize_keyword(item.get('term', ''))
        if not phrase:
            continue
        for seed in seeds:
            if f' {seed} ' in f' {phrase} ':
                add(phrase, 'site_observed', seed, {'run_id': site_run_id, 'pages': item.get('source_pages', [])})
    if suggestions:
        for entry in suggestions['results']:
            if entry['seed'] in seeds:
                for phrase in entry['suggestions']:
                    add(phrase, 'imported_suggestion', entry['seed'],
                        {k: suggestions.get(k) for k in ('source', 'retrieved_at', 'country', 'language')})
    return {'algorithm_version': VERSION, 'created_at': datetime.now(timezone.utc).isoformat(),
            'seeds': seeds, 'prefixes': prefixes, 'suffixes': suffixes, 'site_run_id': site_run_id,
            'suggestion_source': {k: suggestions.get(k) for k in ('source', 'retrieved_at', 'country', 'language')} if suggestions else None,
            'rows': list(results.values()),
            'skipped_long_phrases': len(skipped),
            'warnings': [f'{len(skipped)} عبارت تولیدشده با طول بیش از ۲۰۰ نویسه کنار گذاشته شد؛ سایر نتایج آماده‌اند.'] if skipped else []}

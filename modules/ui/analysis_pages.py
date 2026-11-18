"""Adapters from saved analysis contracts to dedicated desktop views."""
from collections import Counter
from modules.ui.intelligence import EvidenceTable

SPECS = {
    'audit': ('ممیزی فنی', 'هر یافته با شدت، نشانی، شواهد و راهکار؛ شدت را فیلتر و ردیف را انتخاب کنید.',
              [('rule_id', 'قاعده'), ('severity', 'شدت'), ('category', 'دسته'), ('title', 'مشکل'), ('url', 'نشانی صفحه'), ('recommendation', 'اقدام پیشنهادی')], 'severity'),
    'keywords': ('کلمات کلیدی', 'فراوانی و TF-IDF محاسبه‌شده از محتوای سایت؛ این اعداد حجم جست‌وجو نیستند.',
                 [('term', 'عبارت'), ('frequency', 'فراوانی'), ('tfidf', 'TF-IDF داخلی'), ('cluster', 'خوشه')], 'cluster'),
    'competitors': ('رقبا و SERP', 'دامنه‌ها از SERP منبع‌دار؛ برای انتخاب و اجرای بررسی از «انتخاب رقیب هر کلمه» استفاده کنید.',
                    [('domain', 'دامنه'), ('competitiveness_score', 'شاخص داخلی حضور'), ('keywords_count', 'تعداد عبارت‌ها'), ('gap_status', 'وضعیت شکاف')], None),
    'opportunities': ('فرصت‌های کلمات کلیدی', 'فرصت‌های آماری داخلی؛ ردیف را برای مؤلفه‌ها، صفحات منبع و روش محاسبه انتخاب کنید.',
                       [('keyword', 'عبارت'), ('opportunity_score', 'امتیاز داخلی'), ('total_tf_idf', 'مجموع TF-IDF'), ('pages_count', 'تعداد صفحات'), ('intent', 'نیت احتمالی')], 'intent'),
    'clusters': ('خوشه‌های موضوعی', 'گروه‌بندی واژگانی فعلی، بر پایه اشتراک توکن و زیررشته؛ رابطه معنایی قطعی نیست.',
                  [('cluster_name', 'خوشه'), ('primary_keyword', 'عبارت اصلی'), ('cluster_size', 'تعداد عبارت'), ('intent', 'نیت احتمالی'), ('secondary_keywords', 'عبارت‌های پشتیبان')], 'intent'),
    'gap': ('شکاف محتوایی', 'عبارت‌های دارای پوشش آماری ناکافی در داده سایت نسبت به رقبا؛ محدودیت پوشش خزش را بررسی کنید.',
             [('term', 'عبارت'), ('competitor_domains_count', 'تعداد دامنه شاهد'), ('competitor_domains', 'رقبا'), ('priority', 'اولویت آماری'), ('recommended_action', 'اقدام پیشنهادی')], 'priority'),
    'cannibalization': ('هم‌نوع‌خواری', 'موارد مشکوک به هم‌پوشانی؛ اشتراک عبارت به‌تنهایی اثبات رقابت یا مجوز ادغام صفحات نیست.',
                         [('term', 'عبارت'), ('competing_pages_count', 'تعداد صفحات'), ('competing_pages', 'صفحات و وزن'), ('severity', 'شدت')], 'severity'),
    'roadmap': ('نقشه راه', 'اقدام‌های اولویت‌بندی‌شده همین اجرا؛ اثر و تلاش فرض‌های روش داخلی‌اند. ثبت وضعیت اجرایی هنوز پشتیبانی نمی‌شود.',
                 [('action_type', 'نوع اقدام'), ('url', 'صفحه'), ('keyword', 'عبارت'), ('priority_score', 'اولویت داخلی'), ('action', 'اقدام بعدی')], 'action_type'),
}


def make_view(key):
    return EvidenceTable(*SPECS[key])


def present_views(window, result):
    """Map existing results; do not compute SEO scores inside widgets."""
    keyword = result.get('keyword_analysis', {})
    inventory = {r['term']: r for r in result.get('keyword_inventory', [])}
    provenance = {key: result.get('meta', {}).get(key) for key in ('analysis_run_id', 'algorithm_version')}
    rows = {
        'audit': result.get('audit_summary', {}).get('issues', []),
        'keywords': [dict(r, source_pages=inventory.get(r['term'], {}).get('source_pages', [])) for r in keyword.get('keywords', [])],
        'competitors': [dict(r, gap_status=result.get('content_gap_analysis', {}).get('status', 'unavailable'),
            source=result.get('serp', {}).get('source'), retrieved_at=result.get('serp', {}).get('retrieved_at')) for r in result.get('project_competitors', [])],
        'opportunities': [dict(r, source_pages=inventory.get(r['keyword'], {}).get('source_pages', []),
            score_method='امتیاز = مجموع TF-IDF × (۱ + ۰٫۲ × حداقل(تعداد صفحات، ۴)). مقیاس باز؛ تقاضا یا رتبه نیست.',
            action='پوشش عبارت در صفحات منبع و نیاز جست‌وجو را بازبینی کنید.') for r in keyword.get('opportunities', [])],
        'clusters': keyword.get('clusters', []),
        'gap': result.get('content_gap_analysis', {}).get('content_gaps', []),
        'cannibalization': result.get('cannibalization_issues', []),
        'roadmap': [dict(r, score_method=result.get('strategy_method', 'روش ثبت نشده')) for r in result.get('seo_roadmap', [])],
    }
    for key, records in rows.items():
        window.analysis_views[key].present([dict(r, **provenance) for r in records])
    charts = {
        'audit': ('یافته‌ها بر اساس شدت', list(Counter(r.get('severity', 'نامشخص') for r in rows['audit']).items()), 'تعداد یافته'),
        'keywords': ('۶ عبارت پرتکرار', [(r['term'], r.get('frequency', 0)) for r in sorted(rows['keywords'], key=lambda r: r.get('frequency', 0), reverse=True)[:6]], 'فراوانی'),
        'competitors': ('حضور در عبارت‌های SERP · حداکثر ۶ دامنه', [(r['domain'], r.get('keywords_count', 0)) for r in sorted(rows['competitors'], key=lambda r: r.get('keywords_count', 0), reverse=True)[:6]], 'تعداد عبارت'),
        'opportunities': ('فرصت‌ها بر اساس نیت احتمالی', list(Counter(r.get('intent', 'نامشخص') for r in rows['opportunities']).items()), 'تعداد فرصت'),
        'clusters': ('۶ خوشه بزرگ‌تر', [(r['cluster_name'], r['cluster_size']) for r in sorted(rows['clusters'], key=lambda r: r['cluster_size'], reverse=True)[:6]], 'تعداد عبارت'),
        'gap': ('شکاف‌ها بر اساس اولویت آماری', list(Counter(r.get('priority', 'نامشخص') for r in rows['gap']).items()), 'تعداد شکاف'),
        'cannibalization': ('۶ مورد دارای بیشترین هم‌پوشانی', [(r['term'], r['competing_pages_count']) for r in sorted(rows['cannibalization'], key=lambda r: r['competing_pages_count'], reverse=True)[:6]], 'تعداد صفحه'),
        'roadmap': ('اقدام‌ها بر اساس نوع', list(Counter(r.get('action_type', 'نامشخص') for r in rows['roadmap']).items()), 'تعداد اقدام'),
    }
    for key, (title, values, unit) in charts.items():
        window.analysis_views[key].show_chart(title, values, unit)
    gap = window.analysis_views['gap']
    if result and result.get('content_gap_analysis', {}).get('status') != 'completed':
        gap.empty.setText('داده مقایسه رقبا در دسترس نیست؛ SERP منبع‌دار را وارد و بررسی رقبای منتخب را اجرا کنید.')

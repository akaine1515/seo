<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:d5d59ca323bdb04708ab4bafdaddac629cbbe228397f51a6fdebc00c9488065c -->

# SEO Intelligence V2

ابزار دسکتاپ Python / PySide6 / SQLite برای تحلیل الگوریتمی سئو، بدون مدل مولد.

## اجرا و تست

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
python -m unittest discover -s tests -v
```

در محیط این تسک از `/home/vercel-sandbox/runtime/venv/bin/python` استفاده شده است. رابط وب ندارد؛ مرورگر جایگزین آزمون رابط دسکتاپ نیست.

## مسیر واقعی اجرا

`main.py` → `core.engine.SEOOrchestrator` → `CrawlerEngine.run` → SQLite → KeywordExtractor → KeywordAnalyzer → KeywordClustering / KeywordOpportunityEngine → SERP provider → CompetitorDiscovery → صفحات انتخابی رقبا → CompetitorAnalyzer → TF-IDF با corpus مشترک → ContentGapStrategyEngine → ممیزی پایه → snapshot.

در UI سقف خزش قابل تنظیم است (پیش‌فرض ۵۰). بدون Provider، رقبا و gap در دسترس نیستند و هشدار نمایش داده می‌شود. رقبای ساختگی، امتیاز TF-IDF ساختگی و gap ثابت حذف شده‌اند.

برای ورود SERP، مسیر فایل JSON را در UI وارد کنید. فایل از یک منبع مجاز تهیه می‌شود؛ برنامه scraping مستقیم گوگل انجام نمی‌دهد:

```json
{
  "source": "Name of authorized SERP provider/export",
  "retrieved_at": "2026-11-17T10:00:00Z",
  "results": [
    {"keyword": "target term", "organic_results": [
      {"url": "https://competitor.example/article", "position": 1}
    ]}
  ]
}
```

SERP برای عبارت‌های استخراج‌شده از سایت و انتخاب‌های ذخیره‌شده مصرف می‌شود. در «انتخاب رقیب هر کلمه» فایل تاریخ‌دار را وارد و برای هر عبارت صفر تا پنج دامنه ذخیره کنید. پس از بازکردن یک خزش ذخیره‌شده، دکمه «بررسی رقبا با خزش ذخیره‌شده» فقط صفحات رقبای منتخب را دریافت می‌کند؛ سایت خودتان دوباره خزش نمی‌شود. پیش‌فرض بودجه پنج URL برای هر دامنه است. بدون انتخاب، هیچ صفحه رقیبی خزش نمی‌شود. هر بررسی مستقل تاریخچه جدا دارد و از صفحه تاریخچه قابل بازکردن است. برای تازه‌کردن داده سایت خودتان تحلیل کامل تازه لازم است.

## قراردادها

- `CrawlerEngine.run(url)` صف و صفحات را ذخیره می‌کند و آمار برمی‌گرداند؛ متد `fetch` ندارد. `request_page` پاسخ HTTP باز برمی‌گرداند که مصرف‌کننده باید ببندد.
- `PageParser.parse(html, url, status_code=None, response_headers=None)` دارای `text_content`, `h1_list`, `h2_list`, `h3_list` است؛ `body_text` و فهرست `links` برنمی‌گرداند.
- `KeywordExtractor.extract_run_keywords(contents)` نگاشت `page_id → {unigrams, bigrams, trigrams, total_tokens}` می‌دهد.
- `KeywordAnalyzer.compute_tf_idf(extracted)` نگاشت `page_id → term → {raw_frequency, tf, idf, tf_idf_score, intent}` می‌دهد. فرمول موجود `tf * (log(N/df + 1) + 1)` حفظ شده است؛ تحلیل فعلی unigram و bigram را مصرف می‌کند.
- Provider باید `source` و `search(keywords) → list[{keyword, organic_results}]` داشته باشد. FileSERPProvider زمان منبع را نگه می‌دارد. نبود Provider با نتیجه صفرِ موفق یکسان نیست.
- `CompetitorAnalyzer.analyze_batch(urls)` موفقیت/خطای هر URL، زمان، ساختار، متن و لینک‌ها را برمی‌گرداند؛ TF-IDF مقایسه‌ای در orchestration با corpus مشترک محاسبه می‌شود. لینک داخلی بر مبنای hostname یکسان است؛ زیردامنه، خارجی محسوب می‌شود. robots و redirect از crawler موجود استفاده می‌کنند.
- موتور فعال gap در `modules/strategy/content_gap.py` است؛ ورودی سایت، خروجی واقعی TF-IDF؛ ورودی رقیب، `keywords_analysis` با همان متریک‌ها. کلیدهای قدیمی حفظ و کلیدهای مورد نیاز گزارش (`term`, `competitor_domains_count`, `competitor_domains`, `evidence_urls`, `priority`, `recommended_action`) اضافه شده‌اند. امتیاز اولویت، آماری است و اولویت تجاری نیست. حضور term اثبات پوشش موضوعی کافی نیست.
- `run_full_pipeline(url, options, progress_callback=None)` تنظیمات `max_pages`, `max_competitors`, `competitor_max_pages`, `timeout`, `selected_competitors` می‌گیرد. خروجی با UI و گزارش‌ها سازگار است؛ خطاهای جدی raise می‌شوند و `pipeline_failed` ثبت می‌شود.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:f6a25eeb9f6f23bf2b90752bd65ae5d2edac4596a3f639cfe16a7ae7a457cc99 -->

## ذخیره و بازیابی

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:67a181c519aeddad4992e487391f8575d56777ae2c735bc546de332e4729b8e7 -->

Schema به ۸ ارتقا یافت؛ جدول site_settings برای active و تنظیمات هر سایت اضافه شد. جدول نسخه ۷ نیز حفظ می‌شود:

<!-- /coderabbit-ai-generated:v1 --> جدول `analysis_results` با `analysis_run_id` یکتا، `format_version=1` و JSON نتیجه اضافه می‌شود. migration افزایشی است، داده نسخه ۶ حفظ می‌شود و اجرای مجدد آن مجاز است. `SEOOrchestrator.load_result(run_id)` جدول جدید را می‌خواند و برای snapshotهای قدیمی به crawl_events برمی‌گردد. متن رقیب به صورت پیش‌فرض در snapshot ذخیره نمی‌شود؛ `retain_competitor_text=True` آن را فعال می‌کند. متن سایت خودی در page_contents باقی می‌ماند. نتیجه هر اجرا با حذف پروژه cascade می‌شود.

`AnalysisResultRepository.compare(previous, current)` تغییر مسائل را برای یک پروژه مقایسه می‌کند. مسئله‌ای که URL آن در اجرای جدید دیده نشده در `unobserved` قرار می‌گیرد و حل‌شده محسوب نمی‌شود. UI دکمه Open saved run و Compare with run دارد؛ شناسه اجرا را وارد کنید. در حال حاضر مقایسه در Execution Logs نمایش داده می‌شود.

## سیاست دریافت و دامنه

دامنه‌های مستقل با snapshot داخلی PSL در tldextract==5.3.0 محاسبه می‌شوند؛ هیچ دانلود PSL یا DNS در تحلیل دامنه انجام نمی‌شود. private suffix فعال است؛ a.github.io و b.github.io مستقل‌اند. gap چند زیردامنه یک دامنه ثبت‌شده را یک رقیب حساب می‌کند. API قدیمی `_extract_clean_domain` برای سازگاری hostname را حفظ می‌کند؛ تجمیع با `site_domain` انجام می‌شود. پسوند ناشناخته کل hostname را حفظ می‌کند.

دریافت صفحات، robots و sitemap از RequestPolicy با pacing مشترک استفاده می‌کند؛ پیش‌فرض نیم‌ثانیه بین درخواست‌های هر origin و سقف دریافت صفحه ۵ MiB است. دریافت streaming با سقف روی بایت‌های بازشده انجام می‌شود؛ ۴۲۹ درخواست‌های بعدی همان origin در policy را متوقف می‌کند. retry خودکار وجود ندارد. برای robots/sitemap پاسخ redirect دنبال نمی‌شود و به عنوان خطای قابل بررسی باقی می‌ماند؛ این سیاست محافظه‌کارانه ممکن است برخی سایت‌ها را محدود کند. redirect صفحات همچنان توسط CrawlerEngine کنترل می‌شود. تنظیمات برنامه‌نویسی: `request_interval` بین ۰ و ۶۰ و `max_response_bytes` عدد مثبت.

FileSERPProvider فایل حداکثر ۱۰ MiB، timestamp با timezone، ساختار entryها و URL/position را اعتبارسنجی می‌کند. داده خراب باعث خطای روشن می‌شود؛ بدون داده ساختگی جایگزین.

## ممیزی و استراتژی

علاوه بر قواعد پایه، ممیزی مشاهده‌شده redirect، canonical mismatch، noindex، alt، H3 بدون H2، mixed content، HTTP، duplicate content، عمق و inlink اندک، URLهای sitemap دیده‌نشده و لینک‌های داخلی با HTTP خطای مشاهده‌شده را پوشش می‌دهد. نتایج HTTP جدا از صفحات موفق ثبت می‌شوند. خزش ناقص به معنی orphan نیست. نبود alt ممکن است برای تصویر تزئینی مجاز باشد؛ موارد برای بررسی‌اند. شدت‌ها همان Critical/High/Medium/Low با قواعد مستقل‌اند و امتیاز رتبه‌بندی جست‌وجو نیستند.

AdvancedOnPageAnalyzer به مسیر اصلی برای title relevance و cannibalization متصل است؛ حضور عبارت در چند صفحه به تنهایی اثبات cannibalization نیست. `seo_roadmap` اقدامات با URL/keyword و evidence دارد. اولویت اولیه impact/effort است: impact از شدت ۱ تا ۴ یا تعداد دامنه رقبا، effort فرضی ۲ برای فنی و ۳ برای محتوا. این اعداد تخمینی‌اند و باید با کسب‌وکار بازبینی شوند. مدل مولد استفاده نمی‌شود.

Excel اکنون داده‌های موجود Pages، Crawl HTTP Results، Keywords، Clusters، Opportunities، Competitor Pages و SEO Roadmap را هم صادر می‌کند. HTML نقشه راه، keyword search و منبع/زمان داده را نشان می‌دهد. داده بدون منبع وارد گزارش نمی‌شود.

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:9ffba3baa0356c005442f706520e6c582772729e7af01eaf1e6241e30ae99778 -->

## جریان P0 مطابق سند محصول

معیار مرجع از این نوبت سند نیازمندی‌های محصول نسخه ۱.۰ مالک است؛ P0 تا P4 ترتیب توسعه‌اند. P4 اختیاری/تکمیلی است و نبود اتصال Google مانع تکمیل هسته نیست.

در محیط کار حداکثر پنج سایت ثبت می‌شود (سایت غیرفعال هم در سقف حساب می‌شود). URL را وارد و Register site را بزنید؛ نام سایت را تعیین کنید. انتخاب سایت، تنظیمات ذخیره‌شده‌اش را بارگذاری می‌کند. Rename، Activate/deactivate و Delete site قابل استفاده‌اند؛ حذف پس از تأیید در خود UI تاریخچه آن سایت را هم cascade حذف می‌کند. اگر دیتابیس قدیمی بیش از پنج پروژه داشته باشد، رکوردهایش حفظ می‌شود و ثبت تازه تا آزادشدن ظرفیت رد می‌شود. چند زیردامنه یک دامنه ثبت‌شده یک سایت در محیط کار محسوب می‌شود؛ private suffixهای مستقل جدا می‌مانند.

Crawl limit، عمق، timeout، فاصله درخواست‌ها و پیشوند مسیرهای مستثنا در UI قابل تغییر و با Save crawl settings ماندگارند. عمق فقط برای لینک‌های کشف‌شده معنی دارد؛ URLهای sitemap بذر مستقل‌اند. دامنه مجاز فعلاً hostname سایت است؛ فهرست چنددامنه‌ای هنوز پشتیبانی نمی‌شود. اعتبارسنجی تنظیمات پیش از اجرا انجام می‌شود. تنظیمات، نسخه الگوریتم، زمان‌ها و شمارنده‌های مشاهده‌شده در snapshot و شیت Run Metadata قرار می‌گیرند.

Stop analysis در worker علامت توقف می‌گذارد؛ درخواست جاری با timeout/حد حجم برمی‌گردد و سپس توقف اعمال می‌شود. صف و صفحات ذخیره‌شده و snapshot ناقص حفظ می‌شوند. ادامه همان run از UI هنوز پشتیبانی نمی‌شود؛ اجرای مجدد run_id جدید می‌سازد. بستن پنجره هنگام worker فعال جلوگیری می‌شود.

وضعیت خزش مستقل از وضعیت کل تحلیل است: cancelled برای توقف، failed برای نبود متن قابل تحلیل، partial برای شکست/صف باقی‌مانده یا مراحل اصلی در دسترس‌نبوده، completed تنها برای مراحل اجراشده کامل. نبود P4 در این تصمیم دخالت ندارد. شمارنده discovered فقط صف کشف‌شده است و اندازه واقعی همه URLهای سایت نیست. محدودیت عمق/مسیر و نبود لینک یا sitemap جامع، پوشش کل سایت را تضمین نمی‌کنند. schema analysis_runs همچنان وضعیت چرخه خزش را نگه می‌دارد؛ UI و خروجی وضعیت pipeline را از snapshot می‌خوانند.

## موارد باز

<!-- /coderabbit-ai-generated:v1 -->

اتصال آنلاین SERP، Trends و Search Console/OAuth به انتخاب سرویس و دسترسی مالک نیاز دارد. Trends و GSC پیاده‌سازی نشده‌اند. On-Page پیشرفته، مقایسه موضوعی کامل رقبا، UI کامل پروژه‌ها، <!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:8dd348fd197935c8742277ba44ef388a32331e72db439bab72bb6507434d16d7 -->

ادامه اجرای متوقف‌شده، گزارش جامع لینک‌ها

<!-- /coderabbit-ai-generated:v1 -->، QA مقیاس بزرگ و بسته‌بندی و آزمون Windows هنوز تکمیل نشده‌اند. نتایج خودکار فعلی offline هستند؛ محصول آماده انتشار اعلام نمی‌شود.


<!-- /coderabbit-ai-generated:v1 -->

## مرجع ادامه توسعه نسخه ۳

ارزیابی ماژول‌ها، فاصله تا معیارهای محصول، قرارداد اجرای مستقل و وابستگی فازها در `docs/V3_ROADMAP_FA.md` ثبت شده است. این سند جایگزین ادعای تکمیل همه موتورهای نسخه ۳ نیست.

Schema فعلی ۱۰ است؛ `analysis_stage_results` تاریخچه افزایشی بررسی رقبا را با FK به اجرای خزش منبع نگه می‌دارد. `analysis_results` و صفحات منبع تغییر نمی‌کنند. `SEOOrchestrator.run_competitor_stage(source_run_id, options, progress_callback, cancel_event)` داده سایت را از SQLite می‌خواند و نتایج رقبا، gap آماری و برنامه هر کلمه را بازسازی می‌کند. `stage_result_id` شناسه بررسی مستقل است؛ `analysis_run_id` همچنان شناسه خزش منبع است. منبع و زمان SERP، زمان خزش سایت و زمان دریافت صفحات رقبا جدا نگه داشته می‌شوند. در نبود Provider تازه، SERP ذخیره‌شده مصرف می‌شود.


<!-- /coderabbit-ai-generated:v1 -->
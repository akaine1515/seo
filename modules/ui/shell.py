"""Desktop shell and form composition, separate from analysis services."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QFormLayout, QPushButton, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox,
    QProgressBar, QTabWidget, QTextEdit, QScrollArea)
from modules.ui.overview import Overview, label, panel
from modules.ui.design_system import CREDIT, GlassBackdrop


def scroll(widget):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    return area


def button(text, handler, role=None):
    control = QPushButton(text)
    if role:
        control.setProperty('role', role)
    control.clicked.connect(handler)
    return control


def page(title, description):
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(16)
    layout.addWidget(label(title, 'title'))
    layout.addWidget(label(description, 'muted'))
    return widget, layout


def build_shell(w):
    central = GlassBackdrop()
    central.setObjectName('shell')
    central.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    w.setCentralWidget(central)
    root = QHBoxLayout(central)
    root.setDirection(QHBoxLayout.Direction.LeftToRight)
    root.setContentsMargins(18, 18, 18, 12)
    root.setSpacing(16)
    content = QWidget()
    content.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    main = QVBoxLayout(content)
    main.setContentsMargins(0, 0, 0, 0)
    main.setSpacing(12)
    root.addWidget(content, 1)
    top = QFrame()
    top.setObjectName('topbar')
    bar = QHBoxLayout(top)
    bar.setContentsMargins(16, 10, 16, 10)
    w.breadcrumb = label('فضای کاری  /  نمای کلی', 'muted')
    bar.addWidget(w.breadcrumb, 1)
    bar.addWidget(label('سایت فعال'))
    w.site_selector = QComboBox()
    w.site_selector.setMinimumWidth(220)
    w.site_selector.setMaximumWidth(300)
    w.site_selector.currentIndexChanged.connect(w.select_site)
    bar.addWidget(w.site_selector)
    w.run_btn = button('شروع تحلیل', w.start_analysis, 'primary')
    bar.addWidget(w.run_btn)
    main.addWidget(top)
    w.site_status_label = label('سایتی انتخاب نشده است', 'muted')
    w.site_status_label.setProperty('role', 'eyebrow')
    main.addWidget(w.site_status_label)
    w.stage_banner = label('', 'muted')
    w.stage_banner.hide()
    main.addWidget(w.stage_banner)
    w.tabs = QTabWidget()
    w.tabs.tabBar().hide()
    main.addWidget(w.tabs, 1)
    w.overview_widget = Overview()
    w.overview_widget.navigate.connect(w.navigate)
    w.kpi_label = w.overview_widget.state_badge
    w.tabs.addTab(scroll(w.overview_widget), 'نمای کلی')
    from modules.ui.analysis_pages import make_view, SPECS
    w.analysis_views = {key: make_view(key) for key in ('audit', 'keywords', 'competitors', 'opportunities', 'clusters', 'gap', 'cannibalization', 'roadmap')}
    for key, attribute in [('audit', 'technical_table'), ('keywords', 'keywords_table'), ('competitors', 'competitors_table')]:
        view = w.analysis_views[key]
        setattr(w, attribute, view.table)
        w.tabs.addTab(view, SPECS[key][0])
    widget, body = page('گزارش عملیات', 'پیام‌های سرویس و جزئیات خطاهای آخرین اجرای بازشده.')
    w.log_output = QTextEdit()
    w.log_output.setReadOnly(True)
    w.log_output.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    body.addWidget(w.log_output)
    w.tabs.addTab(widget, 'گزارش عملیات')
    # Existing controls retain their handlers and repositories.
    widget, body = page('وب‌سایت‌ها', 'حداکثر پنج سایت متعلق به خود را در این فضای کاری مدیریت کنید.')
    frame, form_body = panel('ثبت و مدیریت سایت', 'برای ویرایش، سایت را از نوار بالا انتخاب کنید. حذف سایت، تاریخچه آن را نیز حذف می‌کند.')
    form = QFormLayout()
    w.url_input = QLineEdit()
    w.url_input.setPlaceholderText('https://example.com')
    w.url_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    w.url_input.setAccessibleName('نشانی وب‌سایت')
    form.addRow('نشانی وب‌سایت', w.url_input)
    form_body.addLayout(form)
    w.site_error_label = label('')
    w.site_error_label.setStyleSheet('color: #A82736;')
    w.site_error_label.hide()
    form_body.addWidget(w.site_error_label)
    for text, handler in [('ثبت سایت جدید', w.register_site), ('تغییر نام', w.rename_site),
                          ('فعال / غیرفعال', w.toggle_site), ('حذف سایت و تاریخچه', w.delete_site)]:
        form_body.addWidget(button(text, handler, 'danger' if handler == w.delete_site else None))
    body.addWidget(frame)
    body.addStretch()
    w.tabs.addTab(scroll(widget), 'وب‌سایت‌ها')  # 5
    widget, body = page('اجرای تحلیل', 'تنظیمات به سایت فعال اعمال می‌شود. پیشرفت پردازش، درصد پوشش کل سایت نیست.')
    frame, form_body = panel('محدوده خزش')
    form = QFormLayout()
    w.max_pages_input = QSpinBox()
    w.max_pages_input.setRange(1, 10000)
    w.max_pages_input.setValue(50)
    w.max_depth_input = QSpinBox()
    w.max_depth_input.setRange(0, 100)
    w.max_depth_input.setValue(5)
    w.timeout_input = QSpinBox()
    w.timeout_input.setRange(1, 300)
    w.timeout_input.setValue(15)
    w.interval_input = QDoubleSpinBox()
    w.interval_input.setRange(0, 60)
    w.interval_input.setValue(.5)
    w.excluded_input = QLineEdit()
    w.excluded_input.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    w.excluded_input.setPlaceholderText('/account,/cart')
    for text, control in [('حداکثر صفحه', w.max_pages_input), ('عمق لینک', w.max_depth_input),
        ('مهلت هر درخواست (ثانیه)', w.timeout_input), ('فاصله درخواست‌ها (ثانیه)', w.interval_input),
        ('مسیرهای مستثنا (با کاما)', w.excluded_input)]:
        form.addRow(text, control)
    form_body.addLayout(form)
    form_body.addWidget(button('ذخیره تنظیمات سایت فعال', w.save_site_settings))
    body.addWidget(frame)
    frame, run_body = panel('وضعیت عملیات', 'آماده‌سازی ← خزش و استخراج ← ممیزی ← کلمات ← فرصت‌ها ← رقبا ← ذخیره نتیجه')
    w.run_message = label('آماده شروع؛ از دکمه «شروع تحلیل» در نوار بالا استفاده کنید.')
    run_body.addWidget(w.run_message)
    w.progress_bar = QProgressBar()
    w.progress_bar.setValue(0)
    run_body.addWidget(w.progress_bar)
    w.stop_btn = button('توقف تحلیل', w.stop_analysis, 'danger')
    w.stop_btn.setEnabled(False)
    run_body.addWidget(w.stop_btn)
    run_body.addWidget(button('مشاهده پیام‌ها و خطاها', lambda: w.navigate('logs')))
    body.addWidget(frame)
    body.addStretch()
    w.tabs.addTab(scroll(widget), 'اجرای تحلیل')  # 6
    w.page_indices = dict(overview=0, audit=1, keywords=2, competitors=3, logs=4, sites=5, run=6)
    for key in ('opportunities', 'clusters', 'gap', 'cannibalization', 'roadmap'):
        w.page_indices[key] = w.tabs.addTab(w.analysis_views[key], SPECS[key][0])
    widget, body = page('گزارش‌ها', 'خروجی Excel و HTML مستقل، فقط برای اجرای بارگذاری‌شده.')
    frame, controls = panel('خروجی اجرا', 'تا پیش از وجود نتیجه، خروجی غیرفعال است. وضعیت ناقص و محدودیت‌ها در گزارش حفظ می‌شوند.')
    w.export_excel_btn = button('ذخیره Excel چندشیتی', w.export_excel)
    w.export_html_btn = button('ذخیره گزارش HTML', w.export_html)
    for control in (w.export_excel_btn, w.export_html_btn):
        control.setEnabled(False)
        controls.addWidget(control)
    body.addWidget(frame)
    body.addStretch()
    w.page_indices['reports'] = w.tabs.addTab(widget, 'گزارش‌ها')
    from modules.ui.intelligence import EvidenceTable
    w.history_view = EvidenceTable('تاریخچه اجراها', 'یک اجرا را انتخاب کنید و آن را باز کنید؛ مقایسه با اجرای فعلی همین سایت انجام می‌شود.',
        [('id', 'شناسه'), ('status', 'وضعیت خزش'), ('started_at', 'شروع'), ('finished_at', 'پایان')], 'status')
    body = w.history_view.layout()
    w.history_btn = button('باز کردن اجرای انتخاب‌شده', w.open_selected_run)
    w.compare_btn = button('مقایسه اجرای انتخاب‌شده با نتیجه فعلی', w.compare_selected_run)
    body.addWidget(w.history_btn)
    body.addWidget(w.compare_btn)
    body.addWidget(button('باز کردن اجرا با شناسه', w.open_saved_run))
    body.addWidget(button('تاریخچه بررسی‌های مستقل رقبا', w.open_competitor_history))
    w.comparison_view = EvidenceTable('تغییر یافته‌ها', 'مقایسه فقط برای صفحات مشاهده‌شده معتبر است.',
        [('change', 'تغییر'), ('rule_id', 'قاعده'), ('url', 'صفحه')], 'change')
    body.addWidget(w.comparison_view)
    w.comparison_view.hide()
    w.page_indices['history'] = w.tabs.addTab(w.history_view, 'تاریخچه اجراها')
    widget, body = page('تنظیمات', 'رابط فارسی و راست‌چین؛ اتصال‌های بیرونی تنها با داده واقعی.')
    frame, controls = panel('منبع SERP', 'فایل JSON تاریخ‌دار از منبع مجاز وارد کنید؛ دامنه‌ها را در صفحه «انتخاب رقیب هر کلمه» انتخاب کنید.')
    w.serp_path_input = QLineEdit()
    w.serp_path_input.setPlaceholderText('مسیر فایل SERP JSON · اختیاری')
    w.selected_competitors_input = QLineEdit()
    w.selected_competitors_input.setPlaceholderText('example.org,example.net · حداکثر ۵ دامنه')
    form = QFormLayout()
    for text, control in [('فایل نتایج', w.serp_path_input)]:
        control.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        form.addRow(text, control)
    controls.addLayout(form)
    controls.addWidget(label('Search Console: متصل نیست  ·  داده حجم جست‌وجو و سختی: در دسترس نیست', 'muted'))
    body.addWidget(frame)
    body.addStretch()
    w.page_indices['settings'] = w.tabs.addTab(widget, 'تنظیمات')
    widget, body = page('درباره محصول', 'ابزار دسکتاپ تحلیل و تصمیم‌سازی سئو')
    frame, controls = panel('SEO Intelligence V2')
    w.about_credit = label(CREDIT, 'brand')
    w.about_credit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    controls.addWidget(w.about_credit)
    controls.addWidget(label('معرفی مالک محصول؛ این عبارت نام شرکت یا ادعای ثبت مالکیت حقوقی نیست.', 'muted'))
    controls.addWidget(label('تحلیل الگوریتمی · ذخیره‌سازی محلی · شواهد قابل پیگیری', 'muted'))
    body.addWidget(frame)
    body.addStretch()
    w.page_indices['about'] = w.tabs.addTab(widget, 'درباره محصول')
    from modules.ui.intelligence import EvidenceTable, CompetitorSelection, StrategyMap
    w.site_evidence = EvidenceTable('جزئیات سئوی صفحات',
        'تگ‌های HTML، متادیتا، H1 تا H6، تصاویر و زمان دریافت HTTP. داده ناموجود «—» است؛ سرعت مرورگر اندازه‌گیری نشده است.',
        [('url', 'صفحه'), ('title', 'عنوان'), ('word_count', 'تعداد واژه'), ('image_count', 'تصویر'), ('performance', 'دریافت HTTP')])
    w.keyword_evidence = EvidenceTable('کلمات استفاده‌شده و فرزندان',
        'عبارت‌های یک تا سه‌کلمه‌ای از عنوان، توضیحات، تیترها و متن؛ فرزند یعنی عبارت طولانی‌تر مشاهده‌شده پس از پاک‌سازی.',
        [('term', 'عبارت'), ('frequency', 'فراوانی در فیلدها'), ('children', 'فرزندان'), ('source_pages', 'صفحات منبع')])
    w.competitor_selection = CompetitorSelection(w)
    w.strategy_map = StrategyMap()
    from modules.ui.keyword_research import KeywordResearch
    w.keyword_research = KeywordResearch(w)
    w.page_indices['pages'] = w.tabs.addTab(w.site_evidence, 'جزئیات سئوی صفحات')
    w.page_indices['keyword_tree'] = w.tabs.addTab(w.keyword_evidence, 'کلمات و فرزندان')
    w.page_indices['selection'] = w.tabs.addTab(w.competitor_selection, 'انتخاب رقیب هر کلمه')
    w.page_indices['strategy'] = w.tabs.addTab(w.strategy_map, 'استراتژی و مایندمپ')
    w.page_indices['research'] = w.tabs.addTab(w.keyword_research, 'تحقیق عبارات')
    # Physical right-hand sidebar remains right-aligned independently of bidi text.
    w.sidebar = QFrame()
    w.sidebar.setObjectName('sidebar')
    w.sidebar.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    w.sidebar.setFixedWidth(246)
    side = QVBoxLayout(w.sidebar)
    side.setContentsMargins(14, 18, 14, 14)
    side.setSpacing(6)
    w.brand_label = label('SEO Intelligence', 'brand')
    w.brand_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    side.addWidget(w.brand_label)
    w.brand_subtitle = label('فضای هوشمند تحلیل سئو  /  V2', 'muted')
    side.addWidget(w.brand_subtitle)
    w.collapse_btn = button('جمع کردن منو  ›', w.toggle_sidebar)
    w.collapse_btn.setAccessibleName('جمع یا باز کردن نوار ناوبری')
    side.addWidget(w.collapse_btn)
    nav = QWidget()
    nav_body = QVBoxLayout(nav)
    nav_body.setContentsMargins(0, 8, 0, 8)
    nav_body.setSpacing(2)
    from modules.ui.icons import line_icon
    w.nav_buttons = []
    w.nav_groups = []
    groups = {'overview': 'فضای کاری', 'audit': 'تحلیل سایت', 'competitors': 'تحلیل رقبا', 'pages': 'ابزارها', 'reports': 'مدیریت'}
    for key in ('overview', 'sites', 'run', 'audit', 'keywords', 'opportunities', 'clusters',
                'competitors', 'gap', 'cannibalization', 'roadmap', 'pages', 'keyword_tree', 'research', 'selection', 'strategy', 'reports', 'history', 'settings', 'about'):
        if key in groups:
            heading = label(groups[key], 'navgroup')
            nav_body.addWidget(heading)
            w.nav_groups.append(heading)
        index = w.page_indices[key]
        text = w.tabs.tabText(index)
        control = button(text, lambda checked=False, idx=index: w.switch_tab(idx), 'nav')
        control.setCheckable(True)
        control.setIcon(line_icon(key))
        control.setIconSize(QSize(17, 17))
        control.setProperty('page_index', index)
        control.setProperty('full_text', text)
        control.setAccessibleName(text)
        control.setToolTip(text)
        nav_body.addWidget(control)
        w.nav_buttons.append(control)
    nav_body.addStretch()
    nav_area = scroll(nav)
    nav_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    side.addWidget(nav_area, 1)
    w.credit_label = label(CREDIT)
    w.credit_label.setObjectName('credit')
    w.credit_label.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    w.credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    w.credit_label.setWordWrap(False)
    side.addWidget(w.credit_label)
    w.sidebar_version = label('نسخه ۲ · ذخیره‌سازی محلی', 'muted')
    side.addWidget(w.sidebar_version)
    root.addWidget(w.sidebar)
    w._sidebar_compact = False
    w.switch_tab(0)

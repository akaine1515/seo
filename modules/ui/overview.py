"""Native dashboard presentation. Values are read from snapshots, never fabricated."""
import json
from datetime import datetime, timezone
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout, QDialog, QPlainTextEdit)
from modules.ui.design_system import STATUS_TEXT


def label(text, role=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(True)
    widget.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute | Qt.AlignmentFlag.AlignVCenter)
    if role:
        widget.setProperty('role', role)
    return widget


def panel(title, description=''):
    frame = QFrame()
    frame.setObjectName('panel')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 14, 20, 14)
    layout.setSpacing(10)
    layout.addWidget(label(title, 'section'))
    if description:
        layout.addWidget(label(description, 'muted'))
    return frame, layout


class MetricButton(QPushButton):
    def __init__(self, title):
        super().__init__()
        self.setProperty('role', 'metric')
        self.title = title
        body = QVBoxLayout(self)
        body.setContentsMargins(18, 14, 18, 14)
        body.setSpacing(4)
        self.value_label = label('—')
        self.value_label.setStyleSheet('font-size: 28px; font-weight: 600;')
        body.addWidget(self.value_label)
        body.addWidget(label(title, 'muted'))
        for item in (body.itemAt(i).widget() for i in range(body.count())):
            item.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_value(self, value):
        self.value_label.setText(str(value) if value is not None else '—')
        self.setAccessibleName(self.title + ': ' + self.value_label.text())


# Presentation translations of existing service recommendations; no scoring logic.
ACTION_TEXT = {
    'THIN_CONTENT': 'محتوای صفحه را از نظر کامل‌بودن بررسی کنید؛ برای صفحات کاربردی، وضعیت ایندکس را بازبینی کنید.',
    'META_DESCRIPTION_TOO_SHORT': 'توضیحات متا را برای معرفی روشن‌تر محتوای صفحه بازبینی کنید.',
    'META_DESCRIPTION_MISSING': 'توضیحات متای منحصربه‌فرد و مرتبط با محتوای صفحه اضافه کنید.',
    'PAGE_TITLE_MISSING': 'یک عنوان توصیفی و منحصربه‌فرد برای صفحه اضافه کنید.',
    'EMPTY_CONTENT': 'استخراج‌نشدن متن را بررسی کنید؛ ممکن است صفحه خالی یا وابسته به JavaScript باشد.',
}


def action_text(record):
    return ACTION_TEXT.get(record.get('rule_id'), str(record.get('action', 'پیشنهاد موجود نیست')))


def data_time(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).strftime('%Y/%m/%d · %H:%M UTC')
    except (ValueError, AttributeError):
        return str(value or 'تاریخ نامشخص')


class Overview(QWidget):
    navigate = Signal(str)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        title_row = QHBoxLayout()
        heading = QVBoxLayout()
        heading.addWidget(label('نمای کلی', 'title'))
        self.subtitle = label('از شناخت سایت تا یک برنامه اقدام روشن و قابل پیگیری', 'muted')
        heading.addWidget(self.subtitle)
        title_row.addLayout(heading, 1)
        self.state_badge = label('آماده شروع')
        self.state_badge.setMargin(9)
        self.state_badge.setMaximumHeight(38)
        title_row.addWidget(self.state_badge)
        layout.addLayout(title_row)
        self.demo = label('Demo · داده نمونه برای بررسی طراحی؛ تحلیل واقعی سایت نیست')
        self.demo.setStyleSheet('color: #12647C; background: #D8F4F2; padding: 10px; border-radius: 8px;')
        self.demo.hide()
        layout.addWidget(self.demo)
        metrics = QHBoxLayout()
        self.metrics = {}
        for key, title, destination in [('pages', 'صفحات بررسی‌شده', 'audit'),
            ('critical', 'خطاهای بحرانی', 'audit'), ('opportunities', 'فرصت‌های شناسایی‌شده', 'opportunities'),
            ('actions', 'اقدام‌های پیشنهادی', 'roadmap')]:
            button = MetricButton(title)
            button.setToolTip('مشاهده جزئیات · ' + title)
            button.clicked.connect(lambda checked=False, dest=destination: self.navigate.emit(dest))
            self.metrics[key] = (button, title)
            metrics.addWidget(button, 1)
        layout.addLayout(metrics)
        frame, body = panel('وضعیت تحلیل و میزان پوشش')
        self.summary = label('')
        self.notice = label('', 'muted')
        body.addWidget(self.summary)
        body.addWidget(self.notice)
        self.next_button = QPushButton('افزودن اولین سایت')
        self.next_button.clicked.connect(lambda: self.navigate.emit('sites'))
        body.addWidget(self.next_button, alignment=Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
        layout.addWidget(frame)
        frame, self.actions_layout = panel('اقدام‌های پیشنهادی بعدی', 'برای هر پیشنهاد، دلیل و شواهد آن را بررسی کنید.')
        self.actions_frame = frame
        layout.addWidget(frame)
        bottom = QHBoxLayout()
        trend, body = panel('روند اجراها', 'مقایسه فقط برای اجراهای ذخیره‌شده همان سایت معتبر است.')
        self.trend = label('هنوز دو اجرای قابل مقایسه در این نما بارگذاری نشده است.', 'muted')
        body.addWidget(self.trend)
        button = QPushButton('تاریخچه و مقایسه اجراها')
        button.clicked.connect(lambda: self.navigate.emit('history'))
        body.addWidget(button)
        bottom.addWidget(trend, 1)
        method, body = panel('روش محاسبه و محدودیت‌ها')
        body.addWidget(label('امتیاز سلامت نمایش داده نمی‌شود؛ پوشش خزش، سلامت قطعی کل سایت را اثبات نمی‌کند. اولویت‌ها امتیاز داخلی‌اند و پیش‌بینی رتبه یا ترافیک نیستند.', 'muted'))
        self.provenance = label('هنوز نتیجه‌ای برای نمایش روش و زمان داده وجود ندارد.', 'muted')
        body.addWidget(self.provenance)
        bottom.addWidget(method, 1)
        layout.addLayout(bottom)
        layout.addStretch()
        self.present({})

    def set_state(self, state, message=''):
        self.state_badge.setText(STATUS_TEXT.get(state, STATUS_TEXT['unknown']))
        fg, bg = ('#166345', '#E9F6EF') if state == 'completed' else (
            ('#A82736', '#FDECEF') if state in ('error', 'failed') else
            ('#83530A', '#FFF4DB') if state in ('partial', 'cancelled') else ('#245D70', '#DDF2F3'))
        self.state_badge.setStyleSheet(f'color:{fg};background:{bg};border-radius:6px;')
        if message:
            self.summary.setText(message)

    def present(self, result, previous=None):
        meta = result.get('meta', {})
        available = bool(meta)
        self.strategy_method = result.get('strategy_method', '')
        self.provenance.setText(('شناسه اجرا: ' + str(meta.get('analysis_run_id', 'نامشخص')) + ' · نسخه الگوریتم: ' + str(meta.get('algorithm_version', 'نامشخص'))) if available else 'هنوز نتیجه‌ای برای نمایش روش و زمان داده وجود ندارد.')
        self.demo.setVisible(bool(meta.get('demo') or meta.get('sample_notice')))
        self.subtitle.setText(('\u2066' + str(meta.get('target_domain', '')) + '  |  ' + data_time(meta.get('generated_at')) + '\u2069') if available else 'برای شروع، سایت خود را ثبت و تنظیمات تحلیل را انتخاب کنید.')
        coverage = meta.get('coverage', {})
        actions = result.get('seo_roadmap', [])
        values = dict(pages=coverage.get('attempted'), critical=result.get('audit_summary', {}).get('severity_distribution', {}).get('Critical'),
                      opportunities=len(result['keyword_analysis']['opportunities']) if 'opportunities' in result.get('keyword_analysis', {}) else None,
                      actions=len(actions) if 'seo_roadmap' in result else None)
        for key, (button, title) in self.metrics.items():
            button.set_value(values[key])
        self.set_state(meta.get('pipeline_status', 'empty'))
        self.summary.setText((f"موفق: {coverage.get('saved', '—')} صفحه  ·  ناموفق: {coverage.get('failed', '—')}  ·  در انتظار: {coverage.get('queued_remaining', '—')}  ·  مستثنا در محدوده: {coverage.get('scope_excluded', '—')}") if available else 'هنوز تحلیلی انجام نشده است')
        self.notice.setText('نتایج به صفحات مشاهده‌شده محدودند. داده رقبا: ' + STATUS_TEXT.get(result.get('competitor_status'), 'نامشخص') if available else 'حداکثر پنج سایت خود را مدیریت کنید. برای شروع نیازی به واردکردن فهرست کلمات کلیدی ندارید.')
        if meta.get('pipeline_status') in ('partial', 'failed', 'cancelled'):
            self.notice.setText(self.notice.text() + '\nاین اجرا کامل نیست؛ وضعیت خطاها و محدوده خزش را در اجرای تحلیل بررسی کنید.')
        self.next_button.setText('مشاهده اجرای تحلیل' if available else 'افزودن اولین سایت')
        try:
            self.next_button.clicked.disconnect()
        except RuntimeError:
            pass
        self.next_button.clicked.connect(lambda: self.navigate.emit('run' if available else 'sites'))
        # Keep section title/description; replace previous action rows only.
        while self.actions_layout.count() > 2:
            item = self.actions_layout.takeAt(2)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        if not actions:
            self.actions_layout.addWidget(label('اقدامی برای نمایش موجود نیست؛ ابتدا تحلیل را اجرا کنید یا محدودیت داده‌ها را بررسی کنید.', 'muted'))
        for index, action in enumerate(actions[:3]):
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 4, 0, 4)
            kind = {'technical_review': 'بررسی و اصلاح فنی', 'content_review': 'بازبینی پوشش محتوا'}.get(action.get('action_type'), 'بررسی پیشنهاد')
            text = QVBoxLayout()
            text.addWidget(label(f"{index+1:02d}   {kind}"))
            text.addWidget(label(action_text(action), 'muted'))
            target = label(str(action.get('url') or action.get('keyword', 'هدف مشخص نشده')), 'muted')
            target.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            text.addWidget(target)
            line.addLayout(text, 1)
            button = QPushButton('چرا این اقدام؟')
            button.clicked.connect(lambda checked=False, record=action: self.show_evidence(record))
            line.addWidget(button)
            self.actions_layout.addWidget(row)
        if previous and meta.get('project_id') is not None and previous.get('meta', {}).get('project_id') == meta.get('project_id'):
            self.trend.setText(f"مشکلات مشاهده‌شده: {previous.get('audit_summary', {}).get('total_issues_found', '—')} ← {result.get('audit_summary', {}).get('total_issues_found', '—')}\nتفاوت پوشش دو اجرا می‌تواند روی این تغییر اثر بگذارد.")
        else:
            self.trend.setText('برای مقایسه، اجرای قبلی همین سایت را در تاریخچه انتخاب کنید؛ روند بدون داده ساخته نمی‌شود.')

    def show_evidence(self, record):
        dialog = QDialog(self)
        dialog.setWindowTitle('چرا این اقدام پیشنهاد شده؟')
        dialog.resize(620, 430)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label('دلیل و شواهد پیشنهاد', 'section'))
        layout.addWidget(label(action_text(record)))
        target = label(str(record.get('url') or record.get('keyword', 'هدف نامشخص')))
        target.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        layout.addWidget(target)
        evidence = record.get('evidence', {})
        labels = {'word_count': 'تعداد واژه استخراج‌شده', 'length': 'تعداد نویسه', 'title': 'عنوان ثبت‌شده', 'meta_description': 'توضیحات متا', 'urls': 'صفحات شاهد', 'domains': 'دامنه‌های شاهد'}
        for key, value in evidence.items():
            layout.addWidget(label(labels.get(key, key) + ': ' + str(value), 'muted'))
        layout.addWidget(label('امتیاز داخلی اولویت: ' + str(record.get('priority_score', 'نامشخص'))))
        known_method = self.strategy_method.startswith('Heuristic impact 1–4 / assumed effort 2 (technical) or 3 (content);')
        method = ('روش داخلی: اثر فرضی ۱ تا ۴ تقسیم بر تلاش فرضی (۲ برای فنی، ۳ برای محتوا). امتیاز تا ۲ است؛ عدد بالاتر یعنی اولویت بیشتر. این روش برآورد اثر تجاری نیست.' if known_method else self.strategy_method or 'روش امتیازدهی در این نتیجه ثبت نشده است.')
        layout.addWidget(label(method, 'muted'))
        layout.addWidget(label('اثر فرضی ثبت‌شده: ' + str(record.get('impact', 'نامشخص')) + ' · تلاش فرضی: ' + str(record.get('effort', 'نامشخص')), 'muted'))
        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setPlainText(json.dumps(record, ensure_ascii=False, indent=2))
        details.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        details.hide()
        toggle = QPushButton('نمایش رکورد اصلی سرویس')
        toggle.clicked.connect(lambda: details.setVisible(not details.isVisible()))
        layout.addWidget(toggle)
        layout.addWidget(details)
        button = QPushButton('بستن')
        button.clicked.connect(dialog.accept)
        layout.addWidget(button)
        dialog.exec()

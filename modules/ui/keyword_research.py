"""Desktop presentation for bounded keyword research and sourced imports."""
import json
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QPlainTextEdit,
    QLineEdit, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFileDialog, QMessageBox)
from modules.ui.overview import label, panel

LABELS = {'seed': 'عبارت پایه', 'prefix': 'پیشوند', 'suffix': 'پسوند',
          'prefix_suffix': 'پیشوند و پسوند', 'site_observed': 'مشاهده در سایت',
          'imported_suggestion': 'پیشنهاد واردشده'}


class KeywordResearch(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.result = None
        body = QVBoxLayout(self)
        body.addWidget(label('تحقیق عبارت‌های کلیدی', 'title'))
        body.addWidget(label('از یک یا چند عبارت پایه، ترکیب‌های قابل بررسی بسازید و در صورت دسترسی، عبارت‌های ثبت‌شده سایت یا فایل پیشنهادها را اضافه کنید.', 'muted'))
        frame, controls = panel('ورودی تحقیق', 'هر عبارت را در یک خط وارد کنید. حداکثر ۲۰ عبارت پایه و ۱۰ پیشوند و ۱۰ پسوند؛ مجموع نتایج حداکثر ۱۰۰۰ است.')
        form = QFormLayout()
        self.seeds, self.prefixes, self.suffixes = QPlainTextEdit(), QPlainTextEdit(), QPlainTextEdit()
        for edit, placeholder in ((self.seeds, 'طراحی سایت\nفروشگاه اینترنتی'),
                                  (self.prefixes, 'آموزش\nبهترین'), (self.suffixes, 'فروشگاهی\nبرای کسب و کار')):
            edit.setPlaceholderText(placeholder)
            edit.setMaximumHeight(48)
            option = edit.document().defaultTextOption()
            option.setTextDirection(Qt.LayoutDirection.RightToLeft)
            option.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
            edit.document().setDefaultTextOption(option)
            edit.textChanged.connect(self.invalidate)
        form.addRow('عبارت‌های پایه', self.seeds)
        form.addRow('پیشوندها (اختیاری)', self.prefixes)
        form.addRow('پسوندها (اختیاری)', self.suffixes)
        controls.addLayout(form)
        self.include_site = QCheckBox('افزودن عبارت‌های مشاهده‌شده در نتیجه باز سایت فعال')
        self.include_site.stateChanged.connect(self.invalidate)
        controls.addWidget(self.include_site)
        file_row = QHBoxLayout()
        self.path = QLineEdit()
        self.path.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.path.setPlaceholderText('فایل JSON پیشنهادهای منبع‌دار · اختیاری')
        self.path.textChanged.connect(self.invalidate)
        choose = QPushButton('انتخاب فایل پیشنهادها')
        choose.clicked.connect(self.choose_file)
        file_row.addWidget(self.path, 1)
        file_row.addWidget(choose)
        controls.addLayout(file_row)
        self.run_button = QPushButton('ساخت فهرست عبارات')
        self.run_button.setProperty('role', 'primary')
        self.run_button.clicked.connect(self.run_research)
        controls.addWidget(self.run_button)
        body.addWidget(frame)
        self.notice = label('Autocomplete آنلاین، حجم جست‌وجو و سختی کلمه در دسترس نیستند. فایل واردشده و ترکیب‌های ساخته‌شده، داده جست‌وجوی واقعی تأییدشده محسوب نمی‌شوند.', 'muted')
        body.addWidget(self.notice)
        self.message = label('برای شروع، عبارت پایه را وارد کنید.', 'muted')
        body.addWidget(self.message)
        self.search = QLineEdit()
        self.search.setPlaceholderText('جست‌وجو در عبارت‌ها، پایه‌ها و نوع نتیجه')
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(lambda: self.filter_rows(self.search.text()))
        self.search.textChanged.connect(lambda: self.search_timer.start())
        body.addWidget(self.search)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(['عبارت', 'عبارت پایه', 'نوع نتیجه', 'تعداد واژه'])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.show_details)
        self.table.setSortingEnabled(True)
        self.table.setMinimumHeight(140)
        body.addWidget(self.table, 1)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(70)
        self.details.setPlaceholderText('یک ردیف را انتخاب کنید تا منشأ و جزئیات آن نمایش داده شود.')
        body.addWidget(self.details)
        self.export_button = QPushButton('ذخیره Excel تحقیق')
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export)
        body.addWidget(self.export_button)

    def invalidate(self, *args):
        self.search_timer.stop()
        self.result = None
        self.table.setRowCount(0)
        self.details.clear()
        self.export_button.setEnabled(False)
        self.message.setText('ورودی تغییر کرد؛ برای مشاهده نتیجه تازه تحقیق را اجرا کنید.')

    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'پیشنهادهای منبع‌دار', '', 'JSON (*.json)')
        if path:
            self.path.setText(path)

    def run_research(self):
        from modules.keywords.research import research, load_suggestions
        try:
            data = self.window.last_result_data
            active = self.window.site_selector.currentData()
            site_run = data.get('meta', {}).get('analysis_run_id')
            if self.include_site.isChecked() and (not active or data.get('meta', {}).get('project_id') != active or not site_run):
                raise ValueError('ابتدا نتیجه تحلیل سایت فعال را باز کنید یا گزینه استفاده از سایت را بردارید.')
            suggestion_file = load_suggestions(self.path.text().strip()) if self.path.text().strip() else None
            result = research(self.seeds.toPlainText().splitlines(), self.prefixes.toPlainText().splitlines(),
                self.suffixes.toPlainText().splitlines(),
                site_keywords=data.get('keyword_inventory', []) if self.include_site.isChecked() else None,
                site_run_id=site_run if self.include_site.isChecked() else None, suggestions=suggestion_file)
        except (ValueError, OSError) as error:
            self.invalidate()
            self.message.setText('خطا: ' + str(error))
            return
        self.result = result
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(result['rows']))
        for row_index, row in enumerate(result['rows']):
            values = [row['phrase'], '، '.join(row['seeds']), '، '.join(LABELS[k] for k in row['types']), str(row['word_count'])]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.table.setItem(row_index, col, item)
        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)
        self.filter_rows(self.search.text())
        self.export_button.setEnabled(bool(result['rows']))
        self.message.setText(f"{len(result['rows'])} عبارت بدون تکرار · نسخه روش: {result['algorithm_version']} · جزئیات هر ردیف را انتخاب کنید."
                             + "\n" + "\n".join(result.get('warnings', [])))

    def filter_rows(self, query):
        self.search_timer.stop()
        from modules.ui.intelligence import EvidenceTable
        query = EvidenceTable.normalize(query)
        self.table.setUpdatesEnabled(False)
        try:
            for row in range(self.table.rowCount()):
                # Rows can be reordered by the native header; cache per phrase.
                item = self.table.item(row, 0)
                text = item.data(Qt.ItemDataRole.UserRole + 1)
                if text is None:
                    value = item.data(Qt.ItemDataRole.UserRole)
                    text = EvidenceTable.normalize(' '.join([value['phrase'], *value['seeds'],
                        *(LABELS[k] for k in value['types'])]))
                    # Cache on the item, leaving exported source rows untouched.
                    item.setData(Qt.ItemDataRole.UserRole + 1, text)
                cached = item.data(Qt.ItemDataRole.UserRole + 1) or text
                self.table.setRowHidden(row, query not in cached)
        finally:
            self.table.setUpdatesEnabled(True)

    def show_details(self):
        selected = self.table.selectedItems()
        if selected:
            self.details.setPlainText(json.dumps(selected[0].data(Qt.ItemDataRole.UserRole)['evidence'], ensure_ascii=False, indent=2))

    def export(self):
        if not self.result:
            return
        path, _ = QFileDialog.getSaveFileName(self, 'خروجی تحقیق کلمات', 'keyword_research.xlsx', 'Excel (*.xlsx)')
        if not path:
            return
        try:
            from modules.reporting.keyword_research_excel import export_keyword_research
            saved = export_keyword_research(path, self.result)
            self.message.setText('فایل تحقیق ذخیره شد: ' + saved)
        except (ValueError, OSError) as error:
            self.message.setText('خطا در ذخیره فایل: ' + str(error))
            QMessageBox.warning(self, 'خطای خروجی', str(error))

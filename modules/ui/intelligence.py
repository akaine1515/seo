"""Native searchable evidence tables and per-keyword strategy trees."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QPlainTextEdit, QComboBox, QListWidget,
    QListWidgetItem, QPushButton, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem)
from modules.ui.overview import label


class EvidenceTable(QWidget):
    def __init__(self, title, description, columns):
        super().__init__()
        self.columns, self.rows = columns, []
        body = QVBoxLayout(self)
        body.addWidget(label(title, 'title'))
        body.addWidget(label(description, 'muted'))
        self.search = QLineEdit()
        self.search.setPlaceholderText('جست‌وجو در داده‌ها…')
        self.search.textChanged.connect(self.filter_rows)
        body.addWidget(self.search)
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels([title for key, title in columns])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.details)
        self.table.setSortingEnabled(True)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText('یک ردیف را برای مشاهده منشأ، شواهد و جزئیات انتخاب کنید.')
        self.detail.setMaximumHeight(220)
        body.addWidget(self.table, 1)
        body.addWidget(self.detail)
        self.empty = label('داده‌ای بارگذاری نشده است؛ تحلیل را اجرا یا نتیجه ذخیره‌شده را باز کنید.', 'muted')
        body.addWidget(self.empty)

    def present(self, rows):
        self.rows = rows
        self.search.clear()
        self.detail.clear()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, (key, title) in enumerate(self.columns):
                value = row.get(key)
                text = json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value) if value is not None else '—'
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, row)
                self.table.setItem(i, j, item)
        self.table.setSortingEnabled(True)
        self.empty.setVisible(not rows)

    def filter_rows(self, text):
        for i in range(self.table.rowCount()):
            self.table.setRowHidden(i, not any(text.casefold() in self.table.item(i, j).text().casefold() for j in range(self.table.columnCount())))

    def details(self):
        items = self.table.selectedItems()
        if items:
            self.detail.setPlainText(json.dumps(items[0].data(Qt.ItemDataRole.UserRole), ensure_ascii=False, indent=2))


class CompetitorSelection(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window, self.candidates, self.choices = window, {}, {}
        self.updating = False
        self.project_id = None
        body = QVBoxLayout(self)
        body.addWidget(label('رقبای هر کلمه کلیدی', 'title'))
        body.addWidget(label('۱. نتیجه خزش سایت را باز کنید. ۲. SERP تاریخ‌دار وارد یا از نتایج همان اجرا استفاده کنید. ۳. برای هر کلمه صفر تا پنج رقیب ذخیره کنید. ۴. فقط مرحله رقبا را اجرا کنید؛ سایت شما دوباره خزش نمی‌شود.', 'muted'))
        import_button = QPushButton('انتخاب فایل نتایج SERP')
        import_button.clicked.connect(self.import_serp)
        body.addWidget(import_button)
        self.source = label('بدون منبع نتایج جست‌وجو، رقیبی ساخته نمی‌شود.', 'muted')
        body.addWidget(self.source)
        self.term = QComboBox()
        self.term.currentTextChanged.connect(self.populate)
        body.addWidget(self.term)
        self.list = QListWidget()
        self.list.itemChanged.connect(self.changed)
        body.addWidget(self.list)
        self.counter = label('۰ از ۵ رقیب')
        body.addWidget(self.counter)
        save = QPushButton('ذخیره انتخاب این کلمه')
        save.clicked.connect(self.save)
        body.addWidget(save)
        self.run_stage_btn = QPushButton('بررسی رقبا با خزش ذخیره‌شده')
        self.run_stage_btn.clicked.connect(self.run_stage)
        body.addWidget(self.run_stage_btn)
        body.addWidget(label('انتخاب‌های نمایش‌داده‌شده تنظیمات فعلی سایت هستند؛ نتایج هر بررسی در تاریخچه مستقل حفظ می‌شوند.', 'muted'))

    def present(self, result):
        from database.competitors import CompetitorChoiceRepository
        self.project_id = result.get('meta', {}).get('project_id')
        self.candidates = result.get('competitors_per_keyword', {})
        self.choices = CompetitorChoiceRepository.load(self.project_id) if self.project_id else {}
        source = result.get('serp', {})
        self.source.setText('منبع: ' + str(source.get('source') or 'داده در دسترس نیست') + ' · تاریخ: \u2066' + str(source.get('retrieved_at') or '—') + '\u2069')
        self.term.clear()
        self.term.addItems(list(self.candidates))
        self.populate()

    def import_serp(self):
        path, _ = QFileDialog.getOpenFileName(self, 'نتایج SERP مجاز', '', 'JSON (*.json)')
        if not path:
            return
        try:
            result = self.window.orchestrator.preview_serp(path, self.window.url_input.text(), self.window.site_selector.currentData())
            self.window.serp_path_input.setText(path)
            self.present(result)
        except Exception as error:
            QMessageBox.warning(self, 'ورود نتایج', str(error))

    def populate(self):
        self.updating = True
        self.list.clear()
        term = self.term.currentText()
        for row in self.candidates.get(term, []):
            item = QListWidgetItem(f"{row['domain']}  ·  رتبه ثبت‌شده: {row['position']}\n{row['url']}")
            item.setData(Qt.ItemDataRole.UserRole, row['domain'])
            item.setCheckState(Qt.CheckState.Checked if row['domain'] in self.choices.get(term, []) else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        self.updating = False
        self.update_count()

    def selected(self):
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count()) if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def update_count(self):
        self.counter.setText(f'{len(self.selected())} از ۵ رقیب · برای ذخیره روی دکمه پایین کلیک کنید.')

    def changed(self, item):
        if self.updating:
            return
        if len(self.selected()) > 5:
            self.updating = True
            item.setCheckState(Qt.CheckState.Unchecked)
            self.updating = False
            self.counter.setText('حداکثر پنج رقیب برای هر کلمه مجاز است.')
        else:
            self.update_count()

    def save(self):
        if self.window.worker and self.window.worker.isRunning():
            QMessageBox.information(self, 'تحلیل در حال اجراست', 'پس از پایان تحلیل، انتخاب رقبا را تغییر دهید.')
            return False
        if self.project_id != self.window.site_selector.currentData():
            QMessageBox.warning(self, 'سایت فعال تغییر کرده', 'نتایج مربوط به سایت فعال را بارگذاری کنید.')
            return False
        if not getattr(self, 'project_id', None) or not self.term.currentText():
            QMessageBox.warning(self, 'انتخاب سایت', 'ابتدا سایت را ثبت و نتایج SERP را بارگذاری کنید.')
            return False
        from database.competitors import CompetitorChoiceRepository
        term = self.term.currentText()
        try:
            CompetitorChoiceRepository.save(self.project_id, {term: self.selected()}, self.candidates)
            self.choices[term] = self.selected()
            self.counter.setText('انتخاب ذخیره شد؛ برای مقایسه، مرحله رقبا را اجرا کنید.')
            return True
        except Exception as error:
            QMessageBox.warning(self, 'ذخیره رقبا', str(error))
            return False

    def run_stage(self):
        if self.term.currentText() and not self.save():
            return
        self.window.start_competitor_stage()


class StrategyMap(QWidget):
    def __init__(self):
        super().__init__()
        self.maps = []
        body = QVBoxLayout(self)
        body.addWidget(label('استراتژی و مایندمپ هر کلمه', 'title'))
        body.addWidget(label('ساختار قابل باز و بسته‌شدن بر پایه داده سایت و صفحات منتخب رقبا. الگوی عمومی رقیب، الگوریتم پنهان او نیست. پیشنهادها به بازبینی انسانی نیاز دارند.', 'muted'))
        self.term = QComboBox()
        self.term.setEditable(True)
        self.term.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.term.currentIndexChanged.connect(self.render)
        body.addWidget(self.term)
        self.status = label('ابتدا تحلیل را اجرا کنید.', 'muted')
        body.addWidget(self.status)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(['موضوع / اقدام', 'صفحه منبع'])
        body.addWidget(self.tree, 1)

    def present(self, result):
        self.maps = result.get('keyword_mindmaps', [])
        self.plans = result.get('keyword_strategies', [])
        self.term.clear()
        self.term.addItems([m['label'] for m in self.maps])
        self.render()

    def render(self):
        self.tree.clear()
        index = self.term.currentIndex()
        if not 0 <= index < len(self.maps):
            self.status.setText('نتیجه استراتژی موجود نیست؛ تحلیل جدید اجرا کنید.')
            return
        plan = self.plans[index]
        statuses = {'observed': 'صفحات منتخب بررسی شدند', 'partial': 'داده ناقص', 'unavailable': 'SERP موجود نیست', 'awaiting_selection': 'در انتظار انتخاب رقیب'}
        self.status.setText('وضعیت مقایسه: ' + statuses.get(plan['competitor_status'], plan['competitor_status']) + ' · روش: ' + plan['method_version'])
        def add(node, parent):
            item = QTreeWidgetItem(parent, [node['label'], ('\u2066' + node['url'] + '\u2069') if node.get('url') else ''])
            for child in node.get('children', []):
                add(child, item)
        add(self.maps[index], self.tree)
        self.tree.expandToDepth(1)
        self.tree.header().resizeSection(0, 660)

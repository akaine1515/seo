"""Native searchable evidence tables and per-keyword strategy trees."""
import json
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QPlainTextEdit, QComboBox, QListWidget,
    QListWidgetItem, QPushButton, QFileDialog, QMessageBox, QTreeWidget, QTreeWidgetItem)
from modules.ui.overview import label


class EvidenceTable(QWidget):
    """Cached search, global sort and bounded native table rendering."""
    PAGE_SIZE = 100

    def __init__(self, title, description, columns, filter_key=None):
        super().__init__()
        self.columns, self.rows, self.matches = columns, [], []
        self.page_number, self.sort_column, self.descending = 0, None, False
        self.filter_key = filter_key
        body = QVBoxLayout(self)
        body.addWidget(label(title, 'title'))
        self.notice = label(description, 'muted')
        body.addWidget(self.notice)
        from modules.ui.charts import BarChart
        self.chart = BarChart('')
        self.chart.hide()
        body.addWidget(self.chart)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText('جست‌وجو در تمام نتایج…')
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(150)
        self.search_timer.timeout.connect(lambda: self.filter_rows(self.search.text()))
        self.search.textChanged.connect(lambda: self.search_timer.start())
        filters.addWidget(self.search, 1)
        self.kind = QComboBox()
        self.kind.addItem('همه', None)
        self.kind.currentIndexChanged.connect(lambda: self.filter_rows(self.search.text()))
        self.kind.setVisible(bool(filter_key))
        filters.addWidget(self.kind)
        body.addLayout(filters)
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels([title for key, title in columns])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_by)
        self.table.itemSelectionChanged.connect(self.details)
        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        option = self.detail.document().defaultTextOption()
        option.setTextDirection(Qt.LayoutDirection.RightToLeft)
        option.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignAbsolute)
        self.detail.document().setDefaultTextOption(option)
        self.detail.setPlaceholderText('یک ردیف را برای مشاهده منشأ، شواهد و اقدام بعدی انتخاب کنید.')
        self.detail.setMaximumHeight(150)
        body.addWidget(self.table, 1)
        paging = QHBoxLayout()
        self.previous = QPushButton('صفحه قبل')
        self.following = QPushButton('صفحه بعد')
        self.previous.clicked.connect(lambda: self.move_page(-1))
        self.following.clicked.connect(lambda: self.move_page(1))
        self.count = label('')
        for widget in (self.previous, self.count, self.following):
            paging.addWidget(widget)
        body.addLayout(paging)
        body.addWidget(self.detail)
        self.empty = label('داده‌ای بارگذاری نشده است؛ تحلیل را اجرا یا نتیجه ذخیره‌شده را باز کنید.', 'muted')
        body.addWidget(self.empty)
        self.present([])

    @staticmethod
    def display(value):
        if value is None:
            return '—'
        if isinstance(value, float):
            return format(value, '.6g')
        return json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else str(value)

    @staticmethod
    def normalize(text):
        return ' '.join(text.casefold().replace('ك', 'ک').replace('ي', 'ی').replace('ى', 'ی').split())

    def present(self, rows):
        self.search_timer.stop()
        self.rows = list(rows)
        self._texts = [self.normalize(' '.join(self.display(row.get(key)) for key, _ in self.columns)) for row in self.rows]
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.kind.blockSignals(True)
        self.kind.clear()
        self.kind.addItem('همه', None)
        if self.filter_key:
            for value in sorted({str(row[self.filter_key]) for row in self.rows if row.get(self.filter_key) is not None}):
                self.kind.addItem(value, value)
        self.kind.blockSignals(False)
        self.filter_rows('')

    def filter_rows(self, text):
        self.search_timer.stop()
        query, kind = self.normalize(text), self.kind.currentData()
        self.matches = [i for i, row in enumerate(self.rows) if query in self._texts[i]
                        and (kind is None or str(row.get(self.filter_key)) == kind)]
        self.page_number = 0
        self.apply_sort()

    def sort_by(self, column):
        self.descending = not self.descending if self.sort_column == column else False
        self.sort_column = column
        self.page_number = 0
        self.apply_sort()

    def apply_sort(self):
        if self.sort_column is not None:
            key = self.columns[self.sort_column][0]
            def order(index):
                value = self.rows[index].get(key)
                if value is None:
                    return (2, '')
                if isinstance(value, (int, float)):
                    return (0, value)
                return (1, self.normalize(self.display(value)))
            self.matches.sort(key=order, reverse=self.descending)
            self.table.horizontalHeader().setSortIndicatorShown(True)
            self.table.horizontalHeader().setSortIndicator(self.sort_column,
                Qt.SortOrder.DescendingOrder if self.descending else Qt.SortOrder.AscendingOrder)
        self.render_page()

    def move_page(self, delta):
        self.page_number = max(0, min(self.page_number + delta, max(0, (len(self.matches)-1)//self.PAGE_SIZE)))
        self.render_page()

    def render_page(self):
        start = self.page_number * self.PAGE_SIZE
        indices = self.matches[start:start+self.PAGE_SIZE]
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.detail.clear()
            self.table.clearSelection()
            self.table.setRowCount(len(indices))
            for i, index in enumerate(indices):
                row = self.rows[index]
                for j, (key, _) in enumerate(self.columns):
                    # Long lists/objects live in details; paint at most 100 rows.
                    text = self.display(row.get(key))
                    item = QTableWidgetItem(text[:350] + ('…' if len(text) > 350 else ''))
                    item.setData(Qt.ItemDataRole.UserRole, index)
                    self.table.setItem(i, j, item)
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)
        self.previous.setEnabled(start > 0)
        self.following.setEnabled(start + self.PAGE_SIZE < len(self.matches))
        self.count.setText(f'{start+1 if indices else 0}–{start+len(indices)} از {len(self.matches)} · کل {len(self.rows)}')
        self.empty.setVisible(not indices)
        self.empty.setText('نتیجه‌ای با این فیلتر پیدا نشد.' if self.rows else 'داده‌ای موجود نیست؛ تحلیل را اجرا یا نتیجه ذخیره‌شده همین سایت را باز کنید.')

    def details(self):
        items = self.table.selectedItems()
        if items:
            row = self.rows[items[0].data(Qt.ItemDataRole.UserRole)]
            names = dict(self.columns)
            names.update(evidence='شواهد', recommendation='اقدام پیشنهادی', source_pages='صفحات منبع',
                score_method='روش امتیازدهی', limitation='محدودیت', evidence_urls='نشانی شواهد',
                source='منبع', retrieved_at='تاریخ منبع', algorithm_version='نسخه الگوریتم',
                analysis_run_id='شناسه اجرا', action='اقدام بعدی', total_frequency='مجموع فراوانی',
                intent='نیت احتمالی', total_score='مجموع وزن داخلی', impact='اثر فرضی', effort='تلاش فرضی',
                depends_on='وابستگی‌ها', horizon='بازه پیشنهادی')
            priority = ['term', 'keyword', 'title', 'url', 'recommendation', 'action',
                        'score_method', 'source_pages', 'evidence_urls', 'evidence']
            keys = list(dict.fromkeys([*(k for k in priority if k in row), *row]))
            self.detail.setPlainText('\n\n'.join(names.get(k, k) + ': ' + self.display(row[k]) for k in keys))

    def show_chart(self, title, values, unit='تعداد'):
        self.chart.title, self.chart.unit = title, unit
        self.chart.present(values)
        self.chart.show()


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

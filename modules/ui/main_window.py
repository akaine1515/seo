from typing import Dict, Any
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QInputDialog, QTableWidgetItem,
)
from modules.ui.worker import SEOAnalysisWorker
from modules.reporting.excel_reporter import ExcelReportGenerator
from modules.reporting.html_reporter import HTMLReportGenerator


class MainWindow(QMainWindow):
    """Persian desktop presentation backed by application services."""

    def __init__(self, orchestrator_engine: Any = None):
        super().__init__()
        self.orchestrator = orchestrator_engine
        self.worker = None
        self.last_result_data = {}

        from modules.ui.design_system import STYLES, ui_font
        from modules.ui.shell import build_shell
        self.setWindowTitle("SEO Intelligence V2 | Product by Ashkan")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setFont(ui_font())
        self.resize(1440, 980)
        self.setMinimumSize(980, 700)
        self.setStyleSheet(STYLES)
        build_shell(self)
        self.refresh_sites()

    def navigate(self, destination):
        self.switch_tab(self.page_indices[destination])

    def switch_tab(self, index: int):
        self.tabs.setCurrentIndex(index)
        self.breadcrumb.setText('فضای کاری  /  ' + self.tabs.tabText(index))
        for btn in self.nav_buttons:
            btn.setChecked(btn.property('page_index') == index)

    def toggle_sidebar(self):
        self._sidebar_compact = not self._sidebar_compact
        self.sidebar.setFixedWidth(112 if self._sidebar_compact else 224)
        self.brand_label.setText('SEO V2' if self._sidebar_compact else 'SEO Intelligence')
        self.brand_subtitle.setVisible(not self._sidebar_compact)
        self.collapse_btn.setText('‹' if self._sidebar_compact else 'جمع کردن منو  ›')
        for btn in self.nav_buttons:
            full = btn.property('full_text')
            btn.setText(btn.fontMetrics().elidedText(full, Qt.TextElideMode.ElideRight, 55)
                        if self._sidebar_compact else full)

    def log_message(self, message: str):
        from html import escape
        self.log_output.append(escape(message))

    def refresh_sites(self):
        from database.connection import initialize_database
        from database.sites import SiteRepository
        try:
            initialize_database()
            self._sites = {s['id']: s for s in SiteRepository.list_sites()}
            self.site_selector.blockSignals(True)
            self.site_selector.clear()
            self.site_selector.addItem("انتخاب یا ثبت سایت", None)
            for site in self._sites.values():
                self.site_selector.addItem(site['name'] + (" (غیرفعال)" if not site['is_active'] else ""), site['id'])
            self.site_selector.blockSignals(False)
        except Exception as error:
            self.log_message(f"Site list unavailable: {error}")

    def select_site(self):
        site = self._sites.get(self.site_selector.currentData())
        if site is None:
            self.url_input.clear()
            self.site_status_label.setText('سایتی انتخاب نشده است')
            self.clear_result_view()
            return
        if self.last_result_data.get('meta', {}).get('project_id') != site['id']:
            self.clear_result_view()
        self.url_input.setText(site['website_url'])
        from database.sites import SiteRepository
        status = SiteRepository.status(site['id'])
        self.site_status_label.setText(site['name'] + '  ·  ' + ('فعال' if site['is_active'] else 'غیرفعال') + '  ·  ' + self.status_text(status))
        settings = site['settings']
        self.max_pages_input.setValue(settings['max_pages'])
        self.max_depth_input.setValue(settings['max_depth'])
        self.timeout_input.setValue(settings['timeout'])
        self.interval_input.setValue(settings['request_interval'])
        self.excluded_input.setText(','.join(settings['excluded_paths']))

    def clear_result_view(self):
        self.last_result_data = {}
        self.stage_banner.hide()
        self.site_evidence.present([])
        self.keyword_evidence.present([])
        self.competitor_selection.present({})
        self.strategy_map.present({})
        self.overview_widget.present({})
        self.export_excel_btn.setEnabled(False)
        self.export_html_btn.setEnabled(False)
        self.run_message.setText('آماده شروع؛ تنظیمات سایت فعال را بررسی کنید.')
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.log_output.clear()
        for table in (self.technical_table, self.keywords_table, self.competitors_table):
            table.setRowCount(0)

    def crawl_settings(self):
        return dict(max_pages=self.max_pages_input.value(), max_depth=self.max_depth_input.value(),
                    timeout=self.timeout_input.value(), request_interval=self.interval_input.value(),
                    excluded_paths=[p.strip() for p in self.excluded_input.text().split(',') if p.strip()])

    def change_site(self, operation):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "تحلیل در حال اجراست", "پس از پایان تحلیل می‌توانید سایت را تغییر دهید.")
            return
        try:
            project_id = operation()
            self.site_error_label.hide()
            self.refresh_sites()
            index = self.site_selector.findData(project_id)
            self.site_selector.setCurrentIndex(max(index, 0))
        except Exception as error:
            messages = {
                'Invalid site HTTP URL': 'نشانی معتبر نیست؛ نمونه: https://example.com',
                'Site name and URL are required': 'نام و نشانی سایت را وارد کنید.',
                'Site name is required': 'نام سایت را وارد کنید.',
                'This site is already registered': 'این دامنه قبلاً ثبت شده است؛ آن را از نوار بالا انتخاب کنید.',
                'The workspace supports at most five sites, including inactive sites': 'حداکثر پنج سایت قابل ثبت است؛ سایت‌های غیرفعال نیز محاسبه می‌شوند.',
            }
            message = messages.get(str(error), 'تغییرات ذخیره نشد؛ جزئیات خطا را در گزارش عملیات بررسی کنید.')
            self.site_error_label.setText(message)
            self.site_error_label.show()
            self.log_message(str(error))
            QMessageBox.warning(self, "تنظیمات سایت", message)

    def register_site(self):
        from database.sites import SiteRepository
        name, accepted = QInputDialog.getText(self, "ثبت سایت", "نام سایت:")
        if accepted:
            self.change_site(lambda: SiteRepository.register(name, self.url_input.text()))

    def rename_site(self):
        from database.sites import SiteRepository
        project_id = self.site_selector.currentData()
        if project_id is None:
            return
        name, accepted = QInputDialog.getText(self, "تغییر نام سایت", "نام سایت:")
        if accepted:
            def rename():
                SiteRepository.configure(project_id, name=name)
                return project_id
            self.change_site(rename)

    def toggle_site(self):
        from database.sites import SiteRepository
        project_id = self.site_selector.currentData()
        if project_id is not None:
            def toggle():
                SiteRepository.configure(project_id, active=not self._sites[project_id]['is_active'])
                return project_id
            self.change_site(toggle)

    def delete_site(self):
        from database.repository import ProjectRepository
        project_id = self.site_selector.currentData()
        if project_id is not None and QMessageBox.question(self, "حذف سایت",
                "این سایت و همه تاریخچه تحلیل آن حذف شود؟") == QMessageBox.StandardButton.Yes:
            def delete():
                ProjectRepository.delete_project(project_id)
            self.change_site(delete)

    def save_site_settings(self):
        from database.sites import SiteRepository
        project_id = self.site_selector.currentData()
        if project_id is not None:
            def save():
                SiteRepository.configure(project_id, settings=self.crawl_settings())
                return project_id
            self.change_site(save)

    def stop_analysis(self):
        if self.worker and self.worker.isRunning():
            if QMessageBox.question(self, 'توقف تحلیل',
                    'تحلیل متوقف شود؟ داده‌های ثبت‌شده حفظ می‌شوند؛ نتیجه کامل نخواهد بود.') != QMessageBox.StandardButton.Yes:
                return
            self.worker.cancel()
            self.stop_btn.setEnabled(False)
            self.log_message("درخواست توقف ثبت شد؛ منتظر پایان عملیات جاری هستیم.")

    def worker_finished(self):
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.site_selector.setEnabled(True)
        if self.site_selector.currentData() is not None:
            from database.sites import SiteRepository
            self.site_status_label.setText(self.site_selector.currentText() + '  ·  ' + self.status_text(SiteRepository.status(self.site_selector.currentData())))

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "تحلیل در حال اجراست", "برای بستن برنامه، ابتدا تحلیل را متوقف کنید و منتظر پایان عملیات جاری بمانید.")
            event.ignore()
            return
        event.accept()

    def open_saved_run(self):
        if self.worker and self.worker.isRunning():
            return
        run_id, accepted = QInputDialog.getInt(self, "تاریخچه", "شناسه اجرا:", 1, 1)
        if not accepted:
            return
        try:
            from database.connection import initialize_database
            initialize_database()
            result = self.orchestrator.load_result(run_id)
            if result is None:
                raise ValueError("نتیجه ذخیره‌شده‌ای برای این شناسه اجرا وجود ندارد.")
            self.on_analysis_finished(result)
        except Exception as error:
            QMessageBox.warning(self, "تاریخچه", str(error))

    def compare_saved_run(self):
        if self.last_result_data.get('meta', {}).get('stage_result_id'):
            QMessageBox.information(self, 'مقایسه خزش‌ها', 'این نتیجه، بررسی مستقل رقباست. برای مقایسه وضعیت سایت، دو اجرای کامل خزش را از تاریخچه باز کنید.')
            return
        current = self.last_result_data.get('meta', {}).get('analysis_run_id')
        if not current:
            return
        run_id, accepted = QInputDialog.getInt(self, "مقایسه اجرا", "شناسه اجرای قبلی:", 1, 1)
        if not accepted:
            return
        try:
            import json
            from database.results import AnalysisResultRepository
            comparison = AnalysisResultRepository.compare(run_id, current)
            previous = AnalysisResultRepository.load(run_id)
            self.overview_widget.present(self.last_result_data, previous)
            self.log_message(json.dumps(comparison, ensure_ascii=False, indent=2))
            self.switch_tab(4)
        except Exception as error:
            QMessageBox.warning(self, "مقایسه", str(error))

    def open_competitor_history(self):
        if self.worker and self.worker.isRunning():
            return
        project_id = self.site_selector.currentData()
        if not project_id:
            return
        try:
            from database.stages import StageResultRepository
            rows = StageResultRepository.list_for_project(project_id)
            if not rows:
                QMessageBox.information(self, 'تاریخچه رقبا', 'هنوز بررسی مستقلی برای این سایت ذخیره نشده است.')
                return
            from modules.ui.overview import data_time
            choices = [f"#{r['id']} · خزش منبع {r['source_analysis_run_id']} · {self.status_text(r['status'])} · \u2066{data_time(r['started_at'])}\u2069" for r in rows]
            selected, accepted = QInputDialog.getItem(self, 'تاریخچه مستقل رقبا', 'بررسی موردنظر:', choices, 0, False)
            if accepted:
                result = StageResultRepository.load(rows[choices.index(selected)]['id'])
                if result is None:
                    raise ValueError('این بررسی نتیجه قابل نمایش ندارد؛ وضعیت شکست یا اجرای ناتمام در تاریخچه ثبت شده است.')
                self.on_analysis_finished(result)
        except Exception as error:
            QMessageBox.warning(self, 'تاریخچه رقبا', str(error))

    def start_competitor_stage(self):
        if self.worker and self.worker.isRunning():
            return
        meta = self.last_result_data.get('meta', {})
        project_id = self.site_selector.currentData()
        if not meta.get('analysis_run_id') or meta.get('project_id') != project_id:
            QMessageBox.warning(self, 'خزش منبع لازم است', 'ابتدا نتیجه ذخیره‌شده همین سایت را از تاریخچه باز کنید یا تحلیل سایت را اجرا کنید.')
            return
        try:
            from modules.serp.google_search import FileSERPProvider
            path = self.serp_path_input.text().strip()
            self.orchestrator.serp_provider = FileSERPProvider(path) if path else None
        except (ValueError, OSError) as error:
            QMessageBox.warning(self, 'منبع SERP', str(error))
            return
        self.worker = SEOAnalysisWorker(self.url_input.text(), {'project_id': project_id},
                                       self.orchestrator, source_run_id=meta['analysis_run_id'])
        self.worker.finished.connect(self.worker_finished)
        self.worker.progress_updated.connect(self.on_progress_update)
        self.worker.analysis_finished.connect(self.on_analysis_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.site_selector.setEnabled(False)
        self.export_excel_btn.setEnabled(False)
        self.export_html_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.overview_widget.set_state('running', 'بررسی صفحات منتخب رقبا با داده ذخیره‌شده سایت؛ خزش سایت تکرار نمی‌شود.')
        self.navigate('run')
        self.worker.start()

    def start_analysis(self):
        if self.worker and self.worker.isRunning():
            return
        url = self.url_input.text().strip()
        if not url:
            self.navigate('sites')
            self.url_input.setFocus()
            QMessageBox.warning(self, "نشانی سایت لازم است", "ابتدا در صفحه وب‌سایت‌ها نشانی سایت را وارد یا سایت ثبت‌شده را انتخاب کنید.")
            return

        self.run_btn.setEnabled(False)
        self.export_excel_btn.setEnabled(False)
        self.export_html_btn.setEnabled(False)
        self.log_output.clear()
        self.progress_bar.setRange(0, 0)
        self.overview_widget.set_state("running", "در حال آماده‌سازی تحلیل؛ نتیجه قبلی متعلق به اجرای پیشین است.")
        self.navigate("run")

        from modules.serp.google_search import FileSERPProvider
        try:
            path = self.serp_path_input.text().strip()
            self.orchestrator.serp_provider = FileSERPProvider(path) if path else None
        except (ValueError, OSError) as error:
            self.on_error(str(error))
            return
        options = {**self.crawl_settings(),
                   "selected_competitors": [domain.strip() for domain in
                       self.selected_competitors_input.text().split(",") if domain.strip()]}
        project_id = self.site_selector.currentData()
        if project_id is not None and url == self._sites[project_id]['website_url']:
            options['project_id'] = project_id
        self.worker = SEOAnalysisWorker(url, options, self.orchestrator)
        self.worker.finished.connect(self.worker_finished)
        self.stop_btn.setEnabled(True)
        self.site_selector.setEnabled(False)
        self.site_status_label.setText("تحلیل در حال اجراست")
        self.worker.progress_updated.connect(self.on_progress_update)
        self.worker.analysis_finished.connect(self.on_analysis_finished)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()

    def on_progress_update(self, message: str, progress: int):
        self.run_message.setText("در حال پردازش؛ جزئیات مرحله در گزارش عملیات ثبت می‌شود.")
        self.log_message(message)

    def on_analysis_finished(self, result_data: Dict[str, Any]):
        self.last_result_data = result_data
        self.refresh_sites()
        project_index = self.site_selector.findData(result_data.get('meta', {}).get('project_id'))
        if project_index >= 0:
            self.site_selector.setCurrentIndex(project_index)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.run_btn.setEnabled(not (self.worker and self.worker.isRunning()))
        self.export_excel_btn.setEnabled(True)
        self.export_html_btn.setEnabled(True)

        for warning in result_data.get("meta", {}).get("warnings", []):
            self.log_message(warning)
        self.site_evidence.present(result_data.get('page_details', []))
        self.keyword_evidence.present(result_data.get('keyword_inventory', []))
        self.competitor_selection.present(result_data)
        self.strategy_map.present(result_data)
        self.overview_widget.present(result_data)
        meta = result_data.get('meta', {})
        self.stage_banner.setVisible(bool(meta.get('stage_result_id')))
        from modules.ui.overview import data_time
        self.stage_banner.setText(f"بررسی مستقل رقبا #{meta.get('stage_result_id')} · خزش منبع #{meta.get('analysis_run_id')} (\u2066{data_time(meta.get('finished_at'))}\u2069) · وضعیت مرحله: {self.status_text(meta.get('stage_status', 'unknown'))} · سایت دوباره خزش نشده است.")
        status = self.status_text(result_data.get('meta', {}).get('pipeline_status', 'unknown'))
        self.run_message.setText('نتیجه ذخیره شد · ' + status + '؛ میزان پوشش را در نمای کلی بررسی کنید.')
        self.site_status_label.setText(self.site_selector.currentText() + '  ·  ' + status)

        # به‌روزرسانی جدول ممیزی فنی
        audit = result_data.get("audit_summary", {})
        issues = audit.get("issues", [])
        self.technical_table.setRowCount(len(issues))
        for row, iss in enumerate(issues):
            self.technical_table.setItem(row, 0, QTableWidgetItem(str(iss.get("rule_id", ""))))
            self.technical_table.setItem(row, 1, QTableWidgetItem(str(iss.get("severity", ""))))
            self.technical_table.setItem(row, 2, QTableWidgetItem(str(iss.get("category", ""))))
            self.technical_table.setItem(row, 3, QTableWidgetItem(str(iss.get("title", ""))))
            self.technical_table.setItem(row, 4, QTableWidgetItem(str(iss.get("url", ""))))
            self.technical_table.setItem(row, 5, QTableWidgetItem(str(iss.get("recommendation", ""))))

        # به‌روزرسانی جدول کلمات کلیدی
        kw_data = result_data.get("keyword_analysis", {}).get("keywords", [])
        self.keywords_table.setRowCount(len(kw_data))
        for row, kw in enumerate(kw_data):
            self.keywords_table.setItem(row, 0, QTableWidgetItem(str(kw.get("term", ""))))
            self.keywords_table.setItem(row, 1, QTableWidgetItem(str(kw.get("frequency", ""))))
            self.keywords_table.setItem(row, 2, QTableWidgetItem(str(kw.get("tfidf", ""))))
            self.keywords_table.setItem(row, 3, QTableWidgetItem(str(kw.get("cluster", ""))))

        # به‌روزرسانی جدول رقبا
        comps = result_data.get("project_competitors", [])
        self.competitors_table.setRowCount(len(comps))
        for row, comp in enumerate(comps):
            self.competitors_table.setItem(row, 0, QTableWidgetItem(str(comp.get("domain", ""))))
            self.competitors_table.setItem(row, 1, QTableWidgetItem(str(comp.get("competitiveness_score", ""))))
            self.competitors_table.setItem(row, 2, QTableWidgetItem(str(comp.get("keywords_count", ""))))
            self.competitors_table.setItem(row, 3, QTableWidgetItem(result_data.get("content_gap_analysis", {}).get("status", "unavailable")))

        self.statusBar().showMessage('نتیجه ذخیره شد · ' + status, 8000)
        self.navigate('overview')

    @staticmethod
    def status_text(status):
        from modules.ui.design_system import STATUS_TEXT
        state = status.get('state', 'unknown') if isinstance(status, dict) else status
        return STATUS_TEXT.get(state, str(state))

    def on_error(self, error_msg: str):
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.overview_widget.set_state("error", "تحلیل ناموفق بود؛ پیام خطا و تنظیمات اتصال را بررسی کنید. اعداد موجود متعلق به نتیجه قبلی‌اند.")
        self.run_message.setText("خطا در تحلیل: " + error_msg)
        self.site_status_label.setText("خطا در اجرای تحلیل")
        self.log_message(f"ERROR: {error_msg}")
        self.run_btn.setEnabled(not (self.worker and self.worker.isRunning()))
        QMessageBox.critical(self, "خطای اجرا", f"تحلیل انجام نشد. جزئیات خطا:\n{error_msg}")

    def export_excel(self):
        if not self.last_result_data:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "ذخیره گزارش Excel", "seo_audit_report.xlsx", "Excel Files (*.xlsx)")
        if file_path:
            try:
                reporter = ExcelReportGenerator()
                saved_path = reporter.generate_report(file_path, self.last_result_data)
                QMessageBox.information(self, "گزارش ذخیره شد", f"مسیر گزارش Excel:\n{saved_path}")
            except Exception as e:
                QMessageBox.critical(self, "خطای ساخت گزارش", str(e))

    def export_html(self):
        if not self.last_result_data:
            return
        file_path, _ = QFileDialog.getSaveFileName(self, "ذخیره گزارش HTML", "seo_dashboard.html", "HTML Files (*.html)")
        if file_path:
            try:
                saved_path = HTMLReportGenerator.generate_report(file_path, self.last_result_data)
                QMessageBox.information(self, "گزارش ذخیره شد", f"مسیر گزارش HTML:\n{saved_path}")
            except Exception as e:
                QMessageBox.critical(self, "خطای ساخت گزارش", str(e))

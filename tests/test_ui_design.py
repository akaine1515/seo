"""Desktop presentation acceptance with controlled SQLite and HTTP fixtures."""
import os
import sys
import unittest
from unittest.mock import patch, Mock
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
from tests import test_pipeline as fixtures
from modules.ui.main_window import MainWindow
from modules.ui.design_system import CREDIT
from database.sites import SiteRepository
from core.engine import SEOOrchestrator


class UIDesignTests(unittest.TestCase):
    def setUp(self):
        fixtures.PipelineTests.setUp(self)
        self.app = QApplication.instance() or QApplication([])
        # Qt forwards Python slot errors to excepthook without failing unittest.
        self.slot_errors = []
        hook = patch.object(sys, 'excepthook', lambda *args: self.slot_errors.append(args))
        hook.start()
        self.addCleanup(hook.stop)
        self.window = MainWindow(SEOOrchestrator())
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.window.close)

    def tearDown(self):
        self.assertEqual(self.slot_errors, [], 'Unexpected exception in a Qt slot')

    def result(self):
        return self.window.orchestrator.run_full_pipeline('https://example.com',
                    {'max_pages': 1, 'request_interval': 0})

    def test_rtl_sidebar_brand_and_compact_navigation(self):
        w = self.window
        self.assertEqual(w.layoutDirection(), Qt.LayoutDirection.RightToLeft)
        sidebar_x = w.sidebar.mapTo(w.centralWidget(), w.sidebar.rect().topLeft()).x()
        content_x = w.tabs.mapTo(w.centralWidget(), w.tabs.rect().topLeft()).x()
        self.assertGreater(sidebar_x, content_x + w.tabs.width())
        self.assertEqual(w.credit_label.text(), CREDIT)
        self.assertEqual(w.about_credit.text(), CREDIT)
        self.assertEqual(len(w.nav_buttons), 20)
        self.assertIn('research', w.page_indices)
        w.navigate('about')
        self.assertTrue(w.about_credit.isVisible())
        self.assertIn('درباره محصول', w.breadcrumb.text())
        w.resize(1024, 800)
        w.toggle_sidebar()
        self.app.processEvents()
        self.assertEqual(w.sidebar.width(), 112)
        self.assertTrue(w.credit_label.isVisible())
        w.nav_buttons[0].click()
        self.assertEqual(w.tabs.currentIndex(), w.page_indices['overview'])

    def test_navigation_icons_metric_colors_and_compact_accessibility(self):
        w = self.window
        self.assertTrue(all(not button.icon().isNull() for button in w.nav_buttons))
        self.assertTrue(all(button.accessibleName() == button.property('full_text') for button in w.nav_buttons))
        self.assertTrue(all(group.isVisible() for group in w.nav_groups))
        values = [metric.value_label.styleSheet() for metric, _ in w.overview_widget.metrics.values()]
        self.assertEqual(len(set(values)), 4)
        for button, _ in w.overview_widget.metrics.values():
            self.assertEqual(button.value_label.text(), '—')
        w.toggle_sidebar()
        self.assertTrue(all(not group.isVisible() for group in w.nav_groups))
        self.assertEqual(w.credit_label.text(), CREDIT)
        self.assertTrue(all(not button.text() and not button.icon().isNull() for button in w.nav_buttons))
        self.assertFalse(w.credit_label.wordWrap())
        self.assertTrue(all(button.accessibleName() == button.property('full_text') for button in w.nav_buttons))
        w.toggle_sidebar()
        self.assertTrue(all(group.isVisible() for group in w.nav_groups))
        self.assertEqual(w.sidebar.width(), 246)

    def test_empty_values_unknown_and_kpi_navigates(self):
        overview = self.window.overview_widget
        for button, _ in overview.metrics.values():
            self.assertEqual(button.value_label.text(), '—')
        self.assertEqual(overview.state_badge.text(), 'آماده شروع')
        self.assertFalse(self.window.export_html_btn.isEnabled())
        overview.metrics['pages'][0].click()
        self.assertEqual(self.window.tabs.currentIndex(), self.window.page_indices['audit'])
        overview.present({'meta': {'pipeline_status': 'failed'}})
        self.assertEqual(overview.metrics['opportunities'][0].value_label.text(), '—')

    def test_snapshot_state_values_and_readable_evidence(self):
        result = self.result()
        w = self.window
        w.on_analysis_finished(result)
        overview = w.overview_widget
        self.assertEqual(overview.state_badge.text(), 'نتایج ناقص')
        self.assertEqual(overview.metrics['pages'][0].value_label.text(), str(result['meta']['coverage']['attempted']))
        self.assertEqual(overview.metrics['actions'][0].value_label.text(), str(len(result['seo_roadmap'])))
        self.assertTrue(w.export_excel_btn.isEnabled())
        self.assertIn('نتایج ناقص', w.site_status_label.text())
        self.assertEqual(w.site_selector.currentData(), result['meta']['project_id'])
        QTimer.singleShot(0, lambda: self.app.activeModalWidget().accept())
        overview.show_evidence(result['seo_roadmap'][0])
        self.assertIsNone(self.app.activeModalWidget())
        for code, text in [('running', 'در حال پردازش'), ('failed', 'ناموفق'),
                           ('cancelled', 'متوقف‌شده'), ('completed', 'تکمیل‌شده')]:
            overview.set_state(code, 'پیام وضعیت')
            self.assertEqual(overview.state_badge.text(), text)
        result['meta']['demo'] = True
        overview.present(result)
        self.assertTrue(overview.demo.isVisible())

    def test_switching_sites_clears_previous_results_and_settings_load(self):
        w = self.window
        result = self.result()
        second = SiteRepository.register('Second', 'https://second.example')
        SiteRepository.configure(second, settings={'max_pages': 7})
        w.on_analysis_finished(result)
        w.site_selector.setCurrentIndex(w.site_selector.findData(second))
        self.assertEqual(w.max_pages_input.value(), 7)
        self.assertEqual(w.url_input.text(), 'https://second.example/')
        self.assertEqual(w.last_result_data, {})
        self.assertFalse(w.export_html_btn.isEnabled())
        self.assertEqual(w.progress_bar.value(), 0)
        self.assertIn('آماده شروع', w.run_message.text())
        self.assertEqual(w.overview_widget.state_badge.text(), 'آماده شروع')
        w.site_selector.setCurrentIndex(0)
        self.assertEqual(w.url_input.text(), '')

    def test_error_is_persistent_and_log_treats_source_as_plain_text(self):
        w = self.window
        with patch.object(QMessageBox, 'critical') as critical:
            w.on_error('<b>network failed</b>')
        critical.assert_called_once()
        self.assertEqual(w.overview_widget.state_badge.text(), 'خطا')
        self.assertIn('خطا', w.run_message.text())
        self.assertIn('<b>network failed</b>', w.log_output.toPlainText())

    def test_comparison_uses_selected_saved_snapshot(self):
        w = self.window
        before = self.result()
        after = self.result()
        w.on_analysis_finished(after)
        with patch('modules.ui.main_window.QInputDialog.getInt',
                   return_value=(before['meta']['analysis_run_id'], True)):
            w.compare_saved_run()
        self.assertIn('مشکلات مشاهده‌شده', w.overview_widget.trend.text())
        self.assertIn('resolved', w.log_output.toPlainText())

    def test_registration_error_is_persian_and_persists_next_to_form(self):
        w = self.window
        w.navigate('sites')
        w.url_input.setText('javascript:alert(1)')
        with patch('modules.ui.main_window.QInputDialog.getText', return_value=('نمونه', True)), \
             patch.object(QMessageBox, 'warning') as warning:
            w.register_site()
        warning.assert_called_once()
        self.assertTrue(w.site_error_label.isVisible())
        self.assertIn('نشانی معتبر نیست', w.site_error_label.text())
        self.assertEqual(w.site_selector.count(), 1)

    def test_stop_confirmation_does_not_claim_completed(self):
        w = self.window
        worker = Mock()
        worker.isRunning.return_value = True
        w.worker = worker
        try:
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
                w.stop_analysis()
            worker.cancel.assert_not_called()
            w.overview_widget.set_state('running')
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
                w.stop_analysis()
            worker.cancel.assert_called_once()
            self.assertEqual(w.overview_widget.state_badge.text(), 'در حال پردازش')
            self.assertFalse(w.stop_btn.isEnabled())
        finally:
            w.worker = None

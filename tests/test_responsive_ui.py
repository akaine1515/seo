"""Dedicated views, bounded rendering, charts and responsive export acceptance."""
import copy
import random
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from tests import test_pipeline as fixture
from modules.ui.intelligence import EvidenceTable
from modules.ui.main_window import MainWindow
from modules.keywords.clustering import KeywordClustering
from core.engine import SEOOrchestrator


def original_clusters(data):
    """Pre-optimization contract: score-ordered greedy full scan, including substrings."""
    ordered = sorted(data, key=lambda k: (data[k].get('tf_idf_score', 0), data[k].get('raw_frequency', 0)), reverse=True)
    seen, result = set(), []
    for term in ordered:
        if term in seen:
            continue
        seen.add(term)
        members, tokens = [term], set(term.split())
        for other in ordered:
            if other not in seen and (tokens.intersection(other.split()) or any(t in other for t in tokens if len(t) > 2)):
                seen.add(other)
                members.append(other)
        result.append(dict(cluster_name=term.title(), primary_keyword=term,
            secondary_keywords=members[1:], cluster_size=len(members),
            intent=data[term].get('intent', 'informational'), total_score=sum(data[k].get('tf_idf_score', 0) for k in members)))
    return sorted(result, key=lambda r: r['total_score'], reverse=True)


class ResponsiveTests(unittest.TestCase):
    def setUp(self):
        fixture.PipelineTests.setUp(self)
        self.app = QApplication.instance() or QApplication([])

    def window_result(self):
        window = MainWindow(SEOOrchestrator())
        self.addCleanup(window.close)
        result = window.orchestrator.run_full_pipeline('https://example.com', {'max_pages': 1, 'request_interval': 0})
        window.on_analysis_finished(result)
        window.show()
        self.app.processEvents()
        return window, result

    def select(self, view, row=0):
        self.app.processEvents()
        item = view.table.item(row, 0)
        view.table.scrollToItem(item)
        QTest.mouseClick(view.table.viewport(), Qt.MouseButton.LeftButton,
                         pos=view.table.visualItemRect(item).center())
        self.app.processEvents()

    def test_cluster_equivalence_random_ties_substrings_and_persian(self):
        rng = random.Random(1515)
        words = ['سایت', 'طراحی', 'فروشگاهی', 'فروش', 'خرید', 'خریدنی', 'seo', 'tools', 'tool', 'at', 'cat', 'alpha']
        for _ in range(12):
            phrases = list(dict.fromkeys(' '.join(rng.choices(words, k=rng.randrange(1, 4))) for _ in range(160)))
            data = {p: {'tf_idf_score': rng.choice([0, .1, .2]), 'raw_frequency': rng.randrange(4), 'intent': rng.choice(['commercial', 'informational'])} for p in phrases}
            before = copy.deepcopy(data)
            self.assertEqual(KeywordClustering.cluster_keywords(data), original_clusters(data))
            self.assertEqual(data, before)

    def test_all_five_sections_show_their_own_results_and_chart(self):
        w, result = self.window_result()
        result['keyword_analysis']['opportunities'] = [dict(keyword='طراحی سایت', opportunity_score=.14, total_tf_idf=.1, pages_count=2, intent='commercial')]
        result['keyword_inventory'].append(dict(term='طراحی سایت', source_pages=['https://example.com/source']))
        result['content_gap_analysis'].update(status='completed', content_gaps=[dict(term='موضوع جدید', competitor_domains_count=2,
            competitor_domains=['one.example', 'two.example'], evidence_urls=['https://one.example/source'], priority='Medium', recommended_action='بررسی پوشش')])
        result['cannibalization_issues'] = [dict(term='seo', competing_pages_count=2, competing_pages=[{'url': 'https://example.com/a'}, {'url': 'https://example.com/b'}], severity='Medium')]
        w.on_analysis_finished(result)
        for key, expected in [('opportunities', 1), ('clusters', len(result['keyword_analysis']['clusters'])), ('gap', 1), ('cannibalization', 1), ('roadmap', len(result['seo_roadmap']))]:
            w.navigate(key)
            self.app.processEvents()
            view = w.analysis_views[key]
            self.assertIs(w.tabs.currentWidget(), view)
            self.assertEqual(len(view.rows), expected)
            self.assertGreater(expected, 0)
            self.assertTrue(view.chart.isVisible())
            self.assertTrue(view.chart.values)
            self.assertIn('تعداد', view.chart.accessibleName())
            self.select(view)
            self.assertTrue(view.detail.toPlainText())
        w.navigate('gap')
        view = w.analysis_views['gap']
        self.select(view)
        self.assertIn('https://one.example/source', view.detail.toPlainText())
        w.navigate('opportunities')
        opp = w.analysis_views['opportunities']
        self.select(opp)
        self.assertIn('https://example.com/source', opp.detail.toPlainText())
        self.assertIn('TF-IDF', opp.detail.toPlainText())
        w.clear_result_view()
        for view in w.analysis_views.values():
            self.assertEqual(view.rows, [])
            self.assertEqual(view.chart.values, [])
            self.assertEqual(view.detail.toPlainText(), '')
        self.assertEqual(w.overview_widget.coverage_chart.values, [])

    def test_large_table_search_pagination_numeric_sort_and_detail_identity(self):
        view = EvidenceTable('آزمون', 'Demo', [('term', 'عبارت'), ('count', 'تعداد')], 'kind')
        self.addCleanup(view.close)
        rows = [dict(term=f'کلمه {i}', count=12000-i, kind='odd' if i%2 else 'even', evidence={'url': f'https://example.com/{i}'}) for i in range(12000)]
        view.present(rows)
        self.assertEqual(view.table.rowCount(), 100)
        view.following.click()
        self.assertEqual(view.table.item(0, 0).text(), 'کلمه 100')
        view.table.selectRow(0)
        self.assertIn('https://example.com/100', view.detail.toPlainText())
        view.sort_by(1)
        self.assertEqual(view.table.item(0, 1).text(), '1')
        self.assertEqual(view.table.item(99, 1).text(), '100')
        view.search.setText('كلمه 11999')  # Arabic kaf should match Persian cached text.
        QTest.qWait(210)
        self.assertEqual(len(view.matches), 1)
        self.assertEqual(view.table.item(0, 0).text(), 'کلمه 11999')
        view.table.selectRow(0)
        self.assertIn('https://example.com/11999', view.detail.toPlainText())
        view.kind.setCurrentIndex(view.kind.findData('even'))
        self.assertEqual(view.table.rowCount(), 0)
        self.assertEqual(view.detail.toPlainText(), '')
        view.search.setText('not found')
        view.present([])  # A pending search must not resurrect old site data.
        QTest.qWait(210)
        self.assertEqual(view.matches, [])

    def test_history_comparison_stays_in_history_with_observed_counts(self):
        w, before = self.window_result()
        after = w.orchestrator.run_full_pipeline('https://example.com', {'max_pages': 1, 'request_interval': 0})
        w.on_analysis_finished(after)
        w.navigate('history')
        self.assertEqual(len(w.history_view.rows), 2)
        self.assertEqual(w.history_view.rows[0]['id'], after['meta']['analysis_run_id'])
        self.select(w.history_view, 1)
        self.assertEqual(w.selected_history_id(), before['meta']['analysis_run_id'])
        w.compare_selected_run()
        self.assertEqual(w.tabs.currentIndex(), w.page_indices['history'])
        self.assertTrue(w.comparison_view.isVisible())
        self.assertEqual(w.comparison_view.chart.values, [('جدید', 0.0), ('رفع‌شده در صفحات مشاهده‌شده', 0.0), ('صفحه دوباره مشاهده نشده', 0.0)])
        self.assertEqual(w.overview_widget.trend_chart.values[0][1], before['audit_summary']['total_issues_found'])
        w.on_analysis_finished(before)
        self.assertFalse(w.comparison_view.isVisible())
        self.assertEqual(w.comparison_view.rows, [])
        self.assertEqual(w.comparison_view.chart.values, [])

    def test_export_runs_in_worker_and_gui_timer_keeps_working(self):
        w, result = self.window_result()
        started, release = threading.Event(), threading.Event()
        def slow_export(path, data):
            self.assertIs(data, result)
            started.set()
            release.wait(3)
            Path(path).write_text('controlled fixture')
            return path
        path = str(Path(self.temp.name)/'responsive.html')
        ticks = []
        timer = QTimer(w)
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(True))
        with patch('modules.reporting.html_reporter.HTMLReportGenerator.generate_report', side_effect=slow_export):
            timer.start()
            w.start_export(path, 'html')
            try:
                QTest.qWait(150)
                self.assertTrue(started.is_set())
                self.assertGreater(len(ticks), 2)
                self.assertFalse(w.export_html_btn.isEnabled())
                w.navigate('audit')
                self.assertIs(w.tabs.currentWidget(), w.analysis_views['audit'])
            finally:
                release.set()
                deadline = time.monotonic() + 5
                while w.export_worker.isRunning() and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(.01)
                self.assertFalse(w.export_worker.isRunning())
                self.app.processEvents()
                timer.stop()
            self.assertTrue(Path(path).exists())
            self.assertTrue(w.export_html_btn.isEnabled())

    def test_real_worker_exports_excel_html_and_reports_errors(self):
        from openpyxl import load_workbook
        w, result = self.window_result()
        for kind, extension in [('excel', 'xlsx'), ('html', 'html')]:
            path = str(Path(self.temp.name)/('thread-export.'+extension))
            w.start_export(path, kind)
            deadline = time.monotonic() + 5
            while w.export_worker.isRunning() and time.monotonic() < deadline:
                self.app.processEvents()
                time.sleep(.01)
            self.assertFalse(w.export_worker.isRunning())
            self.app.processEvents()
            self.assertTrue(Path(path).exists())
            self.assertIsNone(w.export_worker.result)
            if kind == 'excel':
                workbook = load_workbook(path)
                self.assertIn('Run Metadata', workbook.sheetnames)
                workbook.close()
            else:
                self.assertIn('example.com', Path(path).read_text())
        with patch('modules.reporting.html_reporter.HTMLReportGenerator.generate_report', side_effect=OSError('controlled disk error')), \
             patch('modules.ui.main_window.QMessageBox.critical') as message:
            w.start_export(str(Path(self.temp.name)/'fail.html'), 'html')
            deadline = time.monotonic()+5
            while w.export_worker.isRunning() and time.monotonic()<deadline:
                self.app.processEvents()
                time.sleep(.01)
            self.app.processEvents()
            self.assertFalse(w.export_worker.isRunning())
            self.assertIn('controlled disk error', w.statusBar().currentMessage())
            message.assert_called_once()
            self.assertTrue(w.export_html_btn.isEnabled())

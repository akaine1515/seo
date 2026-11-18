"""Tests for research provenance, source isolation, bounded input and Excel export."""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from openpyxl import load_workbook
from tests import test_pipeline as fixtures
from modules.keywords.research import research, load_suggestions
from modules.reporting.keyword_research_excel import export_keyword_research


class KeywordResearchTests(unittest.TestCase):
    setUp = fixtures.PipelineTests.setUp

    def test_multiple_seeds_dedup_and_source_evidence(self):
        path = Path(self.temp.name) / 'suggestions.json'
        path.write_text(json.dumps({'source':'fixture', 'retrieved_at':'2026-11-17T12:00:00Z',
            'country':'IR', 'language':'fa', 'results':[
                {'seed':'طراحی سایت', 'suggestions':['آموزش طراحی سایت', 'طراحی سایت ارزان']},
                {'seed':'unselected', 'suggestions':['کاملاً بی ربط']} ]}, ensure_ascii=False))
        rows = research(['طراحی سايت',' طراحی سایت ', 'فروشگاه'], ['آموزش'], ['ارزان'],
            site_keywords=[{'term':'طراحی سایت فروشگاهی','source_pages':['https://example.com/x']}],
            site_run_id=42, suggestions=load_suggestions(path))
        by_phrase = {r['phrase']:r for r in rows['rows']}
        self.assertEqual(len(by_phrase), len(rows['rows']))
        self.assertEqual(rows['seeds'], ['طراحی سایت','فروشگاه'])
        self.assertEqual(set(by_phrase['آموزش طراحی سایت']['types']), {'prefix','imported_suggestion'})
        evidence = by_phrase['آموزش طراحی سایت']['evidence']
        self.assertEqual(next(e for e in evidence if e['type']=='imported_suggestion')['retrieved_at'], '2026-11-17T12:00:00Z')
        self.assertEqual(by_phrase['طراحی سایت فروشگاهی']['evidence'][0]['pages'], ['https://example.com/x'])
        self.assertEqual(by_phrase['طراحی سایت فروشگاهی']['evidence'][0]['run_id'], 42)
        self.assertIn('آموزش فروشگاه ارزان', by_phrase)
        self.assertNotIn('کاملاً بی ربط', by_phrase)
        self.assertNotIn('search_volume', by_phrase['طراحی سایت'])

    def test_rejects_invalid_sources_oversize_and_limits(self):
        path = Path(self.temp.name) / 'bad.json'
        for payload in [{'source':'', 'retrieved_at':'2026-11-17T00:00:00Z','results':[]},
                        {'source':'x','retrieved_at':'2026-11-17T00:00:00','results':[]},
                        {'source':'x','retrieved_at':'2026-11-17T00:00:00Z','results':[{'seed':'a','suggestions':'x'}]}]:
            path.write_text(json.dumps(payload))
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                load_suggestions(path)
        path.write_bytes(b'x' * (1024*1024+1))
        with self.assertRaises(ValueError): load_suggestions(path)
        with self.assertRaises(ValueError): research([])
        with self.assertRaises(ValueError): research(['a'], site_keywords=[], site_run_id=None)
        with self.assertRaises(ValueError): research([str(i) for i in range(20)], [str(i) for i in range(10)], [str(i) for i in range(10)])
        with self.assertRaises(ValueError): research(['a'*201], prefixes=['b'])
        with self.assertRaises(ValueError): research(['عبارت\x00نامعتبر'])

    def test_long_generated_phrase_does_not_discard_other_results(self):
        result = research(['a' * 200, 'سایت'], prefixes=['خرید'],
                          site_keywords=[{'term': 'سایت ' + 'ب' * 250}], site_run_id=1)
        self.assertEqual({row['phrase'] for row in result['rows']}, {'a' * 200, 'سایت', 'خرید سایت'})
        self.assertEqual(result['skipped_long_phrases'], 2)
        self.assertIn('کنار گذاشته', result['warnings'][0])

    def test_excel_provenance_and_formula_safety(self):
        result = research(['=1+1', 'طراحی سایت'], ['+test'], ['-suffix'])
        path = Path(self.temp.name) / 'test.xlsx'
        export_keyword_research(str(path), result)
        wb = load_workbook(path)
        sheet = wb['Keyword Research']
        self.assertEqual(sheet.max_row, len(result['rows'])+1)
        self.assertEqual(sheet['A2'].value, "'=1+1")
        self.assertNotEqual(sheet['A2'].data_type, 'f')
        self.assertIsNone(sheet['F2'].value)
        self.assertIsNone(sheet['G2'].value)
        self.assertTrue(sheet.auto_filter.ref)
        self.assertEqual(wb['Metadata']['B2'].value, 'keyword-research-1.1')
        wb.close()

    def test_desktop_research_results_invalidated_and_exported(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication, QFileDialog
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from modules.ui.main_window import MainWindow
        from core.engine import SEOOrchestrator
        app = QApplication.instance() or QApplication([])
        errors = []
        with patch.object(sys, 'excepthook', lambda *args: errors.append(args)):
            window = MainWindow(SEOOrchestrator())
            try:
                window.show()
                window.navigate('research')
                app.processEvents()
                ui = window.keyword_research
                ui.seeds.setPlainText('a' * 200)
                ui.prefixes.setPlainText('b')
                ui.run_button.click()
                self.assertEqual(ui.table.rowCount(), 1)
                self.assertIn('کنار گذاشته', ui.message.text())
                self.assertTrue(ui.export_button.isEnabled())
                ui.seeds.setPlainText('طراحی سایت\nفروشگاه')
                ui.prefixes.setPlainText('آموزش')
                ui.suffixes.setPlainText('ارزان')
                ui.run_button.click()
                self.assertEqual(ui.table.rowCount(), 8)
                self.assertTrue(ui.export_button.isEnabled())
                app.processEvents()
                cell = ui.table.visualItemRect(ui.table.item(0, 0)).center()
                QTest.mouseClick(ui.table.viewport(), Qt.MouseButton.LeftButton, pos=cell)
                app.processEvents()
                self.assertIn('seed', ui.details.toPlainText())
                ui.search.setText('فروشگاه')
                QTest.qWait(200)
                self.assertEqual(sum(not ui.table.isRowHidden(i) for i in range(ui.table.rowCount())), 4)
                path = str(Path(self.temp.name)/'desktop.xlsx')
                with patch.object(QFileDialog, 'getSaveFileName', return_value=(path, '')):
                    ui.export_button.click()
                self.assertTrue(Path(path).exists())
                ui.seeds.setPlainText('سایت جدید')
                self.assertFalse(ui.export_button.isEnabled())
                self.assertEqual(ui.table.rowCount(), 0)
                ui.include_site.setChecked(True)
                ui.run_button.click()
                self.assertIn('نتیجه تحلیل سایت فعال', ui.message.text())
                self.assertEqual(errors, [])
            finally:
                window.close()

    def test_desktop_uses_only_loaded_active_site_with_source_url(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6.QtWidgets import QApplication
        from modules.ui.main_window import MainWindow
        from core.engine import SEOOrchestrator
        from database.sites import SiteRepository
        from tests import test_keyword_plan as fixture
        app = QApplication.instance() or QApplication([])
        # Use the actual full pipeline and UI site-selection behavior.
        source = fixture.KeywordPlanTests.pipeline(self)
        second = SiteRepository.register('Other', 'https://second.example')
        window = MainWindow(SEOOrchestrator())
        try:
            window.on_analysis_finished(source)
            window.navigate('research')
            ui = window.keyword_research
            ui.seeds.setPlainText('طراحی سایت')
            ui.include_site.setChecked(True)
            ui.run_button.click()
            row = next(row for row in ui.result['rows'] if row['phrase'] == 'طراحی سایت فروشگاهی')
            evidence = next(e for e in row['evidence'] if e['type'] == 'site_observed')
            self.assertEqual(evidence['run_id'], source['meta']['analysis_run_id'])
            self.assertEqual(evidence['pages'], ['https://example.com/'])
            window.site_selector.setCurrentIndex(window.site_selector.findData(second))
            self.assertIsNone(ui.result)
            ui.run_button.click()
            self.assertIn('سایت فعال', ui.message.text())
            self.assertFalse(ui.export_button.isEnabled())
        finally:
            window.close()

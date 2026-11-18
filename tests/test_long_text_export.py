"""Exercise exported files, including Excel cell limits and XML-hostile text."""
from contextlib import closing
import copy
import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook, load_workbook

from modules.reporting.excel_reporter import ExcelReportGenerator
from modules.reporting.excel_text import ExcelText
from modules.reporting.keyword_research_excel import export_keyword_research


class LongTextExportTests(unittest.TestCase):
    def restored(self, workbook):
        groups = {}
        for record in workbook['Long Text'].iter_rows(min_row=2, values_only=True):
            key, sheet, row, column, encoding, part, total, text = record
            self.assertLessEqual(len(text.encode('utf-16-le')) // 2, 32767)
            group = groups.setdefault((sheet, row, column), [encoding, total, []])
            self.assertEqual(part, len(group[2]) + 1)
            group[2].append(text)
            self.assertIn(f'ID {key}', workbook[sheet].cell(row, column).value)
        result = {}
        for location, (encoding, total, parts) in groups.items():
            self.assertEqual(total, len(parts))
            value = ''.join(parts)
            result[location] = json.loads(value) if encoding == 'json' else value
        return result

    def test_full_report_keeps_long_nested_and_invalid_xml_text(self):
        long_text = 'متن فارسی 😀 ' * 10000
        hostile = 'before\x00after\ufffe\ud800'
        data = {'meta': {'target_domain': long_text},
                'crawled_pages': [{'url': 'https://example.com/', 'content': long_text,
                                   'evidence': {'text': long_text}, 'title': hostile},
                                  {'url': 'https://example.com/next', 'content': 'still exported',
                                   'title': '  =1+1'}]}
        original = copy.deepcopy(data)
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'report.xlsx')
            ExcelReportGenerator().generate_report(path, data)
            with closing(load_workbook(path)) as workbook:
                restored = self.restored(workbook)
                self.assertEqual(restored['Project Overview', 2, 2], long_text)
                self.assertEqual(restored['Pages', 2, 2], long_text)
                self.assertEqual(json.loads(restored['Pages', 2, 3]), {'text': long_text})
                self.assertEqual(restored['Pages', 2, 4], hostile)
                self.assertEqual(workbook['Pages']['B3'].value, 'still exported')
                self.assertNotEqual(workbook['Pages']['D3'].data_type, 'f')
        self.assertEqual(data, original)

    def test_research_export_keeps_long_evidence_and_metadata(self):
        long_text = 'شواهد' * 15000
        result = {'rows': [{'phrase': '=SUM(1,2)', 'seeds': ['سایت'], 'types': ['seed'],
                            'word_count': 1, 'evidence': [{'page': long_text}]}],
                  'suggestion_source': {'source': long_text}, 'created_at': 'date\x00time',
                  'warnings': ['عبارت طولانی کنار گذاشته شد']}
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'research.xlsx')
            export_keyword_research(path, result)
            with closing(load_workbook(path)) as workbook:
                restored = self.restored(workbook)
                self.assertEqual(json.loads(restored['Keyword Research', 2, 5]), [{'page': long_text}])
                self.assertEqual(restored['Metadata', 3, 2], 'date\x00time')
                self.assertEqual(json.loads(restored['Metadata', 8, 2]), {'source': long_text})
                self.assertEqual(workbook['Keyword Research']['A2'].value, "'=SUM(1,2)")
                self.assertEqual(workbook['Metadata']['A9'].value, 'هشدار')

    def test_boundaries_and_formula_at_chunk_boundary(self):
        values = ['a' * 32767, 'a' * 32768, '😀' * 16384,
                  'a' * 30000 + '=1+1' + 'b' * 4000, '\x00\udfff']
        with tempfile.TemporaryDirectory() as directory:
            workbook = Workbook()
            workbook.active.title = 'Data'
            text = ExcelText()
            for row, value in enumerate(values, 1):
                workbook.active.append([text.prepare(value, 'Data', row, 1)])
            text.write(workbook)
            path = Path(directory) / 'boundary.xlsx'
            workbook.save(path)
            workbook.close()
            with closing(load_workbook(path)) as loaded:
                restored = self.restored(loaded)
                self.assertEqual(loaded['Data']['A1'].value, values[0])
                for row in range(2, len(values) + 1):
                    self.assertEqual(restored['Data', row, 1], values[row - 1])
                self.assertTrue(all(cell.data_type != 'f' for row in loaded['Long Text'] for cell in row))

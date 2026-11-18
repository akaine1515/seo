"""Lossless handling of external text within Excel's cell/XML limits."""
import json
import re

from openpyxl.styles import Alignment


_INVALID_XML = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]')
_CHUNK_UNITS = 30000  # Below Excel's 32767 UTF-16 code-unit cell limit.


def _chunks(text):
    start = units = 0
    for index, char in enumerate(text):
        size = 2 if ord(char) > 0xffff else 1
        if units + size > _CHUNK_UNITS:
            yield text[start:index]
            start, units = index, 0
        units += size
    yield text[start:]


class ExcelText:
    """Replace exceptional cells with a reference to reconstructable text parts.

    Ordinary workbooks keep their existing sheets. Long Text records locate the
    original cell; concatenate parts by ID/Part, then json.loads for json encoding.
    Source objects are never changed. Part cells are explicitly strings, even if
    a part begins with a formula character.
    """

    def __init__(self):
        self.records = []
        self.next_id = 1

    def prepare(self, value, sheet, row, column):
        if isinstance(value, (list, dict)):
            value = json.dumps(value, ensure_ascii=False)
        if not isinstance(value, str):
            return value
        invalid = bool(_INVALID_XML.search(value))
        encoding = 'json' if invalid else 'text'
        text = json.dumps(value, ensure_ascii=True) if invalid else value
        # Include the formula-protection prefix in the length calculation.
        safe = "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
        if invalid or len(safe.encode('utf-16-le')) // 2 > 32767:
            record_id = self.next_id
            self.next_id += 1
            parts = list(_chunks(text))
            for part, chunk in enumerate(parts, 1):
                self.records.append([record_id, sheet, row, column, encoding, part, len(parts), chunk])
            return f'متن کامل در Long Text · ID {record_id} · {len(parts)} بخش · قالب {encoding}'
        return safe

    def write(self, workbook):
        if not self.records:
            return
        sheet = workbook.create_sheet('Long Text')
        sheet.append(['ID', 'Source Sheet', 'Source Row', 'Source Column', 'Encoding', 'Part', 'Parts', 'Text'])
        for record in self.records:
            sheet.append(record)
            # Never interpret a chunk as a formula or modify it with a prefix.
            sheet.cell(sheet.max_row, 8).data_type = 's'
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        sheet.column_dimensions['B'].width = 25
        sheet.column_dimensions['H'].width = 80
        for row in sheet.iter_rows(min_col=8, max_col=8):
            row[0].alignment = Alignment(wrap_text=True, vertical='top')

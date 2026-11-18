"""Standalone export of keyword research with provenance and safe text cells."""
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from modules.reporting.excel_text import ExcelText


def export_keyword_research(path, result):
    if not path or not isinstance(result, dict) or not isinstance(result.get('rows'), list):
        raise ValueError('نتیجه یا مسیر خروجی معتبر نیست.')
    text = ExcelText()
    workbook = Workbook()

    def append(sheet, values):
        row_number = 1 if sheet.max_row == 1 and sheet.cell(1, 1).value is None else sheet.max_row + 1
        for index, value in enumerate(values, 1):
            sheet.cell(row_number, index, text.prepare(value, sheet.title, row_number, index))
    worksheet = workbook.active
    worksheet.title = 'Keyword Research'
    append(worksheet, ['عبارت', 'عبارت‌های پایه', 'نوع', 'تعداد واژه', 'منشأ و شواهد', 'حجم جست‌وجو', 'سختی کلمه'])
    for row in result['rows']:
        append(worksheet, [row['phrase'], row['seeds'], row['types'],
                          row['word_count'], row['evidence'], None, None])
    meta = workbook.create_sheet('Metadata')
    append(meta, ['نام', 'مقدار'])
    for key in ('algorithm_version', 'created_at', 'seeds', 'prefixes', 'suffixes', 'site_run_id', 'suggestion_source'):
        append(meta, [key, result.get(key)])
    for warning in result.get('warnings', []):
        append(meta, ['هشدار', warning])
    append(meta, ['محدودیت', 'ترکیب‌ها پیشنهاد ماشینی‌اند؛ حجم و سختی بدون منبع معتبر موجود نیست.'])
    for sheet in (worksheet, meta):
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(color='FFFFFF', bold=True)
            cell.fill = PatternFill('solid', fgColor='087E9B')
            cell.alignment = Alignment(horizontal='center')
        for col in range(1, sheet.max_column + 1):
            sheet.column_dimensions[get_column_letter(col)].width = min(50, 22 if col != 5 else 50)
        sheet.sheet_view.rightToLeft = True
    text.write(workbook)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(destination)
    workbook.close()
    return str(destination.resolve())

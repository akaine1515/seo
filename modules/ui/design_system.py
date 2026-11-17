"""Shared desktop design tokens. No application/SEO logic."""
from PySide6.QtGui import QFont, QFontDatabase

COLORS = dict(background='#F5F6F8', surface='#FFFFFF', navy='#14233B', muted='#526175',
              accent='#3459D4', border='#DDE3EC')
SPACING = (4, 8, 12, 16, 24, 32)
CREDIT = 'Product by Ashkan'
STATUS_TEXT = {'empty': 'آماده شروع', 'loading': 'در حال پردازش', 'running': 'در حال پردازش',
               'partial': 'نتایج ناقص', 'cancelled': 'متوقف‌شده', 'failed': 'ناموفق',
               'error': 'خطا', 'completed': 'تکمیل‌شده', 'unavailable': 'داده در دسترس نیست',
               'unknown': 'وضعیت نامشخص', 'ready': 'آماده', 'pending': 'در انتظار'}


def ui_font():
    installed = set(QFontDatabase.families())
    family = next((f for f in ('Vazirmatn', 'Noto Sans Arabic', 'Segoe UI') if f in installed), 'DejaVu Sans')
    font = QFont(family)
    font.setPixelSize(13)
    return font


STYLES = '''
QMainWindow, QWidget#shell { background: #F5F6F8; color: #14233B; }
QWidget { color: #14233B; }
QDialog { background: #F5F6F8; }
QFrame#sidebar, QFrame#panel, QFrame#topbar { background: white; border: 1px solid #DDE3EC; border-radius: 10px; }
QLabel { background: transparent; }
QLabel[role="title"] { font-size: 24px; font-weight: 700; }
QLabel[role="section"] { font-size: 16px; font-weight: 600; }
QLabel[role="muted"] { color: #526175; }
QLabel[role="brand"] { font-size: 18px; font-weight: 700; }
QLabel#credit { color: #526175; font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QPushButton { background: white; border: 1px solid #DDE3EC; padding: 9px 14px; border-radius: 7px; }
QPushButton:hover { background: #EEF2FA; border-color: #B7C5DE; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTableWidget:focus { border: 2px solid #3459D4; }
QPushButton:disabled { color: #67758A; background: #F2F4F7; }
QPushButton[role="primary"] { background: #14233B; color: white; border-color: #14233B; font-weight: 600; }
QPushButton[role="primary"]:disabled { background: #657188; border-color: #657188; }
QPushButton[role="danger"] { color: #A82736; background: #FDECEF; border-color: #EAC5CB; }
QPushButton[role="nav"] { border: 0; text-align: right; padding: 9px 12px; background: transparent; }
QPushButton[role="nav"]:checked { color: #2449BF; background: #ECF0FD; font-weight: 600; }
QPushButton[role="metric"] { background: white; text-align: right; font-size: 15px; padding: 0; min-height: 100px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: white; border: 1px solid #CBD4E1; border-radius: 6px; padding: 7px; min-height: 22px; }
QTableWidget, QTextEdit, QPlainTextEdit { background: white; border: 1px solid #DDE3EC; border-radius: 8px; gridline-color: #EDF0F5; }
QHeaderView::section { background: #F0F3F8; color: #526175; padding: 9px; border: 0; border-bottom: 1px solid #DDE3EC; }
QTableWidget::item { padding: 8px; }
QTableWidget::item:selected { background: #ECF0FD; color: #14233B; }
QTabWidget::pane { border: 0; }
QScrollArea { border: 0; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QProgressBar { background: #E7ECF4; border: 0; border-radius: 5px; text-align: center; min-height: 12px; }
QProgressBar::chunk { background: #3459D4; border-radius: 5px; }
QStatusBar { color: #526175; background: white; }
'''

"""Shared desktop visual tokens and translucent glass surfaces."""
from pathlib import Path
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

COLORS = dict(background='#F1F5FA', surface='#FFFFFF', navy='#182D48', muted='#52657A',
              accent='#167D91', border='#D8E3ED', turquoise='#20B7B1', blue='#426CE7',
              violet='#7864D7', coral='#DF7770', amber='#C28D3A')
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


class GlassBackdrop(QWidget):
    """Paint a scalable atmospheric backdrop behind translucent Qt surfaces."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        base = QLinearGradient(0, 0, w, h)
        base.setColorAt(0, QColor('#EDF5FB'))
        base.setColorAt(.5, QColor('#F5F6FB'))
        base.setColorAt(1, QColor('#EAF7F5'))
        painter.fillRect(self.rect(), base)
        for x, y, radius, color in ((.05, .08, .48, QColor(105, 162, 236, 64)),
                                    (.72, .02, .38, QColor(150, 131, 225, 45)),
                                    (.35, .90, .48, QColor(73, 190, 181, 49))):
            size = max(w, h) * radius
            glow = QRadialGradient(QPointF(w*x, h*y), size)
            glow.setColorAt(0, color)
            glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(w*x, h*y), size, size)
        painter.end()


STYLES = '''
QMainWindow { background: #F1F5FA; color: #182D48; }
QWidget { color: #182D48; }
QDialog, QMessageBox { background: #F6F8FC; }
QFrame#panel, QFrame#topbar { background: rgba(255,255,255,210); border: 1px solid rgba(255,255,255,245); border-radius: 16px; }
QFrame#topbar { background: rgba(255,255,255,225); }
QFrame#actionRow { background: #F7F9FD; border: 1px solid #E6EDF4; border-radius: 10px; }
QFrame#sidebar { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #15263E,stop:.6 #1B3754,stop:1 #164C58); border: 1px solid #38556A; border-radius: 18px; }
QFrame#sidebar QLabel { color: #EAF4FC; }
QFrame#sidebar QLabel[role="muted"], QFrame#sidebar QLabel#credit { color: #B4CDDB; }
QFrame#sidebar QLabel[role="navgroup"] { color: #92AFC3; font-size: 10px; font-weight: 600; padding: 10px 8px 3px; }
QLabel { background: transparent; }
QLabel[role="title"] { font-size: 26px; font-weight: 700; color: #1A304A; }
QLabel[role="section"] { font-size: 16px; font-weight: 700; color: #1C3850; }
QLabel[role="muted"] { color: #536A7C; }
QLabel[role="eyebrow"] { color: #147D87; font-size: 11px; font-weight: 700; }
QLabel[role="brand"] { font-size: 18px; font-weight: 700; }
QLabel#credit { font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QPushButton { background: rgba(255,255,255,210); border: 1px solid #D4E1EA; padding: 9px 14px; border-radius: 10px; color: #263F55; }
QPushButton:hover { background: #FFFFFF; border-color: #6DAFBA; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTableWidget:focus, QListWidget:focus, QTreeWidget:focus, QPlainTextEdit:focus { border: 2px solid #317DAD; }
QPushButton:disabled { color: #798B98; background: #EAF0F4; border-color: #DAE4EA; }
QPushButton[role="primary"] { background: #187F91; color: white; border-color: #187F91; font-weight: 700; }
QPushButton[role="primary"]:hover { background: #126C80; }
QPushButton[role="primary"]:disabled { background: #728F99; color: #EFF8F9; border-color: #728F99; }
QPushButton[role="danger"] { color: #9C293C; background: #FCECEF; border-color: #DFB5BE; }
QPushButton[role="nav"] { color: #D8EAF4; border: 1px solid transparent; text-align: left; padding: 8px 10px; background: transparent; }
QPushButton[role="nav"][compact="true"] { text-align: center; padding: 8px; }
QPushButton[role="nav"]:hover { color: white; background: rgba(177,221,235,25); }
QPushButton[role="nav"]:checked { color: white; background: rgba(93,194,195,60); border: 1px solid rgba(142,225,221,105); font-weight: 700; }
QPushButton[role="metric"] { background: rgba(255,255,255,218); border: 1px solid rgba(255,255,255,250); border-radius: 16px; text-align: right; padding: 0; min-height: 115px; }
QPushButton[role="metric"]:hover { background: #FFFFFF; border-color: #76BECB; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: rgba(255,255,255,230); border: 1px solid #D0DDE7; border-radius: 9px; padding: 7px; min-height: 22px; selection-background-color: #187F91; selection-color: white; }
QComboBox QAbstractItemView { background: #FFFFFF; color: #182D48; selection-background-color: #DCEFF1; selection-color: #182D48; border: 1px solid #C9DBE5; }
QTableWidget, QListWidget, QTreeWidget, QTextEdit, QPlainTextEdit { background: rgba(255,255,255,225); border: 1px solid #E0E8F0; border-radius: 12px; gridline-color: #E9EEF4; selection-background-color: #D8EEF0; selection-color: #182D48; }
QHeaderView::section { background: #EEF3F9; color: #435B72; font-weight: 600; padding: 9px; border: 0; border-bottom: 1px solid #DAE4ED; }
QListWidget::indicator, QTreeWidget::indicator, QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #79A5B3; background: #FFFFFF; }
QListWidget::indicator:checked, QTreeWidget::indicator:checked, QCheckBox::indicator:checked { background: #187F91; border-color: #187F91; image: url("__CHECK_ICON__"); }
QTableWidget::item { padding: 8px; }
QTableWidget::item:selected, QListWidget::item:selected, QTreeWidget::item:selected { background: #D8EEF0; color: #182D48; }
QTabWidget::pane { border: 0; background: transparent; }
QScrollArea { border: 0; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(80,119,145,110); border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { background: #E0E9F2; color: #263F55; border: 0; border-radius: 6px; text-align: center; min-height: 12px; }
QProgressBar::chunk { background: #20A5A4; border-radius: 6px; }
QStatusBar { color: #526A7B; background: #EAF1F7; }
QToolTip { color: #203A50; background: #FFFFFF; border: 1px solid #BDCFDB; padding: 6px; }
'''.replace('__CHECK_ICON__', (Path(__file__).parent / 'assets' / 'check.svg').as_posix())

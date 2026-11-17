"""Shared desktop visual tokens and translucent glass surfaces."""
from pathlib import Path
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

COLORS = dict(background='#D7F1F5', surface='#F4FCFD', navy='#10324B', muted='#41687A',
              accent='#087E9B', border='#A8D4DF', turquoise='#15B9BC', blue='#2373AC')
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
        base.setColorAt(0, QColor('#a8dce9'))
        base.setColorAt(.5, QColor('#d9f1f3'))
        base.setColorAt(1, QColor('#b4e3e7'))
        painter.fillRect(self.rect(), base)
        for x, y, radius, color in ((.12, .15, .58, QColor(31, 151, 205, 105)),
                                    (.67, .08, .48, QColor(50, 203, 194, 100)),
                                    (.34, .92, .55, QColor(31, 153, 168, 80))):
            size = max(w, h) * radius
            glow = QRadialGradient(QPointF(w*x, h*y), size)
            glow.setColorAt(0, color)
            glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QPointF(w*x, h*y), size, size)
        painter.end()


STYLES = '''
QMainWindow { background: #D7F1F5; color: #10324B; }
QWidget { color: #10324B; }
QDialog, QMessageBox { background: #E8F7F8; }
QFrame#panel, QFrame#topbar {
    background: rgba(247, 255, 255, 190); border: 1px solid rgba(255, 255, 255, 220); border-radius: 16px;
}
QFrame#sidebar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #155774, stop:0.5 #126780, stop:1 #0d4e69);
    border: 1px solid rgba(222, 255, 255, 160); border-radius: 18px;
}
QFrame#sidebar QLabel { color: #E9FCFF; }
QFrame#sidebar QLabel[role="muted"], QFrame#sidebar QLabel#credit { color: #C7EEF2; }
QLabel { background: transparent; }
QLabel[role="title"] { font-size: 25px; font-weight: 700; color: #103D55; }
QLabel[role="section"] { font-size: 16px; font-weight: 700; color: #17475D; }
QLabel[role="muted"] { color: #416879; }
QLabel[role="brand"] { font-size: 18px; font-weight: 700; }
QLabel#credit { font-family: 'Segoe UI', sans-serif; font-size: 12px; }
QPushButton { background: rgba(255, 255, 255, 155); border: 1px solid rgba(109, 181, 197, 155); padding: 9px 14px; border-radius: 10px; color: #16455C; }
QPushButton:hover { background: rgba(255, 255, 255, 225); border-color: #55B7C5; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTableWidget:focus, QListWidget:focus, QTreeWidget:focus { border: 2px solid #087F9E; }
QPushButton:disabled { color: #6B8991; background: rgba(231, 242, 244, 190); border-color: #BBD5D9; }
QPushButton[role="primary"] { background: #087E9B; color: white; border-color: #087E9B; font-weight: 700; }
QPushButton[role="primary"]:hover { background: #086B87; }
QPushButton[role="primary"]:disabled { background: #728F99; color: #EFF8F9; border-color: #728F99; }
QPushButton[role="danger"] { color: #9C293C; background: #FCECEF; border-color: #DFB5BE; }
QPushButton[role="nav"] { color: #D7F4F7; border: 0; text-align: right; padding: 9px 12px; background: transparent; }
QPushButton[role="nav"]:hover { color: white; background: rgba(206, 250, 251, 38); }
QPushButton[role="nav"]:checked { color: white; background: rgba(140, 236, 231, 70); border: 1px solid rgba(192, 255, 251, 90); font-weight: 700; }
QPushButton[role="metric"] { background: rgba(250, 255, 255, 180); border: 1px solid rgba(255, 255, 255, 220); border-radius: 16px; text-align: right; font-size: 15px; padding: 0; min-height: 100px; }
QPushButton[role="metric"]:hover { background: rgba(255, 255, 255, 225); border-color: #55B7C5; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: rgba(255, 255, 255, 195); border: 1px solid #A9CFD7; border-radius: 9px; padding: 7px; min-height: 22px; selection-background-color: #087E9B; selection-color: white; }
QComboBox QAbstractItemView { background: #F4FCFD; color: #10324B; selection-background-color: #C6EEF0; selection-color: #10324B; border: 1px solid #A9CFD7; }
QTableWidget, QListWidget, QTreeWidget, QTextEdit, QPlainTextEdit { background: rgba(250, 255, 255, 212); border: 1px solid rgba(255, 255, 255, 230); border-radius: 12px; gridline-color: #D8EBEE; selection-background-color: #C8EBED; selection-color: #10324B; }
QHeaderView::section { background: #D8EFF1; color: #305C6C; padding: 9px; border: 0; border-bottom: 1px solid #B7DAE0; }
QListWidget::indicator, QTreeWidget::indicator, QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px; border: 1px solid #70A9B6; background: #F8FFFF; }
QListWidget::indicator:checked, QTreeWidget::indicator:checked, QCheckBox::indicator:checked { background: #087E9B; border-color: #087E9B; image: url("__CHECK_ICON__"); }
QTableWidget::item { padding: 8px; }
QTableWidget::item:selected, QListWidget::item:selected, QTreeWidget::item:selected { background: #C6EBED; color: #10324B; }
QTabWidget::pane { border: 0; background: transparent; }
QScrollArea { border: 0; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(58, 133, 148, 130); border-radius: 4px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { background: #C9E6E9; color: #173F51; border: 0; border-radius: 6px; text-align: center; min-height: 12px; }
QProgressBar::chunk { background: #078FA3; border-radius: 6px; }
QStatusBar { color: #305C6C; background: #C7E8EC; }
QToolTip { color: #123B4B; background: #F4FCFD; border: 1px solid #8AC5CD; padding: 5px; }
'''.replace('__CHECK_ICON__', (Path(__file__).parent / 'assets' / 'check.svg').as_posix())

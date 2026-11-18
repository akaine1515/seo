"""Small native, accessible count/comparison charts. No extra dependencies."""
import math
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class BarChart(QWidget):
    def __init__(self, title, unit='تعداد', parent=None):
        super().__init__(parent)
        self.title, self.unit, self.values = title, unit, []
        self.setMinimumHeight(65)
        self.setMaximumHeight(210)

    def present(self, values):
        self.values = [(str(name), float(value)) for name, value in values
                       if isinstance(value, (int, float)) and not isinstance(value, bool)
                       and math.isfinite(value) and value >= 0][:6]
        self.setMinimumHeight(50 + 24 * len(self.values))
        description = self.title + ' · ' + self.unit + '\n' + ('\n'.join(f'{n}: {v:g}' for n, v in self.values) or 'داده در دسترس نیست')
        self.setAccessibleName(description)
        self.setToolTip(description)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor('#29475C'))
        painter.drawText(self.rect().adjusted(10, 0, -10, -self.height()+28),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         self.title + ' · ' + self.unit)
        if not self.values:
            painter.drawText(12, 49, 'داده در دسترس نیست')
            return
        peak = max(1, max(v for _, v in self.values))
        label_width = min(235, self.width() // 3)
        available = max(20, self.width() - label_width - 85)
        for i, (name, value) in enumerate(self.values):
            y = 36 + i * 24
            painter.setPen(QColor('#536A7C'))
            text = painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, label_width - 10)
            painter.drawText(QRectF(self.width()-label_width, y-2, label_width-10, 22),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, text)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#E9EFF5'))
            painter.drawRoundedRect(QRectF(55, y+2, available, 13), 4, 4)
            painter.setBrush(QColor(('#2398A2', '#6C75C8', '#E69B66', '#5289C8', '#7EAE8D', '#D77D91')[i % 6]))
            width = available * value / peak
            painter.drawRoundedRect(QRectF(55+available-width, y+2, width, 13), 4, 4)
            painter.setPen(QColor('#29475C'))
            painter.drawText(QRectF(0, y-2, 48, 22), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f'{value:g}')

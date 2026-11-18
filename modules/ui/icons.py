"""A small, consistent line-icon set for the native desktop shell."""
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Drawn on a common 24 × 24 grid; these icons carry no data or status.
PATHS = {
    'overview': '<rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/>',
    'sites': '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 4 6 4 9s-1 6-4 9c-3-3-4-6-4-9s1-6 4-9z"/>',
    'run': '<circle cx="12" cy="12" r="9"/><path d="m10 8 6 4-6 4z"/>',
    'audit': '<path d="M12 3 20 6v5c0 5-3 8-8 10-5-2-8-5-8-10V6z"/><path d="m8 12 3 3 5-6"/>',
    'keywords': '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5M8 10h4M10 8v4"/>',
    'opportunities': '<path d="M9 18h6M10 21h4M8 15c0-2-3-3-3-7a7 7 0 0 1 14 0c0 4-3 5-3 7z"/>',
    'clusters': '<circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><path d="M12 7v5M5 17v-2h14v2M12 12v3"/>',
    'competitors': '<circle cx="9" cy="8" r="3"/><path d="M3 20v-2a6 6 0 0 1 12 0v2M16 5a3 3 0 0 1 0 6M17 14a5 5 0 0 1 4 5v1"/>',
    'gap': '<rect x="3" y="5" width="7" height="14" rx="2"/><rect x="14" y="5" width="7" height="14" rx="2"/><path d="M10 12h4"/>',
    'cannibalization': '<circle cx="9" cy="12" r="6"/><circle cx="15" cy="12" r="6"/>',
    'roadmap': '<path d="M5 19V5M5 6h13l-2 4 2 4H5M5 19h14"/>',
    'pages': '<path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6"/>',
    'keyword_tree': '<circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="M7 6h10M6 8l5 8M18 8l-5 8"/>',
    'research': '<circle cx="10" cy="10" r="6"/><path d="m15 15 5 5M7 10h6"/>',
    'selection': '<path d="M4 6h11M4 12h11M4 18h11M18 5l2 2 2-3M18 11l2 2 2-3"/>',
    'strategy': '<circle cx="12" cy="12" r="3"/><circle cx="4" cy="5" r="2"/><circle cx="20" cy="5" r="2"/><circle cx="4" cy="19" r="2"/><circle cx="20" cy="19" r="2"/><path d="m6 6 4 4m4 0 4-4M6 18l4-4m4 0 4 4"/>',
    'reports': '<path d="M5 3h10l4 4v14H5zM15 3v5h4M8 17v-3m4 3v-6m4 6V9"/>',
    'history': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2M3 4v5h5"/>',
    'settings': '<circle cx="12" cy="12" r="3"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M19 5l-2 2M7 17l-2 2"/>',
    'about': '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
}


def line_icon(name, color='#C9DEEC'):
    """Return a self-contained icon pixmap (does not rely on system fonts)."""
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'
           + PATHS[name] + '</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode('utf-8')))
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, 48, 48))
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)

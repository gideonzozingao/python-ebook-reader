"""Colour themes (Material Design 3 roles), highlight colours and the Qt stylesheet."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

from book_reader.constants import DATA_DIR


THEMES = {
    # Material Design 3 colour roles: bg=surface, panel=surface container, fg=on-surface,
    # muted=on-surface-variant, border=outline-variant, outline=outline, accent=primary,
    # on_accent=on-primary, sel=secondary container, hover=state layer, desk=surface dim
    "Light": dict(bg="#fef7ff", fg="#1d1b20", panel="#f3edf7", border="#cac4d0",
                  outline="#79747e", accent="#6750a4", accent_hi="#7965af",
                  on_accent="#ffffff", muted="#49454f", link="#6750a4", sel="#e8def8",
                  hover="#ece6f0", desk="#e6e0e9"),
    "Sepia": dict(bg="#fbf3e2", fg="#2e2111", panel="#f1e7d0", border="#d9cba8",
                  outline="#9a8660", accent="#8a5100", accent_hi="#9e641a",
                  on_accent="#ffffff", muted="#5f4f35", link="#8a5100", sel="#f0dcb4",
                  hover="#ebdfc3", desk="#d8c9a5"),
    "Dark": dict(bg="#141218", fg="#e6e0e9", panel="#211f26", border="#49454f",
                 outline="#938f99", accent="#d0bcff", accent_hi="#dccfff",
                 on_accent="#381e72", muted="#cac4d0", link="#d0bcff", sel="#4a4458",
                 hover="#2b2930", desk="#0f0d13"),
}


HIGHLIGHT_COLORS = {
    "Yellow": "#ffd54f",
    "Green": "#81c784",
    "Blue": "#64b5f6",
    "Pink": "#f48fb1",
}


def check_icon(t: dict) -> str:
    """Tick mark used by Material-style checkboxes (drawn once per theme, cached on disk)."""
    folder = DATA_DIR / "icons"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"check_{t['on_accent'][1:]}.png"
    if not path.exists():
        pm = QPixmap(18, 18)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(t["on_accent"]), 2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPolyline([QPointF(4.5, 9.5), QPointF(7.7, 12.7), QPointF(13.5, 5.8)])
        p.end()
        pm.save(str(path))
    return path.as_posix()


def build_qss(t: dict) -> str:
    """Material Design 3 styling: tonal surfaces, pill buttons, rounded cards and fields."""
    return f"""
QWidget {{ color: {t['fg']}; }}
QMainWindow, QDialog, #page {{ background: {t['bg']}; }}
#sidePanel {{ background: {t['panel']}; }}
QLabel {{ background: transparent; }}
QLabel#h1 {{ font-size: 28px; font-weight: 400; }}
QLabel#h2 {{ font-size: 16px; font-weight: 500; }}
QLabel#muted {{ color: {t['muted']}; }}

/* top app bar */
QToolBar {{ background: {t['panel']}; border: none; spacing: 4px; padding: 8px 12px; }}
QToolButton {{ background: transparent; border: none; border-radius: 18px; padding: 8px 16px;
               min-height: 20px; font-weight: 500; }}
QToolButton:hover {{ background: {t['hover']}; }}
QToolButton:pressed {{ background: {t['sel']}; }}
QToolButton:checked {{ background: {t['sel']}; }}
QToolButton::menu-indicator {{ image: none; }}
QToolBar::separator {{ background: {t['border']}; width: 1px; margin: 8px 10px; }}

/* buttons: outlined (default), filled (#primary), tonal (#tonal), text (#link) */
QPushButton {{ background: transparent; color: {t['accent']}; border: 1px solid {t['outline']};
               border-radius: 20px; padding: 9px 22px; min-height: 20px; font-weight: 500; }}
QPushButton:hover {{ background: {t['hover']}; }}
QPushButton:pressed {{ background: {t['sel']}; }}
QPushButton:checked {{ background: {t['sel']}; color: {t['fg']}; border: 1px solid {t['sel']}; }}
QPushButton:disabled {{ color: {t['muted']}; border-color: {t['border']}; }}
QPushButton#primary {{ background: {t['accent']}; color: {t['on_accent']}; border: none;
                       padding: 10px 24px; }}
QPushButton#primary:hover {{ background: {t['accent_hi']}; }}
QPushButton#tonal {{ background: {t['sel']}; color: {t['fg']}; border: none; padding: 10px 24px; }}
QPushButton#tonal:hover {{ background: {t['border']}; }}
QPushButton#link {{ background: transparent; border: none; color: {t['accent']};
                    padding: 4px 12px; border-radius: 12px; min-height: 16px; }}
QPushButton#link:hover {{ background: {t['hover']}; }}

/* text fields: outlined, search bars are pills */
QLineEdit, QPlainTextEdit, QComboBox {{ background: {t['bg']}; border: 1px solid {t['outline']};
                                        border-radius: 8px; padding: 8px 12px;
                                        selection-background-color: {t['accent']};
                                        selection-color: {t['on_accent']}; }}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border: 2px solid {t['accent']};
                                                          padding: 7px 11px; }}
QLineEdit#search {{ background: {t['panel']}; border: none; border-radius: 22px;
                    padding: 11px 18px; min-height: 22px; }}
QLineEdit#search:focus {{ border: 2px solid {t['accent']}; padding: 9px 16px; }}
QComboBox QLineEdit {{ border: none; padding: 0; background: transparent; }}
QSpinBox {{ background: {t['bg']}; border: 1px solid {t['outline']};
            border-radius: 8px; padding: 5px 8px; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: {t['panel']}; selection-background-color: {t['sel']};
                               selection-color: {t['fg']}; border: 1px solid {t['border']};
                               border-radius: 8px; padding: 4px; outline: 0; }}
QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border: 2px solid {t['outline']};
                        border-radius: 4px; background: transparent; }}
QCheckBox::indicator:hover {{ border-color: {t['accent']}; }}
QCheckBox::indicator:checked {{ background: {t['accent']}; border-color: {t['accent']};
                                image: url({check_icon(t)}); }}

/* lists, trees, navigation-style selection */
QListWidget, QTreeWidget {{ background: {t['panel']}; border: none; outline: 0; }}
QTreeWidget::item {{ padding: 8px 8px; border-radius: 16px; }}
QTreeWidget::item:hover {{ background: {t['hover']}; }}
QTreeWidget::item:selected {{ background: {t['sel']}; color: {t['fg']}; }}
QHeaderView::section {{ background: {t['panel']}; color: {t['muted']}; border: none;
                        border-bottom: 1px solid {t['border']}; padding: 8px 10px;
                        font-weight: 500; }}
QListWidget#shelf {{ background: {t['bg']}; }}
QListWidget#shelf::item {{ border-radius: 16px; padding: 10px; color: {t['fg']}; }}
QListWidget#shelf::item:hover {{ background: {t['panel']}; }}
QListWidget#shelf::item:selected {{ background: {t['sel']}; color: {t['fg']}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* scrollbars */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['border']}; border-radius: 4px; min-height: 36px;
                               margin: 0 2px; }}
QScrollBar::handle:vertical:hover {{ background: {t['muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 0; }}
#pdfView QScrollBar:horizontal {{ height: 12px; background: transparent; margin: 0; }}
#pdfView QScrollBar::handle:horizontal {{ background: {t['border']}; border-radius: 4px;
                                          min-width: 36px; margin: 2px 0; }}
#pdfView QScrollBar::handle:horizontal:hover {{ background: {t['muted']}; }}
#pdfView QScrollBar::add-line:horizontal, #pdfView QScrollBar::sub-line:horizontal {{ width: 0; }}
#pdfView QScrollBar::add-page:horizontal, #pdfView QScrollBar::sub-page:horizontal {{
    background: transparent; }}

/* progress, menus, sliders, tooltips */
QProgressBar {{ background: {t['sel']}; border: none; border-radius: 2px; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 2px; }}
QMenu {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 12px;
         padding: 8px; }}
QMenu::item {{ padding: 9px 24px; border-radius: 8px; }}
QMenu::item:selected {{ background: {t['sel']}; color: {t['fg']}; }}
QMenu::separator {{ height: 1px; background: {t['border']}; margin: 6px 8px; }}
QSplitter::handle {{ background: {t['border']}; }}
QSlider::groove:horizontal {{ height: 4px; background: {t['sel']}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {t['accent']}; width: 20px; height: 20px;
                              margin: -8px 0; border-radius: 10px; }}
QToolTip {{ background: {t['fg']}; color: {t['bg']}; border: none; border-radius: 4px;
            padding: 6px 10px; }}
"""

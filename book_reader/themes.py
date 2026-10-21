"""Colour themes (Material Design 3 roles), highlight colours and the Qt stylesheet."""
import colorsys

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

from book_reader.constants import DATA_DIR


# --------------------------------------------------------------------------- #
# Colour themes = a colour family x a mode (light / dark). Every family has both modes.
# Palette roles (Material 3 style): bg=surface, panel=surface container, fg=on-surface,
# muted=on-surface-variant, border=outline-variant, outline=outline, accent=primary,
# on_accent=on-primary, sel=secondary container, hover=state layer, desk=surface dim.
# --------------------------------------------------------------------------- #

# hue (degrees), surface saturation, accent saturation; optional light-background lightness
COLOURS = {
    "Lavender": dict(h=262, surface=0.22, accent=0.50),
    "Ocean": dict(h=205, surface=0.30, accent=0.75),
    "Teal": dict(h=176, surface=0.26, accent=0.70),
    "Forest": dict(h=128, surface=0.20, accent=0.45),
    "Sepia": dict(h=34, surface=0.42, accent=0.72, lbg=0.945),
    "Sunset": dict(h=14, surface=0.30, accent=0.80),
    "Rose": dict(h=336, surface=0.28, accent=0.65),
    "Midnight": dict(h=222, surface=0.40, accent=0.75),
    "Graphite": dict(h=215, surface=0.05, accent=0.14),
    "AMOLED": dict(h=262, surface=0.15, accent=0.50),
}
MODES = ["Light", "Dark", "System"]


def _hex(h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def _hls(color: str) -> tuple[float, float, float]:
    c = QColor(color)
    h, l, s = colorsys.rgb_to_hls(c.redF(), c.greenF(), c.blueF())
    return h * 360, l, s


def make_palette(name: str, dark: bool, accent: str | None = None) -> dict:
    """Full palette for a colour family in light or dark mode. `accent` overrides the
    primary colour (used by the Custom theme); the surfaces then follow its hue."""
    spec = COLOURS.get(name, COLOURS["Lavender"])
    h, ss, sa = spec["h"], spec["surface"], spec["accent"]
    if accent:
        h, al, sa = _hls(accent)
        ss = min(0.35, max(0.12, sa * 0.4))
    if dark:
        acc = _hex(h, sa, 0.78) if not accent else _hex(h, sa, max(al, 0.70))
        pal = dict(bg=_hex(h, ss, .075), panel=_hex(h, ss, .115), sel=_hex(h, min(.5, ss * 2.2), .22),
                   hover=_hex(h, min(.5, ss * 1.5), .155), border=_hex(h, ss * 1.3, .25),
                   outline=_hex(h, ss, .55), fg=_hex(h, min(ss, .15), .91),
                   muted=_hex(h, min(ss, .12), .72), desk=_hex(h, ss, .045),
                   accent=acc, accent_hi=_hex(h, sa, .86), on_accent=_hex(h, sa, .16))
        if name == "AMOLED" and not accent:
            pal.update(bg="#000000", panel="#0b0b0d", hover="#141416", border="#26262a",
                       sel="#1f1c2b", desk="#000000", outline="#6e6a78")
    else:
        lb = spec.get("lbg", 0.985)
        acc = _hex(h, sa, 0.40) if not accent else _hex(h, sa, min(al, 0.45))
        pal = dict(bg=_hex(h, ss, lb), panel=_hex(h, ss, lb - .04), sel=_hex(h, min(.6, ss * 1.6), lb - .095),
                   hover=_hex(h, ss * 1.2, lb - .06), border=_hex(h, ss, lb - .155),
                   outline=_hex(h, ss * .8, .52), fg=_hex(h, .2, .11), muted=_hex(h, .1, .34),
                   desk=_hex(h, ss, lb - .085), accent=acc, accent_hi=_hex(h, sa, .48),
                   on_accent="#ffffff")
        if name == "AMOLED" and not accent:
            pal.update(bg="#ffffff", panel="#f2f2f4", hover="#e9e9ec", border="#d4d4d8",
                       sel="#e6e1f5", desk="#e4e4e8", fg="#000000", muted="#4a4a52")
    pal["link"] = pal["accent"]
    return pal


def theme_key(colour: str, dark: bool) -> str:
    return f"{colour} {'Dark' if dark else 'Light'}"


THEMES: dict[str, dict] = {}
for _name in COLOURS:
    for _dark in (False, True):
        THEMES[theme_key(_name, _dark)] = make_palette(_name, _dark)
# short names used by older code and saved settings
THEMES.update({"Light": THEMES["Lavender Light"], "Dark": THEMES["Lavender Dark"],
               "Sepia": THEMES["Sepia Light"], "Forest": THEMES["Forest Light"],
               "Midnight": THEMES["Midnight Dark"]})


def ensure_theme(colour: str, dark: bool, custom_accent: str = "#6750a4") -> str:
    """Name of the theme for (colour, mode); builds the Custom one from `custom_accent`."""
    if colour == "Custom":
        key = theme_key("Custom", dark)
        THEMES[key] = make_palette("Lavender", dark, accent=custom_accent)
        return key
    key = theme_key(colour, dark)
    if key not in THEMES:
        key = theme_key("Lavender", dark)
    return key


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


def build_qss(t: dict, scale: float = 1.0) -> str:
    """Material Design 3 styling: tonal surfaces, pill buttons, rounded cards and fields."""
    return f"""
QWidget {{ color: {t['fg']}; }}
QMainWindow, QDialog, #page {{ background: {t['bg']}; }}
#sidePanel {{ background: {t['panel']}; }}
QLabel {{ background: transparent; }}
QLabel#h1 {{ font-size: {int(28 * scale)}px; font-weight: 400; }}
QLabel#h2 {{ font-size: {int(16 * scale)}px; font-weight: 500; }}
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
QPushButton#seg {{ background: transparent; color: {t['fg']}; border: none; border-radius: 0;
                    padding: 8px 22px; min-height: 20px; font-weight: 600; }}
QPushButton#seg:hover {{ background: {t['hover']}; }}
QPushButton#seg:checked {{ background: {t['sel']}; color: {t['fg']}; border: none; }}
QPushButton#segFirst {{ background: transparent; color: {t['fg']}; border: none; padding: 8px 22px;
                       border-top-left-radius: 16px; border-bottom-left-radius: 16px; min-height: 20px;
                       border-top-right-radius: 0; border-bottom-right-radius: 0; font-weight: 600; }}
QPushButton#segFirst:hover {{ background: {t['hover']}; }}
QPushButton#segFirst:checked {{ background: {t['sel']}; border: none; }}
QPushButton#segLast {{ background: transparent; color: {t['fg']}; border: none; padding: 8px 22px;
                      border-top-right-radius: 16px; border-bottom-right-radius: 16px; min-height: 20px;
                      border-top-left-radius: 0; border-bottom-left-radius: 0; font-weight: 600; }}
QPushButton#segLast:hover {{ background: {t['hover']}; }}
QPushButton#segLast:checked {{ background: {t['sel']}; border: none; }}
QFrame#segFrame {{ border: 1px solid {t['outline']}; border-radius: 20px; background: transparent; }}
QToolButton#themeCard {{ background: {t['panel']}; border: 1px solid {t['border']}; border-radius: 16px;
                        padding: 8px 8px 6px 8px; font-weight: 600; }}
QToolButton#themeCard:hover {{ background: {t['hover']}; border-color: {t['outline']}; }}
QToolButton#themeCard:checked {{ background: {t['sel']}; border: 2px solid {t['accent']}; padding: 7px 7px 5px 7px; }}
QTabWidget::pane {{ border: none; background: transparent; top: -1px; }}
QTabWidget > QWidget {{ background: transparent; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; color: {t['muted']}; padding: 9px 18px; margin-right: 4px;
               border: none; border-bottom: 2px solid transparent; font-weight: 600; }}
QTabBar::tab:hover {{ background: {t['hover']}; color: {t['fg']}; border-top-left-radius: 8px;
                     border-top-right-radius: 8px; }}
QTabBar::tab:selected {{ color: {t['accent']}; border-bottom: 2px solid {t['accent']}; }}
QToolTip {{ background: {t['fg']}; color: {t['bg']}; border: none; border-radius: 4px;
            padding: 6px 10px; }}
"""

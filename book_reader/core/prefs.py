"""Reading preferences persisted with QSettings."""
from PySide6.QtCore import QSettings
from PySide6.QtGui import QFontDatabase

from book_reader.themes import THEMES


class Prefs:
    """Reading preferences, persisted with QSettings."""

    def __init__(self):
        self.s = QSettings("epub-reader", "EpubReader")
        families = set(QFontDatabase.families())
        font = next(
            (f for f in ("Georgia", "Palatino Linotype", "Cambria", "Charter",
                         "Times New Roman", "DejaVu Serif") if f in families),
            "serif",
        )
        defaults = dict(theme="Light", font_family=font, font_size=14,
                        line_height=160, text_width=760, justify=False,
                        pdf_zoom=0.0, pdf_invert=False,
                        show_reminder=True, daily_goal=20)  # pdf_zoom 0 = fit width
        self.v = {k: self.s.value(k, d, type=type(d)) for k, d in defaults.items()}
        if self.v["theme"] not in THEMES:
            self.v["theme"] = "Light"

    def set(self, key, value):
        self.v[key] = value
        self.s.setValue(key, value)

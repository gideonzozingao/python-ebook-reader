"""Reading preferences persisted with QSettings."""
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication

from book_reader.core.features import DEFAULTS as FEATURE_DEFAULTS
from book_reader.themes import COLOURS, ensure_theme


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
                        show_reminder=True, daily_goal=20, roadmap_on_open=True,
                        auto_update_check=True, last_update_check=0.0, skipped_version="",
                        sync_folder="", sync_enabled=False,
                        ui_font="", ui_font_size=10,
                        theme_mode="Light", theme_colour="Lavender", custom_accent="#6750a4",
                        last_backup="", **FEATURE_DEFAULTS)  # pdf_zoom 0 = fit width
        self.defaults = defaults
        self.v = {k: self.s.value(k, d, type=type(d)) for k, d in defaults.items()}
        if not self.s.contains("theme_mode"):  # settings saved by an older version
            legacy = {"Light": ("Light", "Lavender"), "Dark": ("Dark", "Lavender"),
                      "Sepia": ("Light", "Sepia"), "Forest": ("Light", "Forest"),
                      "Midnight": ("Dark", "Midnight")}
            mode, colour = legacy.get(str(self.v["theme"]), ("Light", "Lavender"))
            self.v["theme_mode"], self.v["theme_colour"] = mode, colour
            self.s.setValue("theme_mode", mode)
            self.s.setValue("theme_colour", colour)
        self.resolve()

    @staticmethod
    def system_is_dark() -> bool:
        """True when the operating system is set to dark mode (Qt 6.5 or newer)."""
        try:
            return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except AttributeError:
            return False

    def is_dark(self) -> bool:
        mode = self.v["theme_mode"]
        return self.system_is_dark() if mode == "System" else mode == "Dark"

    def resolve(self):
        """Work out the theme name (e.g. "Ocean Dark") from mode, colour and custom accent."""
        colour = self.v["theme_colour"] if (self.v["theme_colour"] in COLOURS
                                            or self.v["theme_colour"] == "Custom") else "Lavender"
        self.v["theme"] = ensure_theme(colour, self.is_dark(), str(self.v["custom_accent"]))

    def set(self, key, value):
        self.v[key] = value
        self.s.setValue(key, value)
        if key in ("theme_mode", "theme_colour", "custom_accent"):
            self.resolve()

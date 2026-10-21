"""Appearance picker: Light / Dark / System mode, colour cards with live previews, fonts.
Everything is stored once in the app preferences, so it applies to every screen and book."""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QFontComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from book_reader.core.prefs import Prefs
from book_reader.themes import COLOURS, MODES, THEMES, make_palette, theme_key
from book_reader.ui.widgets.theme_preview import make_theme_preview


class AppearancePanel(QWidget):
    changed = Signal()
    KEYS = ("theme_mode", "theme_colour", "custom_accent", "ui_font", "ui_font_size", "font_family",
            "font_size", "line_height", "text_width", "justify", "pdf_invert")
    COLUMNS = 4

    def __init__(self, prefs: Prefs):
        super().__init__()
        self.prefs = prefs
        self._syncing = True
        self.sliders: dict = {}
        self.setMinimumSize(700, 650)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 12)
        lay.setSpacing(8)
        title = QLabel("Appearance")
        title.setObjectName("h1")
        lay.addWidget(title)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._theme_tab(), "Colours")
        self.tabs.addTab(self._fonts_tab(), "Fonts && reading")
        lay.addWidget(self.tabs, 1)
        foot = QHBoxLayout()
        note = QLabel("Applies to the whole app and every book.")
        note.setObjectName("muted")
        reset = QPushButton("Reset")
        reset.setObjectName("link")
        reset.setToolTip("Back to the default theme and fonts")
        reset.clicked.connect(self.reset)
        foot.addWidget(note)
        foot.addStretch()
        foot.addWidget(reset)
        lay.addLayout(foot)
        self._syncing = False
        self.sync()

    # -- colours tab ---------------------------------------------------------------- #

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted")
        return label

    def _theme_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self._label("Mode"))
        frame = QFrame()
        frame.setObjectName("segFrame")
        seg = QHBoxLayout(frame)
        seg.setContentsMargins(1, 1, 1, 1)
        seg.setSpacing(0)
        self.mode_group = QButtonGroup(self)
        self.mode_buttons: dict[str, QPushButton] = {}
        for i, mode in enumerate(MODES):
            b = QPushButton(mode)
            b.setCheckable(True)
            b.setObjectName("segFirst" if i == 0 else "segLast" if i == len(MODES) - 1 else "seg")
            b.clicked.connect(lambda _=False, m=mode: self._set_mode(m))
            self.mode_group.addButton(b)
            self.mode_buttons[mode] = b
            seg.addWidget(b)
        row = QHBoxLayout()
        row.addWidget(frame)
        self.mode_note = QLabel("")
        self.mode_note.setObjectName("muted")
        row.addSpacing(12)
        row.addWidget(self.mode_note)
        row.addStretch()
        lay.addLayout(row)

        lay.addSpacing(6)
        lay.addWidget(self._label("Colour"))
        grid = QGridLayout()
        grid.setSpacing(10)
        self.colour_group = QButtonGroup(self)
        self.cards: dict[str, QToolButton] = {}
        for i, name in enumerate([*COLOURS, "Custom…"]):
            card = QToolButton()
            card.setObjectName("themeCard")
            card.setCheckable(True)
            card.setText(name)
            card.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            card.setIconSize(QSize(132, 84))
            card.setMinimumHeight(124)  # preview + name under it
            card.clicked.connect(lambda _=False, n=name: self._pick_colour(n))
            self.colour_group.addButton(card)
            self.cards[name] = card
            grid.addWidget(card, i // self.COLUMNS, i % self.COLUMNS)
        lay.addLayout(grid)
        lay.addStretch()
        return page

    def _palette_for(self, name: str) -> dict:
        dark = self.prefs.is_dark()
        if name in ("Custom", "Custom…"):
            return make_palette("Lavender", dark, accent=str(self.prefs.v["custom_accent"]))
        return THEMES[theme_key(name, dark)]

    def _refresh_previews(self):
        for name, card in self.cards.items():
            card.setIcon(QIcon(make_theme_preview(self._palette_for(name))))
        mode = self.prefs.v["theme_mode"]
        self.mode_note.setText(f"Following your system: currently {'dark' if self.prefs.system_is_dark() else 'light'}"
                               if mode == "System" else "")

    def _set_mode(self, mode: str):
        self._set("theme_mode", mode)
        self._refresh_previews()

    def _pick_colour(self, name: str):
        if name == "Custom…":
            color = QColorDialog.getColor(QColor(str(self.prefs.v["custom_accent"])), self,
                                          "Choose an accent colour")
            if not color.isValid():
                self.sync()
                return
            self.prefs.set("custom_accent", color.name())
            name = "Custom"
        self._set("theme_colour", name)
        self._refresh_previews()

    # -- fonts tab -------------------------------------------------------------------- #

    def _fonts_tab(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 12, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(self._label("Interface font"))
        row = QHBoxLayout()
        self.ui_font_box = QFontComboBox()
        self.ui_font_box.currentFontChanged.connect(lambda f: self._set("ui_font", f.family()))
        row.addWidget(self.ui_font_box, 1)
        system = QPushButton("System default")
        system.setObjectName("link")
        system.clicked.connect(lambda: (self._set("ui_font", ""), self.sync()))
        row.addWidget(system)
        lay.addLayout(row)
        self._slider(lay, "Interface size", 8, 18, "ui_font_size", " pt")

        lay.addSpacing(8)
        lay.addWidget(self._label("Reading text (EPUB and Markdown)"))
        self.font_box = QFontComboBox()
        self.font_box.currentFontChanged.connect(lambda f: self._set("font_family", f.family()))
        lay.addWidget(self.font_box)
        self.size_slider = self._slider(lay, "Text size", 9, 34, "font_size", " pt")
        self._slider(lay, "Line spacing", 110, 220, "line_height", "%")
        self._slider(lay, "Page width", 480, 1200, "text_width", " px")
        self.justify = QCheckBox("Justify text")
        self.justify.toggled.connect(lambda on: self._set("justify", bool(on)))
        lay.addWidget(self.justify)
        lay.addSpacing(8)
        self.invert = QCheckBox("Invert PDF colours (night reading)")
        self.invert.toggled.connect(lambda on: self._set("pdf_invert", bool(on)))
        lay.addWidget(self.invert)
        lay.addStretch()
        return page

    def _slider(self, lay, name, lo, hi, key, suffix):
        row = QHBoxLayout()
        row.addWidget(QLabel(name))
        row.addStretch()
        val = QLabel("")
        val.setObjectName("muted")
        row.addWidget(val)
        lay.addLayout(row)
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.valueChanged.connect(lambda x: (val.setText(f"{x}{suffix}"), self._set(key, x)))
        lay.addWidget(s)
        self.sliders[key] = (s, val, suffix)
        return s

    # -- state ------------------------------------------------------------------------- #

    def sync(self):
        """Show the current preferences."""
        v = self.prefs.v
        self._syncing = True
        try:
            self.mode_buttons.get(v["theme_mode"], self.mode_buttons["Light"]).setChecked(True)
            current = "Custom…" if v["theme_colour"] == "Custom" else v["theme_colour"]
            self.cards.get(current, self.cards["Lavender"]).setChecked(True)
            self._refresh_previews()
            self.ui_font_box.setCurrentFont(QFont(v["ui_font"] or QApplication.font().family()))
            self.font_box.setCurrentFont(QFont(v["font_family"]))
            for key, (s, val, suffix) in self.sliders.items():
                s.setValue(int(v[key]))
                val.setText(f"{int(v[key])}{suffix}")
            self.justify.setChecked(bool(v["justify"]))
            self.invert.setChecked(bool(v["pdf_invert"]))
        finally:
            self._syncing = False

    def reset(self):
        for key in self.KEYS:
            self.prefs.set(key, self.prefs.defaults[key])
        self.sync()
        self.changed.emit()

    def _set(self, key, value):
        if self._syncing:
            return
        self.prefs.set(key, value)
        self.changed.emit()

"""Appearance panel shared by every page: colour theme, interface font, reading text.
Settings are stored once, in the app preferences, so they apply to every book and screen."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFontComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from book_reader.core.prefs import Prefs
from book_reader.themes import THEMES


class AppearancePanel(QWidget):
    changed = Signal()
    KEYS = ("theme", "ui_font", "ui_font_size", "font_family", "font_size", "line_height",
            "text_width", "justify", "pdf_invert")

    def __init__(self, prefs: Prefs):
        super().__init__()
        self.prefs = prefs
        self._syncing = True
        self.sliders: dict = {}
        self.setMinimumWidth(350)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("Appearance")
        title.setObjectName("h2")
        head.addWidget(title)
        head.addStretch()
        reset = QPushButton("Reset")
        reset.setObjectName("link")
        reset.setToolTip("Back to the default theme and fonts")
        reset.clicked.connect(self.reset)
        head.addWidget(reset)
        lay.addLayout(head)
        note = QLabel("Applies to the whole app and every book.")
        note.setObjectName("muted")
        lay.addWidget(note)

        lay.addWidget(self._section("Colour theme"))
        grid = QGridLayout()
        grid.setSpacing(6)
        self.group = QButtonGroup(self)
        self.theme_buttons: dict[str, QPushButton] = {}
        for i, name in enumerate(THEMES):
            b = QPushButton(name)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, n=name: self._set("theme", n))
            self.group.addButton(b)
            self.theme_buttons[name] = b
            grid.addWidget(b, i // 3, i % 3)
        lay.addLayout(grid)

        lay.addWidget(self._section("Interface font"))
        row = QHBoxLayout()
        self.ui_font_box = QFontComboBox()
        self.ui_font_box.currentFontChanged.connect(lambda f: self._set("ui_font", f.family()))
        row.addWidget(self.ui_font_box, 1)
        system = QPushButton("System")
        system.setObjectName("link")
        system.setToolTip("Use the system's default font")
        system.clicked.connect(lambda: (self._set("ui_font", ""), self.sync()))
        row.addWidget(system)
        lay.addLayout(row)
        self._slider(lay, "Interface size", 8, 18, "ui_font_size", " pt")

        lay.addWidget(self._section("Reading text (EPUB and Markdown)"))
        self.font_box = QFontComboBox()
        self.font_box.currentFontChanged.connect(lambda f: self._set("font_family", f.family()))
        lay.addWidget(self.font_box)
        self.size_slider = self._slider(lay, "Text size", 9, 34, "font_size", " pt")
        self._slider(lay, "Line spacing", 110, 220, "line_height", "%")
        self._slider(lay, "Page width", 480, 1200, "text_width", " px")
        self.justify = QCheckBox("Justify text")
        self.justify.toggled.connect(lambda on: self._set("justify", bool(on)))
        lay.addWidget(self.justify)

        self.invert = QCheckBox("Invert PDF colours (night reading)")
        self.invert.toggled.connect(lambda on: self._set("pdf_invert", bool(on)))
        lay.addWidget(self.invert)
        self._syncing = False
        self.sync()

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        f = label.font()
        f.setBold(True)
        label.setFont(f)
        return label

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

    def sync(self):
        """Show the current preferences (call before the panel is displayed)."""
        v = self.prefs.v
        self._syncing = True
        try:
            for name, b in self.theme_buttons.items():
                b.setChecked(name == v["theme"])
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

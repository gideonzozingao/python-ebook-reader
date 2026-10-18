"""Appearance popup: theme, font, spacing (EPUB)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFontComboBox,
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

    def __init__(self, prefs: Prefs):
        super().__init__()
        self.prefs = prefs
        v = prefs.v
        self.setMinimumWidth(330)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        title = QLabel("Appearance")
        title.setObjectName("h2")
        lay.addWidget(title)

        row = QHBoxLayout()
        self.group = QButtonGroup(self)
        for name in THEMES:
            b = QPushButton(name)
            b.setCheckable(True)
            b.setChecked(name == v["theme"])
            b.clicked.connect(lambda _=False, n=name: self._set("theme", n))
            self.group.addButton(b)
            row.addWidget(b)
        lay.addLayout(row)

        lay.addWidget(QLabel("Font"))
        self.font_box = QFontComboBox()
        self.font_box.setCurrentFont(QFont(v["font_family"]))
        self.font_box.currentFontChanged.connect(lambda f: self._set("font_family", f.family()))
        lay.addWidget(self.font_box)

        self.size_slider = self._slider(lay, "Text size", 9, 34, v["font_size"],
                                        "font_size", " pt")
        self._slider(lay, "Line spacing", 110, 220, v["line_height"], "line_height", "%")
        self._slider(lay, "Page width", 480, 1200, v["text_width"], "text_width", " px")

        self.justify = QCheckBox("Justify text")
        self.justify.setChecked(v["justify"])
        self.justify.toggled.connect(lambda on: self._set("justify", bool(on)))
        lay.addWidget(self.justify)

    def _slider(self, lay, name, lo, hi, value, key, suffix):
        row = QHBoxLayout()
        row.addWidget(QLabel(name))
        row.addStretch()
        val = QLabel(f"{value}{suffix}")
        val.setObjectName("muted")
        row.addWidget(val)
        lay.addLayout(row)
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.setValue(value)
        s.valueChanged.connect(lambda x: (val.setText(f"{x}{suffix}"), self._set(key, x)))
        lay.addWidget(s)
        return s

    def _set(self, key, value):
        self.prefs.set(key, value)
        self.changed.emit()

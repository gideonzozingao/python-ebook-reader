"""Appearance dialog (Ctrl+, or the Aa button): changes apply live."""
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QVBoxLayout

from book_reader.ui.widgets.appearance_panel import AppearancePanel


class AppearanceDialog(QDialog):
    applied = Signal()   # something changed: restyle the app

    def __init__(self, parent, prefs):
        super().__init__(parent)
        self.setWindowTitle("Appearance — Book Reader")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 14)
        self.panel = AppearancePanel(prefs)
        lay.addWidget(self.panel)
        close = QPushButton("Close")
        close.setObjectName("tonal")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.setContentsMargins(24, 0, 24, 0)
        row.addStretch()
        row.addWidget(close)
        lay.addLayout(row)
        self._timer = QTimer(self, singleShot=True, interval=100)  # batch quick slider drags
        self._timer.timeout.connect(self.applied.emit)
        self.panel.changed.connect(self._timer.start)

    def done(self, result):
        if self._timer.isActive():
            self._timer.stop()
            self.applied.emit()
        super().done(result)

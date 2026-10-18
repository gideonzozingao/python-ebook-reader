"""Find bar shown above the EPUB reader (searches the whole book)."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget

from book_reader.ui.helpers import make_shortcut


class FindBar(QWidget):
    searchRequested = Signal(str, int)   # text, step (+1 next / -1 previous)
    closed = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("sidePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 14, 6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Find in book…")
        self.edit.setClearButtonEnabled(True)
        self.edit.setMinimumWidth(300)
        self.edit.returnPressed.connect(lambda: self.searchRequested.emit(self.edit.text(), 1))
        prev = QPushButton("◀")
        prev.setObjectName("link")
        prev.setToolTip("Previous match")
        prev.clicked.connect(lambda: self.searchRequested.emit(self.edit.text(), -1))
        nxt = QPushButton("▶")
        nxt.setObjectName("link")
        nxt.setToolTip("Next match (Enter)")
        nxt.clicked.connect(lambda: self.searchRequested.emit(self.edit.text(), 1))
        self.status = QLabel("")
        self.status.setObjectName("muted")
        close = QPushButton("✕")
        close.setObjectName("link")
        close.clicked.connect(self.closed.emit)
        lay.addWidget(self.edit)
        lay.addWidget(prev)
        lay.addWidget(nxt)
        lay.addWidget(self.status)
        lay.addStretch()
        lay.addWidget(close)
        make_shortcut(self, "Escape", self.closed.emit)

    def focus(self):
        self.edit.setFocus()
        self.edit.selectAll()

    def set_status(self, text: str):
        self.status.setText(text)

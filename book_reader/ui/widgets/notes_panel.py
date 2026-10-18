"""Highlights & notes side panel (EPUB)."""
import textwrap

from datetime import datetime

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from book_reader.themes import HIGHLIGHT_COLORS
from book_reader.ui.helpers import fit_cards
from book_reader.utils import pretty


class NoteCard(QFrame):
    clicked = Signal(int)
    editRequested = Signal(int)
    deleteRequested = Signal(int)

    def __init__(self, row: dict, chapter: str, t: dict):
        super().__init__()
        self.nid = row["id"]
        self.setObjectName("noteCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        color = HIGHLIGHT_COLORS.get(row["color"], "#ffd54f")
        self.setStyleSheet(
            f"QFrame#noteCard {{ background:{t['bg']}; border:1px solid {t['border']};"
            f" border-left:4px solid {color}; border-radius:16px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 10, 8)
        lay.setSpacing(6)

        if row["quote"]:
            q = QLabel("“" + textwrap.shorten(pretty(row["quote"]).replace("\n", " "), 230,
                                              placeholder="…") + "”")
            q.setWordWrap(True)
            f = q.font()
            f.setItalic(True)
            q.setFont(f)
            lay.addWidget(q)
        if row["note"]:
            n = QLabel(row["note"])
            n.setWordWrap(True)
            lay.addWidget(n)

        foot = QHBoxLayout()
        meta = QLabel(f"{chapter}  ·  {datetime.fromtimestamp(row['created_at']):%b %d}")
        meta.setObjectName("muted")
        foot.addWidget(meta)
        foot.addStretch()
        for text, sig in (("Edit", self.editRequested), ("Delete", self.deleteRequested)):
            b = QPushButton(text)
            b.setObjectName("link")
            b.clicked.connect(lambda _=False, s=sig: s.emit(self.nid))
            foot.addWidget(b)
        lay.addLayout(foot)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.nid)


class NotesPanel(QWidget):
    jumpRequested = Signal(int)
    editRequested = Signal(int)
    deleteRequested = Signal(int)
    exportRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("sidePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(300)
        self._last = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 8, 10)
        lay.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel("Notes & highlights")
        title.setObjectName("h2")
        head.addWidget(title)
        head.addStretch()
        export = QPushButton("Export")
        export.setObjectName("link")
        export.clicked.connect(self.exportRequested.emit)
        head.addWidget(export)
        lay.addLayout(head)

        self.only_chapter = QCheckBox("This chapter only")
        self.only_chapter.toggled.connect(lambda _=False: self._rerender())
        lay.addWidget(self.only_chapter)

        self.empty = QLabel("Select text while reading, then right-click to highlight "
                            "or add a note (Ctrl+N).")
        self.empty.setObjectName("muted")
        self.empty.setWordWrap(True)
        lay.addWidget(self.empty)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.holder = QWidget()
        self.vbox = QVBoxLayout(self.holder)
        self.vbox.setContentsMargins(0, 0, 6, 0)
        self.vbox.setSpacing(10)
        self.scroll.setWidget(self.holder)
        lay.addWidget(self.scroll)

    def refresh(self, notes, chapter_label, current_spine, t):
        self._last = (notes, chapter_label, current_spine, t)
        self._rerender()

    def _rerender(self):
        if not self._last:
            return
        notes, chapter_label, current, t = self._last
        while self.vbox.count():
            item = self.vbox.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        shown = [n for n in notes if not self.only_chapter.isChecked()
                 or n["spine_index"] == current]
        self.empty.setVisible(not shown)
        for n in shown:
            card = NoteCard(n, chapter_label(n["spine_index"]), t)
            card.clicked.connect(self.jumpRequested.emit)
            card.editRequested.connect(self.editRequested.emit)
            card.deleteRequested.connect(self.deleteRequested.emit)
            self.vbox.addWidget(card)
        self.vbox.addStretch()
        QTimer.singleShot(0, lambda: fit_cards(self.scroll, self.vbox, NoteCard))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        fit_cards(self.scroll, self.vbox, NoteCard)

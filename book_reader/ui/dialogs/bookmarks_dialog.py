"""Manage a book's bookmarks: jump, rename, delete."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from book_reader.services.journal import ref_text


class BookmarksDialog(QDialog):
    jumpRequested = Signal(int, float)  # spine/page index, ratio

    def __init__(self, parent, library, book_id: int, fmt: str):
        super().__init__(parent)
        self.library, self.book_id, self.fmt = library, book_id, fmt
        self.setWindowTitle("Bookmarks")
        self.setMinimumSize(480, 420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        head = QLabel("Bookmarks")
        head.setObjectName("h2")
        lay.addWidget(head)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _it: self._go())
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        for text, slot, name in (("Delete", self._delete, ""), ("Rename…", self._rename, ""),
                                 ("Go to", self._go, "primary")):
            b = QPushButton(text)
            if name:
                b.setObjectName(name)
            b.clicked.connect(lambda _=False, s=slot: s())
            row.addWidget(b)
        row.insertStretch(2)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        row.insertWidget(0, close)
        lay.addLayout(row)
        self._fill()

    def _fill(self):
        self.list.clear()
        for r in self.library.bookmarks(self.book_id):
            ref = ref_text(r["chapter"], r["page"], r["page_total"], self.fmt)
            item = QListWidgetItem(f"{r['label'] or 'Bookmark'}\n{ref}")
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _current(self):
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _go(self):
        bid = self._current()
        if bid is None:
            return
        row = next((r for r in self.library.bookmarks(self.book_id) if r["id"] == bid), None)
        if row is not None:
            self.jumpRequested.emit(row["spine_index"], row["scroll_ratio"])
            self.accept()

    def _rename(self):
        bid = self._current()
        if bid is None:
            return
        row = next(r for r in self.library.bookmarks(self.book_id) if r["id"] == bid)
        text, ok = QInputDialog.getText(self, "Rename bookmark", "Label:",
                                        QLineEdit.EchoMode.Normal, row["label"])
        if ok:
            self.library.rename_bookmark(bid, text.strip())
            self._fill()

    def _delete(self):
        bid = self._current()
        if bid is not None:
            self.library.delete_bookmark(bid)
            self._fill()

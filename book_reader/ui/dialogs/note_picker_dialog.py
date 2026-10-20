"""Pick a note (from any book) to link to with [[note:ID|title]]."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from book_reader.services import notes_index, notes_text


class NotePickerDialog(QDialog):
    def __init__(self, parent, library, book_id=None):
        super().__init__(parent)
        self.markup: str | None = None
        self.setWindowTitle("Link to a note")
        self.setMinimumSize(520, 440)
        entries = [e for e in notes_index.all_entries(library) if e["kind"] == "note"]
        self.entries = sorted(entries, key=lambda e: (e["book_id"] != book_id, -e["created"]))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        lay.addWidget(QLabel("Choose the note to link to (notes in this book come first):"))
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search notes…")
        self.search.textChanged.connect(self._fill)
        lay.addWidget(self.search)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _it: self._choose())
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Insert link")
        ok.setObjectName("primary")
        ok.clicked.connect(self._choose)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)
        self._fill()

    def _fill(self, _=None):
        self.list.clear()
        for e in notes_index.search(self.entries, self.search.text()):
            item = QListWidgetItem(f"{notes_text.to_plain(e['text'], 90)}\n{e['book_title']}  ·  {e['chapter']}")
            item.setData(Qt.ItemDataRole.UserRole, e)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _choose(self):
        item = self.list.currentItem()
        if item is not None:
            e = item.data(Qt.ItemDataRole.UserRole)
            self.markup = notes_text.link_markup(e["id"], notes_text.to_plain(e["text"], 40))
            self.accept()

"""Notes hub: search across all books, daily review inbox, dashboard, export and sync."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTabWidget, QVBoxLayout

from book_reader.ui.widgets.dashboard_tab import DashboardTab
from book_reader.ui.widgets.export_tab import ExportTab
from book_reader.ui.widgets.inbox_tab import InboxTab
from book_reader.ui.widgets.notes_search_tab import NotesSearchTab


class NotesHubDialog(QDialog):
    openRequested = Signal(dict)   # entry to open in its book

    def __init__(self, parent, library, prefs, sync, theme: dict, tab: int = 0, book_id=None):
        super().__init__(parent)
        self.setWindowTitle("Notes")
        self.resize(1000, 700)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 12)
        self.tabs = QTabWidget()
        self.search = NotesSearchTab(library, theme)
        self.inbox = InboxTab(library, theme)
        self.dashboard = DashboardTab(library, theme)
        self.export = ExportTab(library, prefs, sync, theme)
        for widget, title in ((self.search, "🔎  Search"), (self.inbox, "📥  Inbox"),
                              (self.dashboard, "📊  Dashboard"), (self.export, "📤  Export && sync")):
            self.tabs.addTab(widget, title)
        lay.addWidget(self.tabs)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        lay.addLayout(row)
        for w in (self.search, self.inbox):
            w.openRequested.connect(self._open)
        self.tabs.currentChanged.connect(self._load)
        self.tabs.setCurrentIndex(tab)
        self._load(tab)
        if book_id is not None:
            self.export.set_scope(book_id)

    def _load(self, index: int):
        widget = self.tabs.widget(index)
        widget.reload()
        if widget is self.export:
            self.export.reload()

    def _open(self, entry: dict):
        self.openRequested.emit(entry)
        self.accept()

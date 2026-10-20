"""Notes dashboard: totals, activity chart, per-book counts and tags."""
from html import escape as esc

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from book_reader.services import notes_stats
from book_reader.ui.widgets.reading_chart import ReadingChart
from book_reader.utils import ago


class DashboardTab(QWidget):
    def __init__(self, library, theme: dict):
        super().__init__()
        self.lib, self.t = library, theme
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(10)
        self.cards = QHBoxLayout()
        lay.addLayout(self.cards)
        title = QLabel("Notes added per day (last 30 days)")
        title.setObjectName("h2")
        lay.addWidget(title)
        self.chart = ReadingChart()
        lay.addWidget(self.chart)
        row = QHBoxLayout()
        self.books = QTreeWidget()
        self.books.setRootIsDecorated(False)
        self.books.setHeaderLabels(["Book", "Notes", "Highlights", "Last note"])
        self.books.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.side = QTextBrowser()
        self.side.setMaximumWidth(260)
        self.side.setStyleSheet(f"QTextBrowser {{ background:{theme['panel']}; border:none; "
                                f"border-radius:8px; padding:6px; }}")
        row.addWidget(self.books, 1)
        row.addWidget(self.side)
        lay.addLayout(row, 1)

    def _card(self, value, label):
        box = QFrame()
        box.setObjectName("sidePanel")
        box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        v = QVBoxLayout(box)
        v.setContentsMargins(14, 10, 14, 10)
        big = QLabel(str(value))
        big.setObjectName("h1")
        small = QLabel(label)
        small.setObjectName("muted")
        v.addWidget(big)
        v.addWidget(small)
        return box

    def reload(self):
        d = notes_stats.dashboard(self.lib)
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for value, label in ((d["notes"], "book notes"), (d["highlights"], "highlights"),
                             (d["bookmarks"], "bookmarks"), (d["mindmaps"], "mind maps"),
                             (d["books_with_notes"], "books with notes"), (d["last_30"], "last 30 days")):
            self.cards.addWidget(self._card(value, label))
        self.chart.set_data(d["series"], 0, self.t)
        self.books.clear()
        for b in d["per_book"]:
            last = ago(b["last"]) if b["last"] else "—"
            self.books.addTopLevelItem(QTreeWidgetItem([b["title"], str(b["notes"]),
                                                        str(b["highlights"]), last]))
        t = self.t
        tags = "".join(f"<li>#{esc(n)} <span style='color:{t['muted']}'>({c})</span></li>" for n, c in d["tags"])
        topics = "".join(f"<li>{esc(n)} <span style='color:{t['muted']}'>({c})</span></li>" for n, c in d["topics"])
        self.side.setHtml(f"<b>Top tags</b><ul>{tags or '<li>none yet</li>'}</ul>"
                          f"<b>Note sections</b><ul>{topics or '<li>none yet</li>'}</ul>")

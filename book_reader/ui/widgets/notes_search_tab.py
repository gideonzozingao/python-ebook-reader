"""Search every note, highlight and PDF highlight in the library."""
from datetime import datetime
from html import escape as esc

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from book_reader.services import notes_index, notes_text


class NotesSearchTab(QWidget):
    openRequested = Signal(dict)   # the entry to open in its book

    def __init__(self, library, theme: dict):
        super().__init__()
        self.lib, self.t = library, theme
        self.entries: list[dict] = []
        self.results: list[dict] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(8)
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setObjectName("search")
        self.query.setPlaceholderText("Search all notes, highlights and tags…")
        self.query.setClearButtonEnabled(True)
        self.query.textChanged.connect(lambda _=None: self._run())
        row.addWidget(self.query, 1)
        self.tag = QComboBox()
        self.kind = QComboBox()
        self.kind.addItems(["All types", "Book notes", "Highlights"])
        self.book = QComboBox()
        for box in (self.tag, self.kind, self.book):
            box.currentIndexChanged.connect(lambda _=None: self._run())
            row.addWidget(box)
        lay.addLayout(row)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.list = QListWidget()
        self.list.setStyleSheet(
            f"QListWidget::item {{ padding: 8px 10px; border-bottom: 1px solid {theme['border']}; }}"
            f"QListWidget::item:selected {{ background:{theme['sel']}; color:{theme['fg']}; }}")
        self.list.currentItemChanged.connect(lambda *_: self._preview())
        self.list.itemDoubleClicked.connect(lambda _it: self._open())
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.anchorClicked.connect(self._link)
        self.view.setStyleSheet(f"QTextBrowser {{ background:{theme['bg']}; border:1px solid "
                                f"{theme['border']}; border-radius:8px; }}")
        split.addWidget(self.list)
        split.addWidget(self.view)
        split.setSizes([420, 420])
        lay.addWidget(split, 1)

        foot = QHBoxLayout()
        self.count = QLabel("")
        self.count.setObjectName("muted")
        foot.addWidget(self.count)
        foot.addStretch()
        open_btn = QPushButton("Open in book")
        open_btn.setObjectName("primary")
        open_btn.clicked.connect(self._open)
        foot.addWidget(open_btn)
        lay.addLayout(foot)

    def reload(self):
        self.entries = notes_index.all_entries(self.lib)
        for box in (self.tag, self.book):
            box.blockSignals(True)
            box.clear()
        self.tag.addItem("All tags", "")
        for name, n in notes_index.tag_counts(self.entries).most_common(60):
            self.tag.addItem(f"#{name} ({n})", name)
        self.book.addItem("All books", None)
        seen: dict = {}
        for e in self.entries:
            seen[e["book_id"]] = e["book_title"]
        for bid, title in sorted(seen.items(), key=lambda kv: kv[1].lower()):
            self.book.addItem(title, bid)
        for box in (self.tag, self.book):
            box.blockSignals(False)
        self._run()

    def set_query(self, text: str):
        self.query.setText(text)

    def _run(self):
        kind = {1: "note", 2: "highlight"}.get(self.kind.currentIndex(), "")
        self.results = notes_index.search(self.entries, self.query.text(), self.tag.currentData() or "",
                                          kind, self.book.currentData())[:500]
        self.list.clear()
        for e in self.results:
            where = e["chapter"] + (f" · p. {e['page']}" if e["page"] else "")
            item = QListWidgetItem(f"{e['book_title']}  ·  {where}\n"
                                   f"{notes_text.to_plain(e['text'] or e['quote'], 110)}")
            item.setData(Qt.ItemDataRole.UserRole, e)
            self.list.addItem(item)
        n = len(self.results)
        self.count.setText(f"{n} result{'' if n == 1 else 's'}" + ("  (showing the first 500)" if n >= 500 else ""))
        if n:
            self.list.setCurrentRow(0)
        else:
            self.view.setHtml(f"<p style='color:{self.t['muted']}'>No matching notes.</p>")

    def _current(self):
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _preview(self):
        e = self._current()
        if e is None:
            return
        t = self.t
        where = e["chapter"] + (f" · p. {e['page']}" if e["page"] else "")
        when = datetime.fromtimestamp(e["created"]).strftime("%d %b %Y")
        parts = [f"<p style='color:{t['muted']}'>{esc(e['book_title'])}  ·  {esc(where)}  ·  "
                 f"{esc(e['topic'])}  ·  {when}</p>"]
        if e["quote"]:
            parts.append(f"<blockquote><i>“{esc(e['quote'])}”</i></blockquote>")
        if e["text"]:
            parts.append(notes_text.render_html(e["text"], t))
        back = notes_index.backlinks(self.entries, e["id"]) if e["kind"] == "note" else []
        if back:
            links = "".join(f"<li><a href='note:{b['id']}'>↗ {esc(notes_text.to_plain(b['text'], 70))}</a>"
                            f" <span style='color:{t['muted']}'>({esc(b['book_title'])})</span></li>"
                            for b in back)
            parts.append(f"<p style='color:{t['muted']}'>Linked from:</p><ul>{links}</ul>")
        self.view.setHtml("".join(parts))

    def _link(self, url):
        target = url.toString()
        if target.startswith("tag:"):
            i = self.tag.findData(target[4:])
            if i >= 0:
                self.tag.setCurrentIndex(i)
        elif target.startswith("note:"):
            nid = int(target[5:])
            self.query.clear()
            self.tag.setCurrentIndex(0)
            self.kind.setCurrentIndex(0)
            self.book.setCurrentIndex(0)
            for k, e in enumerate(self.results):
                if e["kind"] == "note" and e["id"] == nid:
                    self.list.setCurrentRow(k)
                    break

    def _open(self):
        e = self._current()
        if e is not None:
            self.openRequested.emit(e)

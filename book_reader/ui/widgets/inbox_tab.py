"""Daily review inbox: a few old notes resurface each day, with growing intervals."""
from datetime import datetime
from html import escape as esc

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from book_reader.services import inbox, notes_text


class InboxTab(QWidget):
    openRequested = Signal(dict)
    changed = Signal()           # the number of due notes changed

    def __init__(self, library, theme: dict, per_session: int = 10):
        super().__init__()
        self.lib, self.t, self.per_session = library, theme, per_session
        self.queue: list[dict] = []
        self.i = self.reviewed = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(10)
        self.header = QLabel("")
        self.header.setObjectName("h2")
        lay.addWidget(self.header)
        self.meta = QLabel("")
        self.meta.setObjectName("muted")
        lay.addWidget(self.meta)
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.setStyleSheet(f"QTextBrowser {{ background:{theme['bg']}; border:1px solid "
                                f"{theme['border']}; border-radius:12px; padding:8px; }}")
        lay.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.buttons = {}
        for key, text, tip in (("again", "Again", "Show it again tomorrow"),
                               ("good", "Good", "Come back later"),
                               ("easy", "Easy", "Come back much later"),
                               ("archive", "Archive", "Never show this note again")):
            b = QPushButton(text)
            b.setObjectName("primary" if key == "good" else "")
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, k=key: self._answer(k))
            self.buttons[key] = b
            row.addWidget(b)
        row.addStretch()
        self.open_btn = QPushButton("Open in book")
        self.open_btn.setObjectName("tonal")
        self.open_btn.clicked.connect(self._open)
        row.addWidget(self.open_btn)
        lay.addLayout(row)

    def reload(self):
        self.queue = inbox.due_items(self.lib, self.per_session)
        self.total_due = inbox.count_due(self.lib)
        self.i = self.reviewed = 0
        self._show()

    def _show(self):
        done = self.i >= len(self.queue)
        for b in (*self.buttons.values(), self.open_btn):
            b.setEnabled(not done)
        if done:
            left = max(0, inbox.count_due(self.lib))
            self.header.setText("Inbox clear 🎉" if not left else f"{self.reviewed} reviewed")
            self.meta.setText("Nothing else is due today." if not left else
                              f"{left} more note{'' if left == 1 else 's'} waiting. Reopen the inbox for the next batch.")
            self.view.setHtml(f"<p style='color:{self.t['muted']}'>Notes come back after growing "
                              "intervals: 1, 3, 7, 14, 30, 60 and 120 days. New notes appear after a day.</p>")
            self.changed.emit()
            return
        e = self.queue[self.i]
        self.header.setText(f"Review {self.i + 1} of {len(self.queue)}"
                            f"  ·  {self.total_due} due in total")
        where = e["chapter"] + (f" · p. {e['page']}" if e["page"] else "")
        self.meta.setText(f"{e['book_title']}  ·  {where}  ·  {e['topic']}  ·  "
                          f"{datetime.fromtimestamp(e['created']):%d %b %Y}")
        parts = []
        if e["quote"]:
            parts.append(f"<blockquote><i>“{esc(e['quote'])}”</i></blockquote>")
        parts.append(notes_text.render_html(e["text"], self.t))
        self.view.setHtml("".join(parts))

    def _answer(self, action: str):
        if self.i < len(self.queue):
            inbox.answer(self.lib, self.queue[self.i], action)
            self.i += 1
            self.reviewed += 1
            self._show()

    def _open(self):
        if self.i < len(self.queue):
            self.openRequested.emit(self.queue[self.i])

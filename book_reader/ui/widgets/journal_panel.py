"""Book journal side panel: composer, live location, grouped note cards."""
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from book_reader.constants import DEFAULT_TOPICS, SUMMARY_MODES
from book_reader.services import notes_text
from book_reader.services.journal import (
    entry_meta,
    group_entries,
    note_entry,
    ref_text,
    topic_color,
)
from book_reader.ui.helpers import fit_cards, make_shortcut
from book_reader.ui.widgets.format_bar import FormatBar


class JournalCard(QFrame):
    clicked = Signal(int)
    editRequested = Signal(int)
    deleteRequested = Signal(int)
    linkActivated = Signal(str)   # note:ID or tag:name clicked inside the text

    def __init__(self, e: dict, meta: str, show_topic: bool, t: dict, backlinks: int = 0):
        super().__init__()
        self.nid = e["id"]
        self.setObjectName("journalCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        color = topic_color(e["topic"])
        self.setStyleSheet(
            f"QFrame#journalCard {{ background:{t['bg']}; border:1px solid {t['border']};"
            f" border-left:4px solid {color}; border-radius:16px; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 10, 8)
        lay.setSpacing(6)

        if show_topic:
            chip = QLabel(e["topic"])
            chip.setStyleSheet(f"color:{color}; font-weight:600;")
            lay.addWidget(chip)
        body = QLabel(notes_text.render_html(e["text"], t))
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        body.setOpenExternalLinks(False)
        body.linkActivated.connect(self.linkActivated.emit)
        lay.addWidget(body)

        foot = QHBoxLayout()
        info = QLabel(meta + (f"  ·  ↩ {backlinks}" if backlinks else ""))
        if backlinks:
            info.setToolTip(f"Linked from {backlinks} other note{'' if backlinks == 1 else 's'}")
        info.setObjectName("muted")
        info.setWordWrap(True)
        foot.addWidget(info, 1)
        for text, sig in (("Edit", self.editRequested), ("Delete", self.deleteRequested)):
            b = QPushButton(text)
            b.setObjectName("link")
            b.clicked.connect(lambda _=False, s=sig: s.emit(self.nid))
            foot.addWidget(b)
        lay.addLayout(foot)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.nid)


class BookNotesPanel(QWidget):
    """Side panel for the book journal.

    The reader page supplies `provider()` -> dict(spine_index, ratio, progress, chapter,
    page, total). The panel shows the live location, locks it when you start writing
    (so scrolling while you type doesn't change where the note is filed) and sends it
    along with the note.
    """

    addRequested = Signal(str, str, object)   # topic, text, location
    jumpRequested = Signal(int)
    editRequested = Signal(int)
    deleteRequested = Signal(int)
    summaryRequested = Signal()
    exportRequested = Signal()
    reviewRequested = Signal()
    linkRequested = Signal(str)   # a note: link was clicked
    mapRequested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("sidePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(400)
        self.provider = None
        self.link_picker = None   # set by the page: () -> '[[note:ID|title]]' or None
        self.fmt = "epub"
        self._locked: dict | None = None
        self._last = None
        self._shown_chapter = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 8, 10)
        lay.setSpacing(8)

        self._head_buttons: dict = {}
        head = QHBoxLayout()
        title = QLabel("Book notes")
        title.setObjectName("h2")
        head.addWidget(title)
        self.count = QLabel("")
        self.count.setObjectName("muted")
        head.addWidget(self.count)
        head.addStretch()
        for text, sig, tip in (("Review", self.reviewRequested, "Flashcards and quizzes from your notes"),
                               ("Summary", self.summaryRequested, "Review your notes as a book summary"),
                               ("Map", self.mapRequested, "Turn your notes into a mind map"),
                               ("Export", self.exportRequested, "Export notes (MD, HTML, TXT, PDF)")):
            b = QPushButton(text)
            b.setObjectName("link")
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, s=sig: s.emit())
            head.addWidget(b)
            self._head_buttons[text] = b
        lay.addLayout(head)

        row = QHBoxLayout()
        row.addWidget(QLabel("Section"))
        self.topic_box = QComboBox()
        self.topic_box.setEditable(True)
        self.topic_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.topic_box.addItems(DEFAULT_TOPICS)
        self.topic_box.setToolTip("Pick a section or type a new one")
        row.addWidget(self.topic_box, 1)
        lay.addLayout(row)

        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("Write a note about what you're reading…  (Ctrl+Enter to add)")
        self.edit.setMinimumHeight(90)
        self.edit.setMaximumHeight(150)
        self.edit.textChanged.connect(self._on_text)
        self.format_bar = FormatBar(self.edit, link_picker=self._pick_link)
        lay.addWidget(self.format_bar)
        lay.addWidget(self.edit)
        make_shortcut(self.edit, "Ctrl+Return", self._add)

        self.loc_label = QLabel("")
        self.loc_label.setObjectName("muted")
        self.loc_label.setWordWrap(True)
        lay.addWidget(self.loc_label)

        row2 = QHBoxLayout()
        self.btn_here = QPushButton("Use current position")
        self.btn_here.setObjectName("link")
        self.btn_here.clicked.connect(self._relock)
        self.btn_here.hide()
        row2.addWidget(self.btn_here)
        row2.addStretch()
        add = QPushButton("Add note")
        add.setObjectName("primary")
        add.clicked.connect(self._add)
        row2.addWidget(add)
        lay.addLayout(row2)

        frow = QHBoxLayout()
        frow.addWidget(QLabel("Group by"))
        self.group = QComboBox()
        self.group.addItems(SUMMARY_MODES)
        self.group.currentTextChanged.connect(lambda _=None: self._rerender())
        frow.addWidget(self.group, 1)
        lay.addLayout(frow)
        self.only_section = QCheckBox("This section only")
        self.only_section.toggled.connect(lambda _=False: self._rerender())
        lay.addWidget(self.only_section)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Search notes…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _=None: self._rerender())
        lay.addWidget(self.search)

        self.empty = QLabel("No notes for this book yet. Write one above — it is filed "
                            "automatically under the section and page you are reading.")
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
        lay.addWidget(self.scroll, 1)

    # -- book / location ----------------------------------------------------- #

    def set_features(self, review: bool, mindmap: bool):
        """Show the Review and Map buttons only when those features are switched on."""
        self._head_buttons["Review"].setVisible(review)
        self._head_buttons["Map"].setVisible(mindmap)

    def set_book(self, fmt: str, provider):
        self.fmt, self.provider = fmt, provider
        self._locked = None
        self._last = None
        self.edit.clear()
        self.search.clear()
        self.track()

    def focus_editor(self):
        self.edit.setFocus()

    def track(self):
        """Called by the reader whenever the reading position changes."""
        live = self.provider() if self.provider else None
        loc = self._locked or live
        if not loc:
            self.loc_label.setText("")
            self.btn_here.hide()
            return
        ref = ref_text(loc["chapter"], loc["page"], loc["total"], self.fmt)
        self.loc_label.setText(("🔒 Pinned to: " if self._locked else "📍 Auto-tracked: ") + ref)
        self.btn_here.setVisible(self._locked is not None)
        if (self.only_section.isChecked() and self._last and live
                and live["chapter"] != self._shown_chapter):
            self._rerender()

    def _on_text(self):
        has = bool(self.edit.toPlainText().strip())
        if has and self._locked is None and self.provider:
            self._locked = self.provider()
        elif not has:
            self._locked = None
        self.track()

    def _relock(self):
        self._locked = self.provider() if self.provider else None
        self.track()

    def _add(self):
        body = self.edit.toPlainText().strip()
        loc = self._locked or (self.provider() if self.provider else None)
        if not body or not loc:
            return
        topic = " ".join(self.topic_box.currentText().split()) or "General"
        self.addRequested.emit(topic, body, loc)
        self.edit.clear()  # unpins the location; the next note tracks live again

    # -- list ------------------------------------------------------------------ #

    def set_topics(self, extra):
        current = self.topic_box.currentText()
        seen, items = set(), []
        for name in [*DEFAULT_TOPICS, *sorted(extra, key=str.lower)]:
            if name and name.lower() not in seen:
                seen.add(name.lower())
                items.append(name)
        self.topic_box.blockSignals(True)
        self.topic_box.clear()
        self.topic_box.addItems(items)
        self.topic_box.setCurrentText(current or items[0])
        self.topic_box.blockSignals(False)

    def refresh(self, notes, t):
        self._last = (notes, t)
        self.set_topics({n["topic"] for n in notes if n["topic"]})
        self._rerender()

    def _rerender(self):
        if not self._last:
            return
        notes, t = self._last
        while self.vbox.count():
            item = self.vbox.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        live = self.provider() if self.provider else None
        self._shown_chapter = live["chapter"] if live else None
        q = self.search.text().strip().lower()
        backlinks: dict = {}
        for n in notes:
            for target in notes_text.extract_links(n["body"] or ""):
                backlinks[target] = backlinks.get(target, 0) + 1
        shown = []
        for n in notes:
            if (self.only_section.isChecked() and live
                    and (n["chapter"] or "") != live["chapter"]):
                continue
            if q and not any(q in (n[k] or "").lower() for k in ("body", "topic", "chapter")):
                continue
            shown.append(note_entry(n))
        total = len(notes)
        self.count.setText(f"{total} note{'' if total == 1 else 's'}" if total else "")
        self.empty.setVisible(not shown)
        if total and not shown:
            self.empty.setText("No notes match the current filter.")
        else:
            self.empty.setText("No notes for this book yet. Write one above — it is filed "
                               "automatically under the section and page you are reading.")
        mode = self.group.currentText()
        for title, items in group_entries(shown, mode):
            head = QLabel(f"{title}  ({len(items)})")
            f = head.font()
            f.setBold(True)
            head.setFont(f)
            head.setWordWrap(True)
            self.vbox.addWidget(head)
            for e in items:
                card = JournalCard(e, entry_meta(e, mode, self.fmt, topic=False),
                                   mode != "Topic", t, backlinks.get(e["id"], 0))
                card.linkActivated.connect(self._on_link)
                card.clicked.connect(self.jumpRequested.emit)
                card.editRequested.connect(self.editRequested.emit)
                card.deleteRequested.connect(self.deleteRequested.emit)
                self.vbox.addWidget(card)
        self.vbox.addStretch()
        QTimer.singleShot(0, lambda: fit_cards(self.scroll, self.vbox, JournalCard))

    def _pick_link(self):
        return self.link_picker() if self.link_picker else None

    def _on_link(self, url: str):
        if url.startswith("tag:"):
            self.search.setText("#" + url[4:])  # filter this book's notes by the tag
        else:
            self.linkRequested.emit(url)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        fit_cards(self.scroll, self.vbox, JournalCard)

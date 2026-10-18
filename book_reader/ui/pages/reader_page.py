"""EPUB reader page."""
import webbrowser

from pathlib import Path

from PySide6.QtCore import QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from book_reader.core.books import open_text_book
from book_reader.core.epub import EpubBook
from book_reader.core.library import Library
from book_reader.core.prefs import Prefs
from book_reader.core.tracker import ReadingTracker
from book_reader.themes import HIGHLIGHT_COLORS, THEMES
from book_reader.ui.dialogs.note_dialog import NoteDialog
from book_reader.ui.helpers import make_shortcut
from book_reader.ui.pages.mixins import (
    BookmarksMixin,
    JournalMixin,
    LookupMixin,
    MindMapMixin,
    ReadingListMixin,
)
from book_reader.ui.widgets.appearance_panel import AppearancePanel
from book_reader.ui.widgets.epub_view import Reader
from book_reader.ui.widgets.find_bar import FindBar
from book_reader.ui.widgets.notes_panel import NotesPanel
from book_reader.ui.widgets.status_bar import StatusBar
from book_reader.utils import pretty


class ReaderPage(ReadingListMixin, JournalMixin, BookmarksMixin, LookupMixin, MindMapMixin,
                 QWidget):
    backRequested = Signal()
    prefsChanged = Signal()
    book_format = "epub"

    def __init__(self, library: Library, prefs: Prefs, tracker: ReadingTracker):
        super().__init__()
        self.library, self.prefs, self.tracker = library, prefs, tracker
        self.book: EpubBook | None = None
        self.book_id: int | None = None
        self.spine_index = 0
        self.titles: dict[str, str] = {}
        self.notes: list[dict] = []
        self.toc_items: list = []
        self._resolved: dict[int, tuple[int, int]] = {}
        self.setObjectName("page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.reader = Reader()
        self.notes_panel = NotesPanel()
        self.appearance = AppearancePanel(prefs)
        self._init_journal()
        self._init_bookmarks()
        self._find_query, self._find_hits, self._find_i, self._find_pos = "", [], -1, None
        self._build_toolbar(root)
        self.find_bar = FindBar()
        self.find_bar.hide()
        self.find_bar.searchRequested.connect(self.run_find)
        self.find_bar.closed.connect(lambda: self.act_find.setChecked(False))
        root.addWidget(self.find_bar)

        self.toc = QTreeWidget()
        self.toc.setHeaderHidden(True)
        self.toc.itemClicked.connect(self.on_toc_clicked)
        self.toc_panel = QWidget()
        self.toc_panel.setObjectName("sidePanel")
        self.toc_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.toc_panel.setMinimumWidth(240)
        tl = QVBoxLayout(self.toc_panel)
        tl.setContentsMargins(14, 14, 6, 6)
        head = QLabel("Contents")
        head.setObjectName("h2")
        tl.addWidget(head)
        tl.addWidget(self.toc)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.addWidget(self.toc_panel)
        self.splitter.addWidget(self.reader)
        self.splitter.addWidget(self.notes_panel)
        self.splitter.addWidget(self.journal)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizes([280, 800, 330, 350])
        self.toc_panel.hide()
        self.notes_panel.hide()
        self.journal.hide()
        root.addWidget(self.splitter, 1)

        self.status = StatusBar()
        root.addWidget(self.status)
        self.tracker.tick.connect(self.status.set_time)
        self.tracker.addedToReading.connect(self._on_auto_reading)

        # wiring
        self.reader.anchorClicked.connect(self.on_link)
        self.reader.nextRequested.connect(self.next_chapter)
        self.reader.prevRequested.connect(lambda: self.prev_chapter(to_end=True))
        self.reader.zoomRequested.connect(self.change_font)
        self.reader.highlightRequested.connect(self.quick_highlight)
        self.reader.lookupRequested.connect(self.lookup_text)
        self.reader.noteRequested.connect(self.add_note)
        self.reader.editNoteRequested.connect(self.edit_note)
        self.reader.deleteNoteRequested.connect(self.delete_note)
        self.reader.positionClicked.connect(self.on_position_clicked)
        self.reader.verticalScrollBar().valueChanged.connect(self.on_scrolled)
        self.notes_panel.jumpRequested.connect(self.jump_to_note)
        self.notes_panel.editRequested.connect(self.edit_note)
        self.notes_panel.deleteRequested.connect(self.delete_note)
        self.notes_panel.exportRequested.connect(self.export_notes)

        self._restyle = QTimer(self, singleShot=True, interval=140)
        self._restyle.timeout.connect(self.prefsChanged.emit)
        self.appearance.changed.connect(self._restyle.start)
        self._save_timer = QTimer(self, singleShot=True, interval=1200)
        self._save_timer.timeout.connect(self.save_position)

        self.apply_style(render=False)

    # -- toolbar ------------------------------------------------------------ #

    def _build_toolbar(self, root):
        bar = QToolBar()
        bar.setMovable(False)
        bar.setFloatable(False)

        def act(text, slot, shortcut=None, tip="", checkable=False):
            a = QAction(text, self)
            a.setCheckable(checkable)
            if tip:
                a.setToolTip(tip)
            (a.toggled if checkable else a.triggered).connect(slot)
            bar.addAction(a)
            if shortcut:
                make_shortcut(self, shortcut, a.toggle if checkable else a.trigger)
            return a

        act("←  Library", lambda: self.backRequested.emit(), "Ctrl+L", "Back to library (Ctrl+L)")
        self.act_toc = act("☰  Contents", self.toc_panel_toggle, "Ctrl+T",
                           "Table of contents (Ctrl+T)", True)
        self.act_notes = act("✎  Notes", self.notes_panel_toggle, "Ctrl+Shift+N",
                             "Notes & highlights (Ctrl+Shift+N)", True)
        self.act_journal = act("📓  Journal", self.journal_toggle, "Ctrl+J",
                               "Book notes filed by section and page (Ctrl+J)", True)
        act("🧠  Mind map", lambda: self.open_mindmap(), "Ctrl+M",
            "Mind maps for this book, or turn your notes into one (Ctrl+M)")
        self.act_find = act("🔍  Find", self.toggle_find, None, "Find in book (Ctrl+F)", True)
        make_shortcut(self, "Ctrl+F", self.focus_find)
        bm = QToolButton()
        bm.setText("🔖")
        bm.setToolTip("Bookmarks (Ctrl+B adds one here)")
        bm.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        bm.setMenu(self.bookmark_menu)
        bar.addWidget(bm)
        make_shortcut(self, "Ctrl+B", self.add_bookmark)
        make_shortcut(self, "Ctrl+K",
                      lambda: self.lookup_text(self.reader.textCursor().selectedText()))
        self.act_reading = act("☆  Reading", self.toggle_reading, "Ctrl+D",
                               "Add to / remove from your reading list (Ctrl+D)", True)

        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(left_spacer)
        self.title_label = QLabel("")
        self.title_label.setObjectName("h2")
        bar.addWidget(self.title_label)
        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(right_spacer)

        act("◀", lambda: self.prev_chapter(), "Alt+Left", "Previous chapter (Alt+←)")
        act("▶", lambda: self.next_chapter(), "Alt+Right", "Next chapter (Alt+→)")
        bar.addSeparator()
        act("＋  Note", self.add_note, "Ctrl+N", "Add a note (Ctrl+N)")

        # quick highlight shortcut (no toolbar button)
        make_shortcut(self, "Ctrl+H", lambda: self.quick_highlight("Yellow"))

        menu = QMenu(self)
        wa = QWidgetAction(menu)
        wa.setDefaultWidget(self.appearance)
        menu.addAction(wa)
        aa = QToolButton()
        aa.setText("Aa")
        aa.setToolTip("Appearance: theme, font, spacing")
        aa.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        aa.setMenu(menu)
        f = aa.font()
        f.setBold(True)
        aa.setFont(f)
        bar.addWidget(aa)
        root.addWidget(bar)

    def toc_panel_toggle(self, on):
        self.toc_panel.setVisible(on)

    def notes_panel_toggle(self, on):
        self.notes_panel.setVisible(on)

    # -- styling ------------------------------------------------------------ #

    def theme(self) -> dict:
        return THEMES[self.prefs.v["theme"]]

    def apply_style(self, render=True):
        p, t = self.prefs.v, self.theme()
        font = QFont(p["font_family"])
        font.setPointSize(p["font_size"])
        doc = self.reader.document()
        doc.setDefaultFont(font)
        gap = int(p["font_size"] * 0.9)
        align = "text-align:justify;" if p["justify"] else ""
        doc.setDefaultStyleSheet(f"""
            body {{ color:{t['fg']}; font-family:'{p['font_family']}';
                    font-size:{p['font_size']}pt; line-height:{p['line_height']}%; }}
            p {{ margin-top:0px; margin-bottom:{gap}px; {align} }}
            a {{ color:{t['link']}; }}
            blockquote {{ margin-left:28px; margin-right:12px; }}
            pre {{ background-color:{t['panel']}; font-family:'DejaVu Sans Mono','Consolas',monospace;
                   font-size:{max(8, p['font_size'] - 2)}pt; margin:0 0 {gap}px 0;
                   line-height:125%; }}
            code {{ background-color:{t['panel']}; font-family:'DejaVu Sans Mono','Consolas',monospace; }}
            th {{ font-weight:600; }}
            h1, h2, h3, h4 {{ margin-top:{gap * 2}px; margin-bottom:{gap}px; }}
        """)
        self.reader.text_width = p["text_width"]
        self.reader.update_margins()
        self.reader.setStyleSheet(
            f"QTextBrowser {{ background:{t['bg']}; border:none;"
            f" selection-background-color:{t['accent']}; selection-color:{t['on_accent']}; }}"
        )
        if render and self.book:
            self.show_chapter(self.spine_index, ratio=self.scroll_ratio())
            self.notes_panel.refresh(self.notes, self.chapter_label, self.spine_index, t)
            self.refresh_journal()

    def change_font(self, delta: int):
        size = max(9, min(34, self.prefs.v["font_size"] + delta))
        self.appearance.size_slider.setValue(size)  # updates prefs and re-renders

    # -- opening / closing -------------------------------------------------- #

    def open_book(self, book_id: int) -> bool:
        row = self.library.get(book_id)
        if row is None:
            return False
        try:
            book = open_text_book(row["path"], row["format"], row["title"])
        except Exception as exc:
            QMessageBox.critical(self, "Could not open book", f"{row['title']}\n\n{exc}")
            return False
        self.close_book()
        self.book, self.book_id = book, book_id
        self.reader.book = book
        self.library.touch(book_id)

        self.titles = {}

        def walk(entries):
            for e in entries:
                if e.path and e.path not in self.titles and e.title:
                    self.titles[e.path] = e.title
                walk(e.children)

        walk(book.toc)
        self.populate_toc()
        fm = self.title_label.fontMetrics()
        self.title_label.setText(fm.elidedText(book.title, Qt.TextElideMode.ElideRight, 420))

        self.notes = [dict(r) for r in self.library.notes(book_id)]
        self.notes_panel.only_chapter.setChecked(False)
        index = row["spine_index"]
        if not 0 <= index < len(book.spine):
            index = 0
        self.apply_style(render=False)
        self.show_chapter(index, ratio=row["scroll_ratio"])
        self.notes_panel.refresh(self.notes, self.chapter_label, self.spine_index, self.theme())
        self._journal_open()
        self.tracker.start(book_id, row["read_seconds"], self)
        self._sync_reading(row["reading"] == 1)
        self.reader.setFocus()
        return True

    def close_book(self):
        self.close_mindmap()
        if self.act_find.isChecked():
            self.act_find.setChecked(False)
        if self.book:
            self._save_timer.stop()
            self.save_position()
            self.tracker.stop()
            self.reader.book = None
            self.book.close()
            self.book = None
            self.book_id = None

    def save_position(self):
        if self.book and self.book_id is not None:
            ratio = self.scroll_ratio()
            overall = min(1.0, (self.spine_index + ratio) / max(1, len(self.book.spine)))
            self.library.update_position(self.book_id, self.spine_index, ratio, overall,
                                         self.chapter_label(self.spine_index))

    # -- journal hooks ------------------------------------------------------- #

    def current_location(self):
        """Where the reader is right now: section title + estimated page."""
        if not self.book:
            return None
        ratio = self.scroll_ratio()
        page, total = self.book.est_page(self.spine_index, ratio)
        overall = min(1.0, (self.spine_index + ratio) / max(1, len(self.book.spine)))
        return dict(spine_index=self.spine_index, ratio=ratio, progress=overall,
                    chapter=self.chapter_label(self.spine_index), page=page, total=total)

    def jump_to_location(self, index: int, ratio: float):
        if not self.book:
            return
        if index == self.spine_index:
            bar = self.reader.verticalScrollBar()
            self.reader.stop_scroll()
            bar.setValue(int(ratio * bar.maximum()))
        else:
            self.show_chapter(index, ratio=ratio)

    def summary_highlights(self) -> list:
        return list(self.notes)

    def summary_chapter_label(self, index: int) -> str:
        return self.chapter_label(index)

    # -- contents ----------------------------------------------------------- #

    def chapter_label(self, index: int) -> str:
        if self.book and 0 <= index < len(self.book.spine):
            return self.titles.get(self.book.spine[index], f"Section {index + 1}")
        return ""

    def populate_toc(self):
        self.toc.clear()
        self.toc_items = []

        def add(parent, entries):
            for e in entries:
                item = QTreeWidgetItem(parent, [e.title or "(untitled)"])
                item.setData(0, Qt.ItemDataRole.UserRole, (e.path, e.fragment))
                self.toc_items.append((item, e.path))
                add(item, e.children)

        add(self.toc, self.book.toc)
        self.toc.expandToDepth(0)

    def highlight_toc(self, path):
        for item, p in self.toc_items:
            if p == path:
                self.toc.setCurrentItem(item)
                break

    def on_toc_clicked(self, item, _col):
        path, fragment = item.data(0, Qt.ItemDataRole.UserRole)
        if path and path in self.book.spine:
            self.show_chapter(self.book.spine.index(path), fragment)

    # -- navigation --------------------------------------------------------- #

    def show_chapter(self, index, fragment="", ratio=None, position=None):
        if not self.book or not 0 <= index < len(self.book.spine):
            return
        self.spine_index = index
        path = self.book.spine[index]
        try:
            html = self.book.render_chapter(path)
        except Exception as exc:
            html = f"<p>Could not load <b>{path}</b>: {exc}</p>"
        self.reader.stop_scroll()
        self.reader.setHtml(html)
        self.refresh_highlights()
        QTimer.singleShot(0, lambda: self._restore_scroll(fragment, ratio, position))
        self.highlight_toc(path)
        self.update_progress()
        self._save_timer.start()

    def _restore_scroll(self, fragment, ratio, position):
        bar = self.reader.verticalScrollBar()
        if position is not None:
            self.scroll_to_position(position)
        elif fragment:
            self.reader.scrollToAnchor(fragment)
        elif ratio:
            bar.setValue(int(ratio * bar.maximum()))
        else:
            bar.setValue(0)
        self.update_progress()

    def scroll_to_position(self, pos: int):
        cur = QTextCursor(self.reader.document())
        cur.setPosition(pos)
        rect = self.reader.cursorRect(cur)
        bar = self.reader.verticalScrollBar()
        bar.setValue(bar.value() + rect.top() - self.reader.viewport().height() // 3)

    def scroll_ratio(self) -> float:
        bar = self.reader.verticalScrollBar()
        return bar.value() / bar.maximum() if bar.maximum() else 0.0

    def next_chapter(self):
        if self.book and self.spine_index + 1 < len(self.book.spine):
            self.show_chapter(self.spine_index + 1)

    def prev_chapter(self, to_end=False):
        if self.book and self.spine_index > 0:
            self.show_chapter(self.spine_index - 1, ratio=1.0 if to_end else None)

    def on_link(self, url):
        if url.scheme() in ("http", "https", "mailto"):
            webbrowser.open(url.toString())
        elif url.scheme() == "epub" and self.book:
            path = url.path().lstrip("/")
            if path in self.book.spine:
                self.show_chapter(self.book.spine.index(path), url.fragment())

    def on_scrolled(self, _value):
        if self.book:
            self.update_progress()
            self._save_timer.start()

    def update_progress(self):
        if not self.book:
            return
        n = len(self.book.spine)
        overall = min(1.0, (self.spine_index + self.scroll_ratio()) / n)
        self.status.set_progress(self.chapter_label(self.spine_index), overall,
                                 f"chapter {self.spine_index + 1} / {n}")
        if not self.journal.isHidden():
            self.journal.track()

    def flash(self, text):
        self.status.left.setText(text)
        QTimer.singleShot(2500, self.update_progress)

    # -- find in book --------------------------------------------------------- #

    def toggle_find(self, on):
        self.find_bar.setVisible(bool(on))
        if on:
            self.find_bar.focus()
            return
        self._find_query, self._find_hits, self._find_i, self._find_pos = "", [], -1, None
        self.find_bar.set_status("")
        if self.book:
            self.refresh_highlights()
        self.reader.setFocus()

    def focus_find(self):
        if self.act_find.isChecked():
            self.find_bar.focus()
        else:
            self.act_find.setChecked(True)

    def run_find(self, text, step=1):
        """Search the whole book; repeat (Enter / arrows) to step through the matches."""
        if not self.book:
            return
        query = " ".join(text.lower().split())
        if not query:
            self._find_query, self._find_hits, self._find_i = "", [], -1
            self.find_bar.set_status("")
            self.refresh_highlights()
            return
        if query != self._find_query:
            self._find_query = query
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self._find_hits = self.book.search(query)
            finally:
                QApplication.restoreOverrideCursor()
            if not self._find_hits:
                self._find_i, self._find_pos = -1, None
                self.find_bar.set_status("No matches")
                self.refresh_highlights()
                return
            self._find_i = next((k for k, (s, _) in enumerate(self._find_hits)
                                 if s >= self.spine_index), 0)
        elif self._find_hits:
            self._find_i = (self._find_i + step) % len(self._find_hits)
        else:
            return
        self._goto_find_hit()

    def _goto_find_hit(self):
        spine, occ = self._find_hits[self._find_i]
        more = "+" if len(self._find_hits) >= 1000 else ""
        self.find_bar.set_status(f"{self._find_i + 1} / {len(self._find_hits)}{more}"
                                 f"   ·   {self.chapter_label(spine)}")
        if spine != self.spine_index:
            self.show_chapter(spine)
        QTimer.singleShot(40, lambda: self._select_occurrence(spine, occ))

    def _select_occurrence(self, spine, occ):
        if spine != self.spine_index or not self._find_query:
            return
        doc = self.reader.document()
        cur = doc.find(self._find_query)
        for _ in range(occ):
            if cur.isNull():
                break
            cur = doc.find(self._find_query, cur)
        if cur.isNull():
            cur = doc.find(self._find_query)
        if cur.isNull():
            self._find_pos = None
        else:
            self._find_pos = (cur.selectionStart(), cur.selectionEnd(), spine)
            self.scroll_to_position(cur.selectionStart())
        self.refresh_highlights()

    def _search_selections(self) -> list:
        """Highlights for every match in the open chapter; the current match in orange."""
        sels = []
        query = self._find_query
        if not query or self.find_bar.isHidden():
            return sels
        doc = self.reader.document()
        cur, n = doc.find(query), 0
        while not cur.isNull() and n < 500:
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(255, 213, 0, 120))
            sel = QTextEdit.ExtraSelection()
            sel.cursor, sel.format = cur, fmt
            sels.append(sel)
            cur, n = doc.find(query, cur), n + 1
        if self._find_pos and self._find_pos[2] == self.spine_index:
            cursor = QTextCursor(doc)
            cursor.setPosition(self._find_pos[0])
            cursor.setPosition(self._find_pos[1], QTextCursor.MoveMode.KeepAnchor)
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(255, 140, 0, 170))
            sel = QTextEdit.ExtraSelection()
            sel.cursor, sel.format = cursor, fmt
            sels.append(sel)
        return sels

    # -- notes & highlights ------------------------------------------------- #

    def refresh_highlights(self):
        doc = self.reader.document()
        last = max(0, doc.characterCount() - 1)
        selections, ranges, self._resolved = [], [], {}
        for n in self.notes:
            if n["spine_index"] != self.spine_index or not n["quote"]:
                continue
            start, end, quote_text = n["pos_start"], n["pos_end"], n["quote"]
            cur = QTextCursor(doc)
            cur.setPosition(min(start, last))
            cur.setPosition(min(end, last), QTextCursor.MoveMode.KeepAnchor)
            if cur.selectedText() != quote_text:  # text moved: search for it
                found = doc.find(quote_text.split("\u2029")[0])
                if found.isNull():
                    continue
                start = found.selectionStart()
                end = start + len(quote_text)
                cur = QTextCursor(doc)
                cur.setPosition(min(start, last))
                cur.setPosition(min(end, last), QTextCursor.MoveMode.KeepAnchor)
            color = QColor(HIGHLIGHT_COLORS.get(n["color"], "#ffd54f"))
            color.setAlpha(110)
            fmt = QTextCharFormat()
            fmt.setBackground(color)
            sel = QTextEdit.ExtraSelection()
            sel.cursor = cur
            sel.format = fmt
            selections.append(sel)
            ranges.append((n["id"], start, end))
            self._resolved[n["id"]] = (start, end)
        self.reader.setExtraSelections(selections + self._search_selections())
        self.reader.note_ranges = ranges

    def _after_note_change(self, message):
        self.notes = [dict(r) for r in self.library.notes(self.book_id)]
        cur = self.reader.textCursor()
        cur.clearSelection()
        self.reader.setTextCursor(cur)
        self.refresh_highlights()
        self.notes_panel.refresh(self.notes, self.chapter_label, self.spine_index, self.theme())
        self.flash(message)

    def _selection(self):
        c = self.reader.textCursor()
        if c.hasSelection():
            return c.selectedText(), c.selectionStart(), c.selectionEnd()
        top = self.reader.cursorForPosition(QPoint(0, 0)).position()
        return "", top, top

    def quick_highlight(self, color="Yellow"):
        if not self.book:
            return
        text, start, end = self._selection()
        if not text:
            self.flash("Select some text first, then highlight it")
            return
        self.library.add_note(self.book_id, self.spine_index, start, end, text, "", color)
        self._after_note_change("Highlight saved")

    def add_note(self):
        if not self.book:
            return
        text, start, end = self._selection()
        dlg = NoteDialog(self, text)
        if dlg.exec():
            note = dlg.text()
            if not note and not text:
                return
            self.library.add_note(self.book_id, self.spine_index, start, end,
                                  text, note, dlg.color())
            self._after_note_change("Note saved")

    def _find(self, nid):
        return next((n for n in self.notes if n["id"] == nid), None)

    def edit_note(self, nid):
        n = self._find(nid)
        if not n:
            return
        dlg = NoteDialog(self, n["quote"], n["note"], n["color"], editing=True)
        if dlg.exec():
            if dlg.deleted:
                self.library.delete_note(nid)
                self._after_note_change("Deleted")
            else:
                self.library.update_note(nid, dlg.text(), dlg.color())
                self._after_note_change("Note updated")

    def delete_note(self, nid):
        n = self._find(nid)
        if not n:
            return
        what = "note" if n["note"] else "highlight"
        if QMessageBox.question(self, "Delete", f"Delete this {what}?") == \
                QMessageBox.StandardButton.Yes:
            self.library.delete_note(nid)
            self._after_note_change("Deleted")

    def on_position_clicked(self, pos):
        nid = self.reader.note_at(pos)
        if nid is not None:
            self.edit_note(nid)

    def jump_to_note(self, nid):
        n = self._find(nid)
        if not n:
            return
        pos = self._resolved.get(nid, (n["pos_start"], n["pos_end"]))[0]
        if n["spine_index"] == self.spine_index:
            self.scroll_to_position(pos)
        else:
            self.show_chapter(n["spine_index"], position=n["pos_start"])

    def export_notes(self):
        if not self.notes:
            self.flash("No notes to export yet")
            return
        safe = "".join(c for c in self.book.title if c.isalnum() or c in " -_").strip() or "book"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export notes", str(Path.home() / f"{safe} - notes.md"),
            "Markdown (*.md);;Text (*.txt)")
        if not path:
            return
        lines = [f"# {self.book.title}", ""]
        if self.book.author:
            lines += [f"*{self.book.author}*", ""]
        last = None
        for n in self.notes:
            if n["spine_index"] != last:
                last = n["spine_index"]
                lines += [f"## {self.chapter_label(last)}", ""]
            if n["quote"]:
                lines.append("> " + pretty(n["quote"]).replace("\n", "\n> "))
                lines.append("")
            if n["note"]:
                lines += [n["note"], ""]
        try:
            Path(path).write_text("\n".join(lines), encoding="utf-8")
            self.flash("Notes exported")
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

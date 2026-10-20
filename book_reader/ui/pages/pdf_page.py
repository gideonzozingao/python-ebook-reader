"""PDF reader page."""
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QToolBar,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from book_reader.core.library import Library
from book_reader.core.pdf import fitz
from book_reader.core.prefs import Prefs
from book_reader.core.tracker import ReadingTracker
from book_reader.themes import THEMES
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
from book_reader.ui.widgets.notes_panel import NotesPanel
from book_reader.ui.widgets.pdf_view import PdfView
from book_reader.ui.widgets.status_bar import StatusBar


class PdfPage(ReadingListMixin, JournalMixin, BookmarksMixin, LookupMixin, MindMapMixin, QWidget):
    backRequested = Signal()
    prefsChanged = Signal()
    noteLinkRequested = Signal(str)   # a [[note:ID]] link was clicked
    book_format = "pdf"

    def __init__(self, library: Library, prefs: Prefs, tracker: ReadingTracker):
        super().__init__()
        self.library, self.prefs, self.tracker = library, prefs, tracker
        self.doc = None
        self.book_id: int | None = None
        self.title = ""
        self._toc_pages: list[tuple[int, QTreeWidgetItem]] = []
        self._last_query = ""
        self.setObjectName("page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.view = PdfView()
        self._init_journal()
        self._init_bookmarks()
        self.notes_panel = NotesPanel()
        self.marks: list[dict] = []
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
        self.toc_panel.hide()

        self._build_toolbar(root)
        self._build_find_bar(root)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.addWidget(self.toc_panel)
        self.splitter.addWidget(self.view)
        self.splitter.addWidget(self.notes_panel)
        self.splitter.addWidget(self.journal)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(1, False)
        self.splitter.setSizes([280, 900, 330, 350])
        self.notes_panel.hide()
        self.journal.hide()
        root.addWidget(self.splitter, 1)

        self.status = StatusBar()
        root.addWidget(self.status)
        self.tracker.tick.connect(self.status.set_time)
        self.tracker.addedToReading.connect(self._on_auto_reading)

        self.view.pageChanged.connect(self.on_page_changed)
        self.view.zoomChanged.connect(self.on_zoom_changed)
        self.view.highlightRequested.connect(self.quick_highlight)
        self.view.noteRequested.connect(self.add_note)
        self.view.lookupRequested.connect(self.lookup_text)
        self.view.markClicked.connect(self.edit_mark)
        self.view.markEditRequested.connect(self.edit_mark)
        self.view.markDeleteRequested.connect(self.delete_mark)
        self.notes_panel.jumpRequested.connect(self.jump_to_mark)
        self.notes_panel.editRequested.connect(self.edit_mark)
        self.notes_panel.deleteRequested.connect(self.delete_mark)
        self.notes_panel.exportRequested.connect(self.export_journal)
        self._save_timer = QTimer(self, singleShot=True, interval=1200)
        self._save_timer.timeout.connect(self.save_position)

        self.apply_style()

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
        self.act_toc = act("☰  Contents", self.toc_panel.setVisible, "Ctrl+T",
                           "Table of contents (Ctrl+T)", True)
        self.act_find = act("Find", self.toggle_find, None, "Find in book (Ctrl+F)", True)
        self.act_journal = act("📓  Journal", self.journal_toggle, "Ctrl+J",
                               "Book notes filed by section and page (Ctrl+J)", True)
        act("🧠  Mind map", lambda: self.open_mindmap(), "Ctrl+M",
            "Mind maps for this book, or turn your notes into one (Ctrl+M)")
        self.act_notes = act("✎  Notes", self.notes_panel.setVisible, "Ctrl+Shift+N",
                             "Highlights and notes (Ctrl+Shift+N)", True)
        self.act_select = act("⌶  Select", self.set_select_mode, "Ctrl+E",
                              "Select text to highlight, copy or look up (Ctrl+E)", True)
        bm = QToolButton()
        bm.setText("🔖")
        bm.setToolTip("Bookmarks (Ctrl+B adds one here)")
        bm.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        bm.setMenu(self.bookmark_menu)
        bar.addWidget(bm)
        make_shortcut(self, "Ctrl+B", self.add_bookmark)
        make_shortcut(self, "Ctrl+K", lambda: self.lookup_text(self.view.selected_text()))
        self.act_reading = act("☆  Reading", self.toggle_reading, "Ctrl+D",
                               "Add to / remove from your reading list (Ctrl+D)", True)
        make_shortcut(self, "Ctrl+F", self.focus_find)

        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(left_spacer)
        self.title_label = QLabel("")
        self.title_label.setObjectName("h2")
        bar.addWidget(self.title_label)
        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bar.addWidget(right_spacer)

        act("◀", self.prev_page, "Alt+Left", "Previous page (Alt+←)")
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 1)
        self.page_spin.setKeyboardTracking(False)
        self.page_spin.setToolTip("Go to page")
        self.page_spin.valueChanged.connect(lambda v: self.view.jump_to_page(v - 1))
        bar.addWidget(self.page_spin)
        self.page_total = QLabel(" / 1 ")
        self.page_total.setObjectName("muted")
        bar.addWidget(self.page_total)
        act("▶", self.next_page, "Alt+Right", "Next page (Alt+→)")
        bar.addSeparator()
        act("－", lambda: self.view.zoom_by(1 / 1.15), None, "Zoom out (Ctrl+−)")
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("muted")
        self.zoom_label.setMinimumWidth(46)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar.addWidget(self.zoom_label)
        act("＋", lambda: self.view.zoom_by(1.15), None, "Zoom in (Ctrl++)")
        act("Fit width", self.view.set_fit_width, None, "Fit to width (Ctrl+0)")

        self.appearance = AppearancePanel(self.prefs)
        menu = QMenu(self)
        wa = QWidgetAction(menu)
        wa.setDefaultWidget(self.appearance)
        menu.addAction(wa)
        menu.aboutToShow.connect(self.appearance.sync)
        aa = QToolButton()
        aa.setText("Aa")
        aa.setToolTip("Appearance: colour theme and fonts for the whole app (Ctrl+,)")
        aa.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        aa.setMenu(menu)
        bold = aa.font()
        bold.setBold(True)
        aa.setFont(bold)
        bar.addSeparator()
        bar.addWidget(aa)
        self._restyle = QTimer(self, singleShot=True, interval=140)
        self._restyle.timeout.connect(self.prefsChanged.emit)
        self.appearance.changed.connect(self._restyle.start)
        root.addWidget(bar)

    def _build_find_bar(self, root):
        self.find_bar = QWidget()
        self.find_bar.setObjectName("sidePanel")
        self.find_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        fl = QHBoxLayout(self.find_bar)
        fl.setContentsMargins(14, 6, 14, 6)
        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Find in document…")
        self.find_edit.setClearButtonEnabled(True)
        self.find_edit.setMinimumWidth(300)
        self.find_edit.returnPressed.connect(lambda: self.run_find(1))
        prev = QPushButton("◀")
        prev.setObjectName("link")
        prev.setToolTip("Previous match")
        prev.clicked.connect(lambda: self.run_find(-1))
        nxt = QPushButton("▶")
        nxt.setObjectName("link")
        nxt.setToolTip("Next match (Enter)")
        nxt.clicked.connect(lambda: self.run_find(1))
        self.find_label = QLabel("")
        self.find_label.setObjectName("muted")
        close = QPushButton("✕")
        close.setObjectName("link")
        close.clicked.connect(lambda: self.act_find.setChecked(False))
        fl.addWidget(self.find_edit)
        fl.addWidget(prev)
        fl.addWidget(nxt)
        fl.addWidget(self.find_label)
        fl.addStretch()
        fl.addWidget(close)
        make_shortcut(self.find_bar, "Escape", lambda: self.act_find.setChecked(False))
        self.find_bar.hide()
        root.addWidget(self.find_bar)

    # -- find --------------------------------------------------------------- #

    def toggle_find(self, on):
        self.find_bar.setVisible(on)
        if on:
            self.find_edit.setFocus()
            self.find_edit.selectAll()
        else:
            self._last_query = ""
            self.find_label.setText("")
            self.view.clear_hits()
            self.view.setFocus()

    def focus_find(self):
        if self.act_find.isChecked():
            self.find_edit.setFocus()
            self.find_edit.selectAll()
        else:
            self.act_find.setChecked(True)

    def run_find(self, step: int = 1):
        text = self.find_edit.text().strip()
        if self.doc is None:
            return
        if not text:
            self._last_query = ""
            self.view.clear_hits()
            self.find_label.setText("")
            return
        if text != self._last_query:
            self._last_query = text
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                n = self.view.search(text)
            finally:
                QApplication.restoreOverrideCursor()
            if n == 0:
                self.find_label.setText("No matches")
                return
            step = 1
        idx = self.view.go_hit(step)
        if idx >= 0:
            more = "+" if len(self.view.hits) >= PdfView.HIT_LIMIT else ""
            self.find_label.setText(f"{idx + 1} / {len(self.view.hits)}{more}")

    # -- styling ------------------------------------------------------------ #

    def apply_style(self):
        t = THEMES[self.prefs.v["theme"]]
        self.view.bg = QColor(t["desk"])
        invert = bool(self.prefs.v["pdf_invert"])
        if invert != self.view.invert:
            self.view.cache.clear()
        self.view.invert = invert
        self.view.viewport().update()
        if self.doc is not None:
            self.refresh_journal()

    # -- opening / closing -------------------------------------------------- #

    def open_book(self, book_id: int) -> bool:
        row = self.library.get(book_id)
        if row is None:
            return False
        if fitz is None:
            QMessageBox.critical(self, "PDF support missing",
                                 "Reading PDFs needs PyMuPDF:\n\n    pip install pymupdf")
            return False
        try:
            doc = fitz.open(row["path"])
            if doc.needs_pass:
                doc.close()
                raise ValueError("password-protected PDFs are not supported")
        except Exception as exc:
            QMessageBox.critical(self, "Could not open book", f"{row['title']}\n\n{exc}")
            return False
        self.close_book()
        self.doc, self.book_id, self.title = doc, book_id, row["title"]
        self.library.touch(book_id)
        fm = self.title_label.fontMetrics()
        self.title_label.setText(fm.elidedText(self.title, Qt.TextElideMode.ElideRight, 420))

        n = doc.page_count
        self.page_spin.blockSignals(True)
        self.page_spin.setRange(1, n)
        self.page_spin.setValue(1)
        self.page_spin.blockSignals(False)
        self.page_total.setText(f" / {n} ")

        self.apply_style()
        self.populate_toc()
        self.view.set_document(doc, float(self.prefs.v["pdf_zoom"]))
        page = row["spine_index"] if 0 <= (row["spine_index"] or 0) < n else 0
        self.view.scroll_to(page, row["scroll_ratio"] or 0.0)
        self.on_page_changed()
        self._journal_open()
        self._load_marks()
        self.tracker.start(book_id, row["read_seconds"], self)
        self._sync_reading(row["reading"] == 1)
        QTimer.singleShot(0, self.view.relayout)  # re-fit once the page is shown
        QTimer.singleShot(0, self.view.setFocus)
        return True

    def close_book(self):
        if self.doc is None:
            return
        self.close_mindmap()
        self._save_timer.stop()
        self.save_position()
        self.tracker.stop()
        self.act_find.setChecked(False)
        if self.act_select.isChecked():
            self.act_select.setChecked(False)
        self.view.clear()
        self.view.set_marks([])
        self.marks = []
        self.doc.close()
        self.doc, self.book_id = None, None

    def save_position(self):
        if self.doc is not None and self.book_id is not None:
            page, frac = self.view.position()
            item = self._current_toc_item(page)
            self.library.update_position(self.book_id, page, frac, self.view.overall(),
                                         item.text(0) if item is not None else "")

    # -- journal hooks ------------------------------------------------------- #

    def current_location(self):
        """Where the reader is right now: TOC section (if any) and exact page."""
        if self.doc is None:
            return None
        page, frac = self.view.position()
        item = self._current_toc_item(page)
        return dict(spine_index=page, ratio=frac, progress=self.view.overall(),
                    chapter=item.text(0) if item is not None else self.title,
                    page=page + 1, total=self.doc.page_count)

    def jump_to_location(self, index: int, ratio: float):
        if self.doc is not None:
            self.view.scroll_to(index, ratio)

    # -- text selection, highlights and notes -------------------------------- #

    def set_select_mode(self, on):
        self.view.set_select_mode(bool(on))
        self.flash("Drag over text to select it, then right-click: highlight, note, look up"
                   if on else "Select mode off — drag to move the page")

    def page_label(self, index: int) -> str:
        item = self._current_toc_item(index)
        return f"{item.text(0)} · p. {index + 1}" if item is not None else f"Page {index + 1}"

    def _load_marks(self):
        self.marks = self.library.pdf_marks(self.book_id) if self.book_id is not None else []
        self.view.set_marks(self.marks)
        self.notes_panel.refresh(self.marks, self.page_label, self.view.position()[0],
                                 THEMES[self.prefs.v["theme"]])

    def _marks_changed(self, message):
        self._load_marks()
        self.flash(message)

    def quick_highlight(self, color="Yellow"):
        sel = self.view.sel
        if not sel:
            self.flash("Select some text first (turn on Select in the toolbar)")
            return
        self.library.add_pdf_mark(self.book_id, sel["page"], sel["rects"], sel["text"], "", color)
        self.view.clear_selection()
        self._marks_changed("Highlight saved")

    def add_note(self):
        sel = self.view.sel
        if not sel:
            self.flash("Select some text first (turn on Select in the toolbar)")
            return
        dlg = NoteDialog(self, sel["text"])
        if dlg.exec():
            self.library.add_pdf_mark(self.book_id, sel["page"], sel["rects"], sel["text"],
                                      dlg.text(), dlg.color())
            self.view.clear_selection()
            self._marks_changed("Note saved")

    def _find_mark(self, mark_id):
        return next((m for m in self.marks if m["id"] == mark_id), None)

    def edit_mark(self, mark_id):
        m = self._find_mark(mark_id)
        if not m:
            return
        dlg = NoteDialog(self, m["quote"], m["note"], m["color"], editing=True)
        if dlg.exec():
            if dlg.deleted:
                self.library.delete_pdf_mark(mark_id)
                self._marks_changed("Deleted")
            else:
                self.library.update_pdf_mark(mark_id, dlg.text(), dlg.color())
                self._marks_changed("Note updated")

    def delete_mark(self, mark_id):
        m = self._find_mark(mark_id)
        if not m:
            return
        what = "note" if m["note"] else "highlight"
        if QMessageBox.question(self, "Delete", f"Delete this {what}?") == \
                QMessageBox.StandardButton.Yes:
            self.library.delete_pdf_mark(mark_id)
            self._marks_changed("Deleted")

    def jump_to_mark(self, mark_id):
        m = self._find_mark(mark_id)
        if not m:
            return
        page = m["spine_index"]
        height = self.view.sizes[page][1] if page < len(self.view.sizes) else 1.0
        self.view.scroll_to(page, max(0.0, m["pos_start"] / height - 0.04))

    def summary_highlights(self) -> list:
        return list(self.marks)

    def summary_chapter_label(self, index: int) -> str:
        item = self._current_toc_item(index)
        return item.text(0) if item is not None else self.title

    # -- contents ----------------------------------------------------------- #

    def populate_toc(self):
        self.toc.clear()
        self._toc_pages = []
        try:
            entries = self.doc.get_toc(simple=True)
        except Exception:
            entries = []
        stack: list[tuple[int, QTreeWidgetItem | None]] = [(0, None)]
        for lvl, title, page in entries:
            lvl = max(1, int(lvl))
            while len(stack) > 1 and stack[-1][0] >= lvl:
                stack.pop()
            parent = stack[-1][1] if stack[-1][1] is not None else self.toc
            item = QTreeWidgetItem(parent, [(title or "").strip() or "(untitled)"])
            page0 = max(0, int(page) - 1)
            item.setData(0, Qt.ItemDataRole.UserRole, page0)
            self._toc_pages.append((page0, item))
            stack.append((lvl, item))
        self.toc.expandToDepth(0)
        has = bool(entries)
        self.act_toc.setEnabled(has)
        if not has:
            self.act_toc.setChecked(False)
        self.act_toc.setToolTip("Table of contents (Ctrl+T)" if has
                                else "This PDF has no table of contents")

    def on_toc_clicked(self, item, _col):
        self.view.jump_to_page(item.data(0, Qt.ItemDataRole.UserRole))

    def _current_toc_item(self, page: int):
        best = None
        for pg, item in self._toc_pages:
            if pg <= page:
                best = item
        return best

    # -- navigation / progress --------------------------------------------- #

    def prev_page(self):
        if self.doc is not None:
            page, frac = self.view.position()
            self.view.jump_to_page(page - 1 if frac < 0.02 else page)

    def next_page(self):
        if self.doc is not None:
            self.view.jump_to_page(self.view.position()[0] + 1)

    def on_zoom_changed(self, scale: float, fit: bool):
        self.zoom_label.setText(f"{scale * 100:.0f}%")
        value = 0.0 if fit else round(scale, 3)
        if self.doc is not None and self.prefs.v["pdf_zoom"] != value:
            self.prefs.set("pdf_zoom", value)

    def on_page_changed(self):
        if self.doc is None:
            return
        page, _ = self.view.position()
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page + 1)
        self.page_spin.blockSignals(False)
        self.update_progress()
        self._save_timer.start()

    def flash(self, text):
        self.status.left.setText(text)
        QTimer.singleShot(2500, self.update_progress)

    def update_progress(self):
        if self.doc is None:
            return
        page, _ = self.view.position()
        item = self._current_toc_item(page)
        if item is not None and self.toc.currentItem() is not item:
            self.toc.setCurrentItem(item)
        label = item.text(0) if item is not None else self.title
        self.status.set_progress(label, self.view.overall(),
                                 f"page {page + 1} / {self.doc.page_count}")
        if not self.journal.isHidden():
            self.journal.track()

"""Library page: shelf, search, catalogue, context menu."""
import textwrap

from datetime import datetime

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from book_reader.constants import COVER_H, COVER_W
from book_reader.core.library import Library
from book_reader.services import goals
from book_reader.ui.dialogs.subject_dialog import SubjectDialog
from book_reader.ui.widgets.appearance_panel import AppearancePanel
from book_reader.ui.widgets.cover import make_collection_tile, make_cover
from book_reader.utils import ago, fmt_duration


class LibraryPage(QWidget):
    openRequested = Signal(int)
    addFilesRequested = Signal()
    addFolderRequested = Signal()
    removeRequested = Signal(int)
    statsRequested = Signal()
    continueRequested = Signal(int)
    backupRequested = Signal()
    restoreRequested = Signal()
    reviewRequested = Signal(int)
    mindmapRequested = Signal(int)
    notesRequested = Signal()
    prefsChanged = Signal()   # appearance settings were changed here

    def __init__(self, library: Library, prefs=None):
        super().__init__()
        self.library = library
        self.prefs = prefs
        self._cat_sel: dict = {}  # catalogue selection per group-by mode
        self.open_collection: str | None = None  # collection page currently shown
        self.setObjectName("page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 12)
        root.setSpacing(14)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        h1 = QLabel("My Library")
        h1.setObjectName("h1")
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("muted")
        titles.addWidget(h1)
        titles.addWidget(self.subtitle)
        self.goal_label = QLabel("")
        self.goal_label.setObjectName("muted")
        titles.addWidget(self.goal_label)
        head.addLayout(titles)
        head.addStretch()
        self._continue_id = None
        self.btn_continue = QPushButton("")
        self.btn_continue.setObjectName("tonal")
        self.btn_continue.setVisible(False)
        self.btn_continue.clicked.connect(
            lambda: self._continue_id and self.continueRequested.emit(self._continue_id))
        stats = QPushButton("Reading Stats")
        stats.clicked.connect(self.statsRequested.emit)
        add_folder = QPushButton("Add Folder")
        add_folder.clicked.connect(self.addFolderRequested.emit)
        add_books = QPushButton("＋  Add Books")
        add_books.setObjectName("primary")
        add_books.clicked.connect(self.addFilesRequested.emit)
        aa = None
        if prefs is not None:  # the same appearance panel as in the readers
            self.appearance = AppearancePanel(prefs)
            aa_menu = QMenu(self)
            wa = QWidgetAction(aa_menu)
            wa.setDefaultWidget(self.appearance)
            aa_menu.addAction(wa)
            aa_menu.aboutToShow.connect(self.appearance.sync)
            aa = QToolButton()
            aa.setText("Aa")
            aa.setToolTip("Appearance: colour theme and fonts for the whole app (Ctrl+,)")
            aa.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            aa.setMenu(aa_menu)
            bold = aa.font()
            bold.setBold(True)
            aa.setFont(bold)
            self._restyle = QTimer(self, singleShot=True, interval=140)
            self._restyle.timeout.connect(self.prefsChanged.emit)
            self.appearance.changed.connect(self._restyle.start)
        more = QToolButton()
        more.setText("⋯")
        more.setToolTip("Library tools: back up and restore")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(more)
        more_menu.addAction("Back up library…").triggered.connect(lambda: self.backupRequested.emit())
        more_menu.addAction("Restore from backup…").triggered.connect(
            lambda: self.restoreRequested.emit())
        more.setMenu(more_menu)
        self.btn_notes = QPushButton("📝  Notes")
        self.btn_notes.setToolTip("Search all notes, daily review inbox, dashboard, export and sync (Ctrl+Shift+F)")
        self.btn_notes.clicked.connect(lambda: self.notesRequested.emit())
        head.addWidget(self.btn_continue)
        head.addWidget(self.btn_notes)
        head.addWidget(stats)
        head.addWidget(add_folder)
        head.addWidget(add_books)
        head.addWidget(more)
        if aa is not None:
            head.addWidget(aa)
        root.addLayout(head)

        tools = QHBoxLayout()
        self.btn_all = QPushButton("All Books")
        self.btn_reading = QPushButton("Reading List")
        self.btn_cat = QPushButton("Catalogue")
        scope = QButtonGroup(self)
        scope.setExclusive(True)
        for b in (self.btn_all, self.btn_reading, self.btn_cat):
            b.setCheckable(True)
            scope.addButton(b)
            b.clicked.connect(lambda _=False: self.refresh())
        self.btn_all.setChecked(True)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(300)
        self.search.textChanged.connect(lambda _=None: self.refresh())
        self.field = QComboBox()
        self.field.addItems(["Title & Author", "Title", "Author", "Subject", "Tag", "Collection"])
        self.field.currentTextChanged.connect(self._on_field)
        self.fmt = QComboBox()
        self.fmt.addItems(["All formats", "EPUB", "PDF", "Markdown"])
        self.fmt.currentTextChanged.connect(lambda _=None: self.refresh())
        self.sort = QComboBox()
        self.sort.addItems(["Recently read", "Recently added", "Title", "Author",
                            "Most read time", "Progress"])
        self.sort.currentTextChanged.connect(lambda _=None: self.refresh())
        tools.addWidget(self.btn_all)
        tools.addWidget(self.btn_reading)
        tools.addWidget(self.btn_cat)
        tools.addSpacing(12)
        tools.addWidget(self.search)
        tools.addWidget(QLabel("in"))
        tools.addWidget(self.field)
        tools.addSpacing(8)
        tools.addWidget(self.fmt)
        tools.addStretch()
        tools.addWidget(QLabel("Sort by"))
        tools.addWidget(self.sort)
        root.addLayout(tools)
        self._on_field(self.field.currentText())

        self.stack = QStackedWidget()

        # catalogue panel: group books by subject / folder / author
        self.cat_panel = QWidget()
        self.cat_panel.setObjectName("sidePanel")
        self.cat_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.cat_panel.setMinimumWidth(230)
        cl = QVBoxLayout(self.cat_panel)
        cl.setContentsMargins(14, 14, 8, 10)
        cl.setSpacing(8)
        ch = QLabel("Catalogue")
        ch.setObjectName("h2")
        cl.addWidget(ch)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Group by"))
        self.cat_mode = QComboBox()
        self.cat_mode.addItems(["Subject", "Tag", "Collection", "Folder", "Author"])
        self.cat_mode.currentTextChanged.connect(lambda _=None: self.refresh())
        mode_row.addWidget(self.cat_mode, 1)
        cl.addLayout(mode_row)
        self.cat_tree = QTreeWidget()
        self.cat_tree.setHeaderHidden(True)
        self.cat_tree.currentItemChanged.connect(self._on_cat_select)
        cl.addWidget(self.cat_tree, 1)
        self.cat_hint = QLabel("")
        self.cat_hint.setObjectName("muted")
        self.cat_hint.setWordWrap(True)
        cl.addWidget(self.cat_hint)

        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setHandleWidth(1)
        self.split.addWidget(self.cat_panel)
        self.split.addWidget(self.stack)
        self.split.setStretchFactor(1, 1)
        self.split.setCollapsible(1, False)
        self.split.setSizes([270, 900])
        self.cat_panel.hide()
        self.coll_bar = QWidget()
        cb = QHBoxLayout(self.coll_bar)
        cb.setContentsMargins(0, 0, 0, 0)
        cb.setSpacing(10)
        back = QPushButton("←  All books")
        back.setObjectName("tonal")
        back.clicked.connect(lambda: self.close_collection())
        self.coll_title = QLabel("")
        self.coll_title.setObjectName("h2")
        self.coll_count = QLabel("")
        self.coll_count.setObjectName("muted")
        rename = QPushButton("Rename")
        rename.setObjectName("link")
        rename.clicked.connect(lambda: self._rename_collection(self.open_collection))
        delete = QPushButton("Delete collection")
        delete.setObjectName("link")
        delete.setToolTip("Removes the collection only; the books stay in your library")
        delete.clicked.connect(lambda: self._delete_collection(self.open_collection))
        for w in (back, self.coll_title, self.coll_count):
            cb.addWidget(w)
        cb.addStretch()
        cb.addWidget(rename)
        cb.addWidget(delete)
        self.coll_bar.hide()
        root.addWidget(self.coll_bar)
        root.addWidget(self.split, 1)

        self.shelf = QListWidget()
        self.shelf.setObjectName("shelf")
        self.shelf.setViewMode(QListView.ViewMode.IconMode)
        self.shelf.setIconSize(QSize(COVER_W, COVER_H))
        self.shelf.setGridSize(QSize(190, 332))
        self.shelf.setResizeMode(QListView.ResizeMode.Adjust)
        self.shelf.setMovement(QListView.Movement.Static)
        self.shelf.setWordWrap(True)
        self.shelf.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.shelf.setUniformItemSizes(True)
        self.shelf.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.shelf.setFrameShape(QFrame.Shape.NoFrame)
        self.shelf.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.shelf.customContextMenuRequested.connect(self._menu)
        self.shelf.itemDoubleClicked.connect(lambda it: self._open(it))
        QShortcut(QKeySequence(Qt.Key.Key_Return), self.shelf,
                  context=Qt.ShortcutContext.WidgetShortcut).activated.connect(
            lambda: self._open(self.shelf.currentItem()))
        for key in (Qt.Key.Key_Backspace, Qt.Key.Key_Escape):
            QShortcut(QKeySequence(key), self.shelf,
                      context=Qt.ShortcutContext.WidgetShortcut).activated.connect(
                lambda: self.close_collection())
        self.stack.addWidget(self.shelf)

        empty = QWidget()
        el = QVBoxLayout(empty)
        el.addStretch()
        t1 = QLabel("Your library is empty")
        t1.setObjectName("h1")
        t1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t2 = QLabel("Add EPUB, PDF or Markdown documents to start reading.\nYou can also drag and drop "
                    "files anywhere in this window.")
        t2.setObjectName("muted")
        t2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn = QPushButton("＋  Add Books")
        btn.setObjectName("primary")
        btn.setMinimumHeight(40)
        btn.setMaximumWidth(220)
        btn.clicked.connect(self.addFilesRequested.emit)
        el.addWidget(t1)
        el.addWidget(t2)
        el.addSpacing(10)
        el.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        el.addStretch()
        self.stack.addWidget(empty)

    def _on_field(self, text):
        self.search.setPlaceholderText({
            "Title": "Search by title…", "Author": "Search by author…",
            "Subject": "Search by subject…", "Tag": "Search by tag…",
            "Collection": "Search by collection…",
        }.get(text, "Search by title or author…"))
        self.refresh()

    def set_inbox_count(self, n: int):
        """Badge on the Notes button: how many notes are due for review today."""
        self.btn_notes.setText(f"📝  Notes · {n} to review" if n else "📝  Notes")
        self.btn_notes.setObjectName("tonal" if n else "")
        self.btn_notes.style().unpolish(self.btn_notes)
        self.btn_notes.style().polish(self.btn_notes)

    def show_message(self, text: str):
        self.subtitle.setText(text)
        QTimer.singleShot(5000, self._update_subtitle)

    def _update_subtitle(self):
        n = self.library.count()
        self.subtitle.setText(f"{n} book{'s' if n != 1 else ''}" if n else "")

    def refresh(self):
        if not hasattr(self, "shelf"):  # called while the page is still being built
            return
        total = self.library.count()
        self.btn_reading.setText(f"Reading List ({self.library.count_reading()})")
        cid = self.library.continue_book()
        self._continue_id = cid
        if cid:
            t = textwrap.shorten(self.library.get(cid)["title"], 26, placeholder="…")
            self.btn_continue.setText(f"▶  Continue: {t}")
        self.btn_continue.setVisible(bool(cid))
        self._update_subtitle()
        if self.prefs is not None:
            self.goal_label.setText(goals.header_text(
                goals.summary(self.library, self.prefs.v["daily_goal"])))
        query = self.search.text().strip()
        reading_only = self.btn_reading.isChecked()
        rows = self.library.list_books(
            query, self.sort.currentText(), self.field.currentText(), self.fmt.currentText(),
            "Reading List" if reading_only else "All books")
        in_cat = self.btn_cat.isChecked() and total > 0
        self.cat_panel.setVisible(in_cat)
        if in_cat:
            rows = self._catalogue(rows)
        collections: dict[str, list] = {}
        if in_cat or reading_only:
            self.open_collection = None
        else:
            cmap = self.library.labels_map("collections")
            if self.open_collection:  # collection page: only this collection's books
                key = self.open_collection.lower()
                rows = [r for r in rows if any(n.lower() == key for n in cmap.get(r["id"], []))]
                if not rows and key not in {n.lower() for v in cmap.values() for n in v}:
                    self.open_collection = None  # it was deleted or emptied
                    self.refresh()
                    return
            elif not query:  # main view: a tile per collection, then the ungrouped books
                for r in rows:
                    for n in cmap.get(r["id"], []):
                        collections.setdefault(n, []).append(r)
                rows = [r for r in rows if not cmap.get(r["id"])]
        self.coll_bar.setVisible(bool(self.open_collection))
        if self.open_collection:
            self.coll_title.setText(f"📚  {self.open_collection}")
            self.coll_count.setText(f"{len(rows)} book{'' if len(rows) == 1 else 's'}")
        subs = self.library.subjects_map()
        tags = self.library.labels_map("tags")
        colls = self.library.labels_map("collections")
        self.shelf.clear()
        for name in sorted(collections, key=str.lower):
            members = collections[name]
            n = len(members)
            item = QListWidgetItem(
                QIcon(make_collection_tile(name, members)),
                f"{textwrap.shorten(name, 44, placeholder='…')}\n"
                f"Collection · {n} book{'' if n == 1 else 's'}")
            item.setData(Qt.ItemDataRole.UserRole + 1, name)
            item.setToolTip(f"{name}\n" + "\n".join(f"• {r['title']}" for r in members[:8])
                            + ("\n…" if n > 8 else "") + "\n\nDouble-click to open")
            item.setSizeHint(QSize(180, 322))
            self.shelf.addItem(item)
        for r in rows:
            p = r["progress"] or 0
            pct = ("Finished" if p >= 0.98
                   else f"{int(p * 100)}%" if p > 0.005 else "New")
            parts = [(r["format"] or "epub").upper(), pct]
            if (r["read_seconds"] or 0) >= 60:
                parts.append(fmt_duration(r["read_seconds"]))
            title = textwrap.shorten(r["title"], 44, placeholder="…")
            last = r["last_read_at"] or 0
            lines = [title, " · ".join(parts)]
            if last:
                lines.append(f"Last read {ago(last)}")
            item = QListWidgetItem(
                QIcon(make_cover(r["title"], r["author"], r["cover"], p, r["reading"] == 1)),
                "\n".join(lines))
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            tip = f"{r['title']}\n{r['author']}".strip()
            if subs.get(r["id"]):
                tip += "\nSubjects: " + ", ".join(subs[r["id"]])
            if tags.get(r["id"]):
                tip += "\nTags: " + ", ".join(tags[r["id"]])
            if colls.get(r["id"]):
                tip += "\nCollections: " + ", ".join(colls[r["id"]])
            if r["folder"]:
                tip += f"\nFolder: {r['folder']}"
            n_notes = self.library.count_book_notes(r["id"])
            if n_notes:
                tip += f"\nBook notes: {n_notes}"
            n_maps = self.library.count_mindmaps(r["id"])
            if n_maps:
                tip += f"\nMind maps: {n_maps}"
            if last:
                tip += f"\nLast read: {datetime.fromtimestamp(last):%Y-%m-%d %H:%M}"
            item.setToolTip(tip)
            item.setSizeHint(QSize(180, 322))
            self.shelf.addItem(item)
        if total and not rows and not collections:
            self.subtitle.setText(
                "Your reading list is empty — read a book for a moment, or right-click a "
                "book and choose “Mark as currently reading”"
                if reading_only and not query else "No books match your search")
        self.stack.setCurrentIndex(0 if total else 1)

    # -- catalogue ---------------------------------------------------------- #

    _SEP = "\x1f"

    def _catalogue(self, rows):
        """Rebuild the group tree from the (already filtered) rows and return the
        rows that belong to the selected group."""
        mode = self.cat_mode.currentText()
        none_label = {"Subject": "(No subject)", "Folder": "(No folder)",
                      "Author": "(Unknown author)", "Tag": "(No tag)",
                      "Collection": "(No collection)"}[mode]
        self.cat_hint.setText({
            "Subject": "Subjects come from the book metadata. Right-click books → "
                       "Set subjects… to organise them (select several at once).",
            "Folder": "Books are grouped by the folder they were added from. "
                      "Right-click → Set folder… to move them.",
            "Author": "Books grouped by author.",
            "Tag": "Your own labels. Right-click books → Set tags… (select several at once).",
            "Collection": "Hand-picked shelves such as “To read” or “Favourites”. "
                          "Right-click books → Add to collections…",
        }[mode])
        subs = (self.library.subjects_map() if mode == "Subject"
                else self.library.labels_map("tags") if mode == "Tag"
                else self.library.labels_map("collections") if mode == "Collection" else {})

        def keys(r):  # group paths (tuples) a book belongs to
            if mode in ("Subject", "Tag", "Collection"):
                return [(sub,) for sub in subs.get(r["id"], [])] or [(none_label,)]
            if mode == "Author":
                return [((r["author"] or "").strip() or none_label,)]
            folder = (r["folder"] or "").strip("/ ")
            return [tuple(folder.split("/"))] if folder else [(none_label,)]

        counts: dict = {}
        for r in rows:
            nodes = {k[:i] for k in keys(r) for i in range(1, len(k) + 1)}
            for node in nodes:
                counts[node] = counts.get(node, 0) + 1

        tree = self.cat_tree
        tree.blockSignals(True)
        tree.clear()
        top = QTreeWidgetItem(tree, [f"All books ({len(rows)})"])
        top.setData(0, Qt.ItemDataRole.UserRole, "")
        items = {(): top}
        order = sorted(counts, key=lambda p: tuple((x == none_label, x.lower()) for x in p))
        for path in order:
            item = QTreeWidgetItem(items[path[:-1]], [f"{path[-1]} ({counts[path]})"])
            item.setData(0, Qt.ItemDataRole.UserRole, self._SEP.join(path))
            items[path] = item
        sel = self._cat_sel.get(mode, ())
        if sel not in items:
            sel = ()
        self._cat_sel[mode] = sel
        tree.setCurrentItem(items[sel])
        tree.expandAll()
        tree.blockSignals(False)
        if not sel:
            return rows
        return [r for r in rows if any(k[:len(sel)] == sel for k in keys(r))]

    def _on_cat_select(self, current, _previous):
        if current is None:
            return
        raw = current.data(0, Qt.ItemDataRole.UserRole) or ""
        self._cat_sel[self.cat_mode.currentText()] = tuple(raw.split(self._SEP)) if raw else ()
        QTimer.singleShot(0, self.refresh)  # rebuild after this signal has finished

    def _edit_subjects(self, ids):
        smap = self.library.subjects_map()
        counts: dict = {}
        for i in ids:
            for name in smap.get(i, []):
                counts[name] = counts.get(name, 0) + 1
        dlg = SubjectDialog(self, self.library.all_subjects(), counts, len(ids))
        if dlg.exec():
            add, remove = dlg.changes()
            for i in ids:
                self.library.add_subjects(i, add)
                self.library.remove_subjects(i, remove)
            self.refresh()

    def _edit_labels(self, ids, kind):
        """Tags / collections editor (same picker as subjects)."""
        lmap = self.library.labels_map(kind)
        counts: dict = {}
        for i in ids:
            for name in lmap.get(i, []):
                counts[name] = counts.get(name, 0) + 1
        dlg = SubjectDialog(self, self.library.all_labels(kind), counts, len(ids), kind)
        if dlg.exec():
            add, remove = dlg.changes()
            for i in ids:
                self.library.add_labels(kind, i, add)
                self.library.remove_labels(kind, i, remove)
            self.refresh()

    def _edit_folder(self, ids):
        current = (self.library.get(ids[0])["folder"] or "") if len(ids) == 1 else ""
        text, ok = QInputDialog.getText(
            self, "Set folder",
            "Folder group (use / for sub-folders, e.g. Programming/Python).\n"
            "Leave empty to clear:", QLineEdit.EchoMode.Normal, current)
        if ok:
            label = "/".join(p.strip() for p in text.replace("\\", "/").split("/") if p.strip())
            for i in ids:
                self.library.set_folder(i, label)
            self.refresh()

    def _open(self, item):
        if item is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole + 1)
        if name:
            self.open_collection_page(name)
        else:
            self.openRequested.emit(item.data(Qt.ItemDataRole.UserRole))

    # -- collection pages ------------------------------------------------------ #

    def open_collection_page(self, name: str):
        self.open_collection = name
        self.search.clear()
        self.refresh()

    def close_collection(self):
        if self.open_collection:
            self.open_collection = None
            self.refresh()

    def _rename_collection(self, name):
        if not name:
            return
        text, ok = QInputDialog.getText(self, "Rename collection", "New name:",
                                        QLineEdit.EchoMode.Normal, name)
        new = " ".join(text.split())
        if ok and new:
            self.library.rename_label("collections", name, new)
            if self.open_collection and self.open_collection.lower() == name.lower():
                self.open_collection = new
            self.refresh()

    def _delete_collection(self, name):
        if not name:
            return
        answer = QMessageBox.question(
            self, "Delete collection",
            f"Delete the collection “{name}”?\n\nThe books stay in your library; they just "
            "leave this collection.")
        if answer == QMessageBox.StandardButton.Yes:
            self.library.delete_label("collections", name)
            if self.open_collection and self.open_collection.lower() == name.lower():
                self.open_collection = None
            self.refresh()

    def _remove_from_open(self, ids):
        for i in ids:
            self.library.remove_labels("collections", i, [self.open_collection])
        self.refresh()

    def _collection_menu(self, name, pos):
        menu = QMenu(self)
        menu.addAction("Open collection").triggered.connect(
            lambda: self.open_collection_page(name))
        menu.addAction("Rename…").triggered.connect(lambda: self._rename_collection(name))
        menu.addSeparator()
        menu.addAction("Delete collection…").triggered.connect(
            lambda: self._delete_collection(name))
        menu.exec(self.shelf.mapToGlobal(pos))

    def _menu(self, pos):
        item = self.shelf.itemAt(pos)
        if not item:
            return
        cname = item.data(Qt.ItemDataRole.UserRole + 1)
        if cname:
            self._collection_menu(cname, pos)
            return
        bid = item.data(Qt.ItemDataRole.UserRole)
        selected = [it.data(Qt.ItemDataRole.UserRole) for it in self.shelf.selectedItems()
                    if it.data(Qt.ItemDataRole.UserRole) is not None]
        ids = selected if bid in selected else [bid]
        suffix = f"  ({len(ids)} books)" if len(ids) > 1 else ""
        row = self.library.get(bid)
        menu = QMenu(self)
        menu.addAction("Open").triggered.connect(lambda: self.openRequested.emit(bid))
        if row is not None and row["reading"] == 1:
            menu.addAction("Remove from reading list").triggered.connect(
                lambda: self._set_reading(bid, False))
        else:
            menu.addAction("Mark as currently reading").triggered.connect(
                lambda: self._set_reading(bid, True))
        menu.addSeparator()
        menu.addAction(f"Set subjects…{suffix}").triggered.connect(
            lambda: self._edit_subjects(ids))
        menu.addAction(f"Set folder…{suffix}").triggered.connect(
            lambda: self._edit_folder(ids))
        menu.addAction(f"Set tags…{suffix}").triggered.connect(
            lambda: self._edit_labels(ids, "tags"))
        menu.addAction(f"Add to collections…{suffix}").triggered.connect(
            lambda: self._edit_labels(ids, "collections"))
        if self.open_collection:
            menu.addAction(f"Remove from “{self.open_collection}”{suffix}").triggered.connect(
                lambda: self._remove_from_open(ids))
        menu.addSeparator()
        menu.addAction("Review notes (flashcards)…").triggered.connect(
            lambda: self.reviewRequested.emit(bid))
        menu.addAction("Mind maps…").triggered.connect(lambda: self.mindmapRequested.emit(bid))
        menu.addSeparator()
        menu.addAction("Remove from library…").triggered.connect(
            lambda: self.removeRequested.emit(bid))
        menu.exec(self.shelf.mapToGlobal(pos))

    def _set_reading(self, book_id, on):
        self.library.set_reading(book_id, on)
        self.refresh()

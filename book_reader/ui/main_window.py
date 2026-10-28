"""Main window: page stack, theme, adding books, drag & drop."""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QFont, QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QStackedWidget,
)

from book_reader.constants import BOOK_EXTS
from book_reader.core.library import Library
from book_reader.core.prefs import Prefs
from book_reader.core.tracker import ReadingTracker
from book_reader.services import backup, inbox
from book_reader.services.notes_sync import NotesSync
from book_reader.services.summary import SummaryBuilder, stored_highlights
from book_reader.themes import THEMES, build_qss
from book_reader.ui.dialogs.appearance_dialog import AppearanceDialog
from book_reader.ui.dialogs.flashcard_dialog import FlashcardDialog
from book_reader.ui.dialogs.mindmap_dialog import MindMapDialog
from book_reader.ui.dialogs.notes_hub_dialog import NotesHubDialog
from book_reader.ui.dialogs.reminder_dialog import ReminderDialog
from book_reader.ui.dialogs.stats_dialog import StatsDialog
from book_reader.ui.pages.library_page import LibraryPage
from book_reader.ui.pages.pdf_page import PdfPage
from book_reader.ui.pages.reader_page import ReaderPage
from book_reader.ui.updates import UpdateManager
from book_reader.utils import folder_label


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.prefs = Prefs()
        self._default_font = QFont(QApplication.font())  # the font chosen at start-up
        self.library = Library()
        self.tracker = ReadingTracker(self.library, self)
        self.sync = NotesSync(self.library, self.prefs, self)
        self.library.add_listener(self.sync.schedule)
        self._qss_theme = None
        self.setWindowTitle("Book Reader")
        self.resize(1180, 820)
        self.setAcceptDrops(True)

        self.stack = QStackedWidget()
        self.library_page = LibraryPage(self.library, self.prefs)
        self.reader_page = ReaderPage(self.library, self.prefs, self.tracker)
        self.pdf_page = PdfPage(self.library, self.prefs, self.tracker)
        self.stack.addWidget(self.library_page)
        self.stack.addWidget(self.reader_page)
        self.stack.addWidget(self.pdf_page)
        self.setCentralWidget(self.stack)

        self.library_page.openRequested.connect(self.open_book)
        self.library_page.addFilesRequested.connect(self.add_files_dialog)
        self.library_page.addFolderRequested.connect(self.add_folder_dialog)
        self.library_page.removeRequested.connect(self.remove_book)
        self.library_page.statsRequested.connect(self.show_stats)
        self.library_page.continueRequested.connect(self.open_book)
        self.library_page.backupRequested.connect(self.backup_library)
        self.library_page.restoreRequested.connect(self.restore_library)
        self.updates = UpdateManager(self, self.prefs)
        self.library_page.updatesRequested.connect(self.updates.check_now)
        self.library_page.reviewRequested.connect(self.review_notes)
        self.library_page.mindmapRequested.connect(self.open_mindmaps)
        self.library_page.notesRequested.connect(lambda: self.open_notes_hub())
        self.library_page.prefsChanged.connect(self.on_prefs_changed)
        self.library_page.appearanceRequested.connect(self.open_appearance)
        self.library_page.modeToggleRequested.connect(self.toggle_mode)
        QShortcut(QKeySequence("Ctrl+Shift+L"), self).activated.connect(self.toggle_mode)
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._system_scheme_changed)
        QShortcut(QKeySequence("Ctrl+,"), self).activated.connect(self.open_appearance)
        for page in (self.reader_page, self.pdf_page):
            page.backRequested.connect(self.show_library)
            page.prefsChanged.connect(self.on_prefs_changed)
            page.appearanceRequested.connect(self.open_appearance)
            page.modeToggleRequested.connect(self.toggle_mode)
            page.noteLinkRequested.connect(self.follow_note_link)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self).activated.connect(lambda: self.open_notes_hub())

        fs = QAction(self)
        fs.setShortcut("F11")
        fs.triggered.connect(self.toggle_fullscreen)
        self.addAction(fs)

        self.apply_theme()
        self.show_library()
        if self.sync.enabled():  # refresh the sync folder shortly after start-up
            QTimer.singleShot(2500, self.sync.sync_all)
        QTimer.singleShot(5000, self.updates.check_on_startup)  # quiet, at most once a day

    # -- theme -------------------------------------------------------------- #

    def apply_theme(self):
        """Colour theme and interface font for the whole application."""
        v = self.prefs.v
        key = (v["theme"], int(v["ui_font_size"]), v["ui_font"])
        if key != self._qss_theme:
            font = QFont(self._default_font)
            if v["ui_font"]:
                font.setFamily(v["ui_font"])
            font.setPointSizeF(float(v["ui_font_size"]))
            QApplication.setFont(font)
            QApplication.instance().setStyleSheet(build_qss(THEMES[v["theme"]], v["ui_font_size"] / 10))
            self._qss_theme = key

    def on_prefs_changed(self):
        """A setting changed anywhere: restyle everything that is on screen."""
        self.apply_theme()
        self.reader_page.apply_style()
        self.pdf_page.apply_style()
        self.library_page.refresh()
        theme = THEMES[self.prefs.v["theme"]]
        for dlg in (self.reader_page._mm_dialog, self.pdf_page._mm_dialog,
                    getattr(self, "_mm_dialog", None)):
            if dlg is not None:
                dlg.set_theme(theme)

    def open_appearance(self):
        """Appearance dialog (Ctrl+, / Aa): mode, colours and fonts apply live."""
        dlg = AppearanceDialog(self, self.prefs)
        dlg.applied.connect(self.on_prefs_changed)
        dlg.exec()

    def toggle_mode(self):
        """Quick switch between light and dark (Ctrl+Shift+L)."""
        self.prefs.set("theme_mode", "Light" if self.prefs.is_dark() else "Dark")
        self.on_prefs_changed()

    def _system_scheme_changed(self, *_):
        if self.prefs.v["theme_mode"] == "System":  # follow the operating system
            self.prefs.resolve()
            self.on_prefs_changed()

    def toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    # -- pages -------------------------------------------------------------- #

    def show_library(self):
        self.reader_page.close_book()
        self.pdf_page.close_book()
        self.setWindowTitle("Book Reader")
        self.library_page.refresh()
        self.library_page.set_inbox_count(inbox.count_due(self.library))
        self.stack.setCurrentWidget(self.library_page)

    def open_book(self, book_id: int):
        row = self.library.get(book_id)
        if row is None:
            return
        page = self.pdf_page if row["format"] == "pdf" else self.reader_page
        if page.open_book(book_id):
            self.setWindowTitle(f"{row['title']} — Book Reader")
            self.stack.setCurrentWidget(page)

    # -- notes hub, note links, sync ---------------------------------------------- #

    def open_notes_hub(self, tab: int = 0):
        book_id = (self.reader_page.book_id if self.stack.currentWidget() is self.reader_page
                   else self.pdf_page.book_id if self.stack.currentWidget() is self.pdf_page else None)
        dlg = NotesHubDialog(self, self.library, self.prefs, self.sync,
                             THEMES[self.prefs.v["theme"]], tab, book_id)
        dlg.openRequested.connect(self.open_entry)
        dlg.exec()
        if self.stack.currentWidget() is self.library_page:
            self.library_page.set_inbox_count(inbox.count_due(self.library))

    def open_entry(self, e: dict):
        """Open the book a note belongs to and scroll to the note."""
        row = self.library.get(e["book_id"])
        if row is None:
            return
        self.open_book(e["book_id"])
        page = self.pdf_page if row["format"] == "pdf" else self.reader_page
        QTimer.singleShot(300, lambda: self._jump_to_entry(page, e))

    def _jump_to_entry(self, page, e: dict):
        if page.book_id != e["book_id"]:
            return
        if e["kind"] == "note":
            page.jump_to_location(e["index"], e["pos"])
            if page.journal.isHidden():
                page.act_journal.setChecked(True)
        elif e["kind"] == "highlight":
            page.jump_to_note(e["id"])
        else:
            page.jump_to_mark(e["id"])

    def follow_note_link(self, url: str):
        """A [[note:ID]] link inside a note was clicked."""
        if not url.startswith("note:"):
            return
        row = self.library.book_note(int(url[5:]))
        if row is None:
            QMessageBox.information(self, "Note not found", "The linked note no longer exists.")
            return
        self.open_entry(dict(kind="note", id=row["id"], book_id=row["book_id"],
                             index=row["spine_index"] or 0, pos=row["scroll_ratio"] or 0.0))

    def show_stats(self):
        StatsDialog(self, self.library, self.prefs).exec()
        self.library_page.refresh()  # goal / streak line

    def show_reminder(self):
        """Startup reminder: last book read, where you stopped, links to reopen."""
        if not self.prefs.v["show_reminder"]:
            return
        last = self.library.last_read_book()
        if last is None:
            return
        others = [r for r in self.library.reading_list(6) if r["id"] != last["id"]][:4]
        dlg = ReminderDialog(self, last, others, THEMES[self.prefs.v["theme"]])
        dlg.exec()
        self.prefs.set("show_reminder", dlg.show_again())
        if dlg.chosen is not None:
            self.open_book(dlg.chosen)

    def remove_book(self, book_id: int):
        row = self.library.get(book_id)
        if not row:
            return
        answer = QMessageBox.question(
            self, "Remove book",
            f"Remove “{row['title']}” from your library?\n\n"
            "Its notes, highlights, book notes and reading history will be deleted too. "
            "Your original file is not touched.")
        if answer == QMessageBox.StandardButton.Yes:
            self.library.remove_book(book_id)
            self.library_page.refresh()

    # -- backup, restore, review ---------------------------------------------- #

    def _progress(self, text: str) -> QProgressDialog:
        dlg = QProgressDialog(text, "", 0, 100, self)
        dlg.setCancelButton(None)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        return dlg

    @staticmethod
    def _tick(dlg: QProgressDialog, done: int, total: int):
        dlg.setValue(int(done / max(1, total) * 100))
        QApplication.processEvents()

    def backup_library(self):
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        path, _ = QFileDialog.getSaveFileName(
            self, "Back up library", str(Path.home() / f"book-reader-backup-{stamp}.zip"),
            "Backup (*.zip)")
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        self.show_library()  # saves the position and time of an open book first
        dlg = self._progress("Backing up library…")
        try:
            info = backup.create_backup(self.library, Path(path),
                                        lambda d, n: self._tick(dlg, d, n))
        except Exception as exc:
            dlg.close()
            QMessageBox.critical(self, "Backup failed", str(exc))
            return
        dlg.close()
        self.library_page.show_message(f"Backup saved · {info['books']} book(s)")

    def restore_library(self):
        path, _ = QFileDialog.getOpenFileName(self, "Restore from backup", str(Path.home()),
                                              "Backup (*.zip)")
        if not path:
            return
        try:
            info = backup.inspect_backup(Path(path))
        except backup.BackupError as exc:
            QMessageBox.warning(self, "Cannot restore", str(exc))
            return
        answer = QMessageBox.question(
            self, "Restore library",
            f"Replace your current library with this backup "
            f"({info.get('books', '?')} books, made {info.get('created', 'unknown date')})?\n\n"
            "A safety copy of your current library is saved first.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.show_library()
        dlg = self._progress("Restoring library…")
        try:
            backup.restore_backup(self.library, Path(path), lambda d, n: self._tick(dlg, d, n))
        except Exception as exc:
            dlg.close()
            self.library_page.refresh()
            QMessageBox.critical(self, "Restore failed", str(exc))
            return
        dlg.close()
        self.library_page.refresh()
        self.library_page.show_message("Library restored · your previous copy is in safety-backups")

    def open_mindmaps(self, book_id: int):
        """Mind maps for a book that is not open (no jumping to the text)."""
        row = self.library.get(book_id)
        if row is None:
            return
        label = (lambda i: f"Page {i + 1}") if row["format"] == "pdf" else \
            (lambda i: f"Section {i + 1}")
        builder = SummaryBuilder(self.library, book_id,
                                 lambda: stored_highlights(self.library, book_id), label)
        old, self._mm_dialog = getattr(self, "_mm_dialog", None), None
        if old is not None:
            old.close()
        dlg = MindMapDialog(self, self.library, builder, THEMES[self.prefs.v["theme"]],
                            can_jump=False)
        self._mm_dialog = dlg
        dlg.show()

    def review_notes(self, book_id: int):
        """Flashcards / quizzes for a book that is not open."""
        row = self.library.get(book_id)
        if row is None:
            return
        label = (lambda i: f"Page {i + 1}") if row["format"] == "pdf" else \
            (lambda i: f"Section {i + 1}")
        builder = SummaryBuilder(self.library, book_id,
                                 lambda: stored_highlights(self.library, book_id), label)
        if not builder.entries():
            QMessageBox.information(self, "Nothing to review",
                                    "This book has no notes or highlights yet.")
            return
        FlashcardDialog(self, builder, THEMES[self.prefs.v["theme"]]).exec()

    # -- adding books ------------------------------------------------------- #

    def add_files_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add books", "",
            "Books (*.epub *.pdf *.md *.markdown);;EPUB books (*.epub);;PDF documents (*.pdf);;"
            "Markdown documents (*.md *.markdown)")
        self.add_files(paths)

    def add_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(self, "Add all EPUB, PDF and Markdown files in a folder")
        if folder:
            root = Path(folder)
            found = self._books_in(root)
            self.add_files(found, self._labels(root, found))

    @staticmethod
    def _books_in(folder: Path):
        def hidden(p: Path) -> bool:  # skip .git, node_modules and similar
            return any(part.startswith(".") or part == "node_modules"
                       for part in p.relative_to(folder).parts[:-1])

        return sorted(str(p) for p in folder.rglob("*")
                      if p.suffix.lower() in BOOK_EXTS and not hidden(p))

    @staticmethod
    def _labels(root: Path, found) -> dict:
        return {f: folder_label(root, Path(f)) for f in found}

    def add_files(self, paths, labels=None):
        paths = list(paths)
        labels = labels or {}
        if not paths:
            return
        progress = QProgressDialog("Adding books…", "", 0, len(paths), self)
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(400)
        added, duplicates, errors = 0, 0, []
        for i, path in enumerate(paths):
            progress.setLabelText(f"Adding {Path(path).name}…")
            progress.setValue(i)
            QApplication.processEvents()
            status, _, err = self.library.add_book(path, labels.get(path, ""))
            if status == "added":
                added += 1
            elif status == "duplicate":
                duplicates += 1
            else:
                errors.append(err)
        progress.setValue(len(paths))

        self.show_library()  # also stops any open book and its reading clock
        parts = []
        if added:
            parts.append(f"Added {added} book{'s' if added != 1 else ''}")
        if duplicates:
            parts.append(f"{duplicates} already in library")
        if parts:
            self.library_page.show_message(" · ".join(parts))
        if errors:
            QMessageBox.warning(self, "Some books couldn't be added", "\n".join(errors[:10]))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths, labels = [], {}
        for url in event.mimeData().urls():
            p = Path(url.toLocalFile())
            if p.is_dir():
                found = self._books_in(p)
                paths += found
                labels.update(self._labels(p, found))
            elif p.suffix.lower() in BOOK_EXTS:
                paths.append(str(p))
        self.add_files(paths, labels)

    def closeEvent(self, event):
        self.reader_page.close_book()
        self.pdf_page.close_book()
        super().closeEvent(event)

"""Behaviour shared by both reader pages: reading list and book journal."""
import textwrap

from PySide6.QtWidgets import QMenu, QMessageBox

from book_reader.services import dictionary
from book_reader.services.export import export_summary_dialog
from book_reader.services.journal import note_entry, ref_text
from book_reader.services.summary import SummaryBuilder
from book_reader.themes import THEMES
from book_reader.ui.dialogs.bookmarks_dialog import BookmarksDialog
from book_reader.ui.dialogs.flashcard_dialog import FlashcardDialog
from book_reader.ui.dialogs.journal_note_dialog import JournalNoteDialog
from book_reader.ui.dialogs.lookup_dialog import LookupDialog
from book_reader.ui.dialogs.mindmap_dialog import MindMapDialog
from book_reader.ui.dialogs.note_picker_dialog import NotePickerDialog
from book_reader.ui.dialogs.summary_dialog import SummaryDialog
from book_reader.ui.widgets.journal_panel import BookNotesPanel


class ReadingListMixin:
    """Needs: self.act_reading (checkable QAction), self.library, self.book_id, self.flash()."""

    def _sync_reading(self, on: bool):
        self.act_reading.blockSignals(True)
        self.act_reading.setChecked(on)
        self.act_reading.blockSignals(False)
        self.act_reading.setText("★  Reading" if on else "☆  Reading")

    def toggle_reading(self, on):
        if self.book_id is None:
            return
        on = bool(on)
        self.library.set_reading(self.book_id, on)
        self._sync_reading(on)
        self.flash("Added to your reading list" if on else "Removed from your reading list")

    def _on_auto_reading(self, book_id):
        if book_id == self.book_id:
            self._sync_reading(True)
            self.flash("Added to your reading list")


class JournalMixin:
    """Book journal: notes auto-filed under the section/page being read.

    Needs: self.library, self.book_id, self.prefs, self.flash(), self.book_format,
    self.current_location() -> dict | None, self.jump_to_location(index, ratio).
    Optional: summary_highlights() and summary_chapter_label(index) (EPUB highlights).
    """

    book_format = "epub"

    def _init_journal(self):
        self.journal = BookNotesPanel()
        self.journal.hide()
        self.journal_rows: list = []
        self.journal.addRequested.connect(self._journal_add)
        self.journal.jumpRequested.connect(self._journal_jump)
        self.journal.editRequested.connect(self._journal_edit)
        self.journal.deleteRequested.connect(self._journal_delete)
        self.journal.summaryRequested.connect(self.show_summary)
        self.journal.exportRequested.connect(self.export_journal)
        self.journal.reviewRequested.connect(self.review_notes)
        self.journal.mapRequested.connect(lambda: self.open_mindmap(generate=True))
        self.journal.link_picker = self._pick_note_link
        self.journal.linkRequested.connect(lambda url: self.noteLinkRequested.emit(url))

    def _pick_note_link(self):
        dlg = NotePickerDialog(self, self.library, self.book_id)
        return dlg.markup if dlg.exec() else None

    def _journal_theme(self) -> dict:
        return THEMES[self.prefs.v["theme"]]

    def journal_toggle(self, on):
        self.journal.setVisible(bool(on))
        if on:
            self.journal.track()
            self.journal.focus_editor()

    def _journal_open(self):
        """Call once a book is loaded."""
        self.journal.set_book(self.book_format, self.current_location)
        self.refresh_journal()

    def refresh_journal(self, message=""):
        if self.book_id is None:
            return
        self.journal_rows = self.library.book_notes(self.book_id)
        self.journal.refresh(self.journal_rows, self._journal_theme())
        if message:
            self.flash(message)

    def _journal_add(self, topic, body, loc):
        if self.book_id is None:
            return
        self.library.add_book_note(self.book_id, topic, body, loc)
        self.refresh_journal("Note saved · " + ref_text(
            loc["chapter"], loc["page"], loc["total"], self.book_format))

    def _journal_edit(self, nid):
        row = self.library.book_note(nid)
        if row is None:
            return
        e = note_entry(row)
        dlg = JournalNoteDialog(
            self, self.library.book_note_topics(self.book_id), e["topic"], e["text"],
            ref_text(e["chapter"], e["page"], e["total"], self.book_format), editing=True,
            link_picker=self._pick_note_link)
        if not dlg.exec():
            return
        if dlg.deleted:
            self.library.delete_book_note(nid)
            self.refresh_journal("Note deleted")
            return
        if not dlg.text():
            self.flash("A note can't be empty — use Delete to remove it")
            return
        loc = self.current_location() if dlg.relocate.isChecked() else None
        self.library.update_book_note(nid, dlg.topic(), dlg.text(), loc)
        self.refresh_journal("Note updated")

    def _journal_delete(self, nid):
        if QMessageBox.question(self, "Delete", "Delete this book note?") == \
                QMessageBox.StandardButton.Yes:
            self.library.delete_book_note(nid)
            self.refresh_journal("Note deleted")

    def _journal_jump(self, nid):
        row = self.library.book_note(nid)
        if row is not None:
            self.jump_to_location(row["spine_index"] or 0, row["scroll_ratio"] or 0.0)

    # -- summary / export ----------------------------------------------------- #

    def summary_highlights(self) -> list:
        return []

    def summary_chapter_label(self, index: int) -> str:
        return ""

    def _summary_builder(self) -> SummaryBuilder:
        return SummaryBuilder(self.library, self.book_id, self.summary_highlights,
                              self.summary_chapter_label)

    def show_summary(self):
        if self.book_id is None:
            return
        SummaryDialog(self, self._summary_builder(), self._journal_theme()).exec()

    def review_notes(self):
        """Flashcards / quizzes from this book's notes and highlights."""
        if self.book_id is None:
            return
        builder = self._summary_builder()
        if not builder.entries():
            self.flash("Add some notes or highlights first, then review them")
            return
        FlashcardDialog(self, builder, self._journal_theme()).exec()

    def export_journal(self):
        if self.book_id is None:
            return
        builder = self._summary_builder()
        if not builder.entries():
            self.flash("No notes to export yet")
            return
        if export_summary_dialog(self, builder):
            self.flash("Notes exported")


class BookmarksMixin:
    """Bookmarks: quick add (Ctrl+B), a jump menu and a manager dialog.

    Needs: self.library, self.book_id, self.book_format, self.flash(),
    self.current_location(), self.jump_to_location(index, ratio).
    """

    def _init_bookmarks(self):
        self.bookmark_menu = QMenu(self)
        self.bookmark_menu.aboutToShow.connect(self._fill_bookmark_menu)

    def _fill_bookmark_menu(self):
        menu = self.bookmark_menu
        menu.clear()
        menu.addAction("Add bookmark here   (Ctrl+B)").triggered.connect(
            lambda: self.add_bookmark())
        rows = self.library.bookmarks(self.book_id) if self.book_id is not None else []
        if rows:
            menu.addSeparator()
        for r in rows[:20]:
            ref = ref_text(r["chapter"], r["page"], r["page_total"], self.book_format)
            text = f"{r['label']}  —  {ref}" if r["label"] else ref
            act = menu.addAction(textwrap.shorten(text or "Bookmark", 70, placeholder="…"))
            act.triggered.connect(lambda _=False, i=r["spine_index"], x=r["scroll_ratio"]:
                                  self.jump_to_location(i, x))
        if rows:
            menu.addSeparator()
            menu.addAction("Manage bookmarks…").triggered.connect(lambda: self.manage_bookmarks())

    def add_bookmark(self):
        loc = self.current_location()
        if self.book_id is None or loc is None:
            return
        self.library.add_bookmark(self.book_id, loc)
        self.flash("Bookmarked · " + ref_text(loc["chapter"], loc["page"], loc["total"],
                                              self.book_format))

    def manage_bookmarks(self):
        if self.book_id is None:
            return
        dlg = BookmarksDialog(self, self.library, self.book_id, self.book_format)
        dlg.jumpRequested.connect(self.jump_to_location)
        dlg.exec()


class LookupMixin:
    """Dictionary / web look-up of selected text, with 'save to book notes'.

    Needs: self.library, self.book_id, self.flash(), self.current_location(),
    self.refresh_journal(), self._journal_theme().
    """

    def lookup_text(self, text: str):
        term = dictionary.clean_term(text)
        if not term:
            self.flash("Select a word or phrase first, then look it up")
            return
        dlg = LookupDialog(self, term, self._journal_theme())
        dlg.saveRequested.connect(self._save_lookup)
        dlg.exec()

    def _save_lookup(self, body: str):
        loc = self.current_location()
        if self.book_id is None or loc is None:
            return
        self.library.add_book_note(self.book_id, "Vocabulary", body, loc)
        self.refresh_journal("Saved to book notes")


class MindMapMixin:
    """Mind maps for the open book (non-modal window, so you can keep reading).

    Needs: self.library, self.book_id, self._summary_builder(), self._journal_theme(),
    self.current_location(), self.jump_to_location(index, ratio).
    """

    _mm_dialog = None

    def open_mindmap(self, generate: bool = False):
        if self.book_id is None:
            return
        dlg = self._mm_dialog
        if dlg is not None and dlg.book_id == self.book_id:
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
        else:
            self.close_mindmap()
            dlg = MindMapDialog(self, self.library, self._summary_builder(), self._journal_theme(),
                                location=self.current_location)
            dlg.jumpRequested.connect(self.jump_to_location)
            self._mm_dialog = dlg
            dlg.show()
        if generate:
            dlg.generate_from_notes()

    def close_mindmap(self):
        dlg, self._mm_dialog = self._mm_dialog, None
        if dlg is not None:
            dlg.close()
            dlg.deleteLater()

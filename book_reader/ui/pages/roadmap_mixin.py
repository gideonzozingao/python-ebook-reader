"""Roadmap of the open book, shared by the EPUB/Markdown reader page and the PDF page."""
from PySide6.QtCore import QTimer

from book_reader.core import features
from book_reader.services import roadmap as rm
from book_reader.ui.background import Job
from book_reader.ui.dialogs.roadmap_dialog import RoadmapDialog


class RoadmapMixin:
    """Generate and show a clickable roadmap (outline) of the open book.

    Needs: self.library, self.prefs, self.book_id, self._journal_theme(),
    self.current_location() -> dict | None, and
    self.goto_roadmap_target(index, fragment)  (implemented by each page).
    """

    # auto-show on open only for books that are barely started; set above 1.0 to always show
    ROADMAP_AUTO_BELOW = 0.02
    _rm_dialog = None
    _rm_data = None

    # -- opening / closing ------------------------------------------------------------ #

    def open_roadmap(self, rebuild: bool = False):
        if self.book_id is None:
            return
        if not features.enabled(self.prefs, "roadmap"):
            self.flash(features.off_message("roadmap"))
            return
        dlg = self._rm_dialog
        if dlg is None or dlg.book_id != self.book_id:
            self.close_roadmap()
            row = self.library.get(self.book_id)
            if row is None:
                return
            dlg = RoadmapDialog(self, self.book_id, row["title"], self._journal_theme(),
                                bool(self.prefs.v["roadmap_on_open"]))
            dlg.jumpRequested.connect(self._roadmap_jump)
            dlg.rescanRequested.connect(lambda: self.open_roadmap(rebuild=True))
            dlg.activated.connect(self._roadmap_refresh)
            dlg.autoShowChanged.connect(lambda on: self.prefs.set("roadmap_on_open", bool(on)))
            self._rm_dialog, self._rm_data = dlg, None
            dlg.show()
        else:
            dlg.show()
            dlg.raise_()
            dlg.activateWindow()
        if rebuild:
            self._rm_data = None
        if self._rm_data is None:
            self._roadmap_load(rebuild)
        else:
            self._roadmap_refresh()

    def close_roadmap(self):
        dlg, self._rm_dialog, self._rm_data = self._rm_dialog, None, None
        if dlg is not None:
            dlg.close()
            dlg.deleteLater()

    def auto_show_roadmap(self):
        """Call at the end of open_book: show the roadmap for a book that is just starting."""
        if (self.book_id is None or not self.prefs.v["roadmap_on_open"]
                or not features.enabled(self.prefs, "roadmap")):
            return
        row = self.library.get(self.book_id)
        if row is not None and (row["progress"] or 0) < self.ROADMAP_AUTO_BELOW:
            QTimer.singleShot(250, self.open_roadmap)   # after the page is on screen

    # -- building ----------------------------------------------------------------------- #

    def _roadmap_load(self, rebuild: bool):
        row = self.library.get(self.book_id)
        if row is None:
            return
        if not rebuild:
            cached = rm.load_cached(self.book_id, row["path"])
            if cached is not None:
                self._rm_data = cached
                self._roadmap_refresh(first=True)
                return
        self._rm_dialog.set_busy("Building the roadmap…")
        book_id, path, fmt, title = self.book_id, row["path"], row["format"], row["title"]

        def work(job):   # runs off the UI thread; the service opens its own copy of the book
            roadmap = rm.generate_roadmap(path, fmt, title)
            rm.save_cached(book_id, path, roadmap)
            return roadmap

        job = Job(self, work)   # a daemon thread: it can never keep the app from quitting
        job.done.connect(lambda roadmap, error, bid=book_id: self._roadmap_built(bid, roadmap, error))
        job.start()

    def _roadmap_built(self, book_id: int, roadmap, error: str):
        dlg = self._rm_dialog
        if dlg is None or dlg.book_id != book_id or book_id != self.book_id:
            return   # the book was closed while the roadmap was being built
        if roadmap is None:
            dlg.set_busy(f"Could not build the roadmap.\n\n{error}")
            return
        self._rm_data = roadmap
        self._roadmap_refresh(first=True)

    # -- showing / navigating ------------------------------------------------------------- #

    def _roadmap_refresh(self, first: bool = False):
        """Redraw with the current reading position (also when the window is re-activated)."""
        dlg, data = self._rm_dialog, self._rm_data
        if dlg is None or data is None or self.book_id is None:
            return
        loc = self.current_location()
        dlg.set_theme(self._journal_theme())
        dlg.show_roadmap(data, loc["spine_index"] if loc else 0,
                         loc["ratio"] if loc else 0.0, scroll_to_current=first)

    def _roadmap_jump(self, index: int, fragment: str):
        self.goto_roadmap_target(index, fragment)
        QTimer.singleShot(350, self._roadmap_refresh)   # move the "you are here" marker

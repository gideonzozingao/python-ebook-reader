"""Reading plan of the open book, shared by the EPUB/Markdown reader page and the PDF page."""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QToolBar

from book_reader.core import features
from book_reader.services import plan_words as pw
from book_reader.services import reading_plan as rp
from book_reader.services import roadmap as rm
from book_reader.ui.background import Job
from book_reader.ui.widgets.plan_drawer import PlanDrawer


class PlanMixin:
    """Open the plan drawer, keep the plan's progress up to date, save it.

    Needs: self.library, self.prefs, self.book_id, self._journal_theme(), self.flash(),
    self.current_location() -> dict | None and self.goto_roadmap_target(index, fragment).
    Uses the roadmap cache (and _rm_data when the roadmap is open) so the book is only
    scanned once.
    """

    _plan_drawer = None
    _plan_data = None       # (roadmap, counts) for the open book

    # -- opening / closing ------------------------------------------------------------ #

    def open_plan(self, rebuild: bool = False, toggle: bool = False):
        """Slide the plan drawer in (or out again when `toggle` and it is already open)."""
        if self.book_id is None:
            return
        if not features.enabled(self.prefs, "plan"):
            self.flash(features.off_message("plan"))
            return
        drawer = self._plan_drawer
        if drawer is None or drawer.book_id != self.book_id:
            self.close_plan()
            row = self.library.get(self.book_id)
            if row is None:
                return
            drawer = PlanDrawer(self, self.book_id, row["title"], self._journal_theme(),
                                self._plan_bounds)
            drawer.jumpRequested.connect(self._plan_jump)
            drawer.locationRequested.connect(self.jump_to_location)
            drawer.saveRequested.connect(self._plan_save)
            drawer.deleteRequested.connect(lambda: self.library.delete_plan(drawer.book_id))
            drawer.rebuildRequested.connect(lambda: self.open_plan(rebuild=True))
            drawer.activated.connect(self._plan_activated)
            self._plan_drawer = drawer
        elif toggle and drawer.is_open() and not rebuild:
            drawer.slide_out()
            return
        drawer.slide_in()
        if rebuild or self._plan_data is None:
            self._plan_data = None
            self._plan_load(rebuild)

    def _plan_bounds(self):
        """The strip between the page's toolbar and its status bar (page coordinates)."""
        top, bottom = 0, self.height()
        bar = self.findChild(QToolBar, "", Qt.FindChildOption.FindDirectChildrenOnly)
        if bar is not None and bar.isVisible():
            top = bar.mapTo(self, QPoint(0, 0)).y() + bar.height()
        status = getattr(self, "status", None)
        if status is not None and status.isVisible():
            bottom = status.mapTo(self, QPoint(0, 0)).y()
        return top, max(top + 200, bottom)

    def plan_on_open(self):
        """Call at the end of open_book. If this book has a plan but its word counts are not
        cached (first run of a new version, or the book file changed), count them quietly in
        the background so progress tracking and the library's "Today's reading" keep working."""
        if self.book_id is None or not features.enabled(self.prefs, "plan"):
            return
        row = self.library.get(self.book_id)
        if row is None or not self.library.get_plan(self.book_id):
            return
        roadmap = rm.load_cached(self.book_id, row["path"])
        if roadmap is not None and pw.load_cached(self.book_id, row["path"], roadmap) is not None:
            return
        book_id, path, fmt, title = self.book_id, row["path"], row["format"], row["title"]

        def work(job):
            roadmap = rm.load_cached(book_id, path)
            if roadmap is None:
                roadmap = rm.generate_roadmap(path, fmt, title)
                rm.save_cached(book_id, path, roadmap)
            counts = pw.compute_counts(path, fmt, roadmap, title)
            pw.save_cached(book_id, path, counts)
            return roadmap, counts

        def finished(data, error, bid=book_id):
            if data is not None and self.book_id == bid:
                self._plan_cache = (bid, *data)
        job = Job(self, work)
        job.done.connect(finished)
        job.start()

    def close_plan(self):
        self._plan_cache = None
        drawer, self._plan_drawer, self._plan_data = self._plan_drawer, None, None
        if drawer is not None:
            drawer.hide()
            drawer.deleteLater()

    # -- data ---------------------------------------------------------------------------- #

    def _plan_load(self, rebuild: bool):
        row = self.library.get(self.book_id)
        if row is None:
            return
        book_id, path, fmt, title = self.book_id, row["path"], row["format"], row["title"]
        if not rebuild:
            roadmap = getattr(self, "_rm_data", None) or rm.load_cached(book_id, path)
            counts = pw.load_cached(book_id, path, roadmap) if roadmap is not None else None
            if counts is not None:
                self._plan_ready(book_id, (roadmap, counts), "")
                return
        dlg = self._plan_drawer
        dlg.set_busy("Counting the words in this book…")

        def work(job):   # off the UI thread; the services open their own copy of the book
            roadmap = None if rebuild else rm.load_cached(book_id, path)
            if roadmap is None:
                roadmap = rm.generate_roadmap(path, fmt, title)
                rm.save_cached(book_id, path, roadmap)
            counts = pw.compute_counts(path, fmt, roadmap, title, report=job.report)
            pw.save_cached(book_id, path, counts)
            return roadmap, counts

        job = Job(self, work)
        job.progress.connect(lambda done, total, d=dlg: d.set_busy(
            f"Counting the words in this book… {done} of {total}"))
        job.done.connect(lambda data, error, bid=book_id: self._plan_ready(bid, data, error))
        job.start()

    def _plan_ready(self, book_id: int, data, error: str):
        dlg = self._plan_drawer
        if dlg is None or dlg.book_id != book_id or book_id != self.book_id:
            return   # the book was closed in the meantime
        if data is None:
            dlg.set_busy(f"Could not count the words in this book.\n\n{error}")
            return
        self._plan_data = data
        roadmap, counts = data
        self._plan_cache = (book_id, roadmap, counts)
        stored = self.library.get_plan(book_id)
        plan = None
        if stored:
            try:
                plan = rp.ReadingPlan.from_json(stored)
            except Exception:
                plan = None
        dlg.set_data(roadmap, counts, plan, self._plan_pace(roadmap, counts))
        dlg.track(self.current_location())

    def _plan_pace(self, roadmap, counts):
        """Your speed in this book: words before your position / time spent reading it."""
        loc, row = self.current_location(), self.library.get(self.book_id)
        if loc is None or row is None or counts.estimated:
            return None
        words = pw.words_before(roadmap, counts, loc["spine_index"], loc["ratio"])
        return rp.personal_wpm(words, float(row["read_seconds"] or 0))

    def _plan_save(self, plan):
        if self.book_id is not None and self._plan_drawer is not None:
            self.library.save_plan(self._plan_drawer.book_id, plan.to_json())

    # -- progress --------------------------------------------------------------------------- #

    _plan_cache = None      # (book_id, roadmap, counts) for tracking without the dialog

    def plan_track(self):
        """Tick off the chapter just read past. Called with every saved reading position, so
        it is cheap: one small database read; the roadmap and word counts are loaded from
        their caches once per book and the book is never scanned here."""
        if self.book_id is None or not features.enabled(self.prefs, "plan"):
            return
        dlg = self._plan_drawer
        if dlg is not None and dlg.book_id == self.book_id and dlg.counts is not None:
            if dlg.started:
                dlg.track(self.current_location())
            return
        try:
            stored = self.library.get_plan(self.book_id)
            if not stored:
                return
            cache = self._plan_cache
            if cache is None or cache[0] != self.book_id:
                row = self.library.get(self.book_id)
                roadmap = rm.load_cached(self.book_id, row["path"]) if row else None
                counts = pw.load_cached(self.book_id, row["path"], roadmap) if roadmap else None
                cache = self._plan_cache = (self.book_id, roadmap, counts)
            _, roadmap, counts = cache
            loc = self.current_location()
            if counts is None or loc is None:
                return
            plan = rp.ReadingPlan.from_json(stored)
            tasks = rp.build_tasks(roadmap, counts, plan.settings)
            if rp.auto_complete(plan, tasks, loc["spine_index"], loc["ratio"], loc["progress"]):
                self.library.save_plan(self.book_id, plan.to_json())
        except Exception:
            pass   # progress tracking must never get in the way of reading

    def _plan_activated(self):
        dlg = self._plan_drawer
        if dlg is not None:
            dlg.set_theme(self._journal_theme())
            if self._plan_data is not None:
                dlg.set_pace(self._plan_pace(*self._plan_data))
        self.plan_track()

    def _plan_jump(self, index: int, fragment: str):
        self.goto_roadmap_target(index, fragment)

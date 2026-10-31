"""Reading plan of the open book, in a drawer that slides in from the left: today's
reading, a timeline, the day-by-day schedule and the plan's settings.

The drawer sits over the reader (below its toolbar), so you can keep reading beside it.
Close it with ×, Esc or Ctrl+Shift+P; drag its right edge to make it wider. The drawer does
the planning itself with the Qt-free services.reading_plan; the page (PlanMixin) loads the
data, saves the plan and moves the reader when a chapter link is clicked.
"""
from datetime import date, timedelta
from html import escape
from pathlib import Path

from PySide6.QtCore import (QDate, QEasingCurve, QEvent, QPropertyAnimation, QRect, QTime,
                            QTimer, Qt, Signal)
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QTimeEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from book_reader.services import reading_plan as rp
from book_reader.ui.widgets.plan_timeline import KIND_COLOURS, LATE, PlanTimeline

UNIT_LEVELS = (("Chapters", 1), ("Chapters and sections", 2), ("Down to sub-sections", 3))
MIN_WIDTH, MAX_SHARE = 380, 0.85     # drawer width limits (px, share of the page)


def _qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _pydate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


class _EdgeGrip(QWidget):
    """The drawer's right edge: drag it to change the width."""

    def __init__(self, drawer):
        super().__init__(drawer)
        self.drawer = drawer
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setFixedWidth(6)
        self._x0 = None

    def mousePressEvent(self, e):
        self._x0, self._w0 = e.globalPosition().x(), self.drawer.width()

    def mouseMoveEvent(self, e):
        if self._x0 is not None:
            self.drawer.set_width(self._w0 + e.globalPosition().x() - self._x0)

    def mouseReleaseEvent(self, e):
        self._x0 = None


class PlanDrawer(QFrame):
    jumpRequested = Signal(int, str)         # (spine index or page, heading anchor)
    locationRequested = Signal(int, float)   # (spine index or page, ratio inside it)
    saveRequested = Signal(object)           # the ReadingPlan to store
    deleteRequested = Signal()
    rebuildRequested = Signal()              # count the words again
    activated = Signal()                     # the drawer was opened: update progress
    closed = Signal()

    width_pref = 0                           # remembered across books for this session

    def __init__(self, page, book_id: int, title: str, theme: dict, bounds=None):
        """`page`: the reader page it slides over. `bounds()` -> (top, bottom) in page
        coordinates: the strip between the toolbar and the status bar."""
        super().__init__(page)
        self.page, self.bounds = page, bounds or (lambda: (0, page.height()))
        self.book_id, self.book_title, self.t = book_id, title, theme
        self.roadmap = self.counts = None
        self.plan: rp.ReadingPlan | None = None
        self.started = False
        self.tasks, self.sched, self.status = [], rp.Schedule(), None
        self.pace = None
        self.error = ""
        self._loading = False
        self._open = False
        self.setObjectName("planDrawer")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setVisible(False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 12, 14, 12)
        lay.setSpacing(6)
        top = QHBoxLayout()
        top.setSpacing(8)
        icon = QLabel("📅")
        top.addWidget(icon)
        head = QLabel(title)
        head.setObjectName("h2")
        head.setWordWrap(True)
        top.addWidget(head, 1)
        close = QToolButton()
        close.setText("✕")
        close.setToolTip("Close the plan (Esc)")
        close.setAutoRaise(True)
        close.clicked.connect(self.slide_out)
        top.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top)
        self.info = QLabel("")
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        lay.addWidget(self.bar)
        prog = QHBoxLayout()
        self.progress_text = QLabel("")
        self.progress_text.setObjectName("muted")
        prog.addWidget(self.progress_text, 1)
        self.state = QLabel("")
        prog.addWidget(self.state)
        lay.addLayout(prog)

        self.tabs = QTabWidget()
        self.today_view = self._browser()
        self.tabs.addTab(self.today_view, "Today")
        self.tabs.addTab(self._timeline_tab(), "Timeline")
        self.schedule_view = self._browser()
        self.tabs.addTab(self.schedule_view, "Schedule")
        self.tabs.addTab(self._settings_tab(), "Settings")
        lay.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        self.start_btn = QPushButton("Start this plan")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self._start)
        bottom.addWidget(self.start_btn)
        self.replan_btn = QPushButton("Replan from today")
        self.replan_btn.setToolTip("Schedule what is not done yet again, starting today")
        self.replan_btn.clicked.connect(self._replan)
        bottom.addWidget(self.replan_btn)
        bottom.addStretch()
        export = QToolButton()
        export.setText("Export")
        export.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(export)
        menu.addAction("Calendar file (.ics)…", self._export_ics)
        menu.addAction("Markdown checklist (.md)…", self._export_md)
        export.setMenu(menu)
        self.export_btn = export
        bottom.addWidget(export)
        more = QToolButton()
        more.setText("⋯")
        more.setToolTip("More")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        more_menu = QMenu(more)
        more_menu.addAction("Recount the words", lambda: self.rebuildRequested.emit())
        self.delete_action = more_menu.addAction("Delete plan…", self._delete)
        more.setMenu(more_menu)
        self.more_btn = more
        bottom.addWidget(more)
        lay.addLayout(bottom)

        self.grip = _EdgeGrip(self)
        esc = QShortcut(QKeySequence("Escape"), self,
                        context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        esc.activated.connect(self.slide_out)
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self._anim_done)
        page.installEventFilter(self)

        self._recompute_timer = QTimer(self, singleShot=True, interval=200)
        self._recompute_timer.timeout.connect(self._settings_edited)
        self.set_theme(theme)
        self.set_busy("Counting the words in this book…")

    # -- drawer -------------------------------------------------------------------------- #

    def is_open(self) -> bool:
        return self._open

    def _rect(self, shown: bool) -> QRect:
        top, bottom = self.bounds()
        pw = self.page.width()
        w = PlanDrawer.width_pref or min(620, max(460, int(pw * 0.42)))
        w = int(max(MIN_WIDTH, min(w, pw * MAX_SHARE)))
        return QRect(0 if shown else -w - 4, top, w, max(200, bottom - top))

    def set_width(self, w):
        PlanDrawer.width_pref = int(w)
        if self._open:
            self.setGeometry(self._rect(True))

    def slide_in(self):
        if self._open and self.isVisible():
            self.raise_()
            return
        self._open = True
        self.setGeometry(self._rect(False))
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self._rect(True).topLeft())
        self._anim.start()
        self.activated.emit()

    def slide_out(self):
        if not self._open:
            return
        self._open = False
        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(self._rect(False).topLeft())
        self._anim.start()
        self.page.setFocus()

    def toggle(self):
        self.slide_out() if self._open else self.slide_in()

    def _anim_done(self):
        if not self._open:
            self.hide()
            self.closed.emit()
        else:
            self.tabs.currentWidget().setFocus()

    def eventFilter(self, obj, e):
        if obj is self.page and e.type() == QEvent.Type.Resize and self._open:
            self.setGeometry(self._rect(True))
        return False

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.grip.setGeometry(self.width() - self.grip.width(), 0, self.grip.width(), self.height())
        self.grip.raise_()

    # -- building blocks ---------------------------------------------------------------- #

    def _browser(self) -> QTextBrowser:
        b = QTextBrowser()
        b.setOpenLinks(False)
        b.setOpenExternalLinks(False)
        b.anchorClicked.connect(self._clicked)
        return b

    def _timeline_tab(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 6, 0, 0)
        row = QHBoxLayout()
        for text, slot in (("Fit", lambda: self.timeline.fit()),
                           ("Today", lambda: self.timeline.scroll_to_day(date.today())),
                           ("−", lambda: self.timeline.set_zoom(self.timeline.zoom - 1)),
                           ("+", lambda: self.timeline.set_zoom(self.timeline.zoom + 1))):
            b = QPushButton(text)
            b.setObjectName("tonal")
            b.clicked.connect(slot)
            row.addWidget(b)
        hint = QLabel("Double-click opens · right-click ticks off")
        hint.setToolTip("Double-click a row to open that chapter, right-click to tick it off, "
                        "Ctrl+wheel to zoom, Shift+wheel to scroll sideways")
        hint.setObjectName("muted")
        row.addWidget(hint, 1)
        v.addLayout(row)
        self.timeline = PlanTimeline()
        self.timeline.activated.connect(self._open_task)
        self.timeline.menuRequested.connect(self._task_menu)
        v.addWidget(self.timeline, 1)
        return page

    def _settings_tab(self) -> QWidget:
        holder = QWidget()
        form = QFormLayout(holder)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setContentsMargins(12, 12, 12, 12)
        form.setVerticalSpacing(10)

        self.f_start = QDateEdit(calendarPopup=True)
        self.f_start.setDisplayFormat("ddd d MMM yyyy")
        form.addRow("Start on", self.f_start)

        self.f_minutes = QSpinBox()
        self.f_minutes.setRange(5, rp.MAX_MINUTES_PER_DAY)
        self.f_minutes.setSingleStep(5)
        self.f_minutes.setSuffix(" min a day")
        form.addRow("Reading time", self.f_minutes)

        days = QHBoxLayout()
        days.setSpacing(10)
        self.f_days = []
        for i, name in enumerate(rp.WEEKDAY_NAMES):
            box = QCheckBox(name[:2])
            box.setToolTip(name)
            days.addWidget(box)
            self.f_days.append(box)
        days.addStretch()
        form.addRow("Read on", days)

        speed = QHBoxLayout()
        self.f_wpm = QSpinBox()
        self.f_wpm.setRange(rp.MIN_WPM, rp.MAX_WPM)
        self.f_wpm.setSingleStep(10)
        self.f_wpm.setSuffix(" words per minute")
        speed.addWidget(self.f_wpm)
        self.pace_btn = QPushButton("Use my pace")
        self.pace_btn.setObjectName("link")
        self.pace_btn.clicked.connect(self._use_pace)
        speed.addWidget(self.pace_btn)
        speed.addStretch()
        form.addRow("Reading speed", speed)

        self.f_factor = QDoubleSpinBox()
        self.f_factor.setRange(0.5, 5.0)
        self.f_factor.setSingleStep(0.25)
        self.f_factor.setDecimals(2)
        self.f_factor.setPrefix("× ")
        self.f_factor.setToolTip("Extra time for taking notes and re-reading. "
                                 "×1 = just reading, ×1.5 = studying.")
        form.addRow("Study factor", self.f_factor)

        self.f_unit = QComboBox()
        for label, _ in UNIT_LEVELS:
            self.f_unit.addItem(label)
        form.addRow("Plan by", self.f_unit)

        self.f_min_start = QSpinBox()
        self.f_min_start.setRange(0, 60)
        self.f_min_start.setSuffix(" min left in the day")
        self.f_min_start.setSpecialValueText("always fill the day")
        self.f_min_start.setToolTip("A new chapter is not started at the end of a day with less "
                                    "time than this left (unless it fits completely).")
        form.addRow("New chapter needs at least", self.f_min_start)

        self.f_review = QSpinBox()
        self.f_review.setRange(0, 240)
        self.f_review.setSingleStep(5)
        self.f_review.setSuffix(" min per chapter")
        self.f_review.setSpecialValueText("off")
        form.addRow("Review step", self.f_review)

        self.f_mindmap = QSpinBox()
        self.f_mindmap.setRange(0, 240)
        self.f_mindmap.setSingleStep(5)
        self.f_mindmap.setSuffix(" min per chapter")
        self.f_mindmap.setSpecialValueText("off")
        form.addRow("Mind-map step", self.f_mindmap)

        self.f_matter = QCheckBox("Leave out cover, title pages, contents and index")
        form.addRow("", self.f_matter)

        self.f_time = QTimeEdit()
        self.f_time.setDisplayFormat("HH:mm")
        self.f_time.setToolTip("When your reading time starts; used for the calendar export")
        form.addRow("Reading starts at", self.f_time)

        finish = QHBoxLayout()
        self.f_finish = QDateEdit(calendarPopup=True)
        self.f_finish.setDisplayFormat("ddd d MMM yyyy")
        finish.addWidget(self.f_finish)
        fit = QPushButton("Fit minutes per day")
        fit.setObjectName("tonal")
        fit.clicked.connect(self._fit_to_date)
        finish.addWidget(fit)
        finish.addStretch()
        form.addRow("Finish by", finish)
        self.fit_note = QLabel("Pick a date to see how many minutes a day you need.")
        self.fit_note.setObjectName("muted")
        self.fit_note.setWordWrap(True)
        form.addRow("", self.fit_note)

        for w in (self.f_start, self.f_finish):
            w.dateChanged.connect(self._edited)
        for w in (self.f_minutes, self.f_wpm, self.f_min_start, self.f_review, self.f_mindmap):
            w.valueChanged.connect(self._edited)
        self.f_factor.valueChanged.connect(self._edited)
        self.f_unit.currentIndexChanged.connect(self._edited)
        self.f_time.timeChanged.connect(self._edited)
        for box in self.f_days + [self.f_matter]:
            box.toggled.connect(self._edited)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(holder)
        return scroll

    # -- state ------------------------------------------------------------------------ #

    def set_theme(self, theme: dict):
        self.t = theme
        self.setStyleSheet(
            f"QFrame#planDrawer {{ background:{theme['panel']}; border:none;"
            f" border-right:1px solid {theme['border']}; }}")
        for b in (self.today_view, self.schedule_view):
            b.setStyleSheet(f"QTextBrowser {{ background:{theme['bg']}; border:1px solid "
                            f"{theme['border']}; border-radius:8px; }}")
            b.document().setDefaultStyleSheet(f"a {{ color:{theme['fg']}; text-decoration:none; }}")
        if self.plan is not None and self.counts is not None:
            self._render()

    def set_busy(self, text: str):
        self.info.setText("")
        for b in (self.today_view, self.schedule_view):
            b.setHtml(f'<p style="color:{self.t["muted"]}">{escape(text).replace(chr(10), "<br>")}</p>')
        self._enable(False)

    def _enable(self, on: bool):
        for w in (self.start_btn, self.replan_btn, self.export_btn, self.more_btn):
            w.setEnabled(on)
        self.tabs.widget(3).setEnabled(on)

    def set_data(self, roadmap, counts, plan, pace=None):
        """Show a plan (or, with plan=None, a preview of a new one with default settings)."""
        self.roadmap, self.counts, self.pace = roadmap, counts, pace
        self.started = plan is not None
        self.plan = plan or rp.ReadingPlan.new(date.today(), study_factor=1.0)
        self._enable(True)
        self._fill_form()
        self._recompute()
        if not self.started:
            self.tabs.setCurrentIndex(3)

    def set_pace(self, pace):
        self.pace = pace
        self._update_pace_button()

    def _update_pace_button(self):
        if self.pace:
            self.pace_btn.setText(f"Use my pace (≈ {self.pace} wpm)")
            self.pace_btn.setToolTip("Measured from your reading time in this book so far. "
                                     "It already includes the time you spent on notes, so a "
                                     "study factor of ×1 is usually right with it.")
            self.pace_btn.setEnabled(True)
        else:
            self.pace_btn.setText("Use my pace")
            self.pace_btn.setToolTip("Read this book for at least 10 minutes first")
            self.pace_btn.setEnabled(False)

    def _fill_form(self):
        s = self.plan.settings
        self._loading = True
        try:
            self.f_start.setDate(_qdate(s.start_date()))
            self.f_minutes.setValue(s.minutes_per_day)
            for i, box in enumerate(self.f_days):
                box.setChecked(i in s.weekdays)
            self.f_wpm.setValue(s.wpm)
            self.f_factor.setValue(s.study_factor)
            self.f_unit.setCurrentIndex(max(0, min(len(UNIT_LEVELS) - 1, s.unit_level - 1)))
            self.f_min_start.setValue(s.min_start)
            self.f_review.setValue(s.review_minutes)
            self.f_mindmap.setValue(s.mindmap_minutes)
            self.f_matter.setChecked(s.skip_matter)
            hh, mm = (s.session_time.split(":") + ["0"])[:2]
            self.f_time.setTime(QTime(int(hh) % 24, int(mm) % 60))
            try:
                finish = date.fromisoformat(s.finish_by)
            except ValueError:
                finish = s.start_date() + timedelta(days=27)
            self.f_finish.setDate(_qdate(finish))
        finally:
            self._loading = False
        self._update_pace_button()

    def _read_form(self):
        s = self.plan.settings
        s.start = _pydate(self.f_start.date()).isoformat()
        s.minutes_per_day = self.f_minutes.value()
        s.weekdays = [i for i, box in enumerate(self.f_days) if box.isChecked()]
        s.wpm = self.f_wpm.value()
        s.study_factor = self.f_factor.value()
        s.unit_level = UNIT_LEVELS[self.f_unit.currentIndex()][1]
        s.min_start = self.f_min_start.value()
        s.review_minutes = self.f_review.value()
        s.mindmap_minutes = self.f_mindmap.value()
        s.skip_matter = self.f_matter.isChecked()
        s.session_time = self.f_time.time().toString("HH:mm")
        s.finish_by = _pydate(self.f_finish.date()).isoformat()
        s.clean()

    def _edited(self, *_):
        if not self._loading and self.plan is not None:
            self._recompute_timer.start()

    def _settings_edited(self):
        self._read_form()
        self._recompute()
        self._save()

    def _save(self):
        if self.started:
            self.saveRequested.emit(self.plan)

    # -- planning --------------------------------------------------------------------- #

    def _recompute(self):
        if self.plan is None or self.counts is None:
            return
        s = self.plan.settings
        self.tasks = rp.build_tasks(self.roadmap, self.counts, s)
        try:
            self.sched = rp.plan_schedule(self.plan, self.tasks)
            self.error = ""
        except ValueError as exc:
            self.sched, self.error = rp.Schedule(), str(exc)
        self.status = rp.status(self.plan, self.tasks, self.sched)
        self._update_fit_note()
        self._render()

    def track(self, location) -> bool:
        """Tick off what the reader has read past. True if anything changed."""
        if not self.started or location is None or not self.tasks:
            return False
        newly = rp.auto_complete(self.plan, self.tasks, location["spine_index"],
                                 location["ratio"], location.get("progress", 0.0))
        if newly:
            self._save()
            self.status = rp.status(self.plan, self.tasks, self.sched)
            self._render()
        return bool(newly)

    def _toggle(self, key: str):
        if not self.started:
            self.flash_info("Start the plan first, then tick chapters off as you finish them.")
            return
        rp.set_done(self.plan, key, key not in self.plan.done)
        self._save()
        self.status = rp.status(self.plan, self.tasks, self.sched)
        self._render()

    def _start(self):
        self._read_form()
        self.plan.created = date.today().isoformat()
        self.started = True
        self._save()
        self._recompute()
        self.tabs.setCurrentIndex(0)

    def _replan(self):
        if not self.started:
            return
        rp.replan(self.plan)
        self._fill_form()
        self._save()
        self._recompute()

    def _delete(self):
        if not self.started:
            return
        if QMessageBox.question(self, "Delete plan",
                                "Delete the reading plan for this book? Ticked-off chapters "
                                "are forgotten too.") != QMessageBox.StandardButton.Yes:
            return
        self.deleteRequested.emit()
        self.started = False
        self.plan = rp.ReadingPlan.new(date.today(), study_factor=1.0)
        self._fill_form()
        self._recompute()
        self.tabs.setCurrentIndex(3)

    def _use_pace(self):
        if self.pace:
            self.f_wpm.setValue(self.pace)

    def _fit_to_date(self):
        self._read_form()
        finish = _pydate(self.f_finish.date())
        active = rp.active_tasks(self.plan, self.tasks)
        need = rp.minutes_needed(active, self.plan.settings, finish)
        if need is None:
            self.fit_note.setText("That date is too soon: there are no reading days before it, "
                                  "or it would need more than 12 hours a day.")
            return
        self.f_minutes.setValue(max(self.f_minutes.minimum(), need))
        self._update_fit_note()

    def _update_fit_note(self):
        try:
            finish = _pydate(self.f_finish.date())
            need = rp.minutes_needed(rp.active_tasks(self.plan, self.tasks), self.plan.settings, finish)
        except ValueError:
            need = None
        days = rp.weekdays_label(self.plan.settings.weekdays) if self.plan.settings.weekdays else "—"
        if need is None:
            self.fit_note.setText(f"Finishing by {finish:%a} {finish.day} {finish:%b} isn't possible "
                                  "with these reading days.")
        else:
            self.fit_note.setText(f"To finish by {finish:%a} {finish.day} {finish:%b}: "
                                  f"{need} min a day on {days}. “Fit” sets it.")

    # -- rendering -------------------------------------------------------------------- #

    def flash_info(self, text: str):
        self.state.setText(text)
        QTimer.singleShot(4000, self._render_state)

    def _render(self):
        t, s = self.t, self.plan.settings
        active = rp.active_tasks(self.plan, self.tasks)
        if self.error:
            self.info.setText(self.error)
        elif not self.tasks:
            self.info.setText("No text found to plan in this book.")
        else:
            info = rp.summary_line(active, s, self.sched, self.counts.estimated)
            if self.counts.estimated:
                info += ("\nRough estimate: this PDF has no text layer (scanned), so words are "
                         "counted as pages × an average per page.")
            if not self.started:
                info += "\nPreview: change the settings, then press “Start this plan”."
            self.info.setText(info)
        self.start_btn.setVisible(not self.started)
        self.replan_btn.setVisible(self.started)
        self.delete_action.setEnabled(self.started)
        self._render_state()
        keep = self.today_view.verticalScrollBar().value()
        self.today_view.setHtml(self._today_html())
        self.today_view.verticalScrollBar().setValue(keep)
        keep = self.schedule_view.verticalScrollBar().value()
        self.schedule_view.setHtml(self._schedule_html())
        self.schedule_view.verticalScrollBar().setValue(keep)
        first = not self.timeline.tasks
        self.timeline.set_plan(self.tasks, self.sched, self.plan.done if self.started else {}, s, t)
        if first:
            QTimer.singleShot(0, lambda: self.timeline.scroll_to_day(date.today()))

    def _render_state(self):
        st = self.status
        if st is None:
            return
        self.bar.setValue(st.percent if self.started else 0)
        self.progress_text.setText(f"{st.percent}% · {rp.fmt_minutes(st.done_minutes)} of "
                                   f"{rp.fmt_minutes(st.total_minutes)} read"
                                   if self.started else "Not started yet")
        if not self.started:
            text = ""
        elif st.done_minutes >= st.total_minutes and st.total_minutes:
            text = "Plan complete 🎉"
        elif st.behind_minutes:
            text = f'<span style="color:{LATE}">{rp.fmt_minutes(st.behind_minutes)} behind</span>'
        elif st.done_minutes > st.due_minutes:
            text = f"{rp.fmt_minutes(st.done_minutes - st.due_minutes)} ahead"
        else:
            text = "On track"
        self.state.setText(text)

    def _row(self, b, task, show_day=False) -> str:
        t = self.t
        done = b.key in self.plan.done
        box = "☑" if done else "☐"
        colour = KIND_COLOURS.get(task.kind, t["accent"])
        title = escape(rp.block_title(b, task))
        if task.kind != rp.READ:
            title = "&nbsp;&nbsp;&nbsp;↳ " + title
        if done:
            title = f'<span style="color:{t["muted"]}"><s>{title}</s></span>'
        elif task.kind == rp.READ:
            title = f"<b>{title}</b>"
        extra = ""
        if task.kind == rp.READ:
            part = round(task.words * b.minutes / max(1, task.minutes))
            extra = (f"{task.words:,} words" if b.parts == 1
                     else f"≈ {part:,} of {task.words:,} words")
        day = f'<td><span style="color:{t["muted"]}">{rp.day_label(b.day)}</span></td>' if show_day else ""
        return (f'<tr>{day}<td width="26"><a href="toggle:{b.key}" title="Tick off">'
                f'<span style="color:{colour}; font-size:15px">{box}</span></a></td>'
                f'<td><a href="open:{b.key}.{b.part}">{title}</a></td>'
                f'<td align="right"><span style="color:{t["muted"]}">{extra}</span></td>'
                f'<td align="right" width="60">{b.minutes} min</td></tr>')

    def _today_html(self) -> str:
        t, st = self.t, self.status
        by_key = {x.key: x for x in self.tasks}
        today = date.today()
        out = [f'<h3>{today:%A} {today.day} {today:%B}</h3>']
        if self.error or not self.sched.blocks:
            out.append(f'<p style="color:{t["muted"]}">Nothing scheduled.</p>')
            return "".join(out)
        if not self.started:
            out.append(f'<p style="color:{t["muted"]}">This is a preview. Adjust it on the '
                       f'Settings tab and press “Start this plan”.</p>')
        if self.started and st.done_minutes >= st.total_minutes:
            out.append("<p>Every chapter in the plan is done. Well read!</p>")
            return "".join(out)
        if self.started and st.overdue:
            out.append(f'<p><b style="color:{LATE}">Catch up</b> — '
                       f'{rp.fmt_minutes(st.behind_minutes)} from earlier days. '
                       f'<a href="replan:" style="color:{t["accent"]}">Replan from today</a></p>')
            out.append('<table width="100%" cellspacing="0" cellpadding="5">')
            out += [self._row(b, by_key[b.key], show_day=True) for b in st.overdue]
            out.append("</table>")
        todays = [b for b in self.sched.blocks if b.day == today]
        if todays:
            total = sum(b.minutes for b in todays)
            out.append(f"<p><b>Today’s reading</b> · {rp.fmt_minutes(total)}</p>")
            out.append('<table width="100%" cellspacing="0" cellpadding="5">')
            out += [self._row(b, by_key[b.key]) for b in todays]
            out.append("</table>")
            if today in self.sched.leftover:
                left, title = self.sched.leftover[today]
                out.append(f'<p style="color:{t["muted"]}"><i>{left} min left: not enough to '
                           f'start {escape(title)}.</i></p>')
        else:
            nxt = next((b.day for b in self.sched.blocks if b.day > today), None)
            out.append(f'<p style="color:{t["muted"]}">No reading planned today.</p>')
            if nxt:
                out.append(f"<p><b>Next: {rp.day_label(nxt)}</b></p>")
                out.append('<table width="100%" cellspacing="0" cellpadding="5">')
                out += [self._row(b, by_key[b.key]) for b in self.sched.blocks if b.day == nxt]
                out.append("</table>")
        return "".join(out)

    def _schedule_html(self) -> str:
        t = self.t
        by_key = {x.key: x for x in self.tasks}
        today = date.today()
        if self.error or not self.sched.blocks:
            return f'<p style="color:{t["muted"]}">{escape(self.error) or "Nothing scheduled."}</p>'
        out = ['<table width="100%" cellspacing="0" cellpadding="4">']
        for day, blocks in self.sched.by_day().items():
            mark = '<a name="today"></a>' if day == today else ""
            colour = LATE if day == today else (t["muted"] if day < today else t["fg"])
            total = sum(b.minutes for b in blocks)
            bg = f' bgcolor="{t["sel"]}"' if day == today else ""
            out.append(f'<tr><td colspan="4"{bg}>{mark}<b style="color:{colour}">'
                       f'{day:%a} {day.day} {day:%b %Y}</b>'
                       f'<span style="color:{t["muted"]}"> · {total} min</span></td></tr>')
            out += [self._row(b, by_key[b.key]) for b in blocks]
            if day in self.sched.leftover:
                left, title = self.sched.leftover[day]
                out.append(f'<tr><td></td><td colspan="3"><i style="color:{t["muted"]}">'
                           f'{left} min left: not enough to start {escape(title)}</i></td></tr>')
        out.append("</table>")
        return "".join(out)

    # -- events ------------------------------------------------------------------------ #

    def _clicked(self, url):
        scheme, key = url.scheme(), url.path()
        if scheme == "open":
            key, _, part = key.partition(".")
            self._open_task(key, int(part or 1))
        elif scheme == "toggle":
            self._toggle(key)
        elif scheme == "replan":
            self._replan()

    def _open_task(self, key: str, part: int = 1):
        """Open a task at its heading, or a later part of it where that part begins."""
        task = next((x for x in self.tasks if x.key == key), None)
        if task is None:
            return
        block = next((b for b in self.sched.blocks if b.key == key and b.part == part), None)
        loc = rp.block_location(self.counts, task, block) if block and block.before else None
        if loc is not None:
            self.locationRequested.emit(loc[0], loc[1])
        else:
            self.jumpRequested.emit(task.index, task.fragment)

    def _task_menu(self, key: str, pos):
        task = next((x for x in self.tasks if x.key == key), None)
        if task is None:
            return
        menu = QMenu(self)
        menu.addAction("Open this chapter", lambda: self._open_task(key))
        done = QAction("Done", menu, checkable=True)
        done.setChecked(key in self.plan.done)
        done.triggered.connect(lambda: self._toggle(key))
        menu.addAction(done)
        menu.exec(pos)

    def _export(self, suffix: str, filter_: str, text: str):
        safe = "".join(c for c in self.book_title if c.isalnum() or c in " -_")[:60].strip() or "book"
        path, _ = QFileDialog.getSaveFileName(self, "Export reading plan",
                                              str(Path.home() / f"Reading plan - {safe}{suffix}"),
                                              filter_)
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8", newline="")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        self.flash_info(f"Saved {Path(path).name}")

    def _export_ics(self):
        self._export(".ics", "Calendar (*.ics)",
                     rp.build_ics(self.book_id, self.book_title, self.plan, self.tasks, self.sched))

    def _export_md(self):
        self._export(".md", "Markdown (*.md)",
                     rp.build_markdown(self.book_title, self.plan, self.tasks, self.sched,
                                       self.counts.estimated))


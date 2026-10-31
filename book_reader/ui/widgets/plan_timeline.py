"""Reading-plan timeline (Gantt): one row per task, bars on a date axis.

Adapted from the Zuqongtech Daily Planner's project timeline (planner/ui/gantt.py), made
read-only. Inside each day the bars sit where their minutes fall in that day's reading time,
so consecutive tasks line up end to end and nothing overlaps. Days you don't read are shaded,
the strip under the header shows how full each day is, and a red line marks today.

Mouse: click selects, double-click opens the chapter, right-click offers a menu.
Ctrl+wheel zooms around the cursor, Shift+wheel scrolls sideways.

Signals:
    activated(key)              double-click: jump to the task's chapter
    menuRequested(key, QPoint)  right-click on a row
"""
from datetime import date, timedelta

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QAbstractScrollArea, QToolTip

from book_reader.services import reading_plan as rp

ZOOMS = (12, 18, 26, 40, 60, 90, 140, 220)    # pixels per day
LABEL_W = 240
HEADER_H = 46
LOAD_H = 16
ROW_H = 30
KIND_COLOURS = {rp.REVIEW: "#c77d1a", rp.MINDMAP: "#2a9d8f"}
LATE = "#c0392b"


class PlanTimeline(QAbstractScrollArea):
    activated = Signal(str)
    menuRequested = Signal(str, QPoint)

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.viewport().setMouseTracking(True)
        self.zoom = 4
        self.label_w = LABEL_W
        self.tasks, self.blocks, self.done = [], [], set()
        self.per_day, self.weekdays, self.skip = 30, set(range(7)), set()
        self.t = {}
        self.today = date.today()
        self.d0 = self.d1 = self.today
        self.selected_key = None
        self._rows = {}
        self.horizontalScrollBar().valueChanged.connect(self.viewport().update)
        self.verticalScrollBar().valueChanged.connect(self.viewport().update)

    # ------------------------------------------------------------------ data
    @property
    def ppd(self):
        return ZOOMS[self.zoom]

    def set_plan(self, tasks, schedule, done, settings, theme, today=None):
        self.today = today or date.today()
        keys = {b.key for b in schedule.blocks}
        self.tasks = [t for t in tasks if t.key in keys]
        self.blocks, self.done, self.t = schedule.blocks, set(done), theme
        self.per_day = max(1, settings.minutes_per_day)
        self.weekdays, self.skip = set(settings.weekdays), set(settings.skip_dates or [])
        self._rows = {t.key: i for i, t in enumerate(self.tasks)}
        days = [b.day for b in self.blocks] + [self.today, settings.start_date()]
        self.d0 = min(days) - timedelta(days=2)
        self.d1 = max(days) + timedelta(days=4)
        if self.selected_key not in self._rows:
            self.selected_key = None
        self._update_ranges()
        self.viewport().update()

    def _update_ranges(self):
        content_w = int(((self.d1 - self.d0).days + 1) * self.ppd)
        vw = max(1, self.viewport().width() - self.label_w)
        hb = self.horizontalScrollBar()
        hb.setRange(0, max(0, content_w - vw))
        hb.setPageStep(vw)
        hb.setSingleStep(max(8, self.ppd // 2))
        content_h = HEADER_H + LOAD_H + len(self.tasks) * ROW_H + 8
        vb = self.verticalScrollBar()
        vb.setRange(0, max(0, content_h - self.viewport().height()))
        vb.setPageStep(self.viewport().height())
        vb.setSingleStep(ROW_H)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.label_w = max(130, min(LABEL_W, int(self.viewport().width() * 0.34)))
        self._update_ranges()

    # ------------------------------------------------------------------ geometry
    def x_of(self, d: date, minute: float = 0.0) -> float:
        days = (d - self.d0).days + minute / self.per_day
        return self.label_w + days * self.ppd - self.horizontalScrollBar().value()

    def day_of(self, x) -> date:
        return self.d0 + timedelta(days=int((x - self.label_w + self.horizontalScrollBar().value())
                                            // self.ppd))

    def row_y(self, i):
        return HEADER_H + LOAD_H + i * ROW_H - self.verticalScrollBar().value()

    def block_rect(self, b) -> QRectF:
        i = self._rows[b.key]
        x1 = self.x_of(b.day, b.start_min)
        w = max(3.0, b.minutes / self.per_day * self.ppd - 1)
        return QRectF(x1, self.row_y(i) + 6, w, ROW_H - 12)

    def scroll_to_day(self, d: date, align=0.25):
        vw = self.viewport().width() - self.label_w
        x = (d - self.d0).days * self.ppd - vw * align
        self.horizontalScrollBar().setValue(int(x))

    def set_zoom(self, z, anchor_x=None):
        z = max(0, min(len(ZOOMS) - 1, z))
        if z == self.zoom:
            return
        anchor_x = anchor_x if anchor_x is not None else self.label_w + (self.viewport().width() - self.label_w) / 2
        days = (anchor_x - self.label_w + self.horizontalScrollBar().value()) / self.ppd
        self.zoom = z
        self._update_ranges()
        self.horizontalScrollBar().setValue(int(days * self.ppd - (anchor_x - self.label_w)))
        self.viewport().update()

    def fit(self):
        """Zoom so the whole plan fills the view, then show its start."""
        span = max(1, (self.d1 - self.d0).days + 1)
        vw = self.viewport().width() - self.label_w
        self.zoom = max([i for i, z in enumerate(ZOOMS) if span * z <= vw] or [0])
        self._update_ranges()
        self.horizontalScrollBar().setValue(0)
        self.viewport().update()

    def row_task(self, pos):
        if pos.y() < HEADER_H + LOAD_H:
            return None
        i = int((pos.y() - HEADER_H - LOAD_H + self.verticalScrollBar().value()) // ROW_H)
        return self.tasks[i] if 0 <= i < len(self.tasks) else None

    def block_at(self, pos):
        for b in self.blocks:
            if b.key in self._rows and self.block_rect(b).adjusted(-2, -3, 2, 3).contains(pos):
                return b
        return None

    # ------------------------------------------------------------------ paint
    def _c(self, key, fallback):
        return QColor(self.t.get(key, fallback))

    def paintEvent(self, e):
        p = QPainter(self.viewport())
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.viewport().width(), self.viewport().height()
        bg, panel = self._c("bg", "#ffffff"), self._c("panel", "#f4f4f4")
        grid, muted = self._c("border", "#cccccc"), self._c("muted", "#666666")
        text, accent = self._c("fg", "#111111"), self._c("accent", "#6750a4")
        late = QColor(LATE)
        p.fillRect(0, 0, W, H, bg)
        small = QFont(self.font())
        small.setPointSizeF(max(7.0, self.font().pointSizeF() - 1.5))
        p.setFont(small)
        top_rows = HEADER_H + LOAD_H
        d_first = max(self.d0, self.day_of(self.label_w) - timedelta(days=1))
        d_last = min(self.d1, self.day_of(W) + timedelta(days=1))

        # days you don't read + day grid
        d = d_first
        while d <= d_last:
            x = self.x_of(d)
            if d.weekday() not in self.weekdays or d.isoformat() in self.skip:
                shade = QColor(text)
                shade.setAlpha(14)
                p.fillRect(QRectF(x, top_rows, self.ppd, H), shade)
            if self.ppd >= 18 or d.weekday() == 0:
                pen = QPen(grid, 1)
                pen.setCosmetic(True)
                p.setPen(pen)
                p.drawLine(QPointF(x, top_rows), QPointF(x, H))
            d += timedelta(days=1)

        # row separators
        p.setPen(QPen(grid, 1))
        for i in range(len(self.tasks) + 1):
            y = self.row_y(i)
            if top_rows <= y <= H:
                p.drawLine(QPointF(self.label_w, y), QPointF(W, y))

        # bars
        fm = QFontMetrics(small)
        by_key = {t.key: t for t in self.tasks}
        for b in self.blocks:
            if b.key not in self._rows:
                continue
            r = self.block_rect(b)
            if r.bottom() < top_rows or r.top() > H or r.right() < self.label_w or r.left() > W:
                continue
            task = by_key[b.key]
            col = QColor(KIND_COLOURS.get(task.kind, accent.name()))
            done = b.key in self.done
            behind = not done and b.day < self.today
            fill = QColor(col)
            fill.setAlpha(210 if done else 80)
            path = QPainterPath()
            path.addRoundedRect(r, 4, 4)
            p.fillPath(path, fill)
            pen = QPen(late, 2) if behind else QPen(col.darker(125), 1)
            if b.key == self.selected_key:
                pen = QPen(text, 2)
            p.setPen(pen)
            p.drawPath(path)
            if r.width() > 22:
                label = ("✓ " if done else "") + (f"{b.part}/{b.parts}" if b.parts > 1 else f"{b.minutes}′")
                p.setPen(self._c("on_accent", "#ffffff") if done else text)
                p.drawText(r.adjusted(4, 0, -2, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                           fm.elidedText(label, Qt.TextElideMode.ElideRight, int(r.width()) - 6))

        # today line
        xt = self.x_of(self.today)
        if self.label_w <= xt <= W:
            p.setPen(QPen(late, 2))
            p.drawLine(QPointF(xt, HEADER_H), QPointF(xt, H))

        # ---- sticky header (date axis + how full each day is)
        p.fillRect(QRectF(self.label_w, 0, W - self.label_w, top_rows), panel)
        d, last_month = d_first, None
        while d <= d_last:
            x = self.x_of(d)
            if (d.year, d.month) != last_month and (d.day == 1 or last_month is None):
                left = max(x, self.label_w) + 4
                nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
                room = min(160.0, self.x_of(nxt) - left - 4)   # don't run into the next month
                if room >= 40:
                    p.setPen(text)
                    p.drawText(QRectF(left, 2, room, 18),
                               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                               fm.elidedText(d.strftime("%B %Y"), Qt.TextElideMode.ElideRight, int(room)))
                last_month = (d.year, d.month)
            if self.ppd >= 26:
                lab = f"{d:%a}"[0] + f" {d.day}" if self.ppd < 60 else f"{d:%a} {d.day}"
                p.setPen(late if d == self.today else muted)
                p.drawText(QRectF(x, 22, self.ppd, 20), Qt.AlignmentFlag.AlignCenter, lab)
            elif d.weekday() == 0:
                p.setPen(muted)
                p.drawText(QRectF(x + 2, 22, 7 * self.ppd, 20),
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{d.day} {d:%b}")
            d += timedelta(days=1)
        load: dict = {}
        for b in self.blocks:
            load[b.day] = load.get(b.day, 0) + b.minutes
        for day, mins in load.items():
            if d_first <= day <= d_last:
                x = self.x_of(day)
                lc = QColor(accent)
                lc.setAlpha(60 + int(170 * min(1.0, mins / self.per_day)))
                p.fillRect(QRectF(x + 1, HEADER_H + 2, self.ppd - 2, LOAD_H - 4), lc)
                if self.ppd >= 40:
                    p.setPen(self._c("on_accent", "#ffffff"))
                    p.drawText(QRectF(x, HEADER_H, self.ppd, LOAD_H), Qt.AlignmentFlag.AlignCenter,
                               f"{mins}′")
        p.setPen(QPen(grid, 1))
        p.drawLine(QPointF(self.label_w, top_rows), QPointF(W, top_rows))

        # ---- sticky label column
        p.fillRect(QRectF(0, 0, self.label_w, H), panel)
        p.setPen(muted)
        p.drawText(QRectF(12, 0, self.label_w - 16, HEADER_H),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "CHAPTER")
        p.drawText(QRectF(12, HEADER_H, self.label_w - 16, LOAD_H),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "minutes per day")
        p.setFont(self.font())
        fm = QFontMetrics(self.font())
        for i, t in enumerate(self.tasks):
            y = self.row_y(i)
            if y + ROW_H < top_rows or y > H:
                continue
            rr = QRectF(0, y, self.label_w, ROW_H)
            if t.key == self.selected_key:
                p.fillRect(rr, self._c("sel", "#e8def8"))
            done = t.key in self.done
            mark = "✓" if done else ("·" if t.kind == rp.READ else "◇")
            p.setPen(QColor(KIND_COLOURS.get(t.kind, accent.name())))
            p.drawText(QRectF(8, y, 18, ROW_H), Qt.AlignmentFlag.AlignCenter, mark)
            p.setPen(muted if done else text)
            indent = 10 * (t.level - 1) if t.kind == rp.READ else 10
            p.drawText(rr.adjusted(28 + indent, 0, -8, 0),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                       fm.elidedText(t.label, Qt.TextElideMode.ElideRight, self.label_w - 40 - indent))
        p.setPen(QPen(grid, 1))
        p.drawLine(QPointF(self.label_w, 0), QPointF(self.label_w, H))
        if not self.tasks:
            p.setPen(muted)
            p.drawText(QRectF(self.label_w, top_rows, W - self.label_w, 80), Qt.AlignmentFlag.AlignCenter,
                       "Nothing to schedule yet.")

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, e):
        t = self.row_task(e.position())
        if t is not None and e.button() == Qt.MouseButton.LeftButton:
            self.select(t.key)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        b = self.block_at(e.position())
        if b is None:
            QToolTip.hideText()
            return
        task = next(t for t in self.tasks if t.key == b.key)
        state = "done" if b.key in self.done else ("behind" if b.day < self.today else "planned")
        QToolTip.showText(e.globalPosition().toPoint(),
                          f"{rp.block_title(b, task)}\n{rp.day_label(b.day, self.today)}: "
                          f"{b.minutes} min ({state})", self.viewport())

    def mouseDoubleClickEvent(self, e):
        t = self.row_task(e.position())
        if t is not None:
            self.select(t.key)
            self.activated.emit(t.key)

    def contextMenuEvent(self, e):
        t = self.row_task(QPointF(e.pos()))
        if t is not None:
            self.select(t.key)
            self.menuRequested.emit(t.key, e.globalPos())

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.set_zoom(self.zoom + (1 if e.angleDelta().y() > 0 else -1), e.position().x())
            return
        if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            hb = self.horizontalScrollBar()
            hb.setValue(hb.value() - e.angleDelta().y())
            return
        super().wheelEvent(e)

    def select(self, key):
        if key != self.selected_key:
            self.selected_key = key
            self.viewport().update()

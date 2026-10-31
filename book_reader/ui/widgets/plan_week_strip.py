"""A week at a glance for a reading plan: seven day cells starting today.

Each cell shows the day, a bar for how much of the day's reading time is planned (filled
solid for what is already done) and the minutes. Days you don't read are dimmed.
"""
from datetime import date

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QToolTip, QWidget

from book_reader.services import reading_plan as rp
from book_reader.ui.widgets.plan_timeline import LATE


class PlanWeekStrip(QWidget):
    def __init__(self, theme: dict, parent=None):
        super().__init__(parent)
        self.t, self.week, self.per_day, self.behind = theme, [], 30, False
        self.setMouseTracking(True)
        self.setMinimumHeight(54)

    def sizeHint(self):
        return QSize(7 * 52, 56)

    def set_week(self, week, per_day: int, behind: bool = False):
        self.week, self.per_day, self.behind = week, max(1, per_day), behind
        self.update()

    def _cell(self, i) -> QRectF:
        w = self.width() / max(1, len(self.week))
        return QRectF(i * w + 2, 0, w - 4, self.height())

    def paintEvent(self, e):
        if not self.week:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = self.t
        fg, muted, accent = QColor(t["fg"]), QColor(t["muted"]), QColor(t["accent"])
        track = QColor(t["border"])
        small = QFont(self.font())
        small.setPointSizeF(max(7.0, self.font().pointSizeF() - 1))
        today = date.today()
        for i, wd in enumerate(self.week):
            r = self._cell(i)
            p.setFont(small)
            p.setPen(LATE if (wd.day == today and self.behind) else
                     (fg if wd.reading_day else muted))
            label = "Today" if wd.day == today else f"{wd.day:%a} {wd.day.day}"
            if wd.day == today:
                f = QFont(small)
                f.setBold(True)
                p.setFont(f)
            p.drawText(QRectF(r.left(), 0, r.width(), 16), Qt.AlignmentFlag.AlignCenter, label)
            bar = QRectF(r.left() + 4, 20, r.width() - 8, 10)
            path = QPainterPath()
            path.addRoundedRect(bar, 5, 5)
            tc = QColor(track)
            tc.setAlpha(70 if wd.reading_day else 30)
            p.fillPath(path, tc)
            if wd.planned:
                share = min(1.0, wd.planned / self.per_day)
                planned = QColor(accent)
                planned.setAlpha(150)
                pp = QPainterPath()
                pp.addRoundedRect(QRectF(bar.left(), bar.top(), bar.width() * share, bar.height()), 5, 5)
                p.fillPath(pp, planned)
                if wd.done:
                    dp = QPainterPath()
                    dp.addRoundedRect(QRectF(bar.left(), bar.top(),
                                             bar.width() * share * wd.done / wd.planned,
                                             bar.height()), 5, 5)
                    p.fillPath(dp, accent)
            p.setFont(small)
            p.setPen(muted)
            text = (f"{wd.planned}′" + (" ✓" if wd.planned and wd.done >= wd.planned else "")
                    if wd.planned else ("—" if wd.reading_day else "off"))
            p.drawText(QRectF(r.left(), 34, r.width(), 18), Qt.AlignmentFlag.AlignCenter, text)

    def mouseMoveEvent(self, e):
        for i, wd in enumerate(self.week):
            if self._cell(i).contains(e.position()):
                if wd.planned:
                    tip = (f"{rp.day_label(wd.day)}: {wd.planned} min planned"
                           + (f", {wd.done} done" if wd.done else ""))
                else:
                    tip = (f"{rp.day_label(wd.day)}: "
                           + ("nothing planned" if wd.reading_day else "not a reading day"))
                QToolTip.showText(e.globalPosition().toPoint(), tip, self)
                return
        QToolTip.hideText()

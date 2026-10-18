"""Bar chart of minutes read per day, with the daily goal line."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from book_reader.themes import THEMES


class ReadingChart(QWidget):
    LEFT, RIGHT, TOP, BOTTOM = 36, 10, 12, 24

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(170)
        self.setMouseTracking(True)
        self.rows: list = []
        self.goal = 20
        self.t = THEMES["Light"]

    def set_data(self, rows, goal_min: int, theme: dict):
        self.rows, self.goal, self.t = rows, goal_min, theme
        self.update()

    def _geometry(self):
        plot = QRectF(self.LEFT, self.TOP, self.width() - self.LEFT - self.RIGHT,
                      self.height() - self.TOP - self.BOTTOM)
        top = max([self.goal * 1.25, 10.0] + [m for _, m in self.rows])
        return plot, top

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.rows:
            return
        plot, top = self._geometry()
        t = self.t
        p.setFont(QFont(self.font().family(), 8))
        for k in range(4):  # grid + y labels
            y = plot.bottom() - plot.height() * k / 3
            p.setPen(QColor(t["border"]))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(t["muted"]))
            p.drawText(QRectF(0, y - 8, self.LEFT - 6, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{top * k / 3:.0f}")
        n = len(self.rows)
        slot = plot.width() / n
        bar_w = max(3.0, slot * 0.68)
        for i, (day, minutes) in enumerate(self.rows):
            h = plot.height() * min(minutes, top) / top
            x = plot.left() + i * slot + (slot - bar_w) / 2
            color = QColor(t["accent"] if minutes >= self.goal else t["outline"])
            if minutes < self.goal and minutes > 0:
                color.setAlpha(170)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            if h > 0:
                p.drawRoundedRect(QRectF(x, plot.bottom() - h, bar_w, h), 2, 2)
            if i % 5 == 0 or i == n - 1:
                p.setPen(QColor(t["muted"]))
                p.drawText(QRectF(x - 14, plot.bottom() + 4, bar_w + 28, 16),
                           Qt.AlignmentFlag.AlignHCenter, f"{day.day} {day:%b}")
        gy = plot.bottom() - plot.height() * self.goal / top  # goal line
        pen = QPen(QColor(t["accent"]), 1.5, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(QPointF(plot.left(), gy), QPointF(plot.right(), gy))
        p.end()

    def mouseMoveEvent(self, e):
        if not self.rows:
            return
        plot, _ = self._geometry()
        i = int((e.position().x() - plot.left()) / (plot.width() / len(self.rows)))
        if 0 <= i < len(self.rows):
            day, minutes = self.rows[i]
            QToolTip.showText(e.globalPosition().toPoint(), f"{day:%a %d %b}: {minutes:.0f} min")

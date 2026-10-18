"""Reading statistics dialog."""
import time

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from book_reader.constants import DEFAULT_DAILY_GOAL_MIN
from book_reader.core.library import Library
from book_reader.services import goals
from book_reader.themes import THEMES
from book_reader.ui.widgets.reading_chart import ReadingChart
from book_reader.utils import ago, fmt_duration


class StatItem(QTreeWidgetItem):
    """Tree item that sorts on numeric UserRole data when present."""

    def __lt__(self, other):
        col = self.treeWidget().sortColumn()
        a = self.data(col, Qt.ItemDataRole.UserRole)
        b = other.data(col, Qt.ItemDataRole.UserRole)
        if a is not None and b is not None:
            return a < b
        return self.text(col).lower() < other.text(col).lower()


class StatsDialog(QDialog):
    def __init__(self, parent, library: Library, prefs=None):
        super().__init__(parent)
        self.setWindowTitle("Reading statistics")
        self.resize(980, 760)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(12)

        rows = library.stats()
        total = sum((r["read_seconds"] or 0) for r in rows)
        midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        today = library.time_since(midnight)
        week = library.time_since(time.time() - 7 * 86400)
        head = QLabel("Reading time")
        head.setObjectName("h2")
        summary = QLabel(f"Total: {fmt_duration(total)}     Today: {fmt_duration(today)}"
                         f"     Last 7 days: {fmt_duration(week)}"
                         f"     Currently reading: {library.count_reading()}")
        summary.setObjectName("muted")
        lay.addWidget(head)
        lay.addWidget(summary)
        self._goals(lay, library, prefs)

        tree = QTreeWidget()
        tree.setRootIsDecorated(False)
        tree.setColumnCount(8)
        tree.setHeaderLabels(["Title", "Format", "Status", "Progress", "Time read",
                              "Sessions", "Avg session", "Last read"])
        for r in rows:
            n = r["n_sessions"] or 0
            secs = r["read_seconds"] or 0
            prog = r["progress"] or 0
            last = r["last_read_at"] or 0
            status = ("★ Reading" if r["reading"] == 1
                      else "Finished" if prog >= 0.98 else "")
            item = StatItem([
                r["title"], (r["format"] or "epub").upper(), status, f"{prog * 100:.1f}%",
                fmt_duration(secs), str(n), fmt_duration(secs / n) if n else "—",
                ago(last) if last else "—"])
            item.setData(3, Qt.ItemDataRole.UserRole, prog)
            item.setData(4, Qt.ItemDataRole.UserRole, secs)
            item.setData(5, Qt.ItemDataRole.UserRole, n)
            item.setData(6, Qt.ItemDataRole.UserRole, secs / n if n else 0)
            item.setData(7, Qt.ItemDataRole.UserRole, last)
            tree.addTopLevelItem(item)
        header = tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 8):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        tree.setSortingEnabled(True)
        tree.sortByColumn(7, Qt.SortOrder.DescendingOrder)
        lay.addWidget(tree, 1)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        lay.addLayout(row)

    def _goals(self, lay, library, prefs):
        """Daily goal, today's progress, streaks and a 30-day chart."""
        theme = THEMES[prefs.v["theme"]] if prefs else THEMES["Light"]
        goal = int(prefs.v["daily_goal"]) if prefs else DEFAULT_DAILY_GOAL_MIN
        box = QFrame()
        box.setObjectName("sidePanel")
        box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        g = QVBoxLayout(box)
        g.setContentsMargins(18, 14, 18, 14)
        g.setSpacing(8)
        top = QHBoxLayout()
        title = QLabel("Daily reading goal")
        title.setObjectName("h2")
        top.addWidget(title)
        top.addStretch()
        top.addWidget(QLabel("Goal"))
        spin = QSpinBox()
        spin.setRange(1, 600)
        spin.setSuffix(" min")
        spin.setValue(goal)
        spin.setEnabled(prefs is not None)
        top.addWidget(spin)
        g.addLayout(top)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setTextVisible(False)
        bar.setFixedHeight(6)
        today_label, streak_label = QLabel(""), QLabel("")
        today_label.setObjectName("muted")
        chart = ReadingChart()
        for w in (bar, today_label, streak_label, chart):
            g.addWidget(w)

        def refresh(_=None):
            minutes = spin.value()
            if prefs:
                prefs.set("daily_goal", minutes)
            info = goals.summary(library, minutes)
            pct = min(100, int(info["today_min"] / minutes * 100))
            bar.setValue(pct)
            today_label.setText(f"Today: {int(info['today_min'])} of {minutes} min ({pct}%)"
                                f"   ·   7-day average {info['week_avg']:.0f} min/day")
            streak_label.setText(f"🔥 Current streak: {info['current']} day"
                                 f"{'' if info['current'] == 1 else 's'}"
                                 f"   ·   Best streak: {info['best']} day{'' if info['best'] == 1 else 's'}")
            chart.set_data(goals.daily_minutes(info["totals"], 30), minutes, theme)

        spin.valueChanged.connect(refresh)
        refresh()
        lay.addWidget(box)

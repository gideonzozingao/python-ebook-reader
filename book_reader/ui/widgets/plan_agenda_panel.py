"""Library strip: today's reading from every book with a reading plan.

Each line is a link: it opens the book at the chapter (or where today's part of it begins).
Hidden when no book has a plan or the Reading plan feature is off.
"""
from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from book_reader.services import reading_plan as rp
from book_reader.ui.widgets.plan_timeline import LATE

MAX_ROWS = 5


class PlanAgendaPanel(QFrame):
    itemRequested = Signal(object)    # plan_agenda.AgendaItem

    def __init__(self):
        super().__init__()
        self.setObjectName("sidePanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(4)
        self.text = QLabel("")
        self.text.setTextFormat(Qt.TextFormat.RichText)
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.text.linkActivated.connect(self._clicked)
        lay.addWidget(self.text)
        self.items = []
        self.setVisible(False)

    def show_agenda(self, agenda, theme: dict, expanded: bool = False):
        self.items = agenda.items
        if agenda.planned == 0:
            self.setVisible(False)
            return
        t = theme
        link = f"color:{t['fg']}; text-decoration:none"
        if not agenda.items:
            self.text.setText(f"<b>📅 Today’s reading</b> &nbsp;"
                              f"<span style='color:{t['muted']}'>All done for today in your "
                              f"{agenda.planned} planned book{'s' if agenda.planned != 1 else ''}. "
                              f"✓</span>")
            self.setVisible(True)
            return
        head = f"<b>📅 Today’s reading</b> &nbsp;<span style='color:{t['muted']}'>"
        if agenda.minutes:
            head += (f"{rp.fmt_minutes(agenda.minutes)} in {agenda.books} "
                     f"book{'s' if agenda.books != 1 else ''}")
        if agenda.behind_minutes:
            head += (f" · <span style='color:{LATE}'>{rp.fmt_minutes(agenda.behind_minutes)} "
                     f"to catch up</span>")
        head += "</span>"
        rows = []
        shown = self._rows(agenda.items)
        total_rows = len(shown)
        if not expanded:
            shown = shown[:MAX_ROWS]
        self.items = [item for item, _, _ in shown]
        for n, (item, label, mins) in enumerate(shown):
            tag = (f"<span style='color:{LATE}'>catch up</span> · " if item.overdue else "")
            mins = f" · {rp.fmt_minutes(mins)}" if mins else ""
            label = (f"<i style='color:{t['muted']}'>{escape(label)}</i>" if item.stale
                     else escape(label))
            rows.append(f"▸ {tag}<a href='item:{n}' style='{link}'><b>{escape(item.book)}</b>"
                        f" — {label}</a><span style='color:{t['muted']}'>{mins}</span>")
        more = total_rows - len(shown)
        if more > 0:
            rows.append(f"<a href='more:' style='color:{t['accent']}; text-decoration:none'>"
                        f"+ {more} more</a>")
        self.text.setText(head + "<br>" + "<br>".join(rows))
        self._agenda, self._theme = agenda, theme
        self.setVisible(True)

    @staticmethod
    def _rows(items) -> list:
        """(item to open, label, minutes): at most two lines per book, one for missed
        sessions and one for today ("Chapter 3, part 2 of 2 + 2 more"), each opening at
        its first session. Keeps a busy plan from filling the library."""
        rows, groups = [], {}
        for item in items:
            key = (item.book_id, item.stale, item.overdue)
            if key not in groups:
                groups[key] = []
                rows.append(key)
            groups[key].append(item)
        out = []
        for key in rows:
            group = groups[key]
            first = group[0]
            if first.stale:
                out.append((first, first.label, 0))
                continue
            label = first.label
            if len(group) > 1:
                label += (f" + {len(group) - 1} more" if not first.overdue
                          else f" and {len(group) - 1} more missed")
            out.append((first, label, sum(i.minutes for i in group)))
        return out

    def _clicked(self, href: str):
        if href == "more:":
            self.show_agenda(self._agenda, self._theme, expanded=True)
            return
        try:
            self.itemRequested.emit(self.items[int(href.split(":", 1)[1])])
        except (ValueError, IndexError):
            pass

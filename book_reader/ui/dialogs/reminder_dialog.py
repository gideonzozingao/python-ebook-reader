"""'Welcome back' reminder shown at startup: the last book you read, a preview of its reading
plan (today's sessions and the week ahead), your other plans for today and your reading list."""
import textwrap

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from book_reader.services import reading_plan as rp
from book_reader.ui.widgets.cover import make_cover
from book_reader.ui.widgets.plan_timeline import LATE
from book_reader.ui.widgets.plan_week_strip import PlanWeekStrip
from book_reader.utils import ago, fmt_duration, where_text


class ReminderDialog(QDialog):
    """Shows the last book you read, where you stopped, and links to reopen it."""

    MAX_PLAN_ROWS = 4

    def __init__(self, parent, last, others, theme: dict, plan=None, agenda=None):
        """`plan`: plan_agenda.Overview of the last book (or None); `agenda`:
        plan_agenda.Agenda of today's reading in every planned book (or None)."""
        super().__init__(parent)
        self.setWindowTitle("Welcome back")
        self.setMinimumWidth(620)
        self.chosen: int | None = None
        self.chosen_item = None          # a plan session to open (plan_agenda.AgendaItem)
        self.open_plan = False           # "Open plan" was pressed for the last book
        self.t = theme
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(14)

        head = QLabel("Welcome back — pick up where you left off")
        head.setObjectName("h2")
        lay.addWidget(head)

        card = QFrame()
        card.setObjectName("sidePanel")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 16, 16, 16)
        row.setSpacing(16)
        cover = QLabel()
        cover.setPixmap(make_cover(last["title"], last["author"], last["cover"],
                                   last["progress"] or 0, True).scaled(
            100, 147, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        cover.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(cover)

        info = QVBoxLayout()
        info.setSpacing(5)
        title = QLabel(last["title"])
        title.setObjectName("h2")
        title.setWordWrap(True)
        info.addWidget(title)
        if last["author"]:
            author = QLabel(last["author"])
            author.setObjectName("muted")
            info.addWidget(author)
        info.addSpacing(6)
        lines = [f"Last read {ago(last['last_read_at'])}"]
        if last["last_section"]:
            lines.append(f"Section: {last['last_section']}")
        lines.append(f"Stopped at {where_text(last)}")
        lines.append(f"{(last['progress'] or 0) * 100:.0f}% of the book  ·  "
                     f"{fmt_duration(last['read_seconds'])} read so far")
        for text in lines:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            info.addWidget(lbl)
        info.addStretch()
        go = QPushButton("▶  Continue reading")
        go.setObjectName("primary")
        go.setMinimumHeight(38)
        go.setDefault(True)
        go.clicked.connect(lambda: self._choose(last["id"]))
        info.addWidget(go)
        row.addLayout(info, 1)
        lay.addWidget(card)

        if plan is not None:
            lay.addWidget(self._plan_card(last, plan))
        shown = {last["id"]}
        if agenda is not None:
            box = self._other_plans(agenda, shown)
            if box is not None:
                lay.addWidget(box)
        others = [r for r in others if r["id"] not in shown]

        if others:
            more = QLabel("Also on your reading list")
            more.setObjectName("muted")
            lay.addWidget(more)
            for r in others:
                text = f"{textwrap.shorten(r['title'], 52, placeholder='…')}"
                detail = f"{where_text(r)}  ·  {ago(r['last_read_at'])}"
                b = QPushButton(f"{text}   —   {detail}")
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setStyleSheet(
                    f"QPushButton {{ text-align:left; padding:5px 2px; border:none;"
                    f" background:transparent; color:{theme['link']}; }}"
                    f"QPushButton:hover {{ text-decoration:underline; }}")
                b.clicked.connect(lambda _=False, bid=r["id"]: self._choose(bid))
                lay.addWidget(b)

        foot = QHBoxLayout()
        self.chk = QCheckBox("Show this reminder when the app starts")
        self.chk.setChecked(True)
        foot.addWidget(self.chk)
        foot.addStretch()
        later = QPushButton("Not now")
        later.clicked.connect(self.reject)
        foot.addWidget(later)
        lay.addLayout(foot)

    # -- reading plan preview --------------------------------------------------------- #

    def _link_style(self) -> str:
        return f"color:{self.t['fg']}; text-decoration:none"

    def _plan_card(self, last, ov) -> QFrame:
        t = self.t
        card = QFrame()
        card.setObjectName("sidePanel")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(8)
        head = QHBoxLayout()
        title = QLabel("<b>📅 Reading plan</b>")
        head.addWidget(title)
        colour = LATE if ov.behind else t["accent"]
        finish = (f" · finishes {ov.finish:%a} {ov.finish.day} {ov.finish:%b}"
                  if ov.finish and ov.status != "Plan complete" else "")
        state = QLabel(f"<span style='color:{t['muted']}'>{ov.percent}% done · </span>"
                       f"<span style='color:{colour}'>{escape(ov.status)}</span>"
                       f"<span style='color:{t['muted']}'>{finish}</span>")
        head.addWidget(state, 1)
        open_btn = QPushButton("Open plan")
        open_btn.setObjectName("link")
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self._open_plan)
        head.addWidget(open_btn)
        v.addLayout(head)

        week = PlanWeekStrip(t)
        week.set_week(ov.week, ov.minutes_per_day, ov.behind)
        v.addWidget(week)

        rows = self._session_rows(ov.today)
        if rows:
            due = sum(i.minutes for i in ov.today if not i.overdue)
            late = sum(i.minutes for i in ov.today if i.overdue)
            head = f"Today · {rp.fmt_minutes(due)}" if due else "Nothing new today"
            if late:
                head += f", plus {rp.fmt_minutes(late)} to catch up"
            v.addWidget(self._muted(head))
        elif ov.next_day is not None:
            v.addWidget(self._muted(f"Nothing planned today. Next: {rp.day_label(ov.next_day)}"))
            rows = self._session_rows(ov.next_items)
        elif ov.status == "Plan complete":
            v.addWidget(self._muted("Every chapter in the plan is done. Well read!"))
        else:
            v.addWidget(self._muted("All done for today ✓"))
        if rows:
            text = QLabel("<br>".join(rows))
            text.setTextFormat(Qt.TextFormat.RichText)
            text.setWordWrap(True)
            text.linkActivated.connect(lambda href, items=list(ov.today or ov.next_items):
                                       self._choose_item(items, href))
            v.addWidget(text)
        return card

    def _session_rows(self, items) -> list:
        """Missed sessions as one "catch up" line, then today's sessions. Links carry the
        item's position in `items`."""
        t, out = self.t, []
        late = [n for n, i in enumerate(items) if i.overdue]
        if late:
            first = items[late[0]]
            more = f" and {len(late) - 1} more" if len(late) > 1 else ""
            mins = sum(items[n].minutes for n in late)
            out.append(f"▸ <span style='color:{LATE}'>catch up</span> · "
                       f"<a href='item:{late[0]}' style='{self._link_style()}'>"
                       f"{escape(first.label)}{more}</a>"
                       f"<span style='color:{t['muted']}'> · {rp.fmt_minutes(mins)}</span>")
        fresh = [n for n, i in enumerate(items) if not i.overdue]
        for n in fresh[:self.MAX_PLAN_ROWS - len(out)]:
            item = items[n]
            out.append(f"▸ <a href='item:{n}' style='{self._link_style()}'>{escape(item.label)}</a>"
                       f"<span style='color:{t['muted']}'> · {item.minutes} min</span>")
        hidden = len(fresh) - (self.MAX_PLAN_ROWS - (1 if late else 0))
        if hidden > 0:
            out.append(f"<span style='color:{t['muted']}'>+ {hidden} more today</span>")
        return out

    def _other_plans(self, agenda, shown: set):
        """One line per other planned book with reading due today."""
        t = self.t
        books, order = {}, []
        for item in agenda.items:
            if item.book_id in shown or item.stale:
                continue
            if item.book_id not in books:
                books[item.book_id] = []
                order.append(item.book_id)
            books[item.book_id].append(item)
        if not order:
            return None
        box = QFrame()
        v = QVBoxLayout(box)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        v.addWidget(self._muted("Your other plans today"))
        firsts, rows = [], []
        for bid in order[:3]:
            items = books[bid]
            shown.add(bid)
            first = items[0]
            firsts.append(first)
            mins = sum(i.minutes for i in items)
            extra = f" + {len(items) - 1} more" if len(items) > 1 else ""
            late = (f" · <span style='color:{LATE}'>"
                    f"{rp.fmt_minutes(sum(i.minutes for i in items if i.overdue))} to catch up</span>"
                    if any(i.overdue for i in items) else "")
            rows.append(f"▸ <a href='item:{len(firsts) - 1}' style='{self._link_style()}'>"
                        f"<b>{escape(textwrap.shorten(first.book, 44, placeholder='…'))}</b> — "
                        f"{escape(first.label)}{extra}</a>"
                        f"<span style='color:{t['muted']}'> · {rp.fmt_minutes(mins)}</span>{late}")
        if len(order) > 3:
            rows.append(f"<span style='color:{t['muted']}'>+ {len(order) - 3} more planned "
                        f"book{'s' if len(order) > 4 else ''} (see the library)</span>")
        text = QLabel("<br>".join(rows))
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setWordWrap(True)
        text.linkActivated.connect(lambda href: self._choose_item(firsts, href))
        v.addWidget(text)
        return box

    @staticmethod
    def _muted(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("muted")
        lbl.setWordWrap(True)
        return lbl

    def _choose_item(self, items, href: str):
        try:
            self.chosen_item = items[int(href.split(":", 1)[1])]
        except (ValueError, IndexError):
            return
        self.chosen = self.chosen_item.book_id
        self.accept()

    def _open_plan(self):
        self.open_plan = True
        self.accept()

    def _choose(self, book_id: int):
        self.chosen = book_id
        self.accept()

    def show_again(self) -> bool:
        return self.chk.isChecked()

"""Today's reading across every book that has a reading plan (shown in the library).

Qt-free and cheap: it reads each plan from the database and the roadmap / word-count caches
from disk, and never scans a book. A book whose caches are missing or out of date (the book
file changed, or an older app version made them) is listed as needing its plan opened once.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from book_reader.services import plan_words as pw
from book_reader.services import reading_plan as rp
from book_reader.services import roadmap as rm


@dataclass
class AgendaItem:
    book_id: int
    book: str               # book title
    label: str              # "Ch 2 Foundations, part 2 of 2", or a note when stale
    minutes: int
    index: int = 0          # where to open: spine index / 0-based page
    fragment: str = ""      # heading anchor (start of a task)
    ratio: float = 0.0      # position inside index (a later part of a task)
    exact: bool = False     # True: open at (index, ratio); False: at the heading
    overdue: bool = False   # scheduled on an earlier day and not done yet
    stale: bool = False     # caches missing: open the book's plan once to update


@dataclass
class Agenda:
    items: list
    planned: int            # books with a plan
    behind_minutes: int = 0

    @property
    def minutes(self) -> int:
        return sum(i.minutes for i in self.items if not i.stale)

    @property
    def books(self) -> int:
        return len({i.book_id for i in self.items if not i.stale})


def _book_items(book_id, row, stored: str, today: date) -> list:
    plan = rp.ReadingPlan.from_json(stored)
    roadmap = rm.load_cached(book_id, row["path"])
    counts = pw.load_cached(book_id, row["path"], roadmap) if roadmap is not None else None
    if counts is None:
        return [AgendaItem(book_id, row["title"], "Open the book once to bring its plan up to date", 0,
                           stale=True)]
    tasks = rp.build_tasks(roadmap, counts, plan.settings)
    by_key = {t.key: t for t in tasks}
    sched = rp.plan_schedule(plan, tasks)
    out = []
    for b in sched.blocks:
        if b.day > today or b.key in plan.done:
            continue
        task = by_key[b.key]
        item = AgendaItem(book_id, row["title"], rp.block_title(b, task), b.minutes,
                          task.index, task.fragment, overdue=b.day < today)
        if b.before:                       # a later part: open where it begins
            loc = rp.block_location(counts, task, b)
            if loc is not None:
                item.index, item.ratio, item.exact = loc[0], loc[1], True
        out.append(item)
    return out


def todays_reading(library, today: date = None) -> Agenda:
    """Unfinished blocks scheduled for today or earlier, in every planned book.
    Overdue blocks come first, then books in the order they were last read."""
    today = today or date.today()
    items, planned = [], 0
    for book_id in library.planned_books():
        row = library.get(book_id)
        stored = library.get_plan(book_id)
        if row is None or not stored:
            continue
        planned += 1
        try:
            items += _book_items(book_id, row, stored, today)
        except Exception:
            continue      # one broken plan must not hide the others
    recent = {}
    for book_id in {i.book_id for i in items}:
        row = library.get(book_id)
        recent[book_id] = -float((row["last_read_at"] or 0) if row else 0)
    items.sort(key=lambda i: (i.stale, not i.overdue, recent[i.book_id]))
    behind = sum(i.minutes for i in items if i.overdue)
    return Agenda(items, planned, behind)


def signature(library, today: date = None) -> tuple:
    """Changes whenever any plan is saved (or the day changes): when to rebuild the agenda."""
    rows = library.db.execute("SELECT book_id, updated_at FROM reading_plans").fetchall()
    return (today or date.today(), tuple((r["book_id"], r["updated_at"]) for r in rows))


# -- one book's plan at a glance (the "Welcome back" reminder) ------------------------------ #

@dataclass
class WeekDay:
    day: date
    planned: int            # minutes scheduled that day
    done: int               # of those, minutes of tasks already ticked off
    reading_day: bool       # one of the plan's reading days


@dataclass
class Overview:
    book_id: int
    percent: int
    status: str             # "On track", "20 min behind", "35 min ahead", "Plan complete"
    behind: bool
    finish: object          # date the plan ends
    today: list             # AgendaItems for today (and missed sessions first)
    next_day: object        # next day with reading, when nothing is left today
    next_items: list        # what that day holds
    week: list              # 7 WeekDays starting today
    minutes_per_day: int


def overview(library, book_id: int, today: date = None):
    """The reading plan of one book at a glance, or None (no plan, or caches missing)."""
    today = today or date.today()
    row, stored = library.get(book_id), library.get_plan(book_id)
    if row is None or not stored:
        return None
    try:
        plan = rp.ReadingPlan.from_json(stored)
        roadmap = rm.load_cached(book_id, row["path"])
        counts = pw.load_cached(book_id, row["path"], roadmap) if roadmap is not None else None
        if counts is None:
            return None
        tasks = rp.build_tasks(roadmap, counts, plan.settings)
        sched = rp.plan_schedule(plan, tasks)
    except Exception:
        return None
    st = rp.status(plan, tasks, sched, today)
    if st.total_minutes and st.done_minutes >= st.total_minutes:
        status = "Plan complete"
    elif st.behind_minutes:
        status = f"{rp.fmt_minutes(st.behind_minutes)} behind"
    elif st.done_minutes > st.due_minutes:
        status = f"{rp.fmt_minutes(st.done_minutes - st.due_minutes)} ahead"
    else:
        status = "On track"
    items = [i for i in _book_items(book_id, row, stored, today) if not i.stale]
    nxt = st.next_day if not [i for i in items if not i.overdue] else None
    by_key = {t.key: t for t in tasks}
    next_items = [AgendaItem(book_id, row["title"], rp.block_title(b, by_key[b.key]), b.minutes,
                             by_key[b.key].index, by_key[b.key].fragment)
                  for b in sched.blocks if nxt and b.day == nxt and b.key not in plan.done]
    week = []
    days = set(plan.settings.weekdays)
    skip = set(plan.settings.skip_dates or [])
    for k in range(7):
        d = today + timedelta(days=k)
        blocks = [b for b in sched.blocks if b.day == d]
        week.append(WeekDay(d, sum(b.minutes for b in blocks),
                            sum(b.minutes for b in blocks if b.key in plan.done),
                            d.weekday() in days and d.isoformat() not in skip))
    return Overview(book_id, st.percent, status, bool(st.behind_minutes), sched.finish,
                    items, nxt, next_items, week, plan.settings.minutes_per_day)

"""Reading plans: turn a book's roadmap into a day-by-day reading (or study) schedule.

Qt-free, so all of it can be tested without a screen. The scheduling, time-label and
calendar code is adapted from the Zuqongtech Daily Planner (planner/timespan.py, planner/ics.py).

How a plan is made
  1. Units.   Each roadmap entry down to the chosen level (chapters, or chapters + sections)
              becomes a "read" task. Its words come from plan_words; its minutes are
              words / reading speed x study factor. Optional review and mind-map tasks
              follow each chapter.
  2. Days.    Reading days are the chosen weekdays from the start date, minus skipped dates.
  3. Laying.  Tasks are laid end to end into each day's minutes, so every minute belongs to
              exactly one task (no overlap). A task too long for the day continues on the
              next reading day. A new task is not started when fewer than `min_start` minutes
              are left, unless it fits completely.

The plan itself stores only settings and what is done ({task key: date}); tasks and the
schedule are rebuilt from the roadmap each time, so they follow a rebuilt roadmap.
"""
import hashlib
import json
import re

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta, timezone

DEFAULT_WPM = 230
MIN_WPM, MAX_WPM = 60, 1200
MAX_MINUTES_PER_DAY = 720
MAX_PLAN_DAYS = 3660          # ten years: a guard against impossible settings
WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
READ, REVIEW, MINDMAP = "read", "review", "mindmap"
MIN_UNIT_WORDS = 150      # smaller entries ("Part I" divider pages) join the next one
STEP_MIN_WORDS = 1000     # review / mind-map steps only for chapters at least this long

# Front and back matter nobody plans to read: left out when `skip_matter` is on.
MATTER = re.compile(
    r"^\s*(?:(?:front |back )?cover|half[- ]?title(?: page)?|title(?: page)?|copyright(?: page)?|"
    r"dedication|epigraph|frontispiece|(?:table of )?contents|toc|landmarks|"
    r"list of (?:figures|tables|illustrations|abbreviations|listings)|also by\b.*|"
    r"praise\b.*|other books\b.*|about the authors?|about the publisher|about this e?book|"
    r"colophon|imprint|credits|series page|index|bibliography|references)\s*[.:]?\s*$", re.I)


def is_matter(title: str) -> bool:
    return bool(MATTER.match(title or ""))
KIND_LABEL = {READ: "Read", REVIEW: "Review", MINDMAP: "Mind map"}
PRODID = "-//Zuqongtech//Book Reader reading plan//EN"


# -- model ------------------------------------------------------------------------------- #

@dataclass
class PlanSettings:
    start: str = ""                       # ISO date of the first reading day
    minutes_per_day: int = 30
    weekdays: list = field(default_factory=lambda: [0, 1, 2, 3, 4])   # Mon = 0
    wpm: int = DEFAULT_WPM
    study_factor: float = 1.0             # x1.5 = time for notes and re-reading
    unit_level: int = 1                   # 1 = chapters, 2 = chapters and sections
    min_start: int = 5                    # don't start a new task with fewer minutes left
    review_minutes: int = 0               # per chapter, 0 = no review step
    mindmap_minutes: int = 0              # per chapter, 0 = no mind-map step
    session_time: str = "19:00"           # when reading starts (calendar export only)
    skip_dates: list = field(default_factory=list)
    finish_by: str = ""                   # optional target date (for "fit to date")
    skip_matter: bool = True              # leave out cover, title pages, contents, index...

    def start_date(self) -> date:
        try:
            return date.fromisoformat(self.start)
        except (TypeError, ValueError):
            return date.today()

    def clean(self) -> "PlanSettings":
        self.minutes_per_day = max(1, min(MAX_MINUTES_PER_DAY, int(self.minutes_per_day)))
        self.wpm = max(MIN_WPM, min(MAX_WPM, int(self.wpm)))
        self.study_factor = max(0.5, min(5.0, float(self.study_factor)))
        self.unit_level = max(1, min(3, int(self.unit_level)))
        self.min_start = max(0, min(self.minutes_per_day, int(self.min_start)))
        self.review_minutes = max(0, int(self.review_minutes))
        self.mindmap_minutes = max(0, int(self.mindmap_minutes))
        self.weekdays = sorted({int(d) for d in self.weekdays if 0 <= int(d) <= 6})
        return self


@dataclass
class Task:
    key: str               # stable id, survives a rebuilt roadmap if the entry is unchanged
    kind: str              # READ, REVIEW or MINDMAP
    title: str
    chapter: str           # title of the chapter (level-1 entry) it belongs to
    words: int
    minutes: int
    index: int             # where to jump: spine index (EPUB/Markdown) or 0-based page (PDF)
    fragment: str = ""
    level: int = 1
    node: int = 0          # roadmap entry number
    end: tuple = None      # (index, ratio) where the next unit starts; None = end of book

    @property
    def label(self) -> str:
        return self.title if self.kind == READ else f"{KIND_LABEL[self.kind]}: {self.chapter}"


@dataclass
class Block:
    day: date
    key: str
    start_min: int         # offset within the day's reading time
    minutes: int
    part: int = 1
    parts: int = 1
    before: int = 0        # minutes of the same task scheduled before this block


@dataclass
class Schedule:
    blocks: list = field(default_factory=list)
    leftover: dict = field(default_factory=dict)   # day -> (minutes left, title not started)

    @property
    def finish(self):
        return self.blocks[-1].day if self.blocks else None

    @property
    def days(self) -> list:
        return sorted({b.day for b in self.blocks})

    def by_day(self) -> dict:
        out: dict = {}
        for b in self.blocks:
            out.setdefault(b.day, []).append(b)
        return out


@dataclass
class ReadingPlan:
    settings: PlanSettings = field(default_factory=PlanSettings)
    done: dict = field(default_factory=dict)       # task key -> ISO date it was finished
    created: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, text: str) -> "ReadingPlan":
        d = json.loads(text)
        known = PlanSettings.__dataclass_fields__
        s = PlanSettings(**{k: v for k, v in (d.get("settings") or {}).items() if k in known})
        return cls(s.clean(), dict(d.get("done") or {}), d.get("created") or "")

    @classmethod
    def new(cls, start: date = None, **settings) -> "ReadingPlan":
        s = PlanSettings(start=(start or date.today()).isoformat(), **settings).clean()
        return cls(s, {}, date.today().isoformat())


# -- tasks from a roadmap ------------------------------------------------------------------- #

def minutes_for(words: int, wpm: int, factor: float = 1.0) -> int:
    """Whole minutes to read `words` (at least 1 for any text)."""
    if words <= 0:
        return 0
    return max(1, round(words / max(1, wpm) * factor))


def _key(*parts) -> str:
    raw = "\x1f".join(str(p) for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def build_tasks(roadmap, counts, settings: PlanSettings) -> list:
    """Ordered tasks for `roadmap` with word `counts` (plan_words.WordCounts).

    Front and back matter (cover, copyright, contents, index...) is left out when
    `skip_matter` is on. Entries under MIN_UNIT_WORDS (a "Part I" divider page) are folded
    into the next entry instead of becoming a one-minute task. Review and mind-map steps
    are only added after chapters of at least STEP_MIN_WORDS words."""
    nodes, level = roadmap.nodes, settings.unit_level
    units = [n for n, node in enumerate(nodes) if node.level <= level]
    tasks, seen = [], set()
    chapter = dict(title="", tasks=[], words=0)
    carry = None                    # (node number, words) of a tiny entry waiting to join

    def close_chapter():
        if not chapter["tasks"] or chapter["words"] < STEP_MIN_WORDS:
            return
        last, title = chapter["tasks"][-1], chapter["title"]
        for kind, mins in ((REVIEW, settings.review_minutes), (MINDMAP, settings.mindmap_minutes)):
            if mins > 0:
                tasks.append(Task(_key(kind, last.key), kind, title, title, 0,
                                  mins, last.index, last.fragment, 1, last.node, last.end))

    def matter(n):
        if not settings.skip_matter:
            return False
        node = nodes[n]                          # an entry whose parent is matter is matter
        return is_matter(node.title) or any(is_matter(nodes[a].title)
                                            for a in roadmap.ancestors(n))

    for u, n in enumerate(units):
        node = nodes[n]
        stop = units[u + 1] if u + 1 < len(units) else len(nodes)
        words = sum(counts.own[j] for j in range(n, stop))
        if node.level == 1:
            close_chapter()
            chapter = dict(title=node.title, tasks=[], words=0)
        elif not chapter["title"]:
            chapter["title"] = node.title
        if words <= 0 or matter(n):
            continue
        start = n
        if carry is not None:                    # a tiny entry before this one joins it
            start, words = carry[0], words + carry[1]
            carry = None
        if words < MIN_UNIT_WORDS and stop < len(nodes):
            carry = (start, words)
            continue
        nxt = nodes[stop] if stop < len(nodes) else None
        end = (nxt.index, 0.0 if roadmap.paged else nxt.ratio) if nxt else None
        first = nodes[start]
        key = _key(READ, node.index, node.fragment, node.title)
        dup = 1
        while key in seen:
            dup += 1
            key = _key(READ, node.index, node.fragment, node.title, dup)
        seen.add(key)
        task = Task(key, READ, node.title, chapter["title"], words,
                    minutes_for(words, settings.wpm, settings.study_factor),
                    first.index, first.fragment, node.level, start, end)
        tasks.append(task)
        chapter["tasks"].append(task)
        chapter["words"] += words
    close_chapter()
    return tasks


# -- days and the no-overlap scheduler ------------------------------------------------------- #

def reading_days(settings: PlanSettings, start: date = None):
    """Reading days from `start` (default: the plan's start), forever."""
    if not settings.weekdays:
        raise ValueError("Choose at least one reading day")
    skip = set(settings.skip_dates or [])
    d = start or settings.start_date()
    for _ in range(MAX_PLAN_DAYS * 2):
        if d.weekday() in settings.weekdays and d.isoformat() not in skip:
            yield d
        d += timedelta(days=1)
    raise ValueError("The plan would run for more than ten years; allow more minutes per day")


def schedule(tasks: list, settings: PlanSettings, start: date = None) -> Schedule:
    """Lay `tasks` end to end into the reading days. Every minute of every day belongs to
    exactly one task; long tasks continue on the next reading day."""
    per_day, min_start = settings.minutes_per_day, min(settings.min_start, settings.minutes_per_day)
    out = Schedule()
    days = reading_days(settings, start)
    day, used = None, per_day          # forces the first day to be taken on the first task
    for t in tasks:
        remaining, first = t.minutes, len(out.blocks)
        while remaining > 0:
            left = per_day - used
            fragment = remaining > left and left < min_start and first == len(out.blocks)
            if left <= 0 or fragment:
                if day is not None and 0 < left:
                    out.leftover[day] = (left, t.label)
                day, used = next(days), 0
                continue
            take = min(remaining, left)
            out.blocks.append(Block(day, t.key, used, take))
            used += take
            remaining -= take
        mine, before = out.blocks[first:], 0
        for i, b in enumerate(mine, 1):
            b.part, b.parts, b.before = i, len(mine), before
            before += b.minutes
    return out


def minutes_needed(tasks: list, settings: PlanSettings, finish: date, start: date = None):
    """Fewest minutes per day that finish all `tasks` by `finish` (None if even the maximum
    is not enough, e.g. there are no reading days before the date)."""
    total = sum(t.minutes for t in tasks)
    if total == 0:
        return settings.minutes_per_day
    trial = PlanSettings(**asdict(settings))
    days = 0
    try:
        for d in reading_days(settings, start):
            if d > finish:
                break
            days += 1
    except ValueError:
        return None
    if days == 0:
        return None
    lo = max(1, -(-total // days))           # can't be fewer than total / days
    for m in range(lo, MAX_MINUTES_PER_DAY + 1):
        trial.minutes_per_day, trial.min_start = m, min(settings.min_start, m)
        sched = schedule(tasks, trial, start)
        if sched.finish is not None and sched.finish <= finish:
            return m
    return None


# -- the plan applied: what to show -------------------------------------------------------- #

def active_tasks(plan: ReadingPlan, tasks: list) -> list:
    """Tasks the current schedule covers: everything not finished before the plan's start
    (work done on or after the start stays in the schedule, ticked off)."""
    start = plan.settings.start
    return [t for t in tasks if not (t.key in plan.done and plan.done[t.key] < start)]


def plan_schedule(plan: ReadingPlan, tasks: list) -> Schedule:
    return schedule(active_tasks(plan, tasks), plan.settings)


@dataclass
class Status:
    total_minutes: int
    done_minutes: int
    due_minutes: int        # what the schedule expected to be done before today
    behind_minutes: int     # unfinished minutes scheduled before today
    today: list             # today's blocks
    overdue: list           # earlier blocks of unfinished tasks
    next_day: object        # next reading day with work (if nothing today)
    finish: object

    @property
    def percent(self) -> int:
        return round(100 * self.done_minutes / self.total_minutes) if self.total_minutes else 100


def status(plan: ReadingPlan, tasks: list, sched: Schedule, today: date = None) -> Status:
    today = today or date.today()
    active = active_tasks(plan, tasks)
    total = sum(t.minutes for t in active)
    done = sum(t.minutes for t in active if t.key in plan.done)
    due = sum(b.minutes for b in sched.blocks if b.day < today)
    overdue = [b for b in sched.blocks if b.day < today and b.key not in plan.done]
    todays = [b for b in sched.blocks if b.day == today]
    nxt = next((b.day for b in sched.blocks if b.day > today and b.key not in plan.done), None)
    behind = sum(b.minutes for b in overdue)
    return Status(total, done, due, behind, todays, overdue, nxt, sched.finish)


def replan(plan: ReadingPlan, today: date = None) -> ReadingPlan:
    """Start the plan again from today with whatever is not done yet."""
    plan.settings.start = (today or date.today()).isoformat()
    return plan


def set_done(plan: ReadingPlan, key: str, on: bool, today: date = None):
    if on:
        plan.done.setdefault(key, (today or date.today()).isoformat())
    else:
        plan.done.pop(key, None)


INTO_NEXT = 0.01   # how far into the next unit you must be (a jump lands exactly on its start)


def auto_complete(plan: ReadingPlan, tasks: list, position: int, ratio: float,
                  progress: float, today: date = None) -> list:
    """Tick off the reading task you have just read past. Returns the keys newly marked done.

    Sequential on purpose: a task counts as read when you are a little way into the *next*
    reading unit. So jumping far ahead never ticks off the chapters you skipped (at most the
    one right before where you are reading), and the plan's own links, which land exactly on
    a unit's start, tick nothing. Called often while you read, so reading on from chapter to
    chapter ticks each one off in turn. Never un-ticks anything.
    """
    newly = []
    here = (position, ratio)
    reads = [t for t in tasks if t.kind == READ]
    for i, t in enumerate(reads):
        if t.key in plan.done:
            continue
        if t.end is None:
            finished = progress >= 0.98
        else:
            past = here >= (t.end[0], t.end[1] + INTO_NEXT)
            nxt = reads[i + 1].end if i + 1 < len(reads) else None
            finished = past and (nxt is None or here < nxt)
        if finished:
            set_done(plan, t.key, True, today)
            newly.append(t.key)
    return newly


def personal_wpm(words_read: int, seconds: float):
    """Your own speed in this book, or None if there is too little history to tell."""
    if seconds < 600 or words_read < 1500:
        return None
    return max(MIN_WPM, min(MAX_WPM, round(words_read / (seconds / 60))))


def block_location(counts, task: Task, block: Block = None):
    """Where a block starts in the book, as (index, ratio) for the reader's
    jump_to_location, or None when the word counts can't tell (older cache)."""
    if not counts.starts or task.node >= len(counts.starts):
        return None
    offset = counts.starts[task.node]
    if block is not None and task.kind == READ and task.minutes:
        offset += task.words * block.before / task.minutes
    return counts.location(offset)


# -- labels -------------------------------------------------------------------------------- #

def fmt_minutes(minutes) -> str:
    """405 -> '6 h 45 min' (as the planner's fmt_length, in minutes)."""
    m = int(round(minutes))
    h, m = divmod(m, 60)
    if h and m:
        return f"{h} h {m} min"
    return f"{h} h" if h else f"{m} min"


def day_label(d: date, today: date = None) -> str:
    today = today or date.today()
    if d == today:
        return "Today"
    if d == today + timedelta(days=1):
        return "Tomorrow"
    if d == today - timedelta(days=1):
        return "Yesterday"
    return f"{d:%a} {d.day} {d:%b}" + (f" {d.year}" if d.year != today.year else "")


def weekdays_label(days) -> str:
    days = sorted(days)
    if days == [0, 1, 2, 3, 4]:
        return "weekdays"
    if days == list(range(7)):
        return "every day"
    if days == [5, 6]:
        return "weekends"
    return ", ".join(WEEKDAY_NAMES[d] for d in days)


def block_title(block: Block, task: Task) -> str:
    if block.parts > 1:
        return f"{task.label}, part {block.part} of {block.parts}"
    return task.label


def summary_line(tasks: list, settings: PlanSettings, sched: Schedule, estimated=False) -> str:
    words = sum(t.words for t in tasks)
    total = sum(t.minutes for t in tasks)
    approx = "≈ " if estimated else ""
    parts = [f"{approx}{words:,} words", f"{fmt_minutes(total)} in total",
             f"{settings.minutes_per_day} min on {weekdays_label(settings.weekdays)}"]
    if sched.finish:
        parts.append(f"{len(sched.days)} reading days, done {sched.finish:%a} "
                     f"{sched.finish.day} {sched.finish:%b %Y}")
    return "  ·  ".join(parts)


# -- export: calendar (.ics) and Markdown --------------------------------------------------- #

def _esc(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,") \
        .replace("\r\n", "\\n").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines over 75 octets continue on the next line after a space."""
    if len(line.encode("utf-8")) <= 75:
        return line
    out, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    out.append(cur.decode("utf-8"))
    return "\r\n ".join(out)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")   # naive dt = local time


def _session_start(d: date, hhmm: str) -> datetime:
    try:
        h, m = (int(x) for x in hhmm.split(":"))
    except (ValueError, AttributeError):
        h, m = 19, 0
    return datetime.combine(d, time(h % 24, m % 60))


def build_ics(book_id, book_title: str, plan: ReadingPlan, tasks: list, sched: Schedule) -> str:
    """One calendar event per block. UIDs are stable, so importing a newer export updates
    the same events in apps that honour UIDs."""
    by_key = {t.key: t for t in tasks}
    now = _utc(datetime.now())
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", f"X-WR-CALNAME:{_esc('Reading: ' + book_title)}"]
    for b in sched.blocks:
        t = by_key.get(b.key)
        if t is None:
            continue
        start = _session_start(b.day, plan.settings.session_time) + timedelta(minutes=b.start_min)
        end = start + timedelta(minutes=b.minutes)
        done = b.key in plan.done
        desc = [f"Book: {book_title}"]
        if t.kind == READ:
            part = round(t.words * b.minutes / max(1, t.minutes))
            desc.append(f"{t.words:,} words" if b.parts == 1
                        else f"About {part:,} of its {t.words:,} words")
        if done:
            desc.append(f"Done on {plan.done[b.key]}")
        lines += [
            "BEGIN:VEVENT",
            f"UID:book{book_id}-{b.key}-{b.part}@book-reader",
            f"DTSTAMP:{now}",
            f"DTSTART:{_utc(start)}",
            f"DTEND:{_utc(end)}",
            f"SUMMARY:{_esc(('✓ ' if done else '📖 ') + block_title(b, t))}",
            f"DESCRIPTION:{_esc(chr(10).join(desc))}",
            "CATEGORIES:Reading",
            "TRANSP:TRANSPARENT" if done else "TRANSP:OPAQUE",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(x) for x in lines) + "\r\n"


def build_markdown(book_title: str, plan: ReadingPlan, tasks: list, sched: Schedule,
                   estimated: bool = False) -> str:
    by_key = {t.key: t for t in tasks}
    s = plan.settings
    active = active_tasks(plan, tasks)
    extras = [f"{mins} min {name}" for name, mins in (("review", s.review_minutes),
                                                     ("mind map", s.mindmap_minutes)) if mins]
    out = [f"# Reading plan: {book_title}", "",
           summary_line(active, s, sched, estimated), "",
           f"Reading speed {s.wpm} wpm, study factor ×{s.study_factor:g}"
           + (f"; per chapter: {' and '.join(extras)}" if extras else "") + ".", ""]
    if estimated:
        out += ["> Word counts are a rough estimate (scanned PDF: pages × average words "
                "per page).", ""]
    for day, blocks in sched.by_day().items():
        out.append(f"## {day:%a} {day.day} {day:%b %Y}")
        out.append("")
        for b in blocks:
            t = by_key[b.key]
            tick = "x" if b.key in plan.done else " "
            words = f" ({t.words:,} words)" if t.kind == READ and b.parts == 1 else ""
            out.append(f"- [{tick}] {block_title(b, t)}{words} — {b.minutes} min")
        if day in sched.leftover:
            left, title = sched.leftover[day]
            out.append(f"- *{left} min left: not enough to start {title}*")
        out.append("")
    return "\n".join(out)

"""Reading goals: daily totals, streaks and the text shown in the library header."""
from datetime import date, timedelta

from book_reader.constants import DEFAULT_DAILY_GOAL_MIN


def daily_minutes(totals: dict, days: int = 30, today: date | None = None) -> list[tuple[date, float]]:
    """Minutes read on each of the last `days` days, oldest first."""
    today = today or date.today()
    out = []
    for k in range(days - 1, -1, -1):
        d = today - timedelta(days=k)
        out.append((d, totals.get(d.isoformat(), 0) / 60))
    return out


def streaks(totals: dict, goal_seconds: float, today: date | None = None) -> tuple[int, int]:
    """(current streak, best streak) in days that met the goal. A streak stays alive
    through today until the day is over, so it counts back from yesterday if today is open."""
    today = today or date.today()
    goal = max(1.0, goal_seconds)

    def met(d: date) -> bool:
        return totals.get(d.isoformat(), 0) >= goal

    day = today if met(today) else today - timedelta(days=1)
    current = 0
    while met(day):
        current += 1
        day -= timedelta(days=1)
    best = run = 0
    prev = None
    for d in sorted(date.fromisoformat(k) for k, v in totals.items() if v >= goal):
        run = run + 1 if prev is not None and (d - prev).days == 1 else 1
        best = max(best, run)
        prev = d
    return current, best


def summary(library, goal_minutes: int | None = None) -> dict:
    """Everything the UI needs about goals in one call."""
    goal_min = int(goal_minutes or DEFAULT_DAILY_GOAL_MIN)
    totals = library.daily_seconds()
    today_s = totals.get(date.today().isoformat(), 0)
    current, best = streaks(totals, goal_min * 60)
    week = daily_minutes(totals, 7)
    return dict(goal_min=goal_min, today_min=today_s / 60, current=current, best=best,
                week_avg=sum(m for _, m in week) / 7, totals=totals)


def header_text(info: dict) -> str:
    bits = []
    if info["current"]:
        bits.append(f"🔥 {info['current']}-day streak")
    bits.append(f"{int(info['today_min'])} / {info['goal_min']} min today")
    return "  ·  ".join(bits)

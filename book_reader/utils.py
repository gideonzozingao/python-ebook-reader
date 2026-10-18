"""Small, Qt-free helpers: durations, relative times, labels, subject cleaning."""
import re
import time

from datetime import datetime
from pathlib import Path


def clean_subjects(items, limit: int = 6) -> list[str]:
    """Split raw metadata strings on ; and , into short, de-duplicated subject names."""
    out, seen = [], set()
    for raw in items:
        for part in re.split(r"[;,]", raw or ""):
            name = " ".join(part.split())[:60]
            if len(name) < 2 or name.lower() in seen:
                continue
            seen.add(name.lower())
            out.append(name)
            if len(out) >= limit:
                return out
    return out


def fmt_duration(sec: float, seconds: bool = False) -> str:
    sec = int(sec or 0)
    if sec < 60:
        return f"{sec}s" if seconds else ("< 1m" if sec else "0m")
    if sec < 3600:
        return f"{sec // 60}m {sec % 60:02d}s" if seconds else f"{sec // 60}m"
    return f"{sec // 3600}h {sec % 3600 // 60:02d}m"


def ago(ts: float) -> str:
    """Human-friendly 'last read' time."""
    if not ts:
        return "never"
    dt = datetime.fromtimestamp(ts)
    secs = time.time() - ts
    days = (datetime.now().date() - dt.date()).days
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{int(secs // 60)} min ago"
    if days == 0:
        return f"today, {dt:%H:%M}"
    if days == 1:
        return f"yesterday, {dt:%H:%M}"
    if days < 7:
        return f"{days} days ago"
    return f"{dt:%b %d, %Y}"


def folder_label(root: Path, file: Path) -> str:
    """Catalogue folder for a book: '<added folder>/<sub folders>' (e.g. Books/Python)."""
    base = root.name or str(root)
    try:
        rel = file.parent.relative_to(root).parts
    except ValueError:
        rel = ()
    return "/".join((base, *rel))


def where_text(row) -> str:
    """Where the reader stopped: 'page 12 of 300' or 'chapter 3 of 20 · 40% through'."""
    n = max(1, row["spine_len"] or 1)
    i = row["spine_index"] or 0
    if row["format"] == "pdf":
        return f"page {i + 1} of {n}"
    word = "section" if row["format"] == "md" else "chapter"
    return f"{word} {i + 1} of {n} · {int((row['scroll_ratio'] or 0) * 100)}% through"


def pretty(text: str) -> str:
    return text.replace("\u2029", "\n")

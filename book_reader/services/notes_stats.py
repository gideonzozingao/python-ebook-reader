"""Numbers for the notes dashboard (no Qt)."""
from collections import Counter
from datetime import date, datetime, timedelta

from book_reader.services.notes_index import all_entries, tag_counts


def dashboard(library, days: int = 30, today: date | None = None) -> dict:
    today = today or date.today()
    entries = all_entries(library)
    per_day: Counter = Counter(datetime.fromtimestamp(e["created"]).date() for e in entries if e["created"])
    series = [(today - timedelta(days=k), per_day.get(today - timedelta(days=k), 0))
              for k in range(days - 1, -1, -1)]
    books: dict = {}
    for e in entries:
        b = books.setdefault(e["book_id"], dict(title=e["book_title"], notes=0, highlights=0, last=0))
        b["notes" if e["kind"] == "note" else "highlights"] += 1
        b["last"] = max(b["last"], e["created"])
    scalar = lambda sql: library.db.execute(sql).fetchone()[0]
    return dict(
        notes=sum(e["kind"] == "note" for e in entries),
        highlights=sum(e["kind"] != "note" for e in entries),
        bookmarks=scalar("SELECT COUNT(*) FROM bookmarks"),
        mindmaps=scalar("SELECT COUNT(*) FROM mindmaps"),
        books_with_notes=len(books),
        last_30=sum(n for _, n in series),
        series=series,
        per_book=sorted(books.values(), key=lambda b: b["notes"] + b["highlights"], reverse=True),
        tags=tag_counts(entries).most_common(12),
        topics=Counter(e["topic"] for e in entries if e["kind"] == "note").most_common(8),
    )

"""One searchable list of every note, highlight and PDF highlight in the library."""
from collections import Counter

from book_reader.services.notes_text import extract_links, extract_tags


def all_entries(library) -> list[dict]:
    """Every note as an entry dict (see SummaryBuilder.entries) plus book_id, book_title,
    fmt and tags. kinds: 'note' (book journal), 'highlight' (EPUB/MD), 'pdf' (PDF highlight)."""
    books = {r["id"]: r for r in library.db.execute("SELECT id, title, format FROM books")}
    out: list[dict] = []

    def add(kind, r, **kw):
        book = books.get(r["book_id"])
        if book is None:
            return
        e = dict(kind=kind, id=r["id"], book_id=r["book_id"], book_title=book["title"],
                 fmt=book["format"] or "epub", quote="", color="", **kw)
        e["tags"] = extract_tags(e["text"])
        out.append(e)

    for r in library.db.execute("SELECT * FROM book_notes"):
        add("note", r, topic=r["topic"] or "General", text=r["body"] or "",
            chapter=r["chapter"] or "", page=r["page"] or 0, total=r["page_total"] or 0,
            index=r["spine_index"] or 0, pos=r["scroll_ratio"] or 0.0,
            created=r["created_at"] or 0)
    for r in library.db.execute("SELECT * FROM notes"):
        add("highlight", r, topic="Highlight", text=r["note"] or "", chapter=f"Section {r['spine_index'] + 1}",
            page=0, total=0, index=r["spine_index"], pos=r["pos_start"] or 0,
            created=r["created_at"] or 0)
        out and out[-1].update(quote=(r["quote"] or "").replace("\u2029", "\n"), color=r["color"] or "")
    for r in library.db.execute("SELECT * FROM pdf_marks"):
        add("pdf", r, topic="Highlight", text=r["note"] or "", chapter=f"Page {r['page'] + 1}",
            page=r["page"] + 1, total=0, index=r["page"], pos=0.0, created=r["created_at"] or 0)
        out and out[-1].update(quote=r["quote"] or "", color=r["color"] or "")
    return out


def search(entries, query: str = "", tag: str = "", kind: str = "", book_id=None) -> list[dict]:
    """Every word of `query` must appear in the note, quote, topic, section or book title."""
    words = query.lower().split()
    tag = tag.lower().lstrip("#")
    result = []
    for e in entries:
        if book_id is not None and e["book_id"] != book_id:
            continue
        if kind and (e["kind"] != kind if kind != "highlight" else e["kind"] == "note"):
            continue
        if tag and tag not in e["tags"]:
            continue
        hay = " ".join((e["text"], e["quote"], e["topic"], e["chapter"], e["book_title"])).lower()
        if all(w in hay for w in words):
            result.append(e)
    return sorted(result, key=lambda e: e["created"], reverse=True)


def tag_counts(entries) -> Counter:
    c: Counter = Counter()
    for e in entries:
        c.update(e["tags"])
    return c


def backlinks(entries, note_id: int) -> list[dict]:
    """Notes that link to `note_id` with [[note:ID]]."""
    return [e for e in entries if e["kind"] == "note" and note_id in extract_links(e["text"])]

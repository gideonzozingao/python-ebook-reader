"""Export notes for other tools: an Obsidian vault, a Notion import, or Anki cards."""
import csv
import io
import re
import zipfile

from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

from book_reader.services import flashcards
from book_reader.services.journal import entry_meta, group_entries
from book_reader.services.notes_index import all_entries
from book_reader.services.notes_text import TAG_RE, convert_links, render_html, to_plain


def safe_name(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|#^\[\]]+', " ", title or "")
    return " ".join(name.split())[:80] or "Untitled"


def book_names(library) -> dict[int, str]:
    """Unique file-name stem per book (same title twice gets ' (2)')."""
    names, used = {}, set()
    for r in library.db.execute("SELECT id, title FROM books ORDER BY id"):
        base = safe_name(r["title"])
        name, n = base, 2
        while name.lower() in used:
            name, n = f"{base} ({n})", n + 1
        used.add(name.lower())
        names[r["id"]] = name
    return names


def books_with_notes(library) -> list[tuple[int, str]]:
    seen: dict = {}
    for e in all_entries(library):
        seen[e["book_id"]] = e["book_title"]
    return sorted(seen.items(), key=lambda kv: kv[1].lower())


def _book_entries(entries, book_id):
    return [e for e in entries if e["book_id"] == book_id]


def book_markdown(library, book_id: int, names: dict, entries=None, flavor: str = "obsidian") -> str:
    """One book's notes as Markdown. obsidian: front matter, ^block ids and [[wiki links]] to
    other notes. notion: plain Markdown (links become text)."""
    entries = entries if entries is not None else all_entries(library)
    mine = _book_entries(entries, book_id)
    row = library.get(book_id)
    where = {e["id"]: e["book_id"] for e in entries if e["kind"] == "note"}

    def resolve(note_id, title):
        title = title or f"note {note_id}"
        if flavor == "obsidian" and note_id in where and where[note_id] in names:
            return f"[[{names[where[note_id]]}#^n{note_id}|{title}]]"
        return f"↗ {title}"

    tags = sorted({t for e in mine for t in e["tags"]})
    lines = []
    if flavor == "obsidian":
        lines += ["---", f"title: \"{(row['title'] or '').replace(chr(34), chr(39))}\"",
                  f"author: \"{(row['author'] or '').replace(chr(34), chr(39))}\"",
                  "tags: [" + ", ".join(["book-notes", *tags]) + "]",
                  f"source: {row['format'] or 'epub'}", f"exported: {datetime.now():%Y-%m-%d}",
                  f"notes: {len(mine)}", "---", ""]
    lines += [f"# {row['title']}", ""]
    if row["author"]:
        lines += [f"*{row['author']}*", ""]
    for gtitle, items in group_entries(mine, "Book section"):
        lines += [f"## {gtitle}", ""]
        for e in items:
            if e["quote"]:
                lines += ["> " + e["quote"].replace("\n", "\n> "), ""]
            if e["text"]:
                lines += [convert_links(e["text"], resolve), ""]
            if flavor == "obsidian" and e["kind"] == "note":
                lines += [f"^n{e['id']}", ""]
            lines += [f"*{entry_meta(e, 'Book section', e['fmt'])}*", ""]
    return "\n".join(lines).rstrip() + "\n"


def export_obsidian(library, book_ids, folder, names=None, entries=None) -> list[Path]:
    """One .md per book into `folder` (open it as a vault, or drop it into one)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    names = names or book_names(library)
    entries = entries if entries is not None else all_entries(library)
    written = []
    for bid in book_ids:
        if bid not in names:
            continue
        path = folder / f"{names[bid]}.md"
        path.write_text(book_markdown(library, bid, names, entries), encoding="utf-8")
        written.append(path)
    return written


def export_notion(library, book_ids, zip_path) -> int:
    """A zip for Notion's Import -> Markdown & CSV: one page per book plus a notes table."""
    names, entries = book_names(library), all_entries(library)
    ids = set(book_ids)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "Book", "Section", "Page", "Type", "Tags", "Created", "Note"])
    count = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for bid in book_ids:
            if bid in names:
                z.writestr(f"{names[bid]}.md", book_markdown(library, bid, names, entries, "notion"))
        for e in sorted((e for e in entries if e["book_id"] in ids), key=lambda e: e["created"]):
            body = to_plain(e["text"] or e["quote"])
            writer.writerow([body[:80], e["book_title"], e["chapter"],
                             e["page"] or "", e["topic"], ", ".join(e["tags"]),
                             datetime.fromtimestamp(e["created"]).strftime("%Y-%m-%d %H:%M"),
                             (e["text"] or e["quote"])])
            count += 1
        z.writestr("notes.csv", "\ufeff" + buf.getvalue())
    return count


def export_anki(library, book_ids, path, mode: str = "basic") -> int:
    """Tab-separated file for Anki's File -> Import. mode: basic (front/back) or cloze."""
    entries = all_entries(library)
    lines = ["#separator:tab", "#html:true", "#deck:Book Reader",
             f"#notetype:{'Cloze' if mode == 'cloze' else 'Basic'}", "#tags column:3"]
    count = 0

    def cell(s: str) -> str:
        return s.replace("\t", " ").replace("\r", "").replace("\n", "")

    def html_of(text: str) -> str:
        """Plain HTML for Anki: no link or style markup, tags stay as text."""
        soup = BeautifulSoup(render_html(text), "html.parser")
        for a in soup.find_all("a"):
            a.unwrap()
        for tag in soup.find_all(True):
            tag.attrs.pop("style", None)
        return str(soup)

    for bid in book_ids:
        mine = _book_entries(entries, bid)
        if not mine:
            continue
        book_tag = re.sub(r"\s+", "_", safe_name(mine[0]["book_title"]))
        for card in flashcards.build_cards(mine, mine[0]["fmt"]):
            entry = next(e for e in mine if f"{e['kind']}:{e['id']}" == card.key)
            tags = " ".join([book_tag, *entry["tags"]])
            if mode == "cloze":
                body = TAG_RE.sub("", card.text)  # never blank out a #tag
                made = flashcards.make_cloze(body)
                if not made:
                    continue
                text = body.replace(made[1], "{{c1::" + made[1] + "}}", 1)
                lines.append("\t".join([cell(html_of(text)), cell(card.ref), tags]))
            else:
                lines.append("\t".join([cell(html_of(card.front)), cell(html_of(card.back)), tags]))
            count += 1
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return count

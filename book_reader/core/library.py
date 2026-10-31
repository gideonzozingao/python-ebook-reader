"""SQLite library storage: books, positions, reading list, sessions, highlights, book journal."""
import hashlib
import json
import shutil
import sqlite3
import time

from pathlib import Path

from book_reader.constants import DATA_DIR
from book_reader.core.books import format_of, open_text_book
from book_reader.core.markdown_book import import_assets
from book_reader.core.metadata import file_subjects
from book_reader.core.pdf import pdf_info
from book_reader.utils import clean_subjects


SCHEMA = """
CREATE TABLE IF NOT EXISTS books(
    id INTEGER PRIMARY KEY, hash TEXT UNIQUE, path TEXT, title TEXT, author TEXT,
    cover TEXT, added_at REAL, last_opened REAL DEFAULT 0,
    spine_index INTEGER DEFAULT 0, scroll_ratio REAL DEFAULT 0,
    progress REAL DEFAULT 0, spine_len INTEGER DEFAULT 1,
    format TEXT DEFAULT 'epub', read_seconds REAL DEFAULT 0,
    reading INTEGER DEFAULT 0, reading_since REAL DEFAULT 0, last_read_at REAL DEFAULT 0,
    last_section TEXT DEFAULT '', folder TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS notes(
    id INTEGER PRIMARY KEY, book_id INTEGER, spine_index INTEGER,
    pos_start INTEGER, pos_end INTEGER, quote TEXT, note TEXT,
    color TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS subjects(
    book_id INTEGER, name TEXT COLLATE NOCASE, UNIQUE(book_id, name));
CREATE TABLE IF NOT EXISTS sessions(
    id INTEGER PRIMARY KEY, book_id INTEGER, started_at REAL, seconds REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS book_notes(
    id INTEGER PRIMARY KEY, book_id INTEGER, topic TEXT DEFAULT 'General', body TEXT,
    chapter TEXT DEFAULT '', spine_index INTEGER DEFAULT 0, scroll_ratio REAL DEFAULT 0,
    page INTEGER DEFAULT 0, page_total INTEGER DEFAULT 0, progress REAL DEFAULT 0,
    created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS book_summaries(
    book_id INTEGER PRIMARY KEY, text TEXT DEFAULT '', updated_at REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS bookmarks(
    id INTEGER PRIMARY KEY, book_id INTEGER, label TEXT DEFAULT '', chapter TEXT DEFAULT '',
    spine_index INTEGER DEFAULT 0, scroll_ratio REAL DEFAULT 0, page INTEGER DEFAULT 0,
    page_total INTEGER DEFAULT 0, created_at REAL);
CREATE TABLE IF NOT EXISTS pdf_marks(
    id INTEGER PRIMARY KEY, book_id INTEGER, page INTEGER, rects TEXT, quote TEXT,
    note TEXT DEFAULT '', color TEXT DEFAULT 'Yellow', created_at REAL);
CREATE TABLE IF NOT EXISTS card_progress(
    book_id INTEGER, key TEXT, box INTEGER DEFAULT 0, due REAL DEFAULT 0,
    PRIMARY KEY(book_id, key));
CREATE TABLE IF NOT EXISTS mindmaps(
    id INTEGER PRIMARY KEY, book_id INTEGER, title TEXT, data TEXT, created_at REAL,
    updated_at REAL);
CREATE TABLE IF NOT EXISTS note_reviews(
    key TEXT PRIMARY KEY, book_id INTEGER, box INTEGER DEFAULT 0, due REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS book_tags(
    book_id INTEGER, name TEXT COLLATE NOCASE, UNIQUE(book_id, name));
CREATE TABLE IF NOT EXISTS book_collections(
    book_id INTEGER, name TEXT COLLATE NOCASE, UNIQUE(book_id, name));
CREATE TABLE IF NOT EXISTS reading_plans(
    book_id INTEGER PRIMARY KEY, data TEXT, updated_at REAL);
"""


class Library:
    def __init__(self):
        self.root = DATA_DIR
        self.books_dir = self.root / "books"
        self.covers_dir = self.root / "covers"
        self._listeners: list = []   # called with a book id whenever its notes change
        self._open()

    def close(self):
        self.db.close()

    def reopen(self):
        """Reconnect after the data folder was replaced (restore from backup)."""
        self._open()

    def _open(self):
        for d in (self.books_dir, self.covers_dir):
            d.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "library.db")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        cols = {r["name"] for r in self.db.execute("PRAGMA table_info(books)")}
        if "format" not in cols:
            self.db.execute("ALTER TABLE books ADD COLUMN format TEXT DEFAULT 'epub'")
        if "read_seconds" not in cols:
            self.db.execute("ALTER TABLE books ADD COLUMN read_seconds REAL DEFAULT 0")
        first_run = "last_read_at" not in cols
        new_catalogue = "folder" not in cols
        for col, ddl in (("reading", "INTEGER DEFAULT 0"), ("reading_since", "REAL DEFAULT 0"),
                         ("last_read_at", "REAL DEFAULT 0"),
                         ("last_section", "TEXT DEFAULT ''"),
                         ("folder", "TEXT DEFAULT ''")):
            if col not in cols:
                self.db.execute(f"ALTER TABLE books ADD COLUMN {col} {ddl}")
        if first_run:  # backfill from existing history
            self.db.execute(
                "UPDATE books SET last_read_at = COALESCE((SELECT MAX(started_at + seconds)"
                " FROM sessions WHERE sessions.book_id=books.id AND seconds>=5), 0)")
            self.db.execute("UPDATE books SET reading=1, reading_since=last_opened"
                            " WHERE progress>0.005 AND progress<0.98")
        self.db.commit()
        if new_catalogue:  # fill subjects for existing books from their metadata
            for r in self.db.execute("SELECT id, path, format FROM books").fetchall():
                self.add_subjects(r["id"], file_subjects(r["path"], r["format"] or "epub"))

    # -- books -------------------------------------------------------------- #

    def add_book(self, src, folder: str = "") -> tuple[str, int | None, str]:
        """Returns (status, book_id, error) with status added|duplicate|error."""
        src = Path(src)
        fmt = format_of(src)
        folder = folder or src.parent.name or str(src.parent)
        try:
            digest = hashlib.sha1(src.read_bytes()).hexdigest()
        except OSError as exc:
            return "error", None, f"{src.name}: {exc}"
        row = self.db.execute("SELECT id FROM books WHERE hash=?", (digest,)).fetchone()
        if row:
            self.db.execute("UPDATE books SET folder=? WHERE id=? AND COALESCE(folder,'')=''",
                            (folder, row["id"]))
            self.db.commit()
            return "duplicate", row["id"], ""

        dest = self.books_dir / f"{digest}.{fmt}"
        try:
            shutil.copyfile(src, dest)
            if fmt == "pdf":
                info = pdf_info(dest)
                title = info["title"]
                if not title or title.lower().startswith(("microsoft word", "untitled")):
                    title = src.stem
                author, spine_len, cover = info["author"], info["pages"], info["cover"]
                subjects = info["subjects"]
            else:
                if fmt == "md":  # keep the images the document refers to
                    import_assets(src, dest.with_suffix(".assets"),
                                  dest.read_text(encoding="utf-8-sig", errors="replace"))
                book = open_text_book(str(dest), fmt, src.stem)
                if not book.spine:
                    book.close()
                    raise ValueError("no readable chapters")
                cover = book.cover_bytes()
                title = book.title if book.title != "Untitled" else src.stem
                author, spine_len = book.author, len(book.spine)
                subjects = clean_subjects(book.subjects)
                book.close()
        except Exception as exc:
            try:
                dest.unlink(missing_ok=True)
                shutil.rmtree(dest.with_suffix(".assets"), ignore_errors=True)
            except OSError:
                pass
            return "error", None, f"{src.name}: {exc}"

        cover_path = ""
        if cover:
            cover_path = str(self.covers_dir / f"{digest}.img")
            Path(cover_path).write_bytes(cover)
        cur = self.db.execute(
            "INSERT INTO books(hash,path,title,author,cover,added_at,spine_len,format,folder)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (digest, str(dest), title, author, cover_path, time.time(), spine_len, fmt, folder),
        )
        self.db.commit()
        self.add_subjects(cur.lastrowid, subjects)
        return "added", cur.lastrowid, ""

    def get(self, book_id):
        return self.db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()

    def count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM books").fetchone()[0]

    def list_books(self, query="", sort="Recently read", field="Title & Author",
                   fmt="All formats", scope="All books"):
        order = {
            "Recently read": "COALESCE(last_read_at,0) DESC, last_opened DESC, added_at DESC",
            "Recently added": "added_at DESC",
            "Title": "title COLLATE NOCASE",
            "Author": "author COLLATE NOCASE, title COLLATE NOCASE",
            "Most read time": "read_seconds DESC, title COLLATE NOCASE",
            "Progress": "progress DESC, title COLLATE NOCASE",
        }.get(sort, "COALESCE(last_read_at,0) DESC, last_opened DESC, added_at DESC")
        where, params = [], []
        if scope == "Reading List":
            where.append("reading=1")
        if query:
            like = f"%{query}%"
            if field == "Title":
                where.append("title LIKE ?")
                params.append(like)
            elif field == "Author":
                where.append("author LIKE ?")
                params.append(like)
            elif field == "Subject":
                where.append("id IN (SELECT book_id FROM subjects WHERE name LIKE ?)")
                params.append(like)
            elif field == "Tag":
                where.append("id IN (SELECT book_id FROM book_tags WHERE name LIKE ?)")
                params.append(like)
            elif field == "Collection":
                where.append("id IN (SELECT book_id FROM book_collections WHERE name LIKE ?)")
                params.append(like)
            else:
                where.append("(title LIKE ? OR author LIKE ?)")
                params += [like, like]
        if fmt in ("EPUB", "PDF", "Markdown"):
            where.append("format=?")
            params.append({"Markdown": "md"}.get(fmt, fmt.lower()))
        sql = "SELECT * FROM books"
        if where:
            sql += " WHERE " + " AND ".join(where)
        return self.db.execute(f"{sql} ORDER BY {order}", params).fetchall()

    def remove_book(self, book_id):
        row = self.get(book_id)
        if not row:
            return
        for p in (row["path"], row["cover"]):
            if p:
                try:
                    Path(p).unlink(missing_ok=True)
                except OSError:
                    pass
        if row["format"] == "md":
            shutil.rmtree(Path(row["path"]).with_suffix(".assets"), ignore_errors=True)
        self.db.execute("DELETE FROM notes WHERE book_id=?", (book_id,))
        self.db.execute("DELETE FROM book_notes WHERE book_id=?", (book_id,))
        self.db.execute("DELETE FROM book_summaries WHERE book_id=?", (book_id,))
        for table in ("bookmarks", "pdf_marks", "card_progress", "book_tags",
                      "book_collections", "mindmaps", "note_reviews", "reading_plans"):
            self.db.execute(f"DELETE FROM {table} WHERE book_id=?", (book_id,))
        self.db.execute("DELETE FROM sessions WHERE book_id=?", (book_id,))
        self.db.execute("DELETE FROM subjects WHERE book_id=?", (book_id,))
        self.db.execute("DELETE FROM books WHERE id=?", (book_id,))
        self.db.commit()

    def touch(self, book_id):
        self.db.execute("UPDATE books SET last_opened=? WHERE id=?", (time.time(), book_id))
        self.db.commit()

    def update_position(self, book_id, spine_index, ratio, progress, section=""):
        # crossing 98% for the first time = finished: leave the reading list
        self.db.execute("UPDATE books SET reading=0 WHERE id=? AND reading=1"
                        " AND COALESCE(progress,0)<0.98 AND ?>=0.98", (book_id, progress))
        self.db.execute(
            "UPDATE books SET spine_index=?, scroll_ratio=?, progress=?, last_section=?"
            " WHERE id=?",
            (spine_index, ratio, progress, section or "", book_id),
        )
        self.db.commit()

    # -- catalogue: subjects and folders ------------------------------------- #

    def subjects_map(self) -> dict:
        out: dict = {}
        for r in self.db.execute("SELECT book_id, name FROM subjects ORDER BY name"):
            out.setdefault(r["book_id"], []).append(r["name"])
        return out

    def all_subjects(self) -> list[str]:
        return [r[0] for r in self.db.execute(
            "SELECT name FROM subjects GROUP BY name ORDER BY name")]

    def add_subjects(self, book_id, names):
        canon = {n.lower(): n for n in self.all_subjects()}
        for raw in names:
            name = " ".join((raw or "").split())[:60]
            if not name:
                continue
            name = canon.get(name.lower(), name)
            canon[name.lower()] = name
            self.db.execute("INSERT OR IGNORE INTO subjects(book_id, name) VALUES(?,?)",
                            (book_id, name))
        self.db.commit()

    def remove_subjects(self, book_id, names):
        for name in names:
            self.db.execute("DELETE FROM subjects WHERE book_id=? AND name=?", (book_id, name))
        self.db.commit()

    def set_folder(self, book_id, label: str):
        self.db.execute("UPDATE books SET folder=? WHERE id=?", (label, book_id))
        self.db.commit()

    # -- reading list ------------------------------------------------------- #

    def set_reading(self, book_id, on: bool):
        """on: add to the reading list. off: remove and stop auto-adding it (-1)."""
        if on:
            self.db.execute("UPDATE books SET reading=1, reading_since=? WHERE id=?",
                            (time.time(), book_id))
        else:
            self.db.execute("UPDATE books SET reading=-1 WHERE id=?", (book_id,))
        self.db.commit()

    def auto_add_reading(self, book_id) -> bool:
        cur = self.db.execute(
            "UPDATE books SET reading=1, reading_since=? WHERE id=?"
            " AND COALESCE(reading,0)=0 AND COALESCE(progress,0)<0.98", (time.time(), book_id))
        self.db.commit()
        return cur.rowcount > 0

    def count_reading(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM books WHERE reading=1").fetchone()[0]

    def continue_book(self):
        row = self.db.execute(
            "SELECT id FROM books WHERE reading=1"
            " ORDER BY COALESCE(last_read_at,0) DESC, last_opened DESC LIMIT 1").fetchone()
        return row["id"] if row else None

    def last_read_book(self):
        """Most recently read, unfinished book (ignoring ones removed from the list)."""
        return self.db.execute(
            "SELECT * FROM books WHERE last_read_at>0 AND COALESCE(progress,0)<0.98"
            " AND COALESCE(reading,0)>=0 ORDER BY last_read_at DESC LIMIT 1").fetchone()

    def reading_list(self, limit=50):
        return self.db.execute(
            "SELECT * FROM books WHERE reading=1"
            " ORDER BY COALESCE(last_read_at,0) DESC, last_opened DESC LIMIT ?",
            (limit,)).fetchall()

    # -- reading time ------------------------------------------------------- #

    def start_session(self, book_id) -> int:
        cur = self.db.execute(
            "INSERT INTO sessions(book_id, started_at, seconds) VALUES(?,?,0)",
            (book_id, time.time()))
        self.db.commit()
        return cur.lastrowid

    def add_time(self, book_id, session_id, delta, session_total):
        self.db.execute("UPDATE books SET read_seconds = COALESCE(read_seconds,0) + ?,"
                        " last_read_at=? WHERE id=?", (delta, time.time(), book_id))
        self.db.execute("UPDATE sessions SET seconds=? WHERE id=?", (session_total, session_id))
        self.db.commit()

    def time_since(self, ts: float) -> float:
        return self.db.execute("SELECT COALESCE(SUM(seconds),0) FROM sessions"
                               " WHERE started_at>=?", (ts,)).fetchone()[0]

    def stats(self):
        return self.db.execute(
            "SELECT b.*, (SELECT COUNT(*) FROM sessions s"
            "             WHERE s.book_id=b.id AND s.seconds>=5) AS n_sessions"
            " FROM books b ORDER BY b.read_seconds DESC").fetchall()

    # -- notes -------------------------------------------------------------- #

    def notes(self, book_id):
        return self.db.execute(
            "SELECT * FROM notes WHERE book_id=? ORDER BY spine_index, pos_start", (book_id,)
        ).fetchall()

    def add_note(self, book_id, spine_index, start, end, quote_text, note, color) -> int:
        cur = self.db.execute(
            "INSERT INTO notes(book_id,spine_index,pos_start,pos_end,quote,note,color,created_at)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (book_id, spine_index, start, end, quote_text, note, color, time.time()),
        )
        self.db.commit()
        self._notes_changed(book_id)
        return cur.lastrowid

    def update_note(self, note_id, note, color):
        self.db.execute("UPDATE notes SET note=?, color=? WHERE id=?", (note, color, note_id))
        self.db.commit()
        self._notes_changed(self._book_of("notes", note_id))

    def delete_note(self, note_id):
        book_id = self._book_of("notes", note_id)
        self.db.execute("DELETE FROM notes WHERE id=?", (note_id,))
        self.db.commit()
        self._notes_changed(book_id)

    # -- book journal (free-form notes, auto-tagged with section + page) ------ #

    def book_notes(self, book_id):
        return self.db.execute(
            "SELECT * FROM book_notes WHERE book_id=?"
            " ORDER BY spine_index, scroll_ratio, created_at", (book_id,)).fetchall()

    def book_note(self, note_id):
        return self.db.execute("SELECT * FROM book_notes WHERE id=?", (note_id,)).fetchone()

    def count_book_notes(self, book_id) -> int:
        return self.db.execute("SELECT COUNT(*) FROM book_notes WHERE book_id=?",
                               (book_id,)).fetchone()[0]

    def book_note_topics(self, book_id) -> list[str]:
        return [r[0] for r in self.db.execute(
            "SELECT topic FROM book_notes WHERE book_id=? GROUP BY LOWER(topic)"
            " ORDER BY LOWER(topic)", (book_id,))]

    def add_book_note(self, book_id, topic, body, loc: dict) -> int:
        now = time.time()
        cur = self.db.execute(
            "INSERT INTO book_notes(book_id,topic,body,chapter,spine_index,scroll_ratio,"
            "page,page_total,progress,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (book_id, topic, body, loc.get("chapter", ""), loc.get("spine_index", 0),
             loc.get("ratio", 0.0), loc.get("page", 0), loc.get("total", 0),
             loc.get("progress", 0.0), now, now))
        self.db.commit()
        self._notes_changed(book_id)
        return cur.lastrowid

    def update_book_note(self, note_id, topic, body, loc: dict | None = None):
        if loc:
            self.db.execute(
                "UPDATE book_notes SET topic=?, body=?, chapter=?, spine_index=?,"
                " scroll_ratio=?, page=?, page_total=?, progress=?, updated_at=? WHERE id=?",
                (topic, body, loc.get("chapter", ""), loc.get("spine_index", 0),
                 loc.get("ratio", 0.0), loc.get("page", 0), loc.get("total", 0),
                 loc.get("progress", 0.0), time.time(), note_id))
        else:
            self.db.execute("UPDATE book_notes SET topic=?, body=?, updated_at=? WHERE id=?",
                            (topic, body, time.time(), note_id))
        self.db.commit()
        self._notes_changed(self._book_of("book_notes", note_id))

    def delete_book_note(self, note_id):
        book_id = self._book_of("book_notes", note_id)
        self.db.execute("DELETE FROM book_notes WHERE id=?", (note_id,))
        self.db.commit()
        self._notes_changed(book_id)

    def get_summary(self, book_id) -> str:
        row = self.db.execute("SELECT text FROM book_summaries WHERE book_id=?",
                              (book_id,)).fetchone()
        return (row["text"] or "") if row else ""

    def set_summary(self, book_id, text: str):
        self.db.execute(
            "INSERT INTO book_summaries(book_id,text,updated_at) VALUES(?,?,?)"
            " ON CONFLICT(book_id) DO UPDATE SET text=excluded.text,"
            " updated_at=excluded.updated_at", (book_id, text, time.time()))
        self.db.commit()

    # -- bookmarks ------------------------------------------------------------ #

    def bookmarks(self, book_id):
        return self.db.execute(
            "SELECT * FROM bookmarks WHERE book_id=? ORDER BY spine_index, scroll_ratio",
            (book_id,)).fetchall()

    def add_bookmark(self, book_id, loc: dict, label: str = "") -> int:
        cur = self.db.execute(
            "INSERT INTO bookmarks(book_id,label,chapter,spine_index,scroll_ratio,page,"
            "page_total,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (book_id, label, loc.get("chapter", ""), loc.get("spine_index", 0),
             loc.get("ratio", 0.0), loc.get("page", 0), loc.get("total", 0), time.time()))
        self.db.commit()
        return cur.lastrowid

    def rename_bookmark(self, bookmark_id, label: str):
        self.db.execute("UPDATE bookmarks SET label=? WHERE id=?", (label, bookmark_id))
        self.db.commit()

    def delete_bookmark(self, bookmark_id):
        self.db.execute("DELETE FROM bookmarks WHERE id=?", (bookmark_id,))
        self.db.commit()

    # -- PDF highlights (rectangles in PDF points, one page each) -------------- #

    def pdf_marks(self, book_id) -> list[dict]:
        """Highlights shaped like EPUB notes so the same panel and summary can use them."""
        out = []
        rows = self.db.execute("SELECT * FROM pdf_marks WHERE book_id=? ORDER BY page, id",
                               (book_id,)).fetchall()
        for r in rows:
            rects = json.loads(r["rects"] or "[]")
            out.append(dict(id=r["id"], spine_index=r["page"], page=r["page"] + 1, rects=rects,
                            quote=r["quote"] or "", note=r["note"] or "",
                            color=r["color"] or "Yellow", created_at=r["created_at"] or 0,
                            pos_start=rects[0][1] if rects else 0))
        return out

    def add_pdf_mark(self, book_id, page, rects, quote, note, color) -> int:
        cur = self.db.execute(
            "INSERT INTO pdf_marks(book_id,page,rects,quote,note,color,created_at)"
            " VALUES(?,?,?,?,?,?,?)",
            (book_id, page, json.dumps(rects), quote, note, color, time.time()))
        self.db.commit()
        self._notes_changed(book_id)
        return cur.lastrowid

    def update_pdf_mark(self, mark_id, note, color):
        self.db.execute("UPDATE pdf_marks SET note=?, color=? WHERE id=?", (note, color, mark_id))
        self.db.commit()
        self._notes_changed(self._book_of("pdf_marks", mark_id))

    def delete_pdf_mark(self, mark_id):
        book_id = self._book_of("pdf_marks", mark_id)
        self.db.execute("DELETE FROM pdf_marks WHERE id=?", (mark_id,))
        self.db.commit()
        self._notes_changed(book_id)

    # -- flashcard progress (Leitner boxes) ------------------------------------ #

    def card_states(self, book_id) -> dict:
        return {r["key"]: (r["box"], r["due"]) for r in self.db.execute(
            "SELECT key, box, due FROM card_progress WHERE book_id=?", (book_id,))}

    def set_card(self, book_id, key, box, due):
        self.db.execute(
            "INSERT INTO card_progress(book_id,key,box,due) VALUES(?,?,?,?)"
            " ON CONFLICT(book_id,key) DO UPDATE SET box=excluded.box, due=excluded.due",
            (book_id, key, box, due))
        self.db.commit()

    # -- tags and collections (free-form labels per book) ---------------------- #

    _LABELS = {"tags": "book_tags", "collections": "book_collections"}

    def labels_map(self, kind: str) -> dict:
        out: dict = {}
        for r in self.db.execute(f"SELECT book_id, name FROM {self._LABELS[kind]} ORDER BY name"):
            out.setdefault(r["book_id"], []).append(r["name"])
        return out

    def all_labels(self, kind: str) -> list[str]:
        return [r[0] for r in self.db.execute(
            f"SELECT name FROM {self._LABELS[kind]} GROUP BY name ORDER BY name")]

    def add_labels(self, kind: str, book_id, names):
        table = self._LABELS[kind]
        canon = {n.lower(): n for n in self.all_labels(kind)}
        for raw in names:
            name = " ".join((raw or "").split())[:60]
            if not name:
                continue
            name = canon.get(name.lower(), name)
            canon[name.lower()] = name
            self.db.execute(f"INSERT OR IGNORE INTO {table}(book_id, name) VALUES(?,?)",
                            (book_id, name))
        self.db.commit()

    def remove_labels(self, kind: str, book_id, names):
        table = self._LABELS[kind]
        for name in names:
            self.db.execute(f"DELETE FROM {table} WHERE book_id=? AND name=?", (book_id, name))
        self.db.commit()

    # -- reading goals -------------------------------------------------------- #

    def daily_seconds(self, days: int = 400) -> dict[str, float]:
        """Seconds read per local calendar day, keyed 'YYYY-MM-DD' (by session start)."""
        rows = self.db.execute(
            "SELECT date(started_at,'unixepoch','localtime') AS d, SUM(seconds) AS s"
            " FROM sessions WHERE started_at>=? GROUP BY d", (time.time() - days * 86400,))
        return {r["d"]: r["s"] or 0 for r in rows}

    def rename_label(self, kind: str, old: str, new: str):
        """Rename a tag/collection; renaming onto an existing name merges the two."""
        table = self._LABELS[kind]
        new = " ".join((new or "").split())[:60]
        if not new:
            return
        if new.lower() == old.lower():  # only the capitalisation changes
            self.db.execute(f"UPDATE {table} SET name=? WHERE name=?", (new, old))
        else:
            self.db.execute(f"INSERT OR IGNORE INTO {table}(book_id, name)"
                            f" SELECT book_id, ? FROM {table} WHERE name=?", (new, old))
            self.db.execute(f"DELETE FROM {table} WHERE name=?", (old,))
        self.db.commit()

    def delete_label(self, kind: str, name: str):
        """Remove a tag/collection from every book (the books themselves stay)."""
        self.db.execute(f"DELETE FROM {self._LABELS[kind]} WHERE name=?", (name,))
        self.db.commit()

    # -- mind maps (one JSON document per map) ---------------------------------- #

    def mindmaps(self, book_id):
        return self.db.execute(
            "SELECT id, title, updated_at FROM mindmaps WHERE book_id=?"
            " ORDER BY updated_at DESC, id DESC", (book_id,)).fetchall()

    def mindmap(self, map_id):
        return self.db.execute("SELECT * FROM mindmaps WHERE id=?", (map_id,)).fetchone()

    def count_mindmaps(self, book_id) -> int:
        return self.db.execute("SELECT COUNT(*) FROM mindmaps WHERE book_id=?",
                               (book_id,)).fetchone()[0]

    def add_mindmap(self, book_id, title: str, data: str) -> int:
        now = time.time()
        cur = self.db.execute(
            "INSERT INTO mindmaps(book_id,title,data,created_at,updated_at) VALUES(?,?,?,?,?)",
            (book_id, title, data, now, now))
        self.db.commit()
        return cur.lastrowid

    def save_mindmap(self, map_id, data: str):
        self.db.execute("UPDATE mindmaps SET data=?, updated_at=? WHERE id=?",
                        (data, time.time(), map_id))
        self.db.commit()

    def rename_mindmap(self, map_id, title: str):
        self.db.execute("UPDATE mindmaps SET title=? WHERE id=?", (title, map_id))
        self.db.commit()

    def delete_mindmap(self, map_id):
        self.db.execute("DELETE FROM mindmaps WHERE id=?", (map_id,))
        self.db.commit()

    # -- reading plans (one JSON document per book) ------------------------------ #

    def get_plan(self, book_id) -> str | None:
        row = self.db.execute("SELECT data FROM reading_plans WHERE book_id=?",
                              (book_id,)).fetchone()
        return row["data"] if row else None

    def save_plan(self, book_id, data: str):
        self.db.execute(
            "INSERT INTO reading_plans(book_id,data,updated_at) VALUES(?,?,?)"
            " ON CONFLICT(book_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
            (book_id, data, time.time()))
        self.db.commit()

    def delete_plan(self, book_id):
        self.db.execute("DELETE FROM reading_plans WHERE book_id=?", (book_id,))
        self.db.commit()

    def planned_books(self) -> list:
        return [r["book_id"] for r in self.db.execute("SELECT book_id FROM reading_plans")]

    # -- change notifications (used by the notes sync folder) -------------------- #

    def add_listener(self, fn):
        self._listeners.append(fn)

    def _book_of(self, table: str, row_id) -> int | None:
        row = self.db.execute(f"SELECT book_id FROM {table} WHERE id=?", (row_id,)).fetchone()
        return row["book_id"] if row else None

    def _notes_changed(self, book_id):
        if book_id is None:
            return
        for fn in list(self._listeners):
            try:
                fn(book_id)
            except Exception:  # a failing listener must never break saving a note
                pass

    # -- note review inbox (spaced resurfacing) ----------------------------------- #

    def review_states(self) -> dict:
        return {r["key"]: (r["box"], r["due"]) for r in self.db.execute(
            "SELECT key, box, due FROM note_reviews")}

    def set_review(self, key: str, book_id, box: int, due: float):
        self.db.execute(
            "INSERT INTO note_reviews(key,book_id,box,due) VALUES(?,?,?,?)"
            " ON CONFLICT(key) DO UPDATE SET box=excluded.box, due=excluded.due",
            (key, book_id, box, due))
        self.db.commit()

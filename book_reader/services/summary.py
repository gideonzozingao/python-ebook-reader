"""SummaryBuilder: renders journal notes + highlights as Markdown, text, HTML or rich text."""
from datetime import datetime
from html import escape as esc

from book_reader.core.library import Library
from book_reader.services.journal import entry_meta, group_entries, note_entry, topic_color
from book_reader.themes import HIGHLIGHT_COLORS, THEMES
from book_reader.utils import fmt_duration, pretty


def _br(text: str) -> str:
    return esc(text).replace("\n", "<br>")


class SummaryBuilder:
    """Collects a book's journal notes (+ EPUB highlights) and renders them as a summary
    document: Markdown ('md'), plain text ('txt'), standalone web page ('html') or rich
    text for the preview and PDF ('rich')."""

    def __init__(self, library: Library, book_id: int, highlights=None, chapter_label=None):
        self.library, self.book_id = library, book_id
        self._highlights = highlights or (lambda: [])
        self._chapter = chapter_label or (lambda i: "")
        row = library.get(book_id)
        self.title = row["title"] if row else "Book"
        self.fmt = (row["format"] or "epub") if row else "epub"

    def topics(self) -> list[str]:
        out = list(self.library.book_note_topics(self.book_id))
        if self._highlights():
            out.append("Highlight")
        return out

    def has_highlights(self) -> bool:
        return bool(self._highlights())

    def entries(self, topic="", notes=True, highlights=True) -> list[dict]:
        out = []
        if notes:
            for n in self.library.book_notes(self.book_id):
                if topic and (n["topic"] or "").lower() != topic.lower():
                    continue
                out.append(note_entry(n))
        if highlights and (not topic or topic.lower() == "highlight"):
            for h in self._highlights():
                if not h["quote"] and not h["note"]:
                    continue
                out.append(dict(
                    kind="highlight", id=h["id"], topic="Highlight", text=h["note"] or "",
                    quote=pretty(h["quote"] or ""), chapter=self._chapter(h["spine_index"]),
                    page=h.get("page", 0), total=h.get("total", 0), index=h["spine_index"],
                    pos=h["pos_start"],
                    created=h["created_at"] or 0, color=h["color"]))
        return out

    def _stats(self, ents) -> str:
        row = self.library.get(self.book_id)
        n_notes = sum(e["kind"] == "note" for e in ents)
        n_hl = sum(e["kind"] == "highlight" for e in ents)
        bits = [f"{n_notes} note{'' if n_notes == 1 else 's'}"]
        if self.fmt != "pdf":
            bits.append(f"{n_hl} highlight{'' if n_hl == 1 else 's'}")
        if row:
            bits.append(f"{(row['progress'] or 0) * 100:.0f}% read")
            if row["read_seconds"]:
                bits.append(f"{fmt_duration(row['read_seconds'])} reading time")
        return "  ·  ".join(bits)

    def render(self, kind, mode="Book section", topic="", notes=True, highlights=True,
               theme=None) -> str:
        row = self.library.get(self.book_id)
        author = (row["author"] or "") if row else ""
        ents = self.entries(topic, notes, highlights)
        groups = group_entries(ents, mode)
        summary = self.library.get_summary(self.book_id).strip()
        stats = self._stats(ents)
        args = (self.title, author, stats, summary, groups, mode)
        if kind == "md":
            return self._md(*args)
        if kind == "txt":
            return self._txt(*args)
        return self._html(*args, theme or THEMES["Light"], web=(kind == "html"))

    # -- renderers --------------------------------------------------------------- #

    def _md(self, title, author, stats, summary, groups, mode) -> str:
        lines = [f"# {title}", ""]
        if author:
            lines += [f"*{author}*", ""]
        lines += [f"> {stats}", "", f"_Notes exported {datetime.now():%Y-%m-%d %H:%M}_", ""]
        if summary:
            lines += ["## My summary", "", summary, ""]
        if not groups:
            lines += ["_No notes yet._", ""]
        for gtitle, items in groups:
            lines += [f"## {gtitle}", ""]
            for e in items:
                if e["quote"]:
                    lines += ["> " + e["quote"].replace("\n", "\n> "), ""]
                if e["text"]:
                    lines += [e["text"], ""]
                lines += [f"*{entry_meta(e, mode, self.fmt)}*", ""]
        return "\n".join(lines)

    def _txt(self, title, author, stats, summary, groups, mode) -> str:
        lines = [title.upper()]
        if author:
            lines.append(author)
        lines += [stats, f"Notes exported {datetime.now():%Y-%m-%d %H:%M}", ""]
        if summary:
            lines += ["MY SUMMARY", "-" * 10, summary, ""]
        if not groups:
            lines.append("No notes yet.")
        for gtitle, items in groups:
            lines += [gtitle.upper(), "=" * min(len(gtitle), 72), ""]
            for e in items:
                lines.append(f"[{entry_meta(e, mode, self.fmt)}]")
                if e["quote"]:
                    lines += ["  “" + e["quote"].replace("\n", "\n  ") + "”"]
                if e["text"]:
                    lines += ["  " + e["text"].replace("\n", "\n  ")]
                lines.append("")
        return "\n".join(lines)

    def _html(self, title, author, stats, summary, groups, mode, t, web) -> str:
        fg, muted, border, bg = t["fg"], t["muted"], t["border"], t["bg"]
        body = [f'<h1 style="margin-bottom:2px">{esc(title)}</h1>']
        if author:
            body.append(f'<p style="color:{muted}; margin-top:0">{esc(author)}</p>')
        body.append(f'<p style="color:{muted}">{esc(stats)}</p>')
        if summary:
            body.append(f"<h2>My summary</h2><p>{_br(summary)}</p>")
        if not groups:
            body.append(f'<p style="color:{muted}"><i>No notes yet.</i></p>')
        for gtitle, items in groups:
            body.append(f'<h2 style="margin-top:22px">{esc(gtitle)}</h2>')
            for e in items:
                color = (HIGHLIGHT_COLORS.get(e["color"], "#ffd54f") if e["kind"] == "highlight"
                         else topic_color(e["topic"]))
                inner = []
                if e["quote"]:
                    inner.append(f'<p style="margin:0 0 6px 0"><i>“{_br(e["quote"])}”</i></p>')
                if e["text"]:
                    inner.append(f'<p style="margin:0 0 6px 0">{_br(e["text"])}</p>')
                meta = esc(entry_meta(e, mode, self.fmt))
                inner.append(f'<p style="margin:0; color:{muted}; font-size:9pt">{meta}</p>')
                cell = "".join(inner)
                body.append(
                    '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
                    f'<td width="5" bgcolor="{color}"></td>'
                    f'<td style="padding-left:12px">{cell}</td></tr></table>'
                    '<p style="margin:0; font-size:4pt">&nbsp;</p>')
        content = "".join(body)
        if web:
            css = (f"body {{ font-family: Georgia, 'Times New Roman', serif; color:{fg};"
                   f" background:{bg}; max-width:780px; margin:36px auto; padding:0 20px;"
                   f" line-height:1.55; }}"
                   f" h2 {{ border-bottom:1px solid {border}; padding-bottom:4px; }}")
            return ("<!DOCTYPE html><html><head><meta charset='utf-8'>"
                    f"<title>{esc(title)} — notes</title><style>{css}</style></head>"
                    f"<body>{content}</body></html>")
        return (f'<html><body style="font-family:Georgia,serif; color:{fg}">'
                f"{content}</body></html>")


def stored_highlights(library, book_id) -> list[dict]:
    """Highlights of a book that is not open (EPUB notes or PDF marks)."""
    row = library.get(book_id)
    if row is not None and row["format"] == "pdf":
        return library.pdf_marks(book_id)
    return [dict(r) for r in library.notes(book_id)]

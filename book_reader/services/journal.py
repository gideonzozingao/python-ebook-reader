"""Journal data helpers: location references, entry normalisation, grouping, captions."""
import colorsys
import zlib

from collections import OrderedDict
from datetime import datetime


def topic_color(topic: str) -> str:
    """Stable accent colour (hex) for a journal section name."""
    hue = zlib.crc32((topic or "").lower().encode()) % 360 / 360
    r, g, b = colorsys.hsv_to_rgb(hue, 130 / 255, 205 / 255)
    return "#{:02x}{:02x}{:02x}".format(round(r * 255), round(g * 255), round(b * 255))


def page_text(page, total, fmt) -> str:
    """'p. 12 of 300' for PDFs, '≈ p. 42 of 310' for EPUBs (estimated pages)."""
    if not page:
        return ""
    text = f"{'p.' if fmt == 'pdf' else '≈ p.'} {page}"
    return f"{text} of {total}" if total else text


def ref_text(chapter, page, total, fmt) -> str:
    """Where a note was taken: section/chapter plus page."""
    parts = [(chapter or "").strip(), page_text(page, total, fmt)]
    return "  ·  ".join(p for p in parts if p)


def note_entry(row) -> dict:
    """Normalise a book_notes row into the entry dict used by panel and summary."""
    return dict(kind="note", id=row["id"], topic=row["topic"] or "General",
                text=row["body"] or "", quote="", chapter=row["chapter"] or "",
                page=row["page"] or 0, total=row["page_total"] or 0,
                index=row["spine_index"] or 0, pos=row["scroll_ratio"] or 0.0,
                created=row["created_at"] or 0, color="")


def group_entries(entries: list[dict], mode: str) -> list[tuple[str, list[dict]]]:
    """Group entries by book section (in reading order), topic, or date (newest first)."""
    def order(e):
        return (e["index"], 0 if e["kind"] == "highlight" else 1, e["pos"], e["created"])

    if mode == "Date":
        buckets: dict = {}
        for e in sorted(entries, key=lambda e: e["created"]):
            buckets.setdefault(datetime.fromtimestamp(e["created"]).date(), []).append(e)
        return [(f"{d:%A, %d %B %Y}", items) for d, items in sorted(buckets.items(),
                                                                   reverse=True)]
    groups: OrderedDict = OrderedDict()
    if mode == "Topic":
        for e in sorted(entries, key=lambda e: (e["topic"].lower(),) + order(e)):
            groups.setdefault(e["topic"].lower(), (e["topic"], []))[1].append(e)
    else:
        for e in sorted(entries, key=order):
            key = e["chapter"] or "(Untitled section)"
            groups.setdefault(key, (key, []))[1].append(e)
    return list(groups.values())


def entry_meta(e: dict, mode: str, fmt: str, topic: bool = True) -> str:
    """Small caption under an entry: topic, section/page reference and date."""
    page = page_text(e["page"], e["total"], fmt)
    full = ref_text(e["chapter"], e["page"], e["total"], fmt)
    when = datetime.fromtimestamp(e["created"])
    if mode == "Topic":
        parts = [full, f"{when:%b %d, %Y}"]
    elif mode == "Date":
        parts = [e["topic"] if topic else "", full, f"{when:%H:%M}"]
    else:
        parts = [e["topic"] if topic else "", page, f"{when:%b %d, %Y}"]
    return "  ·  ".join(p for p in parts if p)

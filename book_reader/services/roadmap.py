"""Book roadmap: an ordered outline of a book (chapters and sub-sections) with the location
of every entry, page ranges, and a small on-disk cache.

Qt-free. `generate_roadmap` opens its own copy of the book, so it is safe to run in a
background thread while the reader keeps using its own copy.

Where the outline comes from, best source first:
  "toc"       the book's own table of contents (EPUB nav/NCX, Markdown headings, PDF outline)
  "headings"  no usable TOC: scan chapter headings (EPUB/Markdown) or detect large text (PDF)
  "pages"     nothing found (e.g. a scanned PDF): split the book into page ranges
"""
import json
import re

from bs4 import BeautifulSoup
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

from book_reader.constants import DATA_DIR
from book_reader.core.books import open_text_book
from book_reader.core.pdf import fitz


CACHE_VERSION = 2
MAX_TITLE = 120
MAX_HEADINGS = 400
_GENERIC = re.compile(r"Section \d+")   # titles EpubBook invents when a book has no TOC


# -- model ---------------------------------------------------------------------------- #

@dataclass
class RoadmapNode:
    title: str
    level: int            # 1 = chapter, 2 = section, ...
    index: int            # EPUB/Markdown: spine index.  PDF: 0-based page.
    fragment: str = ""    # heading anchor inside the chapter (EPUB/Markdown only)
    page: int = 1         # first page, 1-based (estimated for EPUB/Markdown)
    end_page: int = 1     # last page of this entry, including its sub-sections
    ratio: float = 0.0    # how far into its chapter the heading sits, 0..1 (EPUB/Markdown)


@dataclass
class Roadmap:
    title: str
    fmt: str              # "pdf", "epub" or "md"
    total_pages: int
    source: str           # "toc", "headings" or "pages"
    nodes: list = field(default_factory=list)

    @property
    def paged(self) -> bool:
        return self.fmt == "pdf"

    def current_node(self, position: int, ratio: float = 0.0):
        """Number of the entry the reader is in, or None before the first entry.

        `position` is the spine index (EPUB/Markdown) or 0-based page (PDF); `ratio` is the
        scroll position inside that chapter (ignored for PDFs). Of the entries that have
        already started, the latest one wins."""
        reach = (position, 0.0 if self.paged else ratio + 0.02)   # small tolerance
        best, best_key = None, None
        for n, node in enumerate(self.nodes):
            key = (node.index, node.ratio)
            if key <= reach and (best_key is None or key >= best_key):
                best, best_key = n, key
        return best

    def ancestors(self, n: int) -> set:
        """Numbers of the entries that contain node `n` (its chapter, section, ...)."""
        out, level = set(), self.nodes[n].level
        for j in range(n - 1, -1, -1):
            if self.nodes[j].level < level:
                out.add(j)
                level = self.nodes[j].level
        return out

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Roadmap":
        return cls(d["title"], d["fmt"], d["total_pages"], d["source"],
                   [RoadmapNode(**n) for n in d["nodes"]])


def _finish(nodes: list, total_pages: int) -> list:
    """Tidy the levels (no jumps deeper than one step) and fill in each entry's last page."""
    prev = 0
    for n in nodes:
        n.level = max(1, min(n.level, prev + 1))
        prev = n.level
        n.page = max(1, min(n.page, total_pages))
    for i, n in enumerate(nodes):
        n.end_page = total_pages
        for j in range(i + 1, len(nodes)):
            if nodes[j].level <= n.level:      # next entry at the same or a higher level
                n.end_page = max(n.page, nodes[j].page - 1)
                break
    return nodes


# -- EPUB / Markdown -------------------------------------------------------------------- #

def _scan_headings(book, max_level: int = 3) -> list:
    """[level, title, spine index, anchor] for every h1..h3 in the book."""
    pattern = re.compile(rf"^h[1-{max_level}]$")
    out = []
    for i, path in enumerate(book.spine):
        try:
            soup = BeautifulSoup(book.render_chapter(path), "html.parser")
        except Exception:
            continue
        for h in soup.find_all(pattern):
            title = h.get_text(" ", strip=True)
            if title:
                out.append([int(h.name[1]), title[:MAX_TITLE], i, h.get("id") or ""])
    return out


def _fragment_ratio(book, idx: int, fragment: str, memo: dict) -> float:
    """How far into chapter `idx` (0..1) a heading anchor sits, so sections that share a
    chapter get different page estimates. `memo` keeps the last rendered chapter."""
    if not fragment:
        return 0.0
    if memo.get("idx") != idx:
        try:
            memo["idx"], memo["html"] = idx, book.render_chapter(book.spine[idx])
        except Exception:
            memo["idx"], memo["html"] = idx, ""
    html = memo["html"]
    start = html.find("<body>") + len("<body>") if "<body>" in html else 0   # skip the wrapper
    end = html.rfind("</body>") if "</body>" in html else len(html)
    at = html.find(f'name="{fragment}"')
    at = html.rfind("<", 0, at) if at >= 0 else -1        # start of the <a name=...> tag
    if at < start or end <= start:
        return 0.0
    return min(1.0, (at - start) / (end - start))


def _text_roadmap(book, fmt: str) -> Roadmap:
    spine_pos = {p: i for i, p in enumerate(book.spine)}
    flat: list = []

    def walk(entries, level):
        for e in entries:
            title = (e.title or "").strip()[:MAX_TITLE] or "(untitled)"
            flat.append([level, title, spine_pos.get(e.path) if e.path else None,
                         e.fragment or ""])
            walk(e.children, level + 1)

    walk(book.toc, 1)
    source = "toc"
    if flat and all(_GENERIC.fullmatch(r[1]) for r in flat):   # no real TOC in the file
        scanned = _scan_headings(book)
        if scanned:
            flat, source = scanned, "headings"

    # entries that only group others (no location of their own) point at their first child
    ahead = None
    for r in reversed(flat):
        if r[2] is None:
            if ahead:
                r[2], r[3] = ahead
        else:
            ahead = (r[2], r[3])

    nodes: list[RoadmapNode] = []
    memo: dict = {}
    for level, title, idx, frag in flat:
        if idx is None:
            continue
        if nodes and (nodes[-1].title, nodes[-1].index, nodes[-1].fragment) == (title, idx, frag):
            continue
        ratio = _fragment_ratio(book, idx, frag, memo)
        nodes.append(RoadmapNode(title, level, idx, frag, book.est_page(idx, ratio)[0],
                                 ratio=ratio))
    if not nodes:
        nodes = [RoadmapNode(f"Section {i + 1}", 1, i, "", book.est_page(i, 0.0)[0])
                 for i in range(len(book.spine))]
    total = book.est_page(0, 0.0)[1]
    return Roadmap(book.title, fmt, total, source, _finish(nodes, total))


# -- PDF ---------------------------------------------------------------------------------- #

def _page_blocks(page) -> list:
    flags = fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_MEDIABOX_CLIP
    return [b for b in page.get_text("dict", flags=flags)["blocks"] if b.get("type") == 0]


def _block_headings(block, page_height: float, min_size: float) -> list:
    """(text, size) for each run of large lines in a text block (a heading can wrap)."""
    out, run, run_size = [], [], 0.0

    def flush():
        nonlocal run, run_size
        if run:
            out.append((" ".join(run), run_size))
        run, run_size = [], 0.0

    for line in block["lines"]:
        spans = [s for s in line["spans"] if s["text"].strip()]
        if not spans:
            continue
        size = round(max(s["size"] for s in spans) * 2) / 2
        text = " ".join("".join(s["text"] for s in spans).split())
        top, bottom = line["bbox"][1], line["bbox"][3]
        in_margin = top < page_height * 0.06 or bottom > page_height * 0.94  # running heads
        if size >= min_size and not in_margin and any(c.isalpha() for c in text):
            if run and size != run_size:
                flush()
            run.append(text)
            run_size = size
        else:
            flush()
    flush()
    return out


def _pdf_headings(doc, max_pages: int = 800) -> list:
    """Headings of a PDF without an outline: text clearly larger than the body text."""
    total = min(doc.page_count, max_pages)
    step = max(1, total // 60)
    sizes = Counter()                        # which font size is the body text?
    for i in range(0, total, step):
        for block in _page_blocks(doc[i]):
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if text:
                        sizes[round(span["size"] * 2) / 2] += len(text)
    if not sizes:
        return []                            # no text layer (scanned PDF)
    body = sizes.most_common(1)[0][0]
    min_size = max(body * 1.2, body + 1.5)

    found = []                               # (page, text, size)
    for i in range(total):
        page = doc[i]
        for block in _page_blocks(page):
            for text, size in _block_headings(block, page.rect.height, min_size):
                if 2 <= len(text) <= 100:
                    found.append((i, text, size))

    repeats = Counter(t.lower() for _, t, _ in found)       # drop running titles
    found = [f for f in found if repeats[f[1].lower()] <= 3]
    size_count = Counter(s for _, _, s in found)
    common = {s for s, c in size_count.items() if c >= 2}   # a lone huge size = cover title
    if common:
        found = [f for f in found if f[2] in common]
    ranks = {s: min(r + 1, 3) for r, s in enumerate(sorted({f[2] for f in found}, reverse=True))}
    nodes = [RoadmapNode(t, ranks[s], p, "", p + 1) for p, t, s in found]
    if len(nodes) > MAX_HEADINGS:
        nodes = [n for n in nodes if n.level <= 2][:MAX_HEADINGS]
    return nodes


def _page_chunks(total: int) -> list:
    size = max(10, -(-total // 12))
    return [RoadmapNode(f"Pages {s + 1}–{min(total, s + size)}", 1, s, "", s + 1)
            for s in range(0, total, size)]


def _pdf_roadmap(path: str, title_hint: str) -> Roadmap:
    if fitz is None:
        raise RuntimeError("PDF support needs PyMuPDF:  pip install pymupdf")
    doc = fitz.open(str(path))
    try:
        total = doc.page_count
        try:
            entries = doc.get_toc(simple=True)
        except Exception:
            entries = []
        nodes: list[RoadmapNode] = []
        source, last = "toc", 0
        for level, title, page in entries:
            p = int(page) - 1
            p = last if p < 0 else min(p, total - 1)      # -1 = unresolved destination
            last = p
            nodes.append(RoadmapNode((title or "").strip()[:MAX_TITLE] or "(untitled)",
                                     max(1, int(level)), p, "", p + 1))
        if not nodes:
            nodes, source = _pdf_headings(doc), "headings"
        if not nodes:
            nodes, source = _page_chunks(total), "pages"
        title = ((doc.metadata or {}).get("title") or "").strip() or title_hint or "PDF"
        return Roadmap(title, "pdf", total, source, _finish(nodes, total))
    finally:
        doc.close()


# -- public API --------------------------------------------------------------------------- #

def generate_roadmap(path: str, fmt: str, title_hint: str = "") -> Roadmap:
    """Build the roadmap of the book at `path` (fmt: 'pdf', 'epub' or 'md')."""
    if fmt == "pdf":
        return _pdf_roadmap(path, title_hint)
    book = open_text_book(path, fmt, title_hint)
    try:
        return _text_roadmap(book, fmt)
    finally:
        book.close()


# -- cache (one small JSON file per book, invalidated when the book file changes) ---------- #

def _cache_file(book_id: int) -> Path:
    return DATA_DIR / "roadmaps" / f"{int(book_id)}.json"


def _stamp(path: str) -> dict:
    st = Path(path).stat()
    return {"v": CACHE_VERSION, "size": st.st_size, "mtime": int(st.st_mtime)}


def load_cached(book_id: int, path: str):
    try:
        data = json.loads(_cache_file(book_id).read_text(encoding="utf-8"))
        if data.get("stamp") != _stamp(path):
            return None
        return Roadmap.from_dict(data["roadmap"])
    except Exception:
        return None


def save_cached(book_id: int, path: str, roadmap: Roadmap):
    try:
        f = _cache_file(book_id)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"stamp": _stamp(path), "roadmap": roadmap.to_dict()}),
                     encoding="utf-8")
    except Exception:
        pass   # the cache is only an optimisation

"""Word counts for a book's roadmap entries, used by the reading plan.

Qt-free and safe to run in a background thread (it opens its own copy of the book).

Every roadmap entry gets the words of its *own* text: from where it starts to where the next
entry (at any level) starts. A chapter's full length is its own text plus its sections'.
That way nothing is counted twice and the parts always add up to the book.

  EPUB / Markdown  words per chapter file; sections split at the heading anchors the roadmap
                   already found (falling back to the roadmap's position estimate).
  PDF              words per page, summed over each entry's page range.
  scanned PDF      no text layer: pages x AVG_WORDS_PER_PAGE, flagged as a rough estimate.
"""
import hashlib
import json
import re

from bs4 import BeautifulSoup, Comment, NavigableString
from dataclasses import asdict, dataclass, field
from pathlib import Path

from book_reader.constants import DATA_DIR
from book_reader.core.books import open_text_book
from book_reader.core.pdf import fitz


CACHE_VERSION = 2
AVG_WORDS_PER_PAGE = 300        # printed non-fiction page; only used for scanned PDFs
MIN_TEXT_WORDS = 20             # a PDF page with fewer words than this has "no text"
SCANNED_SHARE = 0.10            # under 10 % of pages with text -> treat the PDF as scanned

# One CJK character counts as a word (they are written without spaces); everything else is
# a run of letters/digits, with inner apostrophes kept ("don't" is one word).
_WORD = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]|[^\W_]+(?:['’][^\W_]+)*")
_SKIP = {"script", "style", "title", "head"}


def count_words(text: str) -> int:
    return len(_WORD.findall(text or ""))


@dataclass
class WordCounts:
    own: list = field(default_factory=list)   # words of each roadmap entry's own text
    total: int = 0                            # words in the whole book
    before_first: int = 0                     # front matter before the first entry (not planned)
    estimated: bool = False                   # True for scanned PDFs (pages x average)
    signature: str = ""                       # which roadmap these numbers belong to
    units: list = field(default_factory=list)   # words per chapter file (EPUB/MD) or page (PDF)
    starts: list = field(default_factory=list)  # where each entry starts, in words into the book

    def location(self, offset: float) -> tuple:
        """(spine index or 0-based page, ratio inside it) for a point `offset` words into the
        book: how the plan opens "part 2" of a chapter where part 2 actually begins."""
        if not self.units:
            return 0, 0.0
        offset = max(0.0, offset)
        acc = 0
        for i, n in enumerate(self.units):
            if n > 0 and offset < acc + n:
                return i, max(0.0, min(0.999, (offset - acc) / n))
            acc += n
        return len(self.units) - 1, 0.999

    def subtree(self, roadmap, n: int) -> int:
        """Words of entry `n` including all of its sub-sections."""
        level, words = roadmap.nodes[n].level, self.own[n]
        for j in range(n + 1, len(roadmap.nodes)):
            if roadmap.nodes[j].level <= level:
                break
            words += self.own[j]
        return words


def roadmap_signature(roadmap) -> str:
    raw = json.dumps([(n.title, n.level, n.index, n.fragment) for n in roadmap.nodes])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _split(starts: list, total: int) -> tuple[list, int]:
    """`starts[i]` is where entry i begins, in words from the start of the book. Each entry
    owns the words up to the next later start; entries that begin at the same spot give
    everything to the last of them (usually a chapter and its first section)."""
    order = sorted(range(len(starts)), key=lambda i: (starts[i], i))
    own = [0] * len(starts)
    for k, i in enumerate(order):
        end = starts[order[k + 1]] if k + 1 < len(order) else total
        own[i] = max(0, end - starts[i])
    return own, (min(starts) if starts else total)


# -- EPUB / Markdown ------------------------------------------------------------------ #

def _chapter_words(html: str, wanted: set) -> tuple[int, dict]:
    """(words in the chapter, {anchor name: words before it}) in one pass over the HTML."""
    soup = BeautifulSoup(html, "html.parser")
    count, offsets = 0, {}
    for el in soup.descendants:
        if isinstance(el, NavigableString):
            if isinstance(el, Comment) or (el.parent is not None and el.parent.name in _SKIP):
                continue
            count += count_words(str(el))
        elif el.name == "a" and el.get("name") in wanted and el["name"] not in offsets:
            offsets[el["name"]] = count
    return count, offsets


def _text_counts(path: str, fmt: str, title_hint: str, roadmap, report=None) -> WordCounts:
    book = open_text_book(path, fmt, title_hint)
    try:
        wanted: dict[int, set] = {}
        for node in roadmap.nodes:
            if node.fragment:
                wanted.setdefault(node.index, set()).add(node.fragment)
        sizes, offsets = [], []
        n = len(book.spine)
        for i, item in enumerate(book.spine):
            try:
                words, offs = _chapter_words(book.render_chapter(item), wanted.get(i, set()))
            except Exception:
                words, offs = 0, {}
            sizes.append(words)
            offsets.append(offs)
            if report:
                report(i + 1, n)
    finally:
        book.close()
    prefix = [0]
    for s in sizes:
        prefix.append(prefix[-1] + s)
    starts = []
    for node in roadmap.nodes:
        i = max(0, min(node.index, len(sizes) - 1)) if sizes else 0
        inside = 0
        if sizes and node.fragment:
            inside = offsets[i].get(node.fragment)
            if inside is None:      # anchor not found: use the roadmap's position estimate
                inside = round(sizes[i] * max(0.0, min(1.0, node.ratio)))
        starts.append(prefix[i] + inside)
    own, first = _split(starts, prefix[-1])
    return WordCounts(own, prefix[-1], first, False, units=sizes, starts=starts)


# -- PDF ------------------------------------------------------------------------------- #

def _pdf_counts(path: str, roadmap, report=None) -> WordCounts:
    if fitz is None:
        raise RuntimeError("PDF support needs PyMuPDF:  pip install pymupdf")
    doc = fitz.open(str(path))
    try:
        n = doc.page_count
        pages = []
        for i in range(n):
            try:
                pages.append(count_words(doc[i].get_text("text")))
            except Exception:
                pages.append(0)
            if report and (i % 10 == 9 or i == n - 1):
                report(i + 1, n)
    finally:
        doc.close()
    with_text = sum(1 for w in pages if w >= MIN_TEXT_WORDS)
    estimated = n > 0 and with_text < max(1, SCANNED_SHARE * n)
    if estimated:
        pages = [AVG_WORDS_PER_PAGE] * n
    prefix = [0]
    for w in pages:
        prefix.append(prefix[-1] + w)
    starts = [prefix[max(0, min(node.index, n))] for node in roadmap.nodes]
    own, first = _split(starts, prefix[-1])
    return WordCounts(own, prefix[-1], first, estimated, units=pages, starts=starts)


# -- public API ------------------------------------------------------------------------- #

def compute_counts(path: str, fmt: str, roadmap, title_hint: str = "", report=None) -> WordCounts:
    """Word counts for every entry of `roadmap` (built for the book at `path`).
    `report(done, total)` is called as chapters/pages are counted."""
    counts = (_pdf_counts(path, roadmap, report) if fmt == "pdf"
              else _text_counts(path, fmt, title_hint, roadmap, report))
    counts.signature = roadmap_signature(roadmap)
    return counts


def words_before(roadmap, counts: WordCounts, position: int, ratio: float = 0.0) -> int:
    """Roughly how many words lie before a reading position (used for your personal pace)."""
    cur = roadmap.current_node(position, ratio)
    if cur is None:
        return 0
    done = sum(counts.own[j] for j in range(len(roadmap.nodes))
               if (roadmap.nodes[j].index, roadmap.nodes[j].ratio)
               < (roadmap.nodes[cur].index, roadmap.nodes[cur].ratio))
    if roadmap.paged:
        return done
    node = roadmap.nodes[cur]
    nxt = next(((m.index, m.ratio) for m in roadmap.nodes
                if (m.index, m.ratio) > (node.index, node.ratio)), None)
    if nxt is None or nxt[0] != node.index:      # the entry runs to the end of the chapter
        span = max(1e-6, 1.0 - node.ratio)
    else:
        span = max(1e-6, nxt[1] - node.ratio)
    frac = max(0.0, min(1.0, (ratio - node.ratio) / span)) if position == node.index else 1.0
    return done + round(counts.own[cur] * frac)


# -- cache (next to the roadmap cache; invalidated when the book or the roadmap changes) ---- #

def _cache_file(book_id: int) -> Path:
    return DATA_DIR / "roadmaps" / f"{int(book_id)}.words.json"


def _stamp(path: str) -> dict:
    st = Path(path).stat()
    return {"v": CACHE_VERSION, "size": st.st_size, "mtime": int(st.st_mtime)}


def load_cached(book_id: int, path: str, roadmap):
    try:
        data = json.loads(_cache_file(book_id).read_text(encoding="utf-8"))
        if data.get("stamp") != _stamp(path):
            return None
        counts = WordCounts(**data["counts"])
        if counts.signature != roadmap_signature(roadmap) or len(counts.own) != len(roadmap.nodes):
            return None
        return counts
    except Exception:
        return None


def save_cached(book_id: int, path: str, counts: WordCounts):
    try:
        f = _cache_file(book_id)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"stamp": _stamp(path), "counts": asdict(counts)}),
                     encoding="utf-8")
    except Exception:
        pass   # the cache is only an optimisation

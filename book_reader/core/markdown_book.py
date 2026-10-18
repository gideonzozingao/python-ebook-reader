"""Markdown documents as readable books: split into sections at headings, with a table of
contents, local images, internal links and full-text search."""
import posixpath
import re
import shutil

from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from book_reader.core.epub import TocEntry
from book_reader.core.search import TextSearchMixin
from book_reader.utils import clean_subjects


try:  # optional: pip install markdown
    import markdown as _markdown
except ImportError:
    _markdown = None

_FRONT = re.compile(r"\A\ufeff?---[ \t]*\n(.*?)\n(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.S)
_IMG_MD = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^)]*[\"'])?\s*\)")
_IMG_HTML = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)
_TASK = re.compile(r"^(\s*(?:[-*+]|\d+\.)\s+)\[( |x|X)\]\s+", re.M)
PAGE_CHARS = 1800   # characters per estimated page
MAX_ASSET = 25 * 1024 * 1024


def parse_front_matter(text: str) -> tuple[dict, str]:
    """Simple YAML-style header (--- key: value ---). Returns (metadata, body)."""
    m = _FRONT.match(text)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "-", "#")):
            key, value = line.split(":", 1)
            meta[key.strip().lower()] = value.strip().strip("\"'")
    return meta, text[m.end():]


def import_assets(src: Path, dest_dir: Path, text: str) -> int:
    """Copy the local images a document refers to (relative to the .md file) next to the
    library copy, keeping their relative paths. Returns how many files were copied."""
    root = Path(src).parent.resolve()
    seen: set = set()
    count = 0
    for ref in _IMG_MD.findall(text) + _IMG_HTML.findall(text):
        ref = unquote(ref.split("#")[0].split("?")[0]).replace("\\", "/")
        if not ref or urlparse(ref).scheme or ref.startswith("/"):
            continue
        rel = posixpath.normpath(ref)
        if rel.startswith("..") or rel in seen:
            continue
        seen.add(rel)
        f = (root / rel).resolve()
        try:
            f.relative_to(root)
        except ValueError:
            continue
        if f.is_file() and f.stat().st_size <= MAX_ASSET:
            target = Path(dest_dir) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(f, target)
            count += 1
    return count


class MarkdownBook(TextSearchMixin):
    """Same interface as EpubBook, so the EPUB reader page can show it."""

    def __init__(self, filename: str, title_hint: str = ""):
        if _markdown is None:
            raise RuntimeError("Markdown support needs the 'markdown' package:\n\n"
                               "    pip install markdown")
        self.filename = filename
        self.title_hint = title_hint
        self.path = Path(filename)
        self.assets = self.path.with_suffix(".assets")
        self.title, self.author = "Untitled", ""
        self.subjects: list[str] = []
        self.spine: list[str] = []
        self.toc: list[TocEntry] = []
        self._sections: list[dict] = []
        self._anchors: dict[str, str] = {}
        self._load()

    def close(self):
        pass

    def cover_bytes(self):
        return None  # the library draws a cover from the title

    # -- parsing -------------------------------------------------------------------- #

    def _load(self):
        raw = self.path.read_text(encoding="utf-8-sig", errors="replace")
        meta, body = parse_front_matter(raw)
        body = _TASK.sub(lambda m: m.group(1) + ("☑ " if m.group(2) in "xX" else "☐ "), body)
        md = _markdown.Markdown(extensions=["extra", "toc", "sane_lists"], output_format="html")
        soup = BeautifulSoup(md.convert(body), "html.parser")

        first_heading = soup.find(re.compile(r"^h[1-6]$"))
        self.title = (meta.get("title") or (first_heading.get_text(" ", strip=True)
                                            if first_heading else "") or self.title_hint
                      or "Untitled")
        self.author = meta.get("author") or meta.get("authors") or ""
        self.subjects = clean_subjects([meta.get(k, "").strip("[]") for k in
                                        ("tags", "keywords", "subject", "subjects", "categories")])

        tops = list(soup.contents)
        counts = {lvl: sum(getattr(el, "name", None) == f"h{lvl}" for el in tops)
                  for lvl in (1, 2, 3)}
        split = next((lvl for lvl in (1, 2, 3) if counts[lvl] >= 2), None)
        split_tags = {f"h{lvl}" for lvl in range(1, (split or 0) + 1)}
        groups: list[dict] = []
        cur = None
        for el in tops:
            name = getattr(el, "name", None)
            starts = name in split_tags
            if cur is None:
                if not starts and not str(el).strip():
                    continue
                head = el.get_text(" ", strip=True) if (starts or (name or "").startswith("h")) else ""
                cur = dict(title=head if starts else (self.title if split is None else "Introduction"),
                           els=[])
                groups.append(cur)
            elif starts:
                cur = dict(title=el.get_text(" ", strip=True), els=[])
                groups.append(cur)
            cur["els"].append(el)
        if not groups:
            groups = [dict(title=self.title, els=[])]

        stack: list[tuple[int, TocEntry]] = []
        for i, g in enumerate(groups):
            sid = f"section-{i}"
            html = "".join(str(e) for e in g["els"])
            sec = BeautifulSoup(html, "html.parser")
            self._sections.append(dict(title=g["title"], html=html,
                                       text=" ".join(sec.get_text(" ").split())))
            self.spine.append(sid)
            for tag in sec.find_all(id=True):
                self._anchors[tag["id"]] = sid
            for h in sec.find_all(re.compile(r"^h[1-6]$")):
                level = int(h.name[1])
                entry = TocEntry(h.get_text(" ", strip=True), sid, h.get("id", ""))
                while stack and stack[-1][0] >= level:
                    stack.pop()
                (stack[-1][1].children if stack else self.toc).append(entry)
                stack.append((level, entry))
        if not self.toc:
            self.toc = [TocEntry(self.title, "section-0")]

    # -- reading ----------------------------------------------------------------------- #

    def chapter_text(self, index: int) -> str:
        return self._sections[index]["text"] if 0 <= index < len(self._sections) else ""

    def est_page(self, index: int, ratio: float) -> tuple[int, int]:
        sizes = [len(s["text"]) for s in self._sections]
        total = sum(sizes)
        if total <= 0:
            return index + 1, max(1, len(self.spine))
        pages = max(1, round(total / PAGE_CHARS))
        inside = sizes[index] * max(0.0, min(1.0, ratio)) if 0 <= index < len(sizes) else 0
        page = int((sum(sizes[:max(0, index)]) + inside) / total * pages) + 1
        return min(page, pages), pages

    def read(self, path: str) -> bytes:
        """Image bytes for the reader (paths are relative to the document)."""
        rel = posixpath.normpath(unquote(path))
        target = (self.assets / rel).resolve()
        try:
            target.relative_to(self.assets.resolve())
        except ValueError:
            raise KeyError(path)
        if not target.is_file():
            raise KeyError(path)
        return target.read_bytes()

    def render_chapter(self, path: str) -> str:
        soup = BeautifulSoup(self._sections[self.spine.index(path)]["html"], "html.parser")
        for tag in soup(["script", "style", "link", "meta", "iframe"]):
            tag.decompose()
        for img in soup.find_all("img"):
            src = img.get("src") or ""
            scheme = urlparse(src).scheme
            if scheme in ("http", "https"):  # no network images: keep a link instead
                link = soup.new_tag("a", href=src)
                link.string = f"🖼 {img.get('alt') or 'image'}"
                img.replace_with(link)
                continue
            if src and scheme != "data":
                img["src"] = "epub:///" + quote(posixpath.normpath(unquote(src.split("#")[0])))
            for attr in ("width", "height", "style"):
                img.attrs.pop(attr, None)
            if img.find_parent(["p", "li", "td", "th", "h1", "h2", "h3", "h4", "a"]) is None:
                wrapper = soup.new_tag("p", attrs={"align": "center", "style": "line-height:100%;"})
                img.replace_with(wrapper)
                wrapper.append(img)
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if urlparse(href).scheme in ("http", "https", "mailto"):
                continue
            target = self._anchors.get(href[1:]) if href.startswith("#") else None
            if target:
                a["href"] = "epub:///" + quote(target) + href
            else:
                del a["href"]  # links to other files can't be followed
        for tag in soup.find_all(id=True):
            tag.insert_before(soup.new_tag("a", attrs={"name": tag["id"]}))
        for code in soup.select("pre code"):
            code.string = code.get_text().rstrip("\n")  # no blank last line in code blocks
        for table in soup.find_all("table"):
            table.attrs.update(border="1", cellspacing="0", cellpadding="6")
        return f"<html><body>{''.join(str(c) for c in soup.contents)}</body></html>"

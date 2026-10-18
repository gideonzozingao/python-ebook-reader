"""EPUB parsing: package, spine, table of contents, chapter rendering, page estimates."""
import posixpath
import warnings
import zipfile

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from dataclasses import dataclass, field
from urllib.parse import quote, unquote, urldefrag, urlparse

from book_reader.core.search import TextSearchMixin


warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)


@dataclass
class TocEntry:
    title: str
    path: str
    fragment: str = ""
    children: list = field(default_factory=list)


class EpubBook(TextSearchMixin):
    PAGE_BYTES = 2600  # rough HTML bytes per printed page (used for page estimates)

    def __init__(self, filename: str):
        self.filename = filename
        self.zip = zipfile.ZipFile(filename)
        self.title = "Untitled"
        self.author = ""
        self.spine: list[str] = []
        self.toc: list[TocEntry] = []
        self._sizes: list[int] | None = None
        try:
            self._load()
        except Exception:
            self.zip.close()
            raise

    def close(self):
        self.zip.close()

    def read(self, path: str) -> bytes:
        try:
            return self.zip.read(path)
        except KeyError:
            return self.zip.read(unquote(path))

    @staticmethod
    def resolve(base_path: str, href: str) -> tuple[str, str]:
        href, fragment = urldefrag(href)
        if not href:
            return base_path, fragment
        path = posixpath.normpath(
            posixpath.join(posixpath.dirname(base_path), unquote(href))
        )
        return path, fragment

    # -- page estimates ------------------------------------------------------ #

    def _spine_sizes(self) -> list[int]:
        if self._sizes is None:
            sizes = []
            for p in self.spine:
                info = None
                for name in (p, unquote(p)):
                    try:
                        info = self.zip.getinfo(name)
                        break
                    except KeyError:
                        continue
                sizes.append(info.file_size if info else 0)
            self._sizes = sizes
        return self._sizes

    def est_page(self, index: int, ratio: float) -> tuple[int, int]:
        """Estimated (page, total pages) for a position. EPUBs have no fixed pages, so
        this is derived from how much of the book's text lies before the position."""
        sizes = self._spine_sizes()
        total_bytes = sum(sizes)
        if total_bytes <= 0:
            return index + 1, max(1, len(self.spine))
        total_pages = max(1, round(total_bytes / self.PAGE_BYTES))
        before = sum(sizes[:max(0, index)])
        inside = sizes[index] * max(0.0, min(1.0, ratio)) if 0 <= index < len(sizes) else 0
        page = int((before + inside) / total_bytes * total_pages) + 1
        return min(page, total_pages), total_pages

    # -- full-text search ---------------------------------------------------- #

    def chapter_text(self, index: int) -> str:
        """Plain, whitespace-normalised text of a chapter (cached)."""
        cache = self.__dict__.setdefault("_texts", {})
        if index not in cache:
            try:
                soup = BeautifulSoup(self.read(self.spine[index]), "html.parser")
                for tag in soup(["script", "style", "title"]):
                    tag.decompose()
                cache[index] = " ".join(soup.get_text(" ").split())
            except Exception:
                cache[index] = ""
        return cache[index]

    # -- package ------------------------------------------------------------ #

    def _load(self):
        container = BeautifulSoup(self.read("META-INF/container.xml"), "html.parser")
        self._opf_path = container.find("rootfile")["full-path"]
        self._opf = BeautifulSoup(self.read(self._opf_path), "html.parser")
        opf = self._opf

        title, creator = opf.find("dc:title"), opf.find("dc:creator")
        if title and title.get_text(strip=True):
            self.title = title.get_text(strip=True)
        if creator:
            self.author = creator.get_text(strip=True)
        self.subjects = [t.get_text(strip=True) for t in opf.find_all("dc:subject")]

        self._manifest = {i["id"]: i for i in opf.find("manifest").find_all("item")}
        spine_tag = opf.find("spine")
        for ref in spine_tag.find_all("itemref"):
            item = self._manifest.get(ref.get("idref"))
            if item:
                self.spine.append(self.resolve(self._opf_path, item["href"])[0])

        nav_item = next(
            (i for i in self._manifest.values()
             if "nav" in (i.get("properties") or "").split()),
            None,
        )
        ncx_item = self._manifest.get(spine_tag.get("toc", "")) or next(
            (i for i in self._manifest.values()
             if i.get("media-type") == "application/x-dtbncx+xml"),
            None,
        )
        try:
            if nav_item:
                self.toc = self._parse_nav(self.resolve(self._opf_path, nav_item["href"])[0])
            if not self.toc and ncx_item:
                self.toc = self._parse_ncx(self.resolve(self._opf_path, ncx_item["href"])[0])
        except Exception:
            self.toc = []
        if not self.toc:
            self.toc = [TocEntry(f"Section {n}", p) for n, p in enumerate(self.spine, 1)]

    def cover_bytes(self) -> bytes | None:
        candidates = []
        for i in self._manifest.values():
            if "cover-image" in (i.get("properties") or "").split():
                candidates.append(i)
        meta = self._opf.find("meta", attrs={"name": "cover"})
        if meta and meta.get("content") in self._manifest:
            candidates.append(self._manifest[meta["content"]])
        for i in self._manifest.values():
            ident = (i.get("id", "") + i.get("href", "")).lower()
            if i.get("media-type", "").startswith("image/") and "cover" in ident:
                candidates.append(i)
        for item in candidates:
            try:
                return self.read(self.resolve(self._opf_path, item["href"])[0])
            except Exception:
                continue
        return None

    # -- table of contents -------------------------------------------------- #

    def _parse_nav(self, nav_path):
        soup = BeautifulSoup(self.read(nav_path), "html.parser")
        nav = soup.find("nav", attrs={"epub:type": "toc"}) or soup.find("nav")
        ol = nav.find(["ol", "ul"]) if nav else None
        return self._walk_list(ol, nav_path) if ol else []

    def _walk_list(self, ol, base):
        entries = []
        for li in ol.find_all("li", recursive=False):
            a = li.find(["a", "span"], recursive=False)
            title = a.get_text(" ", strip=True) if a else ""
            path, fragment = "", ""
            if a is not None and a.name == "a" and a.get("href"):
                path, fragment = self.resolve(base, a["href"])
            entry = TocEntry(title, path, fragment)
            sub = li.find(["ol", "ul"], recursive=False)
            if sub:
                entry.children = self._walk_list(sub, base)
            entries.append(entry)
        return entries

    def _parse_ncx(self, ncx_path):
        soup = BeautifulSoup(self.read(ncx_path), "html.parser")
        navmap = soup.find("navmap")
        return self._walk_navpoints(navmap, ncx_path) if navmap else []

    def _walk_navpoints(self, parent, base):
        entries = []
        for point in parent.find_all("navpoint", recursive=False):
            label = point.find("navlabel")
            content = point.find("content", recursive=False)
            title = label.get_text(" ", strip=True) if label else ""
            path, fragment = "", ""
            if content is not None and content.get("src"):
                path, fragment = self.resolve(base, content["src"])
            entry = TocEntry(title, path, fragment)
            entry.children = self._walk_navpoints(point, base)
            entries.append(entry)
        return entries

    # -- chapter rendering -------------------------------------------------- #

    def render_chapter(self, path: str) -> str:
        soup = BeautifulSoup(self.read(path), "html.parser")
        for tag in soup(["script", "style", "link", "meta", "title"]):
            tag.decompose()

        for svg in soup.find_all("svg"):
            image = svg.find("image")
            href = image and (image.get("xlink:href") or image.get("href"))
            if href:
                svg.replace_with(soup.new_tag("img", src=href))
            else:
                svg.decompose()

        for img in soup.find_all("img"):
            src = img.get("src")
            if src and urlparse(src).scheme not in ("http", "https", "data"):
                img["src"] = "epub:///" + quote(self.resolve(path, src)[0])
            for attr in ("width", "height", "style"):
                img.attrs.pop(attr, None)
            if img.find_parent(["p", "li", "td", "th", "h1", "h2", "h3", "h4", "a"]) is None:
                wrapper = soup.new_tag(
                    "p", attrs={"align": "center", "style": "line-height:100%;"})
                img.replace_with(wrapper)
                wrapper.append(img)

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if urlparse(href).scheme in ("http", "https", "mailto"):
                continue
            target, fragment = self.resolve(path, href)
            a["href"] = "epub:///" + quote(target) + (f"#{fragment}" if fragment else "")

        for tag in soup.find_all(id=True):
            if tag.name not in ("html", "body"):
                tag.insert_before(soup.new_tag("a", attrs={"name": tag["id"]}))

        inner = "".join(str(c) for c in soup.body.contents) if soup.body else str(soup)
        return f"<html><body>{inner}</body></html>"

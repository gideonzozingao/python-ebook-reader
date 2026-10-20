"""Note text: Markdown rendering, #tags and [[note:ID|title]] links (no Qt)."""
import html
import re

from bs4 import BeautifulSoup, NavigableString


try:  # optional: pip install markdown
    import markdown as _markdown
except ImportError:
    _markdown = None

TAG_RE = re.compile(r"(?<![\w&/#\[])#([A-Za-z][\w-]{1,40})")
LINK_RE = re.compile(r"\[\[note:(\d+)(?:\|([^\]]*))?\]\]")
_CODE_RE = re.compile(r"```.*?```|`[^`\n]*`", re.S)
_SPECIAL = re.compile(r"\[\[note:(\d+)(?:\|([^\]]*))?\]\]|(?<![\w&/#\[])#([A-Za-z][\w-]{1,40})")


def extract_tags(text: str) -> list[str]:
    """#tags in a note (not inside code), lower-case, in order, without duplicates."""
    plain = _CODE_RE.sub(" ", text or "")
    seen: dict = {}
    for m in TAG_RE.finditer(plain):
        seen.setdefault(m.group(1).lower(), None)
    return list(seen)


def extract_links(text: str) -> list[int]:
    return list(dict.fromkeys(int(m.group(1)) for m in LINK_RE.finditer(text or "")))


def link_markup(note_id: int, title: str) -> str:
    title = " ".join((title or "").replace("]", "").replace("|", "/").split())[:40]
    return f"[[note:{note_id}|{title}]]" if title else f"[[note:{note_id}]]"


def to_plain(text: str, limit: int = 0) -> str:
    """Markdown note -> short plain text (for list rows and link titles)."""
    t = LINK_RE.sub(lambda m: m.group(2) or f"note {m.group(1)}", text or "")
    t = re.sub(r"[`*_>#]+|^\s*[-+]\s+|^\s*\d+\.\s+", "", t, flags=re.M)
    t = " ".join(t.split())
    return (t[:limit - 1] + "…") if limit and len(t) > limit else t


def convert_links(text: str, resolver) -> str:
    """Rewrite note links with resolver(note_id, title) -> str (used by exports)."""
    return LINK_RE.sub(lambda m: resolver(int(m.group(1)), m.group(2) or ""), text or "")


def render_html(text: str, theme: dict | None = None) -> str:
    """Markdown note -> small HTML for labels/browsers. #tags become tag: links and
    [[note:..]] become note: links. Scripts and event handlers are removed."""
    theme = theme or {}
    text = text or ""
    if _markdown is not None:
        raw = _markdown.markdown(text, extensions=["extra", "sane_lists", "nl2br"])
    else:
        raw = "<p>" + html.escape(text).replace("\n", "<br>") + "</p>"
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "iframe", "object", "embed", "link", "meta"]):
        tag.decompose()
    for tag in soup.find_all(True):
        for attr in list(tag.attrs):
            if attr.lower().startswith("on") or (attr == "href" and
                                                 str(tag.attrs[attr]).strip().lower().startswith("javascript:")):
                del tag.attrs[attr]
    for s in list(soup.find_all(string=True)):
        if s.find_parent(["code", "pre", "a"]) or not _SPECIAL.search(str(s)):
            continue
        value, pos, nodes = str(s), 0, []
        for m in _SPECIAL.finditer(value):
            nodes.append(NavigableString(value[pos:m.start()]))
            a = soup.new_tag("a")
            if m.group(1):
                a["href"] = f"note:{m.group(1)}"
                a.string = "↗ " + (m.group(2) or f"note {m.group(1)}")
            else:
                a["href"] = f"tag:{m.group(3).lower()}"
                a.string = "#" + m.group(3)
            nodes.append(a)
            pos = m.end()
        nodes.append(NavigableString(value[pos:]))
        s.replace_with(*nodes)
    code_bg = theme.get("border", "#dddddd")
    for p in soup.find_all(["p", "ul", "ol", "blockquote", "pre", "h1", "h2", "h3", "h4"]):
        p["style"] = "margin:0 0 4px 0;"
    for c in soup.find_all("code"):
        c["style"] = f"background-color:{code_bg}; font-family:monospace;"
    return str(soup)

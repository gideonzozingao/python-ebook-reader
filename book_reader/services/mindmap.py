"""Mind map model (no Qt): nodes, balanced layout, outline import/export, and building a map
from a book's notes and highlights."""
import json
import re
import textwrap

from dataclasses import asdict, dataclass

from book_reader.services.journal import group_entries, ref_text


NODE_H = 56        # vertical slot per leaf in the automatic layout
LEVEL_GAP = 280    # horizontal distance between levels


@dataclass
class Node:
    id: int
    parent: int | None
    text: str
    seq: float = 0.0          # order among siblings
    x: float = 0.0
    y: float = 0.0
    color: int = -1           # palette index; -1 = inherit from the branch
    detail: str = ""          # longer text (full note / quote), shown as a tooltip
    collapsed: bool = False
    loc: dict | None = None   # where in the book it came from: {"i": spine/page index, "r": ratio}
    ref: str = ""             # human-readable source, e.g. "Chapter 3 · ≈ p. 42"


class MindMap:
    def __init__(self, title: str = "Mind map"):
        self.nodes: dict[int, Node] = {}
        self.next_id = 1
        self.root = self._new(None, title or "Mind map").id

    # -- structure ------------------------------------------------------------- #

    def _new(self, parent, text, **kw) -> Node:
        node = Node(self.next_id, parent, text, **kw)
        self.nodes[node.id] = node
        self.next_id += 1
        return node

    def child_map(self) -> dict:
        m: dict = {}
        for n in self.nodes.values():
            m.setdefault(n.parent, []).append(n)
        for v in m.values():
            v.sort(key=lambda n: (n.seq, n.id))
        return m

    def children(self, nid: int) -> list[Node]:
        return self.child_map().get(nid, [])

    def descendants(self, nid: int) -> list[int]:
        cmap, out, todo = self.child_map(), [], [nid]
        while todo:
            for c in cmap.get(todo.pop(), []):
                out.append(c.id)
                todo.append(c.id)
        return out

    def top_level(self, nid: int) -> int:
        """The branch (child of the root) a node belongs to."""
        n = self.nodes[nid]
        while n.parent is not None and n.parent != self.root:
            n = self.nodes[n.parent]
        return n.id

    def add_child(self, parent: int, text: str = "New idea", **kw) -> Node:
        kids = self.children(parent)
        seq = (kids[-1].seq + 1) if kids else 1.0
        return self._new(parent, text, seq=seq, **kw)

    def add_sibling(self, nid: int, text: str = "New idea", **kw) -> Node:
        node = self.nodes[nid]
        if node.parent is None:
            return self.add_child(nid, text, **kw)
        sibs = self.children(node.parent)
        k = next(i for i, s in enumerate(sibs) if s.id == nid)
        seq = (node.seq + sibs[k + 1].seq) / 2 if k + 1 < len(sibs) else node.seq + 1
        return self._new(node.parent, text, seq=seq, **kw)

    def remove(self, nid: int):
        if nid == self.root or nid not in self.nodes:
            return
        for i in [nid, *self.descendants(nid)]:
            self.nodes.pop(i, None)

    def move_subtree(self, nid: int, dx: float, dy: float):
        for i in [nid, *self.descendants(nid)]:
            self.nodes[i].x += dx
            self.nodes[i].y += dy

    # -- layout ------------------------------------------------------------------ #

    def auto_layout(self):
        """Balanced two-sided tree: root in the middle, branches alternate left/right."""
        cmap = self.child_map()
        memo: dict = {}

        def leaves(nid):
            if nid not in memo:
                kids = cmap.get(nid, [])
                memo[nid] = 1 if not kids else sum(leaves(k.id) for k in kids)
            return memo[nid]

        def place(nid, depth, side, y0, y1):
            n = self.nodes[nid]
            n.x, n.y = side * depth * LEVEL_GAP, (y0 + y1) / 2
            y = y0
            for k in cmap.get(nid, []):
                h = leaves(k.id) * NODE_H
                place(k.id, depth + 1, side, y, y + h)
                y += h

        root = self.nodes[self.root]
        root.x = root.y = 0.0
        sides = {1: [], -1: []}
        totals = {1: 0, -1: 0}
        for k in cmap.get(self.root, []):
            side = 1 if totals[1] <= totals[-1] else -1
            sides[side].append(k)
            totals[side] += leaves(k.id)
        for side, branch in sides.items():
            y = -totals[side] * NODE_H / 2
            for k in branch:
                h = leaves(k.id) * NODE_H
                place(k.id, 1, side, y, y + h)
                y += h

    # -- persistence ------------------------------------------------------------- #

    def to_json(self) -> str:
        return json.dumps({"v": 1, "root": self.root, "next_id": self.next_id,
                           "nodes": [asdict(n) for n in self.nodes.values()]})

    @classmethod
    def from_json(cls, data: str, title: str = "Mind map") -> "MindMap":
        mm = cls(title)
        try:
            doc = json.loads(data)
            nodes = {}
            for d in doc["nodes"]:
                n = Node(**{k: d[k] for k in Node.__dataclass_fields__ if k in d})
                nodes[n.id] = n
            if doc["root"] in nodes:
                mm.nodes, mm.root = nodes, doc["root"]
                mm.next_id = max(int(doc.get("next_id", 0)), max(nodes) + 1)
        except (ValueError, KeyError, TypeError):
            pass  # unreadable data: fall back to an empty map
        return mm

    # -- text formats -------------------------------------------------------------- #

    def to_outline(self) -> str:
        cmap, lines = self.child_map(), []

        def walk(nid, depth):
            lines.append("  " * depth + " ".join(self.nodes[nid].text.split()))
            for c in cmap.get(nid, []):
                walk(c.id, depth + 1)

        walk(self.root, 0)
        return "\n".join(lines)

    def to_markdown(self) -> str:
        cmap = self.child_map()
        lines = [f"# {self.nodes[self.root].text}", ""]

        def walk(nid, depth):
            for c in cmap.get(nid, []):
                lines.append("  " * depth + f"- {' '.join(c.text.split())}")
                extra = c.detail.strip()
                if extra and " ".join(extra.split()) != " ".join(c.text.split()):
                    lines.extend("  " * depth + f"  > {ln}" for ln in extra.splitlines() if ln.strip())
                if c.ref:
                    lines.append("  " * depth + f"  _{c.ref}_")
                walk(c.id, depth + 1)

        walk(self.root, 0)
        return "\n".join(lines) + "\n"

    @classmethod
    def from_outline(cls, title: str, text: str) -> "MindMap":
        """Indented lines (spaces or tabs, optional '-' / '*' bullets) become nested nodes."""
        mm = cls(title)
        stack = [(-1, mm.root)]
        for raw in text.splitlines():
            if not raw.strip():
                continue
            line = raw.replace("\t", "    ")
            indent = len(line) - len(line.lstrip(" "))
            label = line.strip().lstrip("-*•+ ").strip()
            if not label:
                continue
            while len(stack) > 1 and stack[-1][0] >= indent:
                stack.pop()
            node = mm.add_child(stack[-1][1], label)
            stack.append((indent, node.id))
        mm.auto_layout()
        return mm

    # -- from notes ------------------------------------------------------------------ #

    @classmethod
    def from_entries(cls, title: str, entries: list[dict], mode: str = "Book section",
                     fmt: str = "epub", split: bool = True) -> "MindMap":
        """Turn notes/highlights (SummaryBuilder.entries) into a map: one branch per book
        section (or topic / date), one node per note, extra sentences as sub-nodes."""
        mm = cls(title)
        for gtitle, items in group_entries(entries, mode):
            loc = _loc(items[0]) if mode == "Book section" else None
            group = mm.add_child(mm.root, _headline(gtitle, 48), loc=loc,
                                 ref=ref_text(items[0]["chapter"], items[0]["page"],
                                              items[0]["total"], fmt) if loc else "")
            for e in items:
                text = (e["text"] or e["quote"]).strip()
                parts = _sentences(text) if split else [text]
                head = _headline(parts[0])
                if mode != "Topic" and e["kind"] == "note" and e["topic"] not in ("General", ""):
                    head = f"{e['topic']}: {head}"
                ref = ref_text(e["chapter"], e["page"], e["total"], fmt)
                node = mm.add_child(group.id, head, detail=_detail(e, head), loc=_loc(e), ref=ref)
                for extra in parts[1:6]:
                    mm.add_child(node.id, _headline(extra), loc=_loc(e), ref=ref)
        mm.auto_layout()
        return mm


def _loc(e: dict) -> dict:
    """Notes know their exact position; highlights only their chapter/page."""
    return {"i": e["index"], "r": e["pos"] if e["kind"] == "note" else 0.0}


def _sentences(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
    return parts or [text.strip()]


def _headline(text: str, width: int = 72) -> str:
    return textwrap.shorten(" ".join(text.split()), width, placeholder="…")


def _detail(e: dict, head: str) -> str:
    """Full text kept on the node when the label is a shortened version of it."""
    text, quote = (e["text"] or "").strip(), (e["quote"] or "").strip()
    if not text and " ".join(quote.split()) == head:
        return ""
    full = f"“{quote}”\n\n{text}" if quote and text else (f"“{quote}”" if quote else text)
    return "" if " ".join(full.split()) == head else full

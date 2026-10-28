"""Roadmap of the open book: an outline with page ranges and a 'you are here' marker.

Non-modal (you can keep reading while it is open). Clicking an entry emits jumpRequested;
the reader page decides how to get there.
"""
from html import escape

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from book_reader.services.roadmap import Roadmap


class RoadmapDialog(QDialog):
    jumpRequested = Signal(int, str)    # (spine index or page, heading anchor)
    rescanRequested = Signal()          # "Rebuild" was pressed
    activated = Signal()                # window came to the front: refresh the marker
    autoShowChanged = Signal(bool)      # "show when I open a book" was toggled

    def __init__(self, parent, book_id: int, title: str, theme: dict, auto_show: bool):
        super().__init__(parent)
        self.book_id, self.t = book_id, theme
        self.roadmap: Roadmap | None = None
        self.position, self.ratio = 0, 0.0
        self.setWindowTitle(f"Roadmap — {title}")
        self.resize(560, 740)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(8)

        head = QLabel(title)
        head.setObjectName("h2")
        head.setWordWrap(True)
        lay.addWidget(head)
        self.info = QLabel("")
        self.info.setObjectName("muted")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

        self.browser = QTextBrowser()
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self._clicked)
        lay.addWidget(self.browser, 1)

        bottom = QHBoxLayout()
        self.auto = QCheckBox("Show when I open a new book")
        self.auto.setChecked(auto_show)
        self.auto.toggled.connect(self.autoShowChanged.emit)
        bottom.addWidget(self.auto)
        bottom.addStretch()
        rebuild = QPushButton("Rebuild")
        rebuild.setObjectName("link")
        rebuild.setToolTip("Scan the book again")
        rebuild.clicked.connect(lambda: self.rescanRequested.emit())
        bottom.addWidget(rebuild)
        close = QPushButton("Close")
        close.setObjectName("tonal")
        close.clicked.connect(self.close)
        bottom.addWidget(close)
        lay.addLayout(bottom)
        self.set_theme(theme)

    # -- state ---------------------------------------------------------------------- #

    def set_theme(self, theme: dict):
        self.t = theme
        self.browser.setStyleSheet(
            f"QTextBrowser {{ background:{theme['bg']}; border:1px solid {theme['border']};"
            f" border-radius:8px; }}")
        self.browser.document().setDefaultStyleSheet(
            f"a {{ color:{theme['fg']}; text-decoration:none; }}")

    def set_busy(self, text: str):
        self.roadmap = None
        self.info.setText("")
        self.browser.setHtml(f'<p style="color:{self.t["muted"]}">'
                             f'{escape(text).replace(chr(10), "<br>")}</p>')

    def show_roadmap(self, roadmap: Roadmap, position: int, ratio: float = 0.0,
                     scroll_to_current: bool = False):
        """Show `roadmap`; `position` is the reader's spine index (or page for a PDF) and
        `ratio` how far through that chapter they are."""
        self.roadmap, self.position, self.ratio = roadmap, position, ratio
        count = f"{roadmap.total_pages} page{'' if roadmap.total_pages == 1 else 's'}"
        pages = count if roadmap.paged else f"≈ {count}"
        note = {"toc": "",
                "headings": "  ·  built from headings (the book has no table of contents)",
                "pages": "  ·  no headings found, so split into page ranges"}.get(roadmap.source, "")
        self.info.setText(f"{len(roadmap.nodes)} entries  ·  {pages}{note}")
        bar = self.browser.verticalScrollBar()
        keep = bar.value()
        self.browser.setHtml(self._html())
        if scroll_to_current:
            QTimer.singleShot(0, lambda: self.browser.scrollToAnchor("here"))
        else:
            QTimer.singleShot(0, lambda: bar.setValue(keep))

    # -- rendering -------------------------------------------------------------------- #

    def _html(self) -> str:
        t, rm = self.t, self.roadmap
        cur = rm.current_node(self.position, self.ratio)
        around = rm.ancestors(cur) if cur is not None else set()
        rows = []
        for n, node in enumerate(rm.nodes):
            if n == cur:
                mark = "●"
            elif n in around:
                mark = "◐"
            elif cur is not None and n < cur:
                mark = "✓"
            else:
                mark = "○"
            bg = f' bgcolor="{t["sel"]}"' if n == cur else ""
            title = escape(node.title)
            label = f"<b>{title}</b>" if node.level == 1 else title
            indent = "&nbsp;" * 6 * (node.level - 1)
            anchor = '<a name="here"></a>' if n == cur else ""
            span = (f"p. {node.page}" if node.end_page <= node.page
                    else f"p. {node.page}–{node.end_page}")
            if not rm.paged:
                span = "≈ " + span
            rows.append(
                f'<tr><td{bg} width="28" align="center">'
                f'<span style="color:{t["accent"]}">{mark}</span></td>'
                f'<td{bg}>{anchor}{indent}<a href="roadmap:{n}">{label}</a></td>'
                f'<td{bg} align="right"><span style="color:{t["muted"]}">{span}</span></td></tr>')
        if not rows:
            return f'<p style="color:{t["muted"]}">Nothing to show for this book.</p>'
        legend = (f'<p style="color:{t["muted"]}">✓ read &nbsp;·&nbsp; ● you are here '
                  f'&nbsp;·&nbsp; ◐ section you are in &nbsp;·&nbsp; ○ still ahead</p>')
        return (f'<table width="100%" cellspacing="0" cellpadding="6">{"".join(rows)}</table>'
                f'{legend}')

    # -- events ------------------------------------------------------------------------ #

    def _clicked(self, url):
        if url.scheme() != "roadmap" or self.roadmap is None:
            return
        try:
            node = self.roadmap.nodes[int(url.path())]
        except (ValueError, IndexError):
            return
        self.jumpRequested.emit(node.index, node.fragment)

    def event(self, e):
        if e.type() == QEvent.Type.WindowActivate:
            self.activated.emit()
        return super().event(e)

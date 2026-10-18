"""'Welcome back' reminder shown at startup."""
import textwrap

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from book_reader.ui.widgets.cover import make_cover
from book_reader.utils import ago, fmt_duration, where_text


class ReminderDialog(QDialog):
    """Shows the last book you read, where you stopped, and links to reopen it."""

    def __init__(self, parent, last, others, theme: dict):
        super().__init__(parent)
        self.setWindowTitle("Welcome back")
        self.setMinimumWidth(580)
        self.chosen: int | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 22, 24, 18)
        lay.setSpacing(14)

        head = QLabel("Welcome back — pick up where you left off")
        head.setObjectName("h2")
        lay.addWidget(head)

        card = QFrame()
        card.setObjectName("sidePanel")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 16, 16, 16)
        row.setSpacing(16)
        cover = QLabel()
        cover.setPixmap(make_cover(last["title"], last["author"], last["cover"],
                                   last["progress"] or 0, True).scaled(
            100, 147, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        cover.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(cover)

        info = QVBoxLayout()
        info.setSpacing(5)
        title = QLabel(last["title"])
        title.setObjectName("h2")
        title.setWordWrap(True)
        info.addWidget(title)
        if last["author"]:
            author = QLabel(last["author"])
            author.setObjectName("muted")
            info.addWidget(author)
        info.addSpacing(6)
        lines = [f"Last read {ago(last['last_read_at'])}"]
        if last["last_section"]:
            lines.append(f"Section: {last['last_section']}")
        lines.append(f"Stopped at {where_text(last)}")
        lines.append(f"{(last['progress'] or 0) * 100:.0f}% of the book  ·  "
                     f"{fmt_duration(last['read_seconds'])} read so far")
        for text in lines:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            info.addWidget(lbl)
        info.addStretch()
        go = QPushButton("▶  Continue reading")
        go.setObjectName("primary")
        go.setMinimumHeight(38)
        go.setDefault(True)
        go.clicked.connect(lambda: self._choose(last["id"]))
        info.addWidget(go)
        row.addLayout(info, 1)
        lay.addWidget(card)

        if others:
            more = QLabel("Also on your reading list")
            more.setObjectName("muted")
            lay.addWidget(more)
            for r in others:
                text = f"{textwrap.shorten(r['title'], 52, placeholder='…')}"
                detail = f"{where_text(r)}  ·  {ago(r['last_read_at'])}"
                b = QPushButton(f"{text}   —   {detail}")
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setStyleSheet(
                    f"QPushButton {{ text-align:left; padding:5px 2px; border:none;"
                    f" background:transparent; color:{theme['link']}; }}"
                    f"QPushButton:hover {{ text-decoration:underline; }}")
                b.clicked.connect(lambda _=False, bid=r["id"]: self._choose(bid))
                lay.addWidget(b)

        foot = QHBoxLayout()
        self.chk = QCheckBox("Show this reminder when the app starts")
        self.chk.setChecked(True)
        foot.addWidget(self.chk)
        foot.addStretch()
        later = QPushButton("Not now")
        later.clicked.connect(self.reject)
        foot.addWidget(later)
        lay.addLayout(foot)

    def _choose(self, book_id: int):
        self.chosen = book_id
        self.accept()

    def show_again(self) -> bool:
        return self.chk.isChecked()

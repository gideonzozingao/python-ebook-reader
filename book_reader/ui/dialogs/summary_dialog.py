"""Book summary review dialog (group, filter, own summary, copy, export)."""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from book_reader.constants import SUMMARY_MODES
from book_reader.services.export import export_summary_dialog
from book_reader.services.summary import SummaryBuilder


class SummaryDialog(QDialog):
    """Review all notes for a book as a summary: pick how to group them, filter, write your
    own overall summary, copy as Markdown or export."""

    def __init__(self, parent, builder: SummaryBuilder, theme: dict):
        super().__init__(parent)
        self.b, self.t = builder, theme
        self.setWindowTitle("Book summary")
        self.resize(880, 740)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)

        head = QLabel(f"Summary of your notes — {builder.title}")
        head.setObjectName("h2")
        head.setWordWrap(True)
        lay.addWidget(head)

        opts = QHBoxLayout()
        opts.addWidget(QLabel("Group by"))
        self.group = QComboBox()
        self.group.addItems(SUMMARY_MODES)
        opts.addWidget(self.group)
        opts.addSpacing(10)
        opts.addWidget(QLabel("Section"))
        self.topic_box = QComboBox()
        self.topic_box.addItem("All sections")
        self.topic_box.addItems(builder.topics())
        opts.addWidget(self.topic_box)
        opts.addSpacing(10)
        self.chk_notes = QCheckBox("Book notes")
        self.chk_notes.setChecked(True)
        self.chk_hl = QCheckBox("Highlights")
        self.chk_hl.setChecked(True)
        self.chk_hl.setVisible(builder.has_highlights())
        opts.addWidget(self.chk_notes)
        opts.addWidget(self.chk_hl)
        opts.addStretch()
        lay.addLayout(opts)

        cap = QLabel("Your own overall summary (optional — saved with the book and included "
                     "in exports)")
        cap.setObjectName("muted")
        lay.addWidget(cap)
        self.overall = QPlainTextEdit(builder.library.get_summary(builder.book_id))
        self.overall.setPlaceholderText("In a few sentences: what is this book about and "
                                        "what are the takeaways?")
        self.overall.setFixedHeight(96)
        lay.addWidget(self.overall)

        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.setStyleSheet(f"QTextBrowser {{ background:{theme['bg']};"
                                f" border:1px solid {theme['border']}; border-radius:8px; }}")
        lay.addWidget(self.view, 1)

        buttons = QHBoxLayout()
        copy = QPushButton("Copy as Markdown")
        copy.clicked.connect(self._copy)
        export = QPushButton("Export…")
        export.setObjectName("primary")
        export.clicked.connect(self._export)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(copy)
        buttons.addStretch()
        buttons.addWidget(export)
        buttons.addWidget(close)
        lay.addLayout(buttons)

        self._timer = QTimer(self, singleShot=True, interval=600)
        self._timer.timeout.connect(self._save_overall)
        self.overall.textChanged.connect(self._timer.start)
        for sig in (self.group.currentTextChanged, self.topic_box.currentTextChanged):
            sig.connect(lambda _=None: self._render())
        for chk in (self.chk_notes, self.chk_hl):
            chk.toggled.connect(lambda _=False: self._render())
        self._render()

    def _opts(self):
        topic = "" if self.topic_box.currentIndex() == 0 else self.topic_box.currentText()
        return (self.group.currentText(), topic, self.chk_notes.isChecked(),
                self.chk_hl.isChecked() or not self.chk_hl.isVisible())

    def _render(self):
        mode, topic, notes, hl = self._opts()
        bar = self.view.verticalScrollBar()
        pos = bar.value()
        self.view.setHtml(self.b.render("rich", mode, topic, notes, hl, self.t))
        bar.setValue(pos)

    def _save_overall(self):
        self.b.library.set_summary(self.b.book_id, self.overall.toPlainText().strip())
        self._render()

    def _copy(self):
        self._save_overall_now()
        QApplication.clipboard().setText(self.b.render("md", *self._opts()))

    def _save_overall_now(self):
        if self._timer.isActive():
            self._timer.stop()
            self.b.library.set_summary(self.b.book_id, self.overall.toPlainText().strip())

    def _export(self):
        self._save_overall_now()
        export_summary_dialog(self, self.b, *self._opts())

    def done(self, result):
        self._save_overall_now()
        super().done(result)

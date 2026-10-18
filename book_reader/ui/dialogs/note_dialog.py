"""Dialog for adding/editing a highlight note."""
import textwrap

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from book_reader.themes import HIGHLIGHT_COLORS
from book_reader.ui.helpers import swatch
from book_reader.utils import pretty


class NoteDialog(QDialog):
    def __init__(self, parent, quote_text="", note="", color="Yellow", editing=False):
        super().__init__(parent)
        self.setWindowTitle("Edit note" if editing else "Add note")
        self.setMinimumWidth(480)
        self.deleted = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)

        self.color_box = QComboBox()
        for name, hexv in HIGHLIGHT_COLORS.items():
            self.color_box.addItem(swatch(hexv), name)
        self.color_box.setCurrentText(color)

        if quote_text:
            cap = QLabel("Selected text")
            cap.setObjectName("muted")
            q = QLabel("“" + textwrap.shorten(pretty(quote_text).replace("\n", " "), 320,
                                              placeholder="…") + "”")
            q.setWordWrap(True)
            f = q.font()
            f.setItalic(True)
            q.setFont(f)
            lay.addWidget(cap)
            lay.addWidget(q)
            row = QHBoxLayout()
            row.addWidget(QLabel("Highlight color"))
            row.addWidget(self.color_box)
            row.addStretch()
            lay.addLayout(row)

        self.edit = QPlainTextEdit(note)
        self.edit.setPlaceholderText("Write your note…")
        self.edit.setMinimumHeight(120)
        lay.addWidget(self.edit)

        buttons = QHBoxLayout()
        if editing:
            delete = QPushButton("Delete")
            delete.clicked.connect(self._delete)
            buttons.addWidget(delete)
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        lay.addLayout(buttons)

        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.accept)
        self.edit.setFocus()

    def _delete(self):
        self.deleted = True
        self.accept()

    def text(self) -> str:
        return self.edit.toPlainText().strip()

    def color(self) -> str:
        return self.color_box.currentText()

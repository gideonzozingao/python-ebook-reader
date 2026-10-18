"""Options for turning a book's notes and highlights into a mind map."""
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from book_reader.constants import SUMMARY_MODES


class NotesToMapDialog(QDialog):
    def __init__(self, parent, builder, default_title: str):
        super().__init__(parent)
        self.setWindowTitle("Turn notes into a mind map")
        self.setMinimumWidth(460)
        entries = builder.entries()
        n_notes = sum(e["kind"] == "note" for e in entries)
        n_hl = len(entries) - n_notes
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)
        head = QLabel(f"{n_notes} book note{'' if n_notes == 1 else 's'}"
                      + (f" and {n_hl} highlight{'' if n_hl == 1 else 's'}" if builder.has_highlights() else "")
                      + " will become branches and ideas.")
        head.setWordWrap(True)
        lay.addWidget(head)

        self.title = QLineEdit(default_title)
        lay.addWidget(QLabel("Map name"))
        lay.addWidget(self.title)

        row = QHBoxLayout()
        row.addWidget(QLabel("Main branches"))
        self.mode = QComboBox()
        self.mode.addItems(SUMMARY_MODES)
        self.mode.setToolTip("Book section: one branch per chapter, in reading order.\n"
                             "Topic: one branch per note section (Key idea, Question…).\n"
                             "Date: one branch per day you took notes.")
        row.addWidget(self.mode, 1)
        lay.addLayout(row)

        self.chk_notes = QCheckBox("Book notes")
        self.chk_notes.setChecked(True)
        self.chk_hl = QCheckBox("Highlights")
        self.chk_hl.setChecked(True)
        self.chk_hl.setVisible(builder.has_highlights())
        self.chk_split = QCheckBox("Split longer notes into sub-ideas (one per sentence)")
        self.chk_split.setChecked(True)
        for w in (self.chk_notes, self.chk_hl, self.chk_split):
            lay.addWidget(w)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Create mind map")
        ok.setObjectName("primary")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(ok)
        lay.addLayout(buttons)

    def options(self) -> dict:
        return dict(title=self.title.text().strip() or "Notes map", mode=self.mode.currentText(),
                    notes=self.chk_notes.isChecked(),
                    highlights=self.chk_hl.isChecked() or not self.chk_hl.isVisible(),
                    split=self.chk_split.isChecked())

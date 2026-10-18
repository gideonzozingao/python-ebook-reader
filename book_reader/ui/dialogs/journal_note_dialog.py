"""Dialog for editing a journal note and re-pinning its location."""
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from book_reader.constants import DEFAULT_TOPICS


class JournalNoteDialog(QDialog):
    """Edit an existing journal note (section, text) and optionally re-pin its location."""

    def __init__(self, parent, topics, topic="General", body="", ref="", editing=False):
        super().__init__(parent)
        self.setWindowTitle("Edit book note" if editing else "Add book note")
        self.setMinimumWidth(500)
        self.deleted = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)

        row = QHBoxLayout()
        row.addWidget(QLabel("Section"))
        self.topic_box = QComboBox()
        self.topic_box.setEditable(True)
        self.topic_box.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        seen, items = set(), []
        for name in [topic, *DEFAULT_TOPICS, *topics]:
            if name and name.lower() not in seen:
                seen.add(name.lower())
                items.append(name)
        self.topic_box.addItems(items)
        self.topic_box.setCurrentText(topic)
        row.addWidget(self.topic_box, 1)
        lay.addLayout(row)

        if ref:
            where = QLabel(f"📍 {ref}")
            where.setObjectName("muted")
            where.setWordWrap(True)
            lay.addWidget(where)

        self.edit = QPlainTextEdit(body)
        self.edit.setPlaceholderText("Write your note…")
        self.edit.setMinimumHeight(140)
        lay.addWidget(self.edit)

        self.relocate = QCheckBox("Move this note to my current reading position")
        self.relocate.setVisible(editing)
        lay.addWidget(self.relocate)

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

    def topic(self) -> str:
        return " ".join(self.topic_box.currentText().split()) or "General"

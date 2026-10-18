"""Subject picker for the library catalogue."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from book_reader.utils import clean_subjects


class SubjectDialog(QDialog):
    """Tick existing subjects and/or type new ones. For several books a subject some
    (not all) of them have shows as partially checked and is left alone."""

    def __init__(self, parent, existing, counts, n_books, noun="subjects"):
        super().__init__(parent)
        self.setWindowTitle(f"Set {noun}")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(10)
        what = "1 book" if n_books == 1 else f"{n_books} books"
        head = QLabel(f"{noun.capitalize()} for {what}")
        head.setObjectName("h2")
        lay.addWidget(head)

        self.list = QListWidget()
        self.list.setMinimumHeight(180)
        for name in existing:
            item = QListWidgetItem(name)
            flags = item.flags() | Qt.ItemFlag.ItemIsUserCheckable
            if n_books > 1:
                flags |= Qt.ItemFlag.ItemIsUserTristate
            item.setFlags(flags)
            c = counts.get(name, 0)
            item.setCheckState(Qt.CheckState.Checked if c == n_books
                               else Qt.CheckState.PartiallyChecked if c
                               else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        if not existing:
            lay.addWidget(QLabel(f"No {noun} yet — add some below."))
        else:
            lay.addWidget(self.list)
        self.new = QLineEdit()
        self.new.setPlaceholderText(f"New {noun} (comma separated)…")
        self.new.returnPressed.connect(self.accept)
        lay.addWidget(self.new)

        buttons = QHBoxLayout()
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
        self.new.setFocus()

    def changes(self) -> tuple[list[str], list[str]]:
        add, remove = [], []
        for i in range(self.list.count()):
            item = self.list.item(i)
            state = item.checkState()
            if state == Qt.CheckState.Checked:
                add.append(item.text())
            elif state == Qt.CheckState.Unchecked:
                remove.append(item.text())
        add += clean_subjects([self.new.text()], limit=20)
        keep = {a.lower() for a in add}
        return add, [r for r in remove if r.lower() not in keep]

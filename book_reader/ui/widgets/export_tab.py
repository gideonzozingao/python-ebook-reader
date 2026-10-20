"""Export notes to Obsidian / Notion / Anki, and keep a folder of .md files in sync."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from book_reader.services import export_notes


class ExportTab(QWidget):
    FORMATS = ["Obsidian vault (Markdown files)", "Notion import (zip: pages + notes table)",
               "Anki cards — basic (tab-separated file)", "Anki cards — cloze (tab-separated file)"]
    HINTS = ["Creates one .md file per book in the folder. Open the folder as an Obsidian vault; "
             "note links become [[wiki links]] and #tags work natively.",
             "In Notion: Import → Markdown & CSV, and choose the zip.",
             "In Anki: File → Import, pick the file. Cards go to the “Book Reader” deck.",
             "Cloze cards hide one key word per note. Import the same way (note type: Cloze)."]

    def __init__(self, library, prefs, sync, theme: dict):
        super().__init__()
        self.lib, self.prefs, self.sync = library, prefs, sync
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)
        lay.setSpacing(10)

        head = QLabel("Export notes")
        head.setObjectName("h2")
        lay.addWidget(head)
        form = QFormLayout()
        self.format = QComboBox()
        self.format.addItems(self.FORMATS)
        self.scope = QComboBox()
        self.dest = QLineEdit()
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        drow = QHBoxLayout()
        drow.addWidget(self.dest, 1)
        drow.addWidget(browse)
        form.addRow("Format", self.format)
        form.addRow("Books", self.scope)
        form.addRow("Save to", drow)
        lay.addLayout(form)
        self.hint = QLabel(self.HINTS[0])
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)
        row = QHBoxLayout()
        row.addStretch()
        go = QPushButton("Export")
        go.setObjectName("primary")
        go.clicked.connect(self._export)
        row.addWidget(go)
        lay.addLayout(row)
        self.result = QLabel("")
        self.result.setWordWrap(True)
        lay.addWidget(self.result)
        self.format.currentIndexChanged.connect(self._format_changed)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)
        sh = QLabel("Sync folder")
        sh.setObjectName("h2")
        lay.addWidget(sh)
        info = QLabel("Keep a folder of Markdown files (one per book) up to date automatically "
                      "whenever you add or change a note. One-way: the library is the source.")
        info.setObjectName("muted")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.sync_on = QCheckBox("Keep this folder in sync")
        self.sync_on.setChecked(bool(prefs.v["sync_enabled"]))
        self.sync_path = QLineEdit(prefs.v["sync_folder"])
        sb = QPushButton("Choose folder…")
        sb.clicked.connect(self._pick_sync)
        now = QPushButton("Sync now")
        now.clicked.connect(self._sync_now)
        srow = QHBoxLayout()
        srow.addWidget(self.sync_path, 1)
        srow.addWidget(sb)
        srow.addWidget(now)
        lay.addWidget(self.sync_on)
        lay.addLayout(srow)
        self.sync_status = QLabel(sync.last_message)
        self.sync_status.setObjectName("muted")
        self.sync_status.setWordWrap(True)
        lay.addWidget(self.sync_status)
        self.sync_on.toggled.connect(self._sync_toggled)
        sync.status.connect(self.sync_status.setText)
        lay.addStretch()

    def reload(self):
        self.scope.clear()
        self.scope.addItem("All books with notes", None)
        for bid, title in export_notes.books_with_notes(self.lib):
            self.scope.addItem(title, bid)

    def set_scope(self, book_id):
        i = self.scope.findData(book_id)
        if i >= 0:
            self.scope.setCurrentIndex(i)

    def _format_changed(self, i):
        self.hint.setText(self.HINTS[i])
        self.dest.clear()

    def _book_ids(self) -> list[int]:
        bid = self.scope.currentData()
        return [bid] if bid is not None else [b for b, _ in export_notes.books_with_notes(self.lib)]

    def _browse(self):
        i = self.format.currentIndex()
        if i == 0:
            path = QFileDialog.getExistingDirectory(self, "Choose the vault folder")
        else:
            ext, flt = ("zip", "Zip (*.zip)") if i == 1 else ("txt", "Anki import (*.txt)")
            path, _ = QFileDialog.getSaveFileName(self, "Save export", str(Path.home() / f"book-notes.{ext}"), flt)
        if path:
            self.dest.setText(path)

    def _export(self):
        ids, dest, i = self._book_ids(), self.dest.text().strip(), self.format.currentIndex()
        if not ids:
            self.result.setText("There are no notes to export yet.")
            return
        if not dest:
            self._browse()
            dest = self.dest.text().strip()
            if not dest:
                return
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            if i == 0:
                n = len(export_notes.export_obsidian(self.lib, ids, dest))
                msg = f"Wrote {n} Markdown file{'' if n == 1 else 's'} to {dest}"
            elif i == 1:
                n = export_notes.export_notion(self.lib, ids, dest)
                msg = f"Exported {n} note{'' if n == 1 else 's'} to {dest}"
            else:
                n = export_notes.export_anki(self.lib, ids, dest, "cloze" if i == 3 else "basic")
                msg = f"Exported {n} card{'' if n == 1 else 's'} to {dest}"
        except Exception as exc:
            msg = f"Export failed: {exc}"
        finally:
            QApplication.restoreOverrideCursor()
        self.result.setText(msg)

    def _pick_sync(self):
        path = QFileDialog.getExistingDirectory(self, "Choose the sync folder", self.sync_path.text())
        if path:
            self.sync_path.setText(path)
            self.prefs.set("sync_folder", path)
            if self.sync_on.isChecked():
                self._sync_now()

    def _sync_toggled(self, on: bool):
        if on and not self.sync_path.text().strip():
            self._pick_sync()
            if not self.sync_path.text().strip():
                self.sync_on.blockSignals(True)
                self.sync_on.setChecked(False)
                self.sync_on.blockSignals(False)
                return
        self.prefs.set("sync_folder", self.sync_path.text().strip())
        self.prefs.set("sync_enabled", bool(on))
        if on:
            self._sync_now()

    def _sync_now(self):
        self.prefs.set("sync_folder", self.sync_path.text().strip())
        if not self.prefs.v["sync_folder"]:
            self.sync_status.setText("Choose a folder first.")
            return
        was = self.prefs.v["sync_enabled"]
        self.prefs.set("sync_enabled", True)  # sync_all honours the setting
        try:
            self.sync.sync_all()
        finally:
            self.prefs.set("sync_enabled", was)

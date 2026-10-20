"""Keep a folder of Markdown files (one per book) up to date as you take notes."""
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal

from book_reader.services import export_notes


class NotesSync(QObject):
    status = Signal(str)   # last result, for the UI

    def __init__(self, library, prefs, parent=None):
        super().__init__(parent)
        self.library, self.prefs = library, prefs
        self.dirty: set[int] = set()
        self.last_message = ""
        self._timer = QTimer(self, singleShot=True, interval=2000)
        self._timer.timeout.connect(self.flush)

    def enabled(self) -> bool:
        folder = self.prefs.v["sync_folder"]
        return bool(self.prefs.v["sync_enabled"] and folder)

    def schedule(self, book_id: int):
        """Called by the library whenever a book's notes change (batched for 2 seconds)."""
        if self.enabled():
            self.dirty.add(book_id)
            self._timer.start()

    def flush(self):
        ids, self.dirty = sorted(self.dirty), set()
        if ids and self.enabled():
            self._write(ids)

    def sync_all(self) -> int:
        ids = [bid for bid, _ in export_notes.books_with_notes(self.library)]
        return self._write(ids)

    def _write(self, ids) -> int:
        folder = Path(self.prefs.v["sync_folder"])
        try:
            written = export_notes.export_obsidian(self.library, ids, folder)
        except OSError as exc:
            self.last_message = f"Sync failed: {exc}"
        else:
            self.last_message = f"Synced {len(written)} file(s) to {folder}"
        self.status.emit(self.last_message)
        return len(ids)

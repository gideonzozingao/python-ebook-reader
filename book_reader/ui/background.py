"""Run a function in a background thread and hand the result back to the UI thread."""
import threading

from PySide6.QtCore import QObject, Signal

CANCELLED = "cancelled"


class Job(QObject):
    """Runs fn(job) in a daemon thread (so it can never block the app from quitting).
    `done(result, error)` and `progress(done, total)` arrive on the UI thread."""
    done = Signal(object, str)        # result (or None), error text ("" = success, CANCELLED)
    progress = Signal(object, object)

    def __init__(self, parent, fn):
        super().__init__(parent)
        self._fn = fn
        self._stop = threading.Event()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def cancel(self):
        self._stop.set()

    def is_cancelled(self) -> bool:
        return self._stop.is_set()

    def report(self, done, total):
        self.progress.emit(done, total)

    def _run(self):
        try:
            result = self._fn(self)
        except Exception as exc:
            self.done.emit(None, CANCELLED if self._stop.is_set() else str(exc) or "Unknown error")
        else:
            self.done.emit(result, "")

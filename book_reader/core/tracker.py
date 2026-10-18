"""Reading-time tracker shared by the EPUB and PDF readers."""
import time

from PySide6.QtCore import QEvent, QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from book_reader.constants import IDLE_LIMIT
from book_reader.core.library import Library


class ReadingTracker(QObject):
    """Counts reading time for the open book.

    The clock runs only while the app window is active, the reader page is
    visible, and there was keyboard/mouse input in the last IDLE_LIMIT seconds.
    Time is flushed to SQLite every ~15 s and when the book is closed.
    """

    tick = Signal(float, float)  # session seconds, total seconds for this book
    addedToReading = Signal(int)  # book auto-added to the reading list
    AUTO_ADD_AFTER = 30  # seconds of active reading before auto-adding to the list

    _ACTIVITY = (QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress,
                 QEvent.Type.MouseMove, QEvent.Type.Wheel)

    def __init__(self, library: Library, parent=None):
        super().__init__(parent)
        self.library = library
        self.book_id = None
        self.session_id = None
        self.widget = None
        self.session = 0.0
        self.total = 0.0
        self._unsaved = 0.0
        self._auto_done = False
        self._last_activity = time.monotonic()
        self._last_tick = time.monotonic()
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._on_tick)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj, ev):
        if ev.type() in self._ACTIVITY:
            self._last_activity = time.monotonic()
        return False

    def start(self, book_id, total_seconds, widget):
        self.stop()
        self.book_id, self.widget = book_id, widget
        self.total, self.session, self._unsaved = float(total_seconds or 0), 0.0, 0.0
        self.session_id = self.library.start_session(book_id)
        self._auto_done = False
        self._last_tick = self._last_activity = time.monotonic()
        self.timer.start()
        self.tick.emit(self.session, self.total)

    def stop(self):
        if self.book_id is None:
            return
        self.timer.stop()
        self.flush()
        self.book_id = self.session_id = self.widget = None

    def flush(self):
        if self.book_id is not None and self._unsaved > 0:
            self.library.add_time(self.book_id, self.session_id, self._unsaved, self.session)
            self._unsaved = 0.0

    def _active(self) -> bool:
        win = QApplication.activeWindow()
        if win is None or win.isMinimized():
            return False
        if self.widget is not None and not self.widget.isVisible():
            return False
        return time.monotonic() - self._last_activity < IDLE_LIMIT

    def _on_tick(self):
        now = time.monotonic()
        dt = min(now - self._last_tick, 5.0)  # ignore sleep/hibernate gaps
        self._last_tick = now
        if self._active():
            self.session += dt
            self.total += dt
            self._unsaved += dt
            if self._unsaved >= 15:
                self.flush()
            if not self._auto_done and self.session >= self.AUTO_ADD_AFTER:
                self._auto_done = True
                if self.library.auto_add_reading(self.book_id):
                    self.addedToReading.emit(self.book_id)
        self.tick.emit(self.session, self.total)

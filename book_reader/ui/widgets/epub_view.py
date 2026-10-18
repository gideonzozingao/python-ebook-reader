"""EPUB reading surface: smooth scrolling, centred column, highlights."""
from PySide6.QtCore import QAbstractAnimation, QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFrame, QMenu, QTextBrowser

from book_reader.core.epub import EpubBook
from book_reader.themes import HIGHLIGHT_COLORS
from book_reader.ui.helpers import swatch


class Reader(QTextBrowser):
    nextRequested = Signal()
    prevRequested = Signal()
    zoomRequested = Signal(int)
    highlightRequested = Signal(str)
    lookupRequested = Signal(str)
    noteRequested = Signal()
    editNoteRequested = Signal(int)
    deleteNoteRequested = Signal(int)
    positionClicked = Signal(int)

    def __init__(self):
        super().__init__()
        self.book: EpubBook | None = None
        self.text_width = 760
        self.note_ranges: list[tuple[int, int, int]] = []  # (note id, start, end)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.document().setDocumentMargin(28)
        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._anim.setDuration(230)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # -- layout ------------------------------------------------------------- #

    def update_margins(self):
        m = max(0, (self.width() - self.text_width) // 2)
        self.setViewportMargins(m, 0, m, 0)
        self.document().setTextWidth(max(0, self.viewport().width()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_margins()

    # -- images from the EPUB ---------------------------------------------- #

    def loadResource(self, rtype, url):
        if url.scheme() == "epub" and self.book is not None:
            try:
                image = QImage.fromData(self.book.read(url.path().lstrip("/")))
            except KeyError:
                return QImage()
            avail = self.viewport().width()
            if avail < 300:  # page not shown yet: fall back to the column width
                avail = self.text_width
            max_w = min(avail, self.text_width) - 56
            if not image.isNull() and max_w > 0 and image.width() > max_w:
                image = image.scaledToWidth(max_w, Qt.TransformationMode.SmoothTransformation)
            return image
        return super().loadResource(rtype, url)

    # -- smooth scrolling --------------------------------------------------- #

    def stop_scroll(self):
        self._anim.stop()

    def _target(self) -> int:
        if self._anim.state() == QAbstractAnimation.State.Running:
            return int(self._anim.endValue())
        return self.verticalScrollBar().value()

    def smooth_scroll_by(self, dy: int):
        bar = self.verticalScrollBar()
        target = max(bar.minimum(), min(bar.maximum(), self._target() + dy))
        self._anim.stop()
        self._anim.setStartValue(bar.value())
        self._anim.setEndValue(target)
        self._anim.start()

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoomRequested.emit(1 if e.angleDelta().y() > 0 else -1)
            e.accept()
            return
        if not e.pixelDelta().isNull():  # trackpads are already smooth
            super().wheelEvent(e)
            return
        self.smooth_scroll_by(int(-e.angleDelta().y() / 120 * 110))
        e.accept()

    def keyPressEvent(self, e):
        bar = self.verticalScrollBar()
        k = e.key()
        shift = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        page = int(self.viewport().height() * 0.9)
        if k == Qt.Key.Key_PageDown or (k == Qt.Key.Key_Space and not shift):
            if self._target() >= bar.maximum() - 2:
                self.nextRequested.emit()
            else:
                self.smooth_scroll_by(page)
            return
        if k == Qt.Key.Key_PageUp or (k == Qt.Key.Key_Space and shift):
            if self._target() <= 0:
                self.prevRequested.emit()
            else:
                self.smooth_scroll_by(-page)
            return
        if k == Qt.Key.Key_Down:
            self.smooth_scroll_by(90)
            return
        if k == Qt.Key.Key_Up:
            self.smooth_scroll_by(-90)
            return
        super().keyPressEvent(e)

    # -- highlights / notes interaction ------------------------------------ #

    def note_at(self, pos: int):
        hits = [(end - start, nid) for nid, start, end in self.note_ranges if start <= pos < end]
        return min(hits)[1] if hits else None

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if (e.button() == Qt.MouseButton.LeftButton and not self.textCursor().hasSelection()
                and not self.anchorAt(e.pos())):
            self.positionClicked.emit(self.cursorForPosition(e.pos()).position())

    def contextMenuEvent(self, e):
        menu = QMenu(self)

        def add(target, text, fn):
            act = target.addAction(text)
            act.triggered.connect(lambda _=False: fn())

        nid = self.note_at(self.cursorForPosition(e.pos()).position())
        if self.textCursor().hasSelection():
            sub = menu.addMenu("Highlight")
            for name, hexv in HIGHLIGHT_COLORS.items():
                act = sub.addAction(swatch(hexv), name)
                act.triggered.connect(lambda _=False, n=name: self.highlightRequested.emit(n))
            add(menu, "Add note…", self.noteRequested.emit)
            add(menu, "Look up…", lambda: self.lookupRequested.emit(self.textCursor().selectedText()))
            menu.addSeparator()
            add(menu, "Copy", self.copy)
        elif nid is not None:
            add(menu, "Edit note…", lambda: self.editNoteRequested.emit(nid))
            add(menu, "Remove highlight", lambda: self.deleteNoteRequested.emit(nid))
        else:
            add(menu, "Select all", self.selectAll)
        menu.exec(e.globalPos())

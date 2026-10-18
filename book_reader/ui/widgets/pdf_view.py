"""PDF reading surface: continuous scroll, lazy page rendering, search hits."""
import bisect

from collections import OrderedDict

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QFrame, QMenu

from book_reader.core.pdf import fitz
from book_reader.themes import HIGHLIGHT_COLORS, THEMES
from book_reader.ui.helpers import swatch


class PdfView(QAbstractScrollArea):
    pageChanged = Signal()
    zoomChanged = Signal(float, bool)  # effective scale, fit-width mode
    selectionChanged = Signal(bool)    # text selected / cleared
    highlightRequested = Signal(str)   # colour name
    noteRequested = Signal()
    lookupRequested = Signal(str)
    markClicked = Signal(int)
    markEditRequested = Signal(int)
    markDeleteRequested = Signal(int)

    GAP = 16
    SIDE = 24
    MIN_ZOOM, MAX_ZOOM = 0.25, 4.0
    CACHE_BYTES = 300 * 1024 * 1024
    HIT_LIMIT = 500

    def __init__(self):
        super().__init__()
        self.setObjectName("pdfView")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.doc = None
        self.sizes: list[tuple[float, float]] = []   # page sizes in points
        self.tops: list[int] = []                    # page top y in document pixels
        self.max_w = 1.0
        self.content_w = 0
        self.scale = 1.0
        self.zoom = 1.0
        self.fit_width = True
        self.invert = False
        self.bg = QColor(THEMES["Light"]["desk"])
        self.cache: OrderedDict = OrderedDict()
        self.hits: list = []                         # (page, (x0, y0, x1, y1))
        self.hits_by_page: dict[int, list[int]] = {}
        self.hit_index = -1
        self._drag = None
        self.select_mode = False
        self.marks: dict[int, list] = {}      # page -> saved highlights
        self.sel: dict | None = None          # current selection {page, rects, text}
        self._sel_start = None
        self._press = None
        self._words: dict[int, list] = {}

        self._anim = QPropertyAnimation(self.verticalScrollBar(), b"value", self)
        self._anim.setDuration(230)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.horizontalScrollBar().valueChanged.connect(lambda _=0: self.viewport().update())

    # -- document ----------------------------------------------------------- #

    def set_document(self, doc, zoom: float = 0.0):
        self.clear()
        self.doc = doc
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.sizes = [(max(1.0, float(p.rect.width)), max(1.0, float(p.rect.height)))
                          for p in doc]
        finally:
            QApplication.restoreOverrideCursor()
        self.max_w = max((w for w, _ in self.sizes), default=1.0)
        self.fit_width = zoom <= 0
        self.zoom = zoom if zoom > 0 else 1.0
        self.relayout(keep_anchor=False)

    def clear(self):
        self._anim.stop()
        self.doc = None
        self.sizes, self.tops = [], []
        self.cache.clear()
        self._words.clear()
        self.sel, self._sel_start = None, None
        self.clear_hits()
        self.verticalScrollBar().setRange(0, 0)
        self.horizontalScrollBar().setRange(0, 0)
        self.viewport().update()

    # -- layout / geometry -------------------------------------------------- #

    def relayout(self, keep_anchor: bool = True):
        if not self.sizes:
            return
        anchor = self.position() if keep_anchor and self.tops else (0, 0.0)
        vw, vh = self.viewport().width(), self.viewport().height()
        if self.fit_width:
            self.scale = max(0.1, (vw - 2 * self.SIDE) / self.max_w)
        else:
            self.scale = self.zoom
        y, tops = self.GAP, []
        for _, h in self.sizes:
            tops.append(y)
            y += int(h * self.scale) + self.GAP
        self.tops = tops
        self.content_w = int(self.max_w * self.scale) + 2 * self.SIDE
        vbar, hbar = self.verticalScrollBar(), self.horizontalScrollBar()
        vbar.setPageStep(vh)
        vbar.setSingleStep(60)
        vbar.setRange(0, max(0, y - vh))
        hbar.setPageStep(vw)
        hbar.setSingleStep(40)
        hbar.setRange(0, max(0, self.content_w - vw))
        self.cache.clear()
        self.scroll_to(*anchor)
        self.viewport().update()
        self.zoomChanged.emit(self.scale, self.fit_width)
        self.pageChanged.emit()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.relayout()

    def position(self) -> tuple[int, float]:
        """(page index, fraction of that page scrolled past) at the top of the view."""
        if not self.tops:
            return 0, 0.0
        y = self.verticalScrollBar().value() + self.GAP
        i = max(0, bisect.bisect_right(self.tops, y) - 1)
        h = max(1.0, self.sizes[i][1] * self.scale)
        return i, max(0.0, min(1.0, (y - self.tops[i]) / h))

    def overall(self) -> float:
        bar = self.verticalScrollBar()
        if bar.maximum() > 0:
            return bar.value() / bar.maximum()
        return 1.0 if self.doc is not None else 0.0

    def scroll_to(self, page: int, frac: float = 0.0):
        if not self.tops:
            return
        page = max(0, min(len(self.tops) - 1, page))
        y = self.tops[page] + int(frac * self.sizes[page][1] * self.scale) - self.GAP
        self._anim.stop()
        self.verticalScrollBar().setValue(max(0, y))

    def jump_to_page(self, page: int):
        self.scroll_to(page, 0.0)

    def _on_scroll(self, _value):
        self.viewport().update()
        self.pageChanged.emit()

    # -- zoom --------------------------------------------------------------- #

    def set_zoom(self, z: float):
        self.fit_width = False
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, z))
        self.relayout()

    def zoom_by(self, factor: float):
        self.set_zoom(self.scale * factor)

    def set_fit_width(self):
        self.fit_width = True
        self.relayout()

    # -- rendering ---------------------------------------------------------- #

    def _pixmap(self, i: int):
        dpr = self.devicePixelRatioF()
        key = (i, round(self.scale * dpr, 3), self.invert)
        pm = self.cache.get(key)
        if pm is not None:
            self.cache.move_to_end(key)
            return pm
        try:
            s = self.scale * dpr
            pix = self.doc[i].get_pixmap(matrix=fitz.Matrix(s, s), alpha=False,
                                         colorspace=fitz.csRGB)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride,
                         QImage.Format.Format_RGB888).copy()
        except Exception:
            return None
        if self.invert:
            img.invertPixels()
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)
        self.cache[key] = pm
        while len(self.cache) > 3 and sum(
                p.width() * p.height() * 4 for p in self.cache.values()) > self.CACHE_BYTES:
            self.cache.popitem(last=False)
        return pm

    def paintEvent(self, e):
        p = QPainter(self.viewport())
        p.fillRect(e.rect(), self.bg)
        if self.doc is None or not self.tops:
            p.end()
            return
        y0 = self.verticalScrollBar().value()
        y1 = y0 + self.viewport().height()
        cw = max(self.content_w, self.viewport().width())
        xoff = self.horizontalScrollBar().value()
        first = max(0, bisect.bisect_right(self.tops, y0) - 1)
        for i in range(first, len(self.tops)):
            top = self.tops[i]
            if top > y1:
                break
            w, h = self.sizes[i]
            pw, ph = int(w * self.scale), int(h * self.scale)
            r = QRect((cw - pw) // 2 - xoff, top - y0, pw, ph)
            if r.bottom() < 0:
                continue
            p.fillRect(r.adjusted(3, 3, 3, 3), QColor(0, 0, 0, 45))
            pm = self._pixmap(i)
            if pm is not None:
                p.drawPixmap(r, pm)
            else:
                p.fillRect(r, QColor("white"))
            for idx in self.hits_by_page.get(i, ()):
                x0, ya, x1, yb = self.hits[idx][1]
                hr = QRectF(r.x() + x0 * self.scale, r.y() + ya * self.scale,
                            (x1 - x0) * self.scale, (yb - ya) * self.scale)
                p.fillRect(hr, QColor(255, 140, 0, 150) if idx == self.hit_index
                           else QColor(255, 213, 0, 100))
            for m in self.marks.get(i, ()):
                c = QColor(HIGHLIGHT_COLORS.get(m["color"], "#ffd54f"))
                c.setAlpha(105)
                for x0, ya, x1, yb in m["rects"]:
                    p.fillRect(QRectF(r.x() + x0 * self.scale, r.y() + ya * self.scale,
                                      (x1 - x0) * self.scale, (yb - ya) * self.scale), c)
            if self.sel and self.sel["page"] == i:
                for x0, ya, x1, yb in self.sel["rects"]:
                    p.fillRect(QRectF(r.x() + x0 * self.scale, r.y() + ya * self.scale,
                                      (x1 - x0) * self.scale, (yb - ya) * self.scale),
                               QColor(60, 120, 255, 90))
        p.end()

    # -- search ------------------------------------------------------------- #

    def clear_hits(self):
        self.hits, self.hits_by_page, self.hit_index = [], {}, -1
        self.viewport().update()

    def search(self, text: str) -> int:
        self.clear_hits()
        if not text or self.doc is None:
            return 0
        for i in range(self.doc.page_count):
            for r in self.doc[i].search_for(text):
                if len(self.hits) >= self.HIT_LIMIT:
                    break
                self.hits_by_page.setdefault(i, []).append(len(self.hits))
                self.hits.append((i, (r.x0, r.y0, r.x1, r.y1)))
            if len(self.hits) >= self.HIT_LIMIT:
                break
        self.viewport().update()
        return len(self.hits)

    def go_hit(self, step: int) -> int:
        if not self.hits:
            return -1
        n = len(self.hits)
        if self.hit_index < 0:
            self.hit_index = 0 if step >= 0 else n - 1
        else:
            self.hit_index = (self.hit_index + step) % n
        page, (_x0, y0, _x1, _y1) = self.hits[self.hit_index]
        y = self.tops[page] + int(y0 * self.scale) - self.viewport().height() // 3
        self._anim.stop()
        self.verticalScrollBar().setValue(max(0, y))
        self.viewport().update()
        return self.hit_index

    # -- smooth scrolling / input ------------------------------------------- #

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
        mods = e.modifiers()
        hbar = self.horizontalScrollBar()
        if mods & Qt.KeyboardModifier.ControlModifier:
            self.zoom_by(1.1 if e.angleDelta().y() > 0 else 1 / 1.1)
            e.accept()
            return
        if mods & Qt.KeyboardModifier.ShiftModifier:
            hbar.setValue(hbar.value() - e.angleDelta().y() // 2)
            e.accept()
            return
        if not e.pixelDelta().isNull():  # trackpad
            self._anim.stop()
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()
                                              - e.pixelDelta().y())
            hbar.setValue(hbar.value() - e.pixelDelta().x())
        else:
            if e.angleDelta().x():
                hbar.setValue(hbar.value() - e.angleDelta().x() // 2)
            self.smooth_scroll_by(int(-e.angleDelta().y() / 120 * 110))
        e.accept()

    def keyPressEvent(self, e):
        k = e.key()
        mods = e.modifiers()
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        page = int(self.viewport().height() * 0.9)
        hbar = self.horizontalScrollBar()
        if ctrl and k in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_by(1.15)
        elif ctrl and k == Qt.Key.Key_Minus:
            self.zoom_by(1 / 1.15)
        elif ctrl and k == Qt.Key.Key_0:
            self.set_fit_width()
        elif ctrl and k == Qt.Key.Key_C:
            self.copy_selection()
        elif k == Qt.Key.Key_Escape:
            self.clear_selection()
        elif k == Qt.Key.Key_PageDown or (k == Qt.Key.Key_Space and not shift):
            self.smooth_scroll_by(page)
        elif k == Qt.Key.Key_PageUp or (k == Qt.Key.Key_Space and shift):
            self.smooth_scroll_by(-page)
        elif k == Qt.Key.Key_Down:
            self.smooth_scroll_by(90)
        elif k == Qt.Key.Key_Up:
            self.smooth_scroll_by(-90)
        elif k == Qt.Key.Key_Home:
            self.smooth_scroll_by(-self._target())
        elif k == Qt.Key.Key_End:
            self.smooth_scroll_by(self.verticalScrollBar().maximum())
        elif k == Qt.Key.Key_Left:
            hbar.setValue(hbar.value() - 60)
        elif k == Qt.Key.Key_Right:
            hbar.setValue(hbar.value() + 60)
        else:
            super().keyPressEvent(e)

    # -- text selection & saved highlights ------------------------------------ #

    def set_select_mode(self, on: bool):
        """On: dragging selects text. Off: dragging pans the page."""
        self.select_mode = bool(on)
        self.clear_selection()
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor if on else Qt.CursorShape.ArrowCursor)

    def set_marks(self, marks: list[dict]):
        self.marks = {}
        for m in marks:
            self.marks.setdefault(m["spine_index"], []).append(m)
        self.viewport().update()

    def clear_selection(self):
        had = self.sel is not None
        self.sel = None
        self.viewport().update()
        if had:
            self.selectionChanged.emit(False)

    def selected_text(self) -> str:
        return self.sel["text"] if self.sel else ""

    def copy_selection(self):
        if self.sel:
            QApplication.clipboard().setText(self.sel["text"])

    def _to_page(self, pos, page=None):
        """Viewport point -> (page, x, y) in PDF points, clamped to the page."""
        if not self.tops:
            return None
        gy = pos.y() + self.verticalScrollBar().value()
        i = page if page is not None else max(0, bisect.bisect_right(self.tops, gy) - 1)
        w, h = self.sizes[i]
        cw = max(self.content_w, self.viewport().width())
        left = (cw - int(w * self.scale)) // 2 - self.horizontalScrollBar().value()
        x = (pos.x() - left) / self.scale
        y = (gy - self.tops[i]) / self.scale
        return i, max(0.0, min(w, x)), max(0.0, min(h, y))

    def _page_words(self, i: int) -> list:
        if i not in self._words:
            try:
                self._words[i] = self.doc[i].get_text("words")
            except Exception:
                self._words[i] = []
        return self._words[i]

    @staticmethod
    def _nearest_word(words, x, y) -> int:
        best, best_d = 0, float("inf")
        for k, w in enumerate(words):
            dx = max(w[0] - x, 0, x - w[2])
            dy = max(w[1] - y, 0, y - w[3])
            d = dx * dx + 4 * dy * dy
            if d < best_d:
                best, best_d = k, d
        return best

    def _update_selection(self, pos):
        """Select the words in reading order between the press point and `pos`."""
        page, x0, y0 = self._sel_start
        end = self._to_page(pos, page)
        words = self._page_words(page)
        if not words or end is None:
            self.sel = None
            return
        a = self._nearest_word(words, x0, y0)
        b = self._nearest_word(words, end[1], end[2])
        chosen = words[min(a, b):max(a, b) + 1]
        lines: dict = {}
        for w in chosen:  # one rectangle per text line
            r = lines.get((w[5], w[6]))
            lines[(w[5], w[6])] = ([w[0], w[1], w[2], w[3]] if r is None else
                                   [min(r[0], w[0]), min(r[1], w[1]), max(r[2], w[2]), max(r[3], w[3])])
        self.sel = dict(page=page, rects=[tuple(r) for r in lines.values()],
                        text=" ".join(w[4] for w in chosen))
        self.viewport().update()

    def _mark_at(self, pos):
        hit = self._to_page(pos)
        if hit is None:
            return None
        page, x, y = hit
        for m in self.marks.get(page, ()):
            for x0, y0, x1, y1 in m["rects"]:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return m
        return None

    def contextMenuEvent(self, e):
        menu = QMenu(self)
        mark = self._mark_at(e.pos())
        if self.sel:
            sub = menu.addMenu("Highlight")
            for name, hexv in HIGHLIGHT_COLORS.items():
                act = sub.addAction(swatch(hexv), name)
                act.triggered.connect(lambda _=False, n=name: self.highlightRequested.emit(n))
            menu.addAction("Add note…").triggered.connect(lambda: self.noteRequested.emit())
            menu.addAction("Look up…").triggered.connect(
                lambda: self.lookupRequested.emit(self.sel["text"] if self.sel else ""))
            menu.addAction("Copy").triggered.connect(self.copy_selection)
        elif mark is not None:
            mid = mark["id"]
            menu.addAction("Edit note…").triggered.connect(lambda: self.markEditRequested.emit(mid))
            menu.addAction("Remove highlight").triggered.connect(
                lambda: self.markDeleteRequested.emit(mid))
        elif not self.select_mode:
            hint = menu.addAction("Turn on “Select” in the toolbar to select text")
            hint.setEnabled(False)
        if not menu.isEmpty():
            menu.exec(e.globalPos())

    # -- mouse ---------------------------------------------------------------- #

    def mousePressEvent(self, e):
        self.setFocus()
        if e.button() != Qt.MouseButton.LeftButton:
            return
        self._anim.stop()
        self._press = e.position().toPoint()
        if self.select_mode:
            self._sel_start = self._to_page(self._press)
            if self.sel is not None:
                self.clear_selection()
        else:
            self._drag = self._press
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        pos = e.position().toPoint()
        if self._drag is not None:
            d = pos - self._drag
            self._drag = pos
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - d.y())
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - d.x())
        elif self._sel_start is not None:
            self._update_selection(pos)

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        pos = e.position().toPoint()
        moved = self._press is not None and (pos - self._press).manhattanLength() > 4
        if self._sel_start is not None:
            self._sel_start = None
            self.selectionChanged.emit(self.sel is not None)
        if not moved:
            mark = self._mark_at(pos)
            if mark is not None:
                self.markClicked.emit(mark["id"])
        self._drag = self._press = None
        self.viewport().setCursor(Qt.CursorShape.IBeamCursor if self.select_mode
                                  else Qt.CursorShape.ArrowCursor)

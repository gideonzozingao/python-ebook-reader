"""Mind map canvas: draggable nodes, curved branches, collapse, zoom, export."""
from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QPageLayout,
    QPageSize,
    QPainter,
    QPainterPath,
    QPdfWriter,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QInputDialog,
    QMenu,
    QMessageBox,
)

from book_reader.services.mindmap import LEVEL_GAP, MindMap, NODE_H
from book_reader.themes import THEMES
from book_reader.ui.helpers import swatch


PALETTE = ["#d0bcff", "#a8c7fa", "#a5d6a7", "#ffe082", "#ffab91", "#f48fb1", "#80deea", "#c5e1a5"]
DARK_TEXT = "#1d1b20"
TEXT_FLAGS = int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap)


class NodeItem(QGraphicsItem):
    PAD_X, PAD_Y, MAX_W = 14, 9, 230

    def __init__(self, view, node_id: int):
        super().__init__()
        self.view, self.node_id = view, node_id
        self.edges: list = []
        self._rect = QRectF(-40, -18, 80, 36)
        self._last = QPointF()
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                      | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
                      | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(2)
        self.refresh()

    @property
    def node(self):
        return self.view.mm.nodes[self.node_id]

    def refresh(self):
        """Recompute the size from the text and update the tooltip."""
        node = self.node
        fm = QFontMetricsF(self.view.font_for(node))
        box = fm.boundingRect(QRectF(0, 0, self.MAX_W, 10000), TEXT_FLAGS, node.text or " ")
        w, h = max(76.0, box.width() + 2 * self.PAD_X), box.height() + 2 * self.PAD_Y
        self.prepareGeometryChange()
        self._rect = QRectF(-w / 2, -h / 2, w, h)
        tip = []
        if node.detail:
            tip.append(node.detail)
        if node.ref:
            tip.append(f"📍 {node.ref}" + ("  (use “Go to source”)" if node.loc else ""))
        self.setToolTip("\n\n".join(tip))
        self.update()

    # -- geometry --------------------------------------------------------------- #

    def _is_left(self) -> bool:
        parent = self.node.parent
        return parent is not None and self.view.items_[parent].pos().x() > self.pos().x()

    def _badge_rect(self) -> QRectF:
        cx = self._rect.left() - 12 if self._is_left() else self._rect.right() + 12
        return QRectF(cx - 10, -10, 20, 20)

    def boundingRect(self) -> QRectF:
        return self._rect.adjusted(-26, -4, 26, 4)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(self._rect, 12, 12)
        if self.view.child_count.get(self.node_id) and self.node.parent is not None:
            path.addEllipse(self._badge_rect())
        return path

    # -- painting ----------------------------------------------------------------- #

    def paint(self, p, option, widget=None):
        v, node, r = self.view, self.node, self._rect
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill = QColor(v.color_of(node))
        radius = r.height() / 2 if node.parent is None else 12
        p.setBrush(fill)
        p.setPen(QPen(QColor(v.theme["accent"]), 3) if self.isSelected()
                 else QPen(fill.darker(125), 1.2))
        p.drawRoundedRect(r, radius, radius)
        p.setPen(QColor(v.text_color_of(node)))
        p.setFont(v.font_for(node))
        p.drawText(r.adjusted(self.PAD_X, self.PAD_Y, -self.PAD_X, -self.PAD_Y), TEXT_FLAGS,
                   node.text)
        if node.loc:  # small dot: this node remembers a place in the book
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(v.theme["accent"]))
            p.drawEllipse(QPointF(r.left() + 8, r.top() + 8), 3.5, 3.5)
        if node.parent is not None and v.child_count.get(self.node_id):
            b = self._badge_rect()
            p.setBrush(QColor(v.theme["panel"]))
            p.setPen(QPen(QColor(v.theme["outline"]), 1))
            p.drawEllipse(b)
            p.setPen(QColor(v.theme["fg"]))
            font = QFont(v.font())
            font.setPointSizeF(8)
            p.setFont(font)
            hidden = len(v.mm.descendants(self.node_id)) if node.collapsed else 0
            p.drawText(b, int(Qt.AlignmentFlag.AlignCenter), str(hidden) if node.collapsed else "−")

    # -- interaction ----------------------------------------------------------------- #

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.view.node_moved(self)
        return super().itemChange(change, value)

    def mousePressEvent(self, e):
        if (e.button() == Qt.MouseButton.LeftButton and self.node.parent is not None
                and self.view.child_count.get(self.node_id)
                and self._badge_rect().contains(e.pos())):
            self.view.toggle_collapse(self.node_id)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        self.view.positions_changed()

    def mouseDoubleClickEvent(self, e):
        self.view.edit_node(self.node_id)


class EdgeItem(QGraphicsPathItem):
    def __init__(self, view, parent_item: NodeItem, child_item: NodeItem):
        super().__init__()
        self.view, self.parent_item, self.child_item = view, parent_item, child_item
        self.setZValue(1)
        parent_item.edges.append(self)
        child_item.edges.append(self)
        self.update_path()

    def update_path(self):
        a, b = self.parent_item, self.child_item
        ap, bp = a.pos(), b.pos()
        right = bp.x() >= ap.x()
        x0 = ap.x() + (a._rect.right() if right else a._rect.left())
        x1 = bp.x() + (b._rect.left() if right else b._rect.right())
        dx = (x1 - x0) / 2
        path = QPainterPath(QPointF(x0, ap.y()))
        path.cubicTo(QPointF(x0 + dx, ap.y()), QPointF(x1 - dx, bp.y()), QPointF(x1, bp.y()))
        self.setPath(path)
        color = QColor(self.view.color_of(self.child_item.node)).darker(115)
        self.setPen(QPen(color, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))


class MindMapView(QGraphicsView):
    changed = Signal()                  # structure, text or positions changed
    jumpRequested = Signal(int, float)  # go to the node's source in the book

    def __init__(self):
        super().__init__()
        self.canvas = QGraphicsScene(self)
        self.setScene(self.canvas)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.mm: MindMap | None = None
        self.items_: dict[int, NodeItem] = {}
        self.edges_: dict[int, EdgeItem] = {}
        self.child_count: dict[int, int] = {}
        self.theme = THEMES["Light"]
        self.pin = None        # callable -> (loc dict | None, ref text) for new nodes
        self._moving = False
        self.set_theme(self.theme)

    # -- setup ---------------------------------------------------------------------- #

    def set_theme(self, theme: dict):
        self.theme = theme
        self.setBackgroundBrush(QColor(theme["bg"]))
        if self.mm:
            self.refresh_all()

    def font_for(self, node) -> QFont:
        font = QFont(self.font())
        font.setPointSizeF(12.5 if node.parent is None else 10.5)
        font.setBold(node.parent is None or self.mm.nodes[node.parent].parent is None)
        return font

    def color_of(self, node) -> str:
        n = node
        while True:
            if n.color >= 0:
                return PALETTE[n.color % len(PALETTE)]
            if n.parent is None:
                return self.theme["accent"]
            if self.mm.nodes[n.parent].parent is None:  # a top-level branch
                order = [c.id for c in self.mm.children(self.mm.root)]
                return PALETTE[order.index(n.id) % len(PALETTE)]
            n = self.mm.nodes[n.parent]

    def text_color_of(self, node) -> str:
        explicit = node.parent is None and node.color < 0
        return self.theme["on_accent"] if explicit else DARK_TEXT

    def set_map(self, mm: MindMap):
        self.mm = mm
        self.rebuild()
        self.fit()

    def _recount(self):
        self.child_count = {}
        for n in self.mm.nodes.values():
            if n.parent is not None:
                self.child_count[n.parent] = self.child_count.get(n.parent, 0) + 1

    def rebuild(self):
        self.canvas.clear()
        self.items_, self.edges_ = {}, {}
        self._recount()
        self._moving = True
        for n in self.mm.nodes.values():
            item = NodeItem(self, n.id)
            item.setPos(n.x, n.y)
            item._last = item.pos()
            self.canvas.addItem(item)
            self.items_[n.id] = item
        for n in self.mm.nodes.values():
            if n.parent is not None:
                edge = EdgeItem(self, self.items_[n.parent], self.items_[n.id])
                self.canvas.addItem(edge)
                self.edges_[n.id] = edge
        self._moving = False
        self._apply_visibility()

    def refresh_all(self):
        for item in self.items_.values():
            item.refresh()
        for edge in self.edges_.values():
            edge.update_path()
        self.canvas.update()

    def _apply_visibility(self):
        hidden: set = set()
        for n in self.mm.nodes.values():
            if n.collapsed:
                hidden.update(self.mm.descendants(n.id))
        for nid, item in self.items_.items():
            item.setVisible(nid not in hidden)
            if nid in self.edges_:
                self.edges_[nid].setVisible(nid not in hidden)
        for edge in self.edges_.values():
            edge.update_path()

    # -- node movement --------------------------------------------------------------- #

    def node_moved(self, item: NodeItem):
        if self._moving:
            item._last = item.pos()
            for e in item.edges:
                e.update_path()
            return
        delta = item.pos() - item._last
        item._last = item.pos()
        self._moving = True
        try:
            for nid in self.mm.descendants(item.node_id):  # branches move together
                child = self.items_[nid]
                child.setPos(child.pos() + delta)
                child._last = child.pos()
                for e in child.edges:
                    e.update_path()
        finally:
            self._moving = False
        for e in item.edges:
            e.update_path()

    def positions_changed(self):
        if not self.mm:
            return
        for nid, item in self.items_.items():
            self.mm.nodes[nid].x, self.mm.nodes[nid].y = item.pos().x(), item.pos().y()
        self.changed.emit()

    def relayout(self):
        self.mm.auto_layout()
        self._moving = True
        for nid, item in self.items_.items():
            n = self.mm.nodes[nid]
            item.setPos(n.x, n.y)
            item._last = item.pos()
        self._moving = False
        for edge in self.edges_.values():
            edge.update_path()
        self.changed.emit()
        self.fit()

    # -- selection / editing ------------------------------------------------------------ #

    def selected_id(self) -> int | None:
        sel = [i for i in self.canvas.selectedItems() if isinstance(i, NodeItem)]
        return sel[0].node_id if sel else None

    def select(self, nid: int):
        self.canvas.clearSelection()
        if nid in self.items_:
            self.items_[nid].setSelected(True)
            self.ensureVisible(self.items_[nid])

    def _new_node_position(self, parent_id: int, siblings: int) -> tuple[float, float]:
        parent = self.mm.nodes[parent_id]
        side = 1 if parent.x > 0 else -1 if parent.x < 0 else (1 if siblings % 2 == 0 else -1)
        others = [c for c in self.mm.children(parent_id)]
        y = max([c.y for c in others], default=parent.y - NODE_H) + NODE_H
        if parent_id == self.mm.root:
            y = parent.y + (siblings // 2) * NODE_H * (1 if siblings % 4 < 2 else -1)
        return parent.x + side * LEVEL_GAP, y

    def add_child(self, parent_id: int | None = None):
        if not self.mm:
            return
        parent_id = parent_id if parent_id is not None else (self.selected_id() or self.mm.root)
        loc, ref = self.pin() if self.pin else (None, "")
        node = self.mm.add_child(parent_id, "New idea", loc=loc, ref=ref)
        node.x, node.y = self._new_node_position(parent_id, len(self.mm.children(parent_id)) - 1)
        self.mm.nodes[parent_id].collapsed = False
        self.rebuild()
        self.select(node.id)
        self.changed.emit()
        self.edit_node(node.id)

    def add_sibling(self):
        nid = self.selected_id()
        if nid is None or self.mm.nodes[nid].parent is None:
            return self.add_child(self.mm.root if nid is None else nid)
        loc, ref = self.pin() if self.pin else (None, "")
        node = self.mm.add_sibling(nid, "New idea", loc=loc, ref=ref)
        anchor = self.mm.nodes[nid]
        node.x, node.y = anchor.x, anchor.y + NODE_H
        self.rebuild()
        self.select(node.id)
        self.changed.emit()
        self.edit_node(node.id)

    def edit_node(self, nid: int | None = None):
        nid = nid if nid is not None else self.selected_id()
        if nid is None:
            return
        node = self.mm.nodes[nid]
        text, ok = QInputDialog.getMultiLineText(self, "Edit idea", "Text:", node.text)
        if ok and text.strip() and text.strip() != node.text:
            node.text = text.strip()
            self.items_[nid].refresh()
            for e in self.items_[nid].edges:
                e.update_path()
            self.changed.emit()

    def edit_details(self):
        nid = self.selected_id()
        if nid is None:
            return
        node = self.mm.nodes[nid]
        text, ok = QInputDialog.getMultiLineText(self, "Details", "Longer note for this idea "
                                                 "(shown as a tooltip):", node.detail)
        if ok:
            node.detail = text.strip()
            self.items_[nid].refresh()
            self.changed.emit()

    def delete_selected(self):
        nid = self.selected_id()
        if nid is None or self.mm.nodes[nid].parent is None:
            return
        count = len(self.mm.descendants(nid))
        if count and QMessageBox.question(
                self, "Delete idea", f"Delete this idea and its {count} sub-idea"
                f"{'' if count == 1 else 's'}?") != QMessageBox.StandardButton.Yes:
            return
        self.mm.remove(nid)
        self.rebuild()
        self.changed.emit()

    def toggle_collapse(self, nid: int | None = None):
        nid = nid if nid is not None else self.selected_id()
        if nid is None or not self.child_count.get(nid) or self.mm.nodes[nid].parent is None:
            return
        node = self.mm.nodes[nid]
        node.collapsed = not node.collapsed
        self._apply_visibility()
        self.items_[nid].update()
        self.changed.emit()

    def set_color(self, index: int):
        nid = self.selected_id()
        if nid is not None:
            self.mm.nodes[nid].color = index
            self.refresh_all()
            self.changed.emit()

    def jump_to_source(self):
        nid = self.selected_id()
        loc = self.mm.nodes[nid].loc if nid is not None else None
        if loc:
            self.jumpRequested.emit(int(loc["i"]), float(loc["r"]))

    # -- view ------------------------------------------------------------------------------ #

    def fit(self):
        rect = self.canvas.itemsBoundingRect().adjusted(-40, -40, 40, 40)
        if rect.isEmpty():
            return
        self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        if self.transform().m11() > 1.4:
            self.resetTransform()
            self.scale(1.4, 1.4)
            self.centerOn(rect.center())

    def zoom_by(self, factor: float):
        new = self.transform().m11() * factor
        if 0.1 <= new <= 3.0:
            self.scale(factor, factor)

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_by(1.12 if e.angleDelta().y() > 0 else 1 / 1.12)
            e.accept()
        else:
            super().wheelEvent(e)

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Tab:
            self.add_child()
        elif k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.add_sibling()
        elif k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_selected()
        elif k == Qt.Key.Key_F2:
            self.edit_node()
        elif k == Qt.Key.Key_Space:
            self.toggle_collapse()
        elif k in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_by(1.15)
        elif k == Qt.Key.Key_Minus:
            self.zoom_by(1 / 1.15)
        elif k == Qt.Key.Key_0:
            self.fit()
        else:
            super().keyPressEvent(e)

    def contextMenuEvent(self, e):
        item = self.itemAt(e.pos())
        while item is not None and not isinstance(item, NodeItem):
            item = item.parentItem()
        menu = QMenu(self)
        if item is None:
            menu.addAction("Add idea to the centre").triggered.connect(
                lambda: self.add_child(self.mm.root))
            menu.addAction("Auto layout").triggered.connect(self.relayout)
            menu.addAction("Fit to window").triggered.connect(self.fit)
        else:
            self.select(item.node_id)
            node = item.node
            menu.addAction("Add sub-idea  (Tab)").triggered.connect(lambda: self.add_child())
            if node.parent is not None:
                menu.addAction("Add sibling  (Enter)").triggered.connect(self.add_sibling)
            menu.addAction("Edit text  (F2)").triggered.connect(lambda: self.edit_node())
            menu.addAction("Edit details…").triggered.connect(self.edit_details)
            colors = menu.addMenu("Colour")
            colors.addAction("Automatic").triggered.connect(lambda: self.set_color(-1))
            for i, hexv in enumerate(PALETTE):
                colors.addAction(swatch(hexv), hexv).triggered.connect(
                    lambda _=False, k=i: self.set_color(k))
            if self.child_count.get(node.id) and node.parent is not None:
                menu.addAction("Expand" if node.collapsed else "Collapse").triggered.connect(
                    lambda: self.toggle_collapse())
            if node.loc:
                menu.addSeparator()
                menu.addAction("Go to source in the book").triggered.connect(self.jump_to_source)
            if node.parent is not None:
                menu.addSeparator()
                menu.addAction("Delete").triggered.connect(self.delete_selected)
        menu.exec(e.globalPos())

    # -- export ------------------------------------------------------------------------------ #

    def _content_rect(self) -> QRectF:
        return self.canvas.itemsBoundingRect().adjusted(-30, -30, 30, 30)

    def export_png(self, path: str, scale: float = 2.0):
        self.canvas.clearSelection()
        rect = self._content_rect()
        image = QImage(int(rect.width() * scale), int(rect.height() * scale),
                       QImage.Format.Format_ARGB32)
        image.fill(QColor(self.theme["bg"]))
        p = QPainter(image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.canvas.render(p, QRectF(image.rect()), rect)
        p.end()
        if not image.save(path):
            raise OSError(f"Could not write {path}")

    def export_pdf(self, path: str):
        self.canvas.clearSelection()
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageOrientation(QPageLayout.Orientation.Landscape)
        writer.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Unit.Millimeter)
        p = QPainter(writer)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(0, 0, writer.width(), writer.height(), QColor(self.theme["bg"]))
        self.canvas.render(p, QRectF(0, 0, writer.width(), writer.height()),
                           self._content_rect(), Qt.AspectRatioMode.KeepAspectRatio)
        p.end()

    def export_svg(self, path: str):
        from PySide6.QtSvg import QSvgGenerator  # optional module
        self.canvas.clearSelection()
        rect = self._content_rect()
        svg = QSvgGenerator()
        svg.setFileName(path)
        svg.setSize(rect.size().toSize())
        svg.setViewBox(QRectF(0, 0, rect.width(), rect.height()))
        p = QPainter(svg)
        p.fillRect(QRectF(0, 0, rect.width(), rect.height()), QColor(self.theme["bg"]))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.canvas.render(p, QRectF(0, 0, rect.width(), rect.height()), rect)
        p.end()

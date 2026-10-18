"""Shared Qt helpers: colour swatches, shortcuts, card sizing inside scroll areas."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QWidget


def swatch(hex_color: str) -> QIcon:
    pm = QPixmap(14, 14)
    pm.fill(QColor(hex_color))
    return QIcon(pm)


def make_shortcut(parent: QWidget, key: str, slot):
    sc = QShortcut(QKeySequence(key), parent,
                   context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
    sc.activated.connect(slot)
    return sc


def fit_cards(scroll, vbox, kinds):
    """Give word-wrapped cards the height their text needs at the current panel width
    (layouts inside scroll areas otherwise squash them)."""
    m = vbox.contentsMargins()
    width = scroll.viewport().width() - m.left() - m.right() - 14
    if width < 80:
        return
    for i in range(vbox.count()):
        card = vbox.itemAt(i).widget()
        if isinstance(card, kinds):
            card.setMinimumHeight(0)
            lay = card.layout()
            h = max(card.heightForWidth(width), lay.totalHeightForWidth(width),
                    card.sizeHint().height(), card.minimumSizeHint().height())
            card.setMinimumHeight(h)
    vbox.invalidate()
    holder = scroll.widget()
    if holder is not None:  # scroll areas don't grow their content past the viewport by themselves
        holder.setMinimumHeight(vbox.totalMinimumSize().height())

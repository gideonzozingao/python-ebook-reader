"""Mini interface picture used on the colour cards of the appearance picker."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap


def _mix(a: str, b: str, t: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    return QColor(round(ca.red() + (cb.red() - ca.red()) * t), round(ca.green() + (cb.green() - ca.green()) * t),
                  round(ca.blue() + (cb.blue() - ca.blue()) * t))


def make_theme_preview(p: dict, w: int = 132, h: int = 84) -> QPixmap:
    """A tiny mock-up of the app (sidebar, panel, tile, text, slider) painted in palette `p`."""
    pm = QPixmap(w, h)
    pm.fill(Qt.GlobalColor.transparent)
    g = QPainter(pm)
    g.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 11, 11)
    g.setClipPath(clip)
    g.fillRect(0, 0, w, h, QColor(p["bg"]))
    g.setPen(Qt.PenStyle.NoPen)
    g.setBrush(QColor(p["outline"]))                      # sidebar: selected pill + menu lines
    g.setBrush(_mix(p["bg"], p["outline"], 0.55))
    g.drawRoundedRect(QRectF(9, 10, 30, 9), 4.5, 4.5)
    g.setBrush(_mix(p["bg"], p["outline"], 0.35))
    for k, width in enumerate((22, 26, 18)):
        g.drawRoundedRect(QRectF(9, 26 + k * 8, width, 3.5), 1.75, 1.75)
    g.setBrush(QColor(p["panel"]))                        # main panel
    g.drawRoundedRect(QRectF(46, 8, w - 54, h - 30), 9, 9)
    g.setBrush(_mix(p["accent"], p["panel"], 0.35 if p["bg"] < "#808080" else 0.15))   # accent tile
    g.drawRoundedRect(QRectF(54, 15, 24, 24), 6.5, 6.5)
    g.setBrush(QColor(p["fg"]))                           # two text lines
    g.drawRoundedRect(QRectF(85, 19, 26, 4.5), 2.2, 2.2)
    g.drawRoundedRect(QRectF(85, 28, 18, 4.5), 2.2, 2.2)
    track = QRectF(50, h - 14, w - 62, 3.2)               # slider
    g.setBrush(QColor(p["border"]))
    g.drawRoundedRect(track, 1.6, 1.6)
    g.setBrush(QColor(p["accent"]))
    g.drawRoundedRect(QRectF(track.x(), track.y(), track.width() * 0.55, track.height()), 1.6, 1.6)
    g.drawEllipse(QPointF(track.x() + track.width() * 0.55, track.center().y()), 5, 5)
    g.setClipping(False)
    g.setBrush(Qt.BrushStyle.NoBrush)
    g.setPen(QPen(QColor(p["border"]), 1))
    g.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 11, 11)
    g.end()
    return pm

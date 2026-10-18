"""Book cover thumbnail rendering."""
import textwrap
import zlib

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QTextOption,
)

from book_reader.constants import COVER_H, COVER_W


def make_cover(title: str, author: str, cover_path: str, progress: float = 0.0,
               reading: bool = False) -> QPixmap:
    """Rounded cover thumbnail: the real cover, or a generated one."""
    pm = QPixmap(COVER_W, COVER_H)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, COVER_W, COVER_H, 16, 16)
    p.setClipPath(clip)

    src = QPixmap()
    if cover_path and Path(cover_path).exists():
        src.loadFromData(Path(cover_path).read_bytes())
    if not src.isNull():
        scaled = src.scaled(
            COVER_W, COVER_H,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        p.drawPixmap((COVER_W - scaled.width()) // 2, (COVER_H - scaled.height()) // 2, scaled)
    else:
        hue = zlib.crc32(title.encode()) % 360
        grad = QLinearGradient(0, 0, COVER_W, COVER_H)
        grad.setColorAt(0, QColor.fromHsv(hue, 120, 190))
        grad.setColorAt(1, QColor.fromHsv((hue + 25) % 360, 160, 110))
        p.fillRect(0, 0, COVER_W, COVER_H, grad)
        p.setPen(QColor("white"))
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        p.setFont(font)
        opt = QTextOption(Qt.AlignmentFlag.AlignCenter)
        p.drawText(QRectF(14, 20, COVER_W - 28, COVER_H - 90),
                   textwrap.shorten(title, 60, placeholder="…"), opt)
        font.setBold(False)
        font.setPointSize(9)
        p.setFont(font)
        p.drawText(QRectF(14, COVER_H - 64, COVER_W - 28, 48),
                   textwrap.shorten(author, 40, placeholder="…"), opt)

    if progress > 0.005:  # thin progress bar along the bottom edge
        p.fillRect(0, COVER_H - 6, COVER_W, 6, QColor(0, 0, 0, 120))
        p.fillRect(0, COVER_H - 6, int(COVER_W * min(1.0, progress)), 6, QColor("#b69df8"))
    if reading:  # "currently reading" badge
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#f59e0b"))
        p.drawEllipse(COVER_W - 30, 8, 22, 22)
        p.setPen(QColor("white"))
        p.drawText(QRectF(COVER_W - 30, 8, 22, 22), Qt.AlignmentFlag.AlignCenter, "★")
    p.end()
    return pm


def make_collection_tile(name: str, rows) -> QPixmap:
    """Tile for a collection: a fan of up to three of its covers on a tinted card, with a count."""
    pm = QPixmap(COVER_W, COVER_H)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    clip = QPainterPath()
    clip.addRoundedRect(0, 0, COVER_W, COVER_H, 16, 16)
    p.setClipPath(clip)
    hue = zlib.crc32(name.lower().encode()) % 360
    grad = QLinearGradient(0, 0, COVER_W, COVER_H)
    grad.setColorAt(0, QColor.fromHsv(hue, 55, 238))
    grad.setColorAt(1, QColor.fromHsv((hue + 25) % 360, 95, 205))
    p.fillRect(0, 0, COVER_W, COVER_H, grad)

    w, h = 84, 124
    shown = list(rows[:3])
    for k in range(len(shown) - 1, -1, -1):  # back to front so the first book is on top
        r = shown[k]
        cover = make_cover(r["title"], r["author"], r["cover"]).scaled(
            w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        x, y = 16 + k * 24, 24 + (len(shown) - 1 - k) * 8
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 40))
        p.drawRoundedRect(QRectF(x + 2, y + 3, w, h), 8, 8)
        path = QPainterPath()
        path.addRoundedRect(QRectF(x, y, w, h), 8, 8)
        p.save()
        p.setClipPath(path)
        p.drawPixmap(x, y, cover)
        p.restore()
        p.setPen(QPen(QColor(255, 255, 255, 220), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(x, y, w, h), 8, 8)

    p.setPen(Qt.PenStyle.NoPen)  # count badge
    p.setBrush(QColor("#6750a4"))
    p.drawEllipse(COVER_W - 38, COVER_H - 38, 28, 28)
    p.setPen(QColor("white"))
    font = QFont()
    font.setBold(True)
    font.setPointSize(10)
    p.setFont(font)
    p.drawText(QRectF(COVER_W - 38, COVER_H - 38, 28, 28), Qt.AlignmentFlag.AlignCenter,
               str(len(rows)))
    p.end()
    return pm

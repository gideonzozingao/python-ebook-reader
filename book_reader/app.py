"""Application entry point."""
import sys

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from book_reader.constants import BOOK_EXTS
from book_reader.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    families = set(QFontDatabase.families())  # Material's typeface first, then platform UI fonts
    ui_font = next((f for f in ("Roboto", "Segoe UI Variable", "Segoe UI", "Inter", "Noto Sans")
                    if f in families), None)
    if ui_font:
        app.setFont(QFont(ui_font, 10))
    window = MainWindow()
    window.show()

    files = [a for a in sys.argv[1:]
             if Path(a).suffix.lower() in BOOK_EXTS and Path(a).exists()]
    if files:
        first_id = None
        for f in files:
            _, bid, _ = window.library.add_book(f)
            first_id = first_id or bid
        window.library_page.refresh()
        if first_id:
            window.open_book(first_id)
    else:
        QTimer.singleShot(400, window.show_reminder)

    sys.exit(app.exec())

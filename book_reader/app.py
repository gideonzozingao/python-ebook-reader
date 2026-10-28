"""Application entry point."""
import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

from book_reader.constants import BOOK_EXTS, DATA_DIR
from book_reader.ui.main_window import MainWindow

ASSETS = Path(__file__).parent / "assets"


def selftest() -> int:
    """Check that every dependency works. Used to verify the packaged .exe:

        BookReader.exe --self-test      (the report is saved to <data folder>/selftest.txt)
    """
    import importlib.util
    import tempfile
    import zipfile

    lines: list[str] = []

    def check(name, fn):
        try:
            lines.append(f"OK    {name}: {fn()}")
        except Exception as exc:  # report every failure instead of stopping at the first
            lines.append(f"FAIL  {name}: {exc!r}")

    def updater_check():
        from book_reader import __version__
        from book_reader.services import updater
        assert updater.is_newer("1.10.0", "1.9.9") and not updater.is_newer("1.0.0", __version__)
        return f"version {__version__}"

    def markdown_check():
        import markdown
        html = markdown.markdown("# T\n\n| a |\n|---|\n| 1 |\n\n```\ncode\n```\n- [x] done\n",
                                 extensions=["extra", "toc", "sane_lists", "nl2br"])
        assert "<table>" in html and "<pre>" in html
        return f"markdown {markdown.__version__}"

    def bs4_check():
        from bs4 import BeautifulSoup
        return BeautifulSoup("<p>x</p>", "html.parser").get_text()

    def pdf_check():
        from book_reader.core.pdf import fitz
        assert fitz is not None, "PyMuPDF is not bundled"
        doc = fitz.open()
        doc.new_page().insert_text((72, 100), "hello")
        assert "hello" in doc[0].get_text()
        return "PyMuPDF renders and reads text"

    def svg_check():
        svg = __import__("PySide6.QtSvg", fromlist=["QSvgGenerator"]).QSvgGenerator
        pdf = __import__("PySide6.QtGui", fromlist=["QPdfWriter"]).QPdfWriter
        return f"{svg.__name__} and {pdf.__name__} available"

    def books_check():
        from book_reader.core.epub import EpubBook
        from book_reader.core.markdown_book import MarkdownBook
        tmp = Path(tempfile.mkdtemp())
        (tmp / "a.md").write_text("# One\n\ntext\n\n## Two\n\nmore\n", encoding="utf-8")
        md = MarkdownBook(str(tmp / "a.md"))
        epub = tmp / "a.epub"
        with zipfile.ZipFile(epub, "w") as z:
            z.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="c.opf"/></rootfiles></container>')
            z.writestr("c.opf", '<package><metadata><dc:title>T</dc:title></metadata><manifest><item id="a" href="a.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="a"/></spine></package>')
            z.writestr("a.xhtml", "<html><body><p>x</p></body></html>")
        book = EpubBook(str(epub))
        book.close()
        return f"markdown sections={len(md.spine)}, epub spine={len(book.spine)}"

    check("python", lambda: sys.version.split()[0])
    check("markdown", markdown_check)
    check("beautifulsoup4", bs4_check)
    check("pymupdf", pdf_check)
    check("qt svg/pdf", svg_check)
    check("book parsers", books_check)
    check("updater", updater_check)
    check("voice dictation (optional)", lambda: "installed" if importlib.util.find_spec("speech_recognition")
          else "not installed (optional)")
    report = "\n".join(lines)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "selftest.txt").write_text(report + "\n", encoding="utf-8")
    print(report)
    return 1 if any(line.startswith("FAIL") for line in lines) else 0


def main():
    if "--self-test" in sys.argv:
        sys.exit(selftest())
    if sys.platform == "win32":  # own taskbar identity, so the icon is shown instead of Python's
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("BookReader.App")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setApplicationName("Book Reader")
    app.setStyle("Fusion")
    icon = ASSETS / "book_reader.ico"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
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

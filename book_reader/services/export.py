"""Writing a summary to disk (MD / HTML / TXT / PDF) and the export file dialog."""
from pathlib import Path

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import QFileDialog, QMessageBox

from book_reader.services.summary import SummaryBuilder
from book_reader.themes import THEMES


def write_summary_file(builder: SummaryBuilder, path: str, mode="Book section", topic="",
                       notes=True, highlights=True):
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        doc = QTextDocument()
        doc.setHtml(builder.render("rich", mode, topic, notes, highlights, THEMES["Light"]))
        writer = QPdfWriter(path)
        writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        writer.setPageMargins(QMarginsF(18, 18, 18, 18), QPageLayout.Unit.Millimeter)
        doc.print_(writer)
        return
    kind = {".md": "md", ".markdown": "md", ".txt": "txt"}.get(ext, "html")
    Path(path).write_text(builder.render(kind, mode, topic, notes, highlights),
                          encoding="utf-8")


def export_summary_dialog(parent, builder: SummaryBuilder, mode="Book section", topic="",
                          notes=True, highlights=True) -> bool:
    """Ask for a file name and export the notes. Returns True when a file was written."""
    safe = "".join(c for c in builder.title if c.isalnum() or c in " -_").strip() or "book"
    path, flt = QFileDialog.getSaveFileName(
        parent, "Export book notes", str(Path.home() / f"{safe} - notes.md"),
        "Markdown (*.md);;Web page (*.html);;Plain text (*.txt);;PDF document (*.pdf)")
    if not path:
        return False
    if Path(path).suffix.lower() not in (".md", ".markdown", ".html", ".htm", ".txt", ".pdf"):
        path += (".html" if "html" in flt else ".txt" if "txt" in flt
                 else ".pdf" if "pdf" in flt else ".md")
    try:
        write_summary_file(builder, path, mode, topic, notes, highlights)
    except Exception as exc:
        QMessageBox.critical(parent, "Export failed", str(exc))
        return False
    return True

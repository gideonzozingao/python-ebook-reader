"""Reads subject metadata from stored EPUB / PDF files."""
from book_reader.core.epub import EpubBook
from book_reader.core.markdown_book import MarkdownBook
from book_reader.core.pdf import fitz
from book_reader.utils import clean_subjects


def file_subjects(path, fmt: str) -> list[str]:
    """Subjects from a stored book's metadata (EPUB dc:subject, PDF subject/keywords)."""
    try:
        if fmt == "md":
            return clean_subjects(MarkdownBook(str(path)).subjects)
        if fmt == "pdf":
            if fitz is None:
                return []
            doc = fitz.open(str(path))
            try:
                meta = doc.metadata or {}
            finally:
                doc.close()
            return clean_subjects([meta.get("subject") or "", meta.get("keywords") or ""])
        book = EpubBook(str(path))
        try:
            return clean_subjects(book.subjects)
        finally:
            book.close()
    except Exception:
        return []

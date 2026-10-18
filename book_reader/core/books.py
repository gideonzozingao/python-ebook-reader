"""Choosing the right reader class for a stored book."""
from pathlib import Path

from book_reader.constants import MARKDOWN_EXTS
from book_reader.core.epub import EpubBook
from book_reader.core.markdown_book import MarkdownBook


def format_of(path) -> str:
    """'pdf', 'md' or 'epub' from a file name."""
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    return "md" if suffix in MARKDOWN_EXTS else "epub"


def open_text_book(path: str, fmt: str, title_hint: str = ""):
    """EpubBook or MarkdownBook (both offer spine, toc, render_chapter, search, ...)."""
    if fmt == "md":
        return MarkdownBook(path, title_hint)
    return EpubBook(path)

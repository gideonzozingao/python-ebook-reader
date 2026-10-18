#!/usr/bin/env python3
"""Book Reader launcher.

Install:   pip install PySide6-Essentials beautifulsoup4 pymupdf
Run:       python epub_reader2.py [book.epub|book.pdf ...]
           (or: python -m book_reader [book.epub|book.pdf ...])

Your library lives in ~/.epub_reader (override with the EPUB_READER_HOME
environment variable). Existing libraries are migrated automatically.
"""
from book_reader.app import main

if __name__ == "__main__":
    main()

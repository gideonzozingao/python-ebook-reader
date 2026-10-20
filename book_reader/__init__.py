"""Book Reader — EPUB + PDF library, notes & highlights, book journal, reading-time tracking.

Package layout
    constants.py, themes.py, utils.py      shared constants, Material Design 3 themes, helpers
    core/       EPUB/PDF parsing, SQLite library, preferences, reading-time tracker
    services/   journal data model, summary building, export (no widgets except file dialogs)
    ui/         helpers, widgets, dialogs, pages and the main window
    app.py      application entry point

Formats: EPUB, PDF and Markdown (.md).
Features: library & catalogue (subjects, tags, collections, folders), EPUB + PDF reading,
find in book, bookmarks, highlights (PDF text selection too), dictionary look-up, book journal
with auto section/page references, summary + export, flashcards/quizzes, reading goals and
streaks, backup/restore, note tags/links/Markdown, cross-book note search, review inbox,
notes dashboard, Obsidian/Notion/Anki export, sync folder, voice dictation, mind maps (blank, from notes, from outlines).

Run with:  python -m book_reader   (or: python epub_reader2.py)
"""

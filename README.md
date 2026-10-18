# epub-reader

A feature-rich desktop e-book reader built with Python and PySide6 (Qt6). Supports EPUB, PDF, and Markdown files with an integrated library, note-taking, flashcards, mind maps, and reading statistics.

---

## Features

- **Multi-format support** — EPUB, PDF, and Markdown files
- **Book library** — SQLite-backed catalogue with covers, metadata, progress, and deduplication
- **Highlights & notes** — Color-coded text highlights with attached notes (EPUB/PDF)
- **Book journal** — Structured per-book notes tagged by topic, chapter, and progress
- **Bookmarks** — Named bookmarks at any position
- **Full-text search** — Find-in-book search bar for EPUB and Markdown
- **Summary & export** — Render and export notes/highlights to Markdown, HTML, plain text, or PDF
- **Flashcards** — Leitner spaced-repetition quiz system generated from your notes
- **Mind maps** — Auto-build or manually create mind maps linked to book locations
- **Reading goals & streaks** — Daily reading goal with streak tracking and session statistics
- **Themes** — Light, Sepia, and Dark modes (Material Design 3)
- **Backup & restore** — Full library backup to a ZIP file
- **Drag & drop** — Drop book files or folders directly onto the window

---

## Requirements

- **Python** 3.10 or newer
- **PySide6-Essentials** (Qt6 GUI)
- **beautifulsoup4** (EPUB/HTML parsing)
- **pymupdf** (PDF support — optional but recommended)
- **markdown** (Markdown file support — optional)

---

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd epub-reader
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
- **Windows (CMD):** `.venv\Scripts\activate.bat`
- **macOS / Linux:** `source .venv/bin/activate`

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Running the App

### Option A — Run directly with Python

```bash
python epub_reader2.py
```

Or as a module:

```bash
python -m book_reader
```

### Option B — Open a specific book at launch

```bash
python epub_reader2.py path/to/book.epub
```

### Option C — Windows batch file (automatic venv setup)

Double-click `open.bat` or run it from a terminal. It will:

1. Create a virtual environment at `C:\venv\epub` if one does not exist
2. Install all dependencies automatically
3. Launch the app without a console window

To launch with debug output visible:

```
open.bat /debug
```

To force-reinstall all dependencies:

```
open.bat /update
```

> **Note:** The batch file's virtual environment path (`C:\venv\epub`) and app directory are hardcoded. Edit `open.bat` if your paths differ.

---

## Usage

### Adding Books

- Click **Add Book** in the library toolbar, or
- Drag and drop EPUB, PDF, or Markdown files (or entire folders) onto the window.

Books are stored in the library database with their cover, metadata, and reading progress. Duplicates are detected automatically by file hash.

### Reading

- Click any book in the library to open it.
- Use the **table of contents** panel to jump between chapters/sections.
- Press **F11** to toggle fullscreen.
- The reading position and progress are saved automatically.

### Highlights & Notes

- **EPUB/Markdown** — Select text and choose a highlight color (Yellow, Green, Blue, Pink). Optionally attach a note.
- **PDF** — Draw a rectangle over text to highlight it.
- All highlights appear in the **Notes** side panel.

### Journal

Open the **Journal** panel to write free-form notes for the current book. Each note is tagged with topic, chapter, and reading progress automatically.

Available topics: General, Key Idea, Quote, Question, Action Item, To Look Up, Vocabulary.

### Flashcards

Open **Flashcards** from the reader toolbar. Cards are generated from your notes and highlights using a Leitner box system (5 boxes). Review cards on their due schedule to reinforce learning.

### Mind Map

Open **Mind Map** from the reader toolbar to visualize your notes spatially. You can auto-populate from existing notes or build one manually. Nodes link back to their source location in the book.

### Export / Summary

Open **Summary** from the reader toolbar to see all notes and highlights rendered together. Export to Markdown, HTML, plain text, or PDF.

### Reading Stats

Open **Stats** from the main toolbar to view reading time per book, daily reading chart, current streak, and goal progress.

### Backup & Restore

Go to **Settings → Backup** to create a full ZIP backup of your library (database + book files + covers). Restore from a backup at any time; a safety snapshot is created automatically before restoring.

---

## Data Storage

The library is stored in `~/.epub_reader/` by default. Override this with the environment variable `EPUB_READER_HOME`.

```
~/.epub_reader/
├── library.db        # SQLite database (books, notes, sessions, etc.)
├── books/            # Copies of imported book files (named by SHA1 hash)
├── covers/           # Extracted cover images
└── safety-backups/   # Auto-created snapshots before restore operations
```

User preferences (theme, font, font size, etc.) are stored via Qt's QSettings — the Windows Registry on Windows, `~/.config` on Linux/macOS.

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| F11 | Toggle fullscreen |
| Ctrl+F | Open find/search bar (EPUB/Markdown) |
| Left / Right arrows | Previous / Next chapter (EPUB) |

---

## Project Structure

```
epub-reader/
├── epub_reader2.py        # Top-level launch script
├── open.bat               # Windows launcher with auto-venv setup
├── requirements.txt       # Python dependencies
└── book_reader/
    ├── app.py             # Application entry point (main())
    ├── constants.py       # App-wide constants
    ├── themes.py          # Material Design 3 theme system
    ├── utils.py           # Shared utilities
    ├── core/              # Business logic (no Qt)
    │   ├── epub.py        # EPUB parsing and rendering
    │   ├── pdf.py         # PDF support via PyMuPDF
    │   ├── markdown_book.py  # Markdown document support
    │   ├── library.py     # SQLite library management
    │   ├── tracker.py     # Reading time tracking
    │   └── ...
    ├── services/          # Data models and services (no Qt)
    │   ├── flashcards.py  # Flashcard/quiz logic
    │   ├── mindmap.py     # Mind map data model
    │   ├── goals.py       # Reading goals and streaks
    │   ├── export.py      # Export logic
    │   └── ...
    └── ui/                # PySide6 UI components
        ├── main_window.py # Main application window
        ├── pages/         # Full-screen page views
        ├── widgets/       # Reusable widgets
        └── dialogs/       # Modal dialogs
```

---

## Troubleshooting

**PDF support not available**
Install PyMuPDF: `pip install pymupdf`

**Markdown files not loading**
Install the markdown package: `pip install markdown`

**App won't start on Windows**
Run `open.bat /debug` to see the full error output in a console window.

**Library location**
If you need to reset the library, delete `~/.epub_reader/library.db`. Book files in `~/.epub_reader/books/` will remain intact.

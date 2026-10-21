# Changelog

All notable changes to Zuqongsoft E-Book Reader are recorded here.
The format follows Keep a Changelog, and the project uses Semantic Versioning.

## [1.0.0] - 2026-10-21

First public release.

### Added

**Reading**

- EPUB, PDF and Markdown support in one app
- Table of contents navigation and fullscreen mode (F11)
- Automatic saving of reading position and progress
- Find-in-book search for EPUB and Markdown (Ctrl+F)
- Drag and drop of book files and folders onto the window

**Library**

- SQLite-backed catalogue with covers, metadata and progress
- Duplicate detection by file hash
- Full library backup to a ZIP file, with an automatic safety snapshot before any restore

**Notes and study**

- Colour-coded highlights with attached notes for EPUB, Markdown and PDF
- Per-book journal with entries tagged by topic, chapter and progress
- Named bookmarks
- Leitner spaced-repetition flashcards generated from notes
- Mind maps, built automatically or by hand, linked to book locations
- Summary view with export to Markdown, HTML, plain text and PDF

**Tracking**

- Daily reading goal, streaks and session statistics

**Appearance**

- Light, Dark and System modes, with System following Windows live
- Ten colour palettes (Lavender, Ocean, Teal, Forest, Sepia, Sunset, Rose, Midnight, Graphite, AMOLED) plus a Custom accent colour
- Live preview cards in the Appearance dialog
- "Fonts & reading" tab for interface font, reading font, size, line spacing, page width, justify and PDF invert
- Ctrl+, opens Appearance, and Ctrl+Shift+L flips between light and dark
- Saved themes from earlier builds carry over (for example, Sepia becomes Sepia in light mode)

**Windows packaging**

- `build_exe.bat` builds the program with PyInstaller, with options `/onefile`, `/console`, `/voice` and `/nopause`
- `build_installer.bat` builds the app and then the installer, with `/skipbuild` to reuse an existing build
- Inno Setup installer (`Zuqongsoft-EBook-Reader-Setup.exe`) with a Start-menu shortcut, an optional desktop shortcut, per-user install by default and an all-users option
- "Open with" entries for .epub, .pdf and .md files, without changing default apps
- Fixed installer ID, so later versions upgrade in place
- Windows file properties (company, product name, version) embedded in the .exe
- Self-test (`--self-test`) run after each build to catch missing dependencies

### Notes

- The installer and program are not code-signed, so Windows SmartScreen may warn on first run.
- Uninstalling leaves `%USERPROFILE%\.epub_reader` untouched, so books and notes are kept.
- Builds are 64-bit x64 only. Windows 11 on ARM runs them through emulation.

[1.0.0]: https://github.com/gideonzozingao/python-ebook-reader/releases/tag/v1.0.0

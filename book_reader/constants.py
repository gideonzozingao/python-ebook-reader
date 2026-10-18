"""Application-wide constants (paths, supported formats, defaults)."""
import os

from pathlib import Path


DATA_DIR = Path(os.environ.get("EPUB_READER_HOME", Path.home() / ".epub_reader"))
MARKDOWN_EXTS = {".md", ".markdown", ".mdown", ".mkd"}
BOOK_EXTS = {".epub", ".pdf"} | MARKDOWN_EXTS
IDLE_LIMIT = 300  # seconds without input after which the reading clock pauses
DEFAULT_TOPICS = ["General", "Key idea", "Quote", "Question", "Action item", "To look up",
                  "Vocabulary"]
DEFAULT_DAILY_GOAL_MIN = 20  # reading goal, minutes per day
COVER_W, COVER_H = 150, 220
SUMMARY_MODES = ["Book section", "Topic", "Date"]

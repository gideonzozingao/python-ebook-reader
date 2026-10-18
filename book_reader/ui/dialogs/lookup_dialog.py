"""Dictionary / web look-up for selected text."""
import webbrowser

from html import escape as esc

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout

from book_reader.services import dictionary


class _LookupWorker(QThread):
    finished_with = Signal(object, str)  # result (or None), error message

    def __init__(self, term: str):
        super().__init__()
        self.term = term

    def run(self):
        try:
            self.finished_with.emit(dictionary.lookup_word(self.term), "")
        except LookupError as exc:
            self.finished_with.emit(None, str(exc))
        except Exception as exc:  # never let a worker thread crash the app
            self.finished_with.emit(None, f"Look-up failed: {exc}")


class LookupDialog(QDialog):
    saveRequested = Signal(str)   # text to store as a book note

    def __init__(self, parent, term: str, theme: dict):
        super().__init__(parent)
        self.term, self.t, self.info = term, theme, None
        self.setWindowTitle(f"Look up — {term}")
        self.resize(520, 460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 16)
        lay.setSpacing(10)
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.setStyleSheet(f"QTextBrowser {{ background:{theme['bg']};"
                                f" border:1px solid {theme['border']}; border-radius:8px; }}")
        self.view.setHtml(f"<p style='color:{theme['muted']}'>Looking up “{esc(term)}”…</p>")
        lay.addWidget(self.view, 1)
        row = QHBoxLayout()
        for name, url in dictionary.web_links(term).items():
            b = QPushButton(name)
            b.clicked.connect(lambda _=False, u=url: webbrowser.open(u))
            row.addWidget(b)
        row.addStretch()
        self.btn_save = QPushButton("Save to book notes")
        self.btn_save.setObjectName("tonal")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save)
        close = QPushButton("Close")
        close.setObjectName("primary")
        close.clicked.connect(self.accept)
        row.addWidget(self.btn_save)
        row.addWidget(close)
        lay.addLayout(row)
        self.worker = _LookupWorker(term)
        self.worker.finished_with.connect(self._show)
        self.worker.start()

    def _show(self, info, error: str):
        t = self.t
        if info is None:
            self.view.setHtml(f"<p style='color:{t['muted']}'>{esc(error)}</p>")
            return
        self.info = info
        self.btn_save.setEnabled(True)
        parts = [f"<h2 style='margin-bottom:0'>{esc(info['word'])}</h2>"]
        if info["phonetic"]:
            parts.append(f"<p style='color:{t['muted']}; margin-top:0'>{esc(info['phonetic'])}</p>")
        for pos, defs in info["meanings"]:
            parts.append(f"<p style='margin-bottom:2px'><i>{esc(pos)}</i></p><ol style='margin-top:0'>")
            for definition, example in defs:
                parts.append(f"<li>{esc(definition)}")
                if example:
                    parts.append(f"<br><span style='color:{t['muted']}'><i>“{esc(example)}”</i></span>")
                parts.append("</li>")
            parts.append("</ol>")
        self.view.setHtml("".join(parts))

    def _save(self):
        if self.info:
            self.saveRequested.emit(dictionary.short_definition(self.info))
            self.btn_save.setEnabled(False)
            self.btn_save.setText("Saved")

    def done(self, result):
        self.worker.wait(7000)  # never destroy a running thread
        super().done(result)

"""'A new version is available' dialog: release notes and the three choices."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)


class UpdateDialog(QDialog):
    """After exec(), `choice` is "install", "skip" or "later"."""

    def __init__(self, parent, info, current: str, can_install: bool):
        super().__init__(parent)
        self.choice = "later"
        self.setWindowTitle("Update available")
        self.resize(520, 420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)

        head = QLabel(f"Book Reader {info.version} is available")
        head.setObjectName("h2")
        lay.addWidget(head)
        sub = QLabel(f"You have version {current}.")
        sub.setObjectName("muted")
        lay.addWidget(sub)

        if info.notes.strip():
            notes = QTextBrowser()
            notes.setOpenExternalLinks(True)
            notes.setMarkdown(info.notes)
            lay.addWidget(notes, 1)
        else:
            lay.addStretch(1)

        if not can_install:
            hint = QLabel("This copy can't update itself, so the button below opens the "
                          "download page instead.")
            hint.setObjectName("muted")
            hint.setWordWrap(True)
            lay.addWidget(hint)

        row = QHBoxLayout()
        self.btn_skip = QPushButton("Skip this version")
        self.btn_skip.setObjectName("link")
        self.btn_skip.clicked.connect(lambda: self._done("skip"))
        self.btn_later = QPushButton("Later")
        self.btn_later.setObjectName("tonal")
        self.btn_later.clicked.connect(lambda: self._done("later"))
        self.btn_install = QPushButton("Install and restart" if can_install else "Open download page")
        self.btn_install.setObjectName("primary")
        self.btn_install.setDefault(True)
        self.btn_install.clicked.connect(lambda: self._done("install"))
        row.addWidget(self.btn_skip)
        row.addStretch()
        row.addWidget(self.btn_later)
        row.addWidget(self.btn_install)
        lay.addLayout(row)

    def _done(self, choice: str):
        self.choice = choice
        self.accept()


class DownloadDialog(QDialog):
    """Progress window while the installer downloads.

    Deliberately not a QProgressDialog: a modal QProgressDialog runs the event loop inside
    setValue(), so the 'download finished' signal could close and delete it in the middle
    of an update. This one never re-enters the event loop."""
    canceled = Signal()

    def __init__(self, parent, text: str):
        super().__init__(parent)
        self._finished = False
        self.setWindowTitle("Updating Book Reader")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setMinimumWidth(400)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        self.label = QLabel(text)
        lay.addWidget(self.label)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        lay.addWidget(self.bar)
        row = QHBoxLayout()
        row.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("tonal")
        self.btn_cancel.clicked.connect(self._cancel)
        row.addWidget(self.btn_cancel)
        lay.addLayout(row)

    def set_progress(self, done, total):
        if total:
            self.bar.setRange(0, 100)
            self.bar.setValue(min(100, int(done * 100 / total)))
        else:
            self.bar.setRange(0, 0)   # size unknown: busy indicator

    def _cancel(self):
        if self._finished or not self.btn_cancel.isEnabled():
            return
        self.btn_cancel.setEnabled(False)
        self.label.setText("Cancelling…")
        self.canceled.emit()          # the window closes once the download has stopped

    def reject(self):                 # Esc or the window's close button
        self._cancel()

    def finish(self):
        self._finished = True
        self.accept()

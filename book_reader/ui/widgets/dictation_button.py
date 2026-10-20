"""Microphone button: speak, and the recognised text is inserted into a note."""
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QMessageBox, QToolButton

from book_reader.services import dictation


class _Worker(QThread):
    done = Signal(str, str)  # text, error message

    def run(self):
        try:
            self.done.emit(dictation.listen_once(), "")
        except dictation.DictationError as exc:
            self.done.emit("", str(exc))
        except Exception as exc:  # keep the app alive whatever the audio stack does
            self.done.emit("", f"Dictation failed: {exc}")


class DictationButton(QToolButton):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.worker: _Worker | None = None
        self.setText("🎤")
        self.setToolTip("Dictate: speak and the text is added to the note")
        self.clicked.connect(self._start)

    def _start(self):
        if not dictation.available():
            QMessageBox.information(self, "Dictation", dictation.INSTALL_HINT)
            return
        if self.worker is not None and self.worker.isRunning():
            return
        self.setText("● Listening…")
        self.setEnabled(False)
        self.worker = _Worker()
        self.worker.done.connect(self._finished)
        self.worker.start()

    def _finished(self, text: str, error: str):
        self.setText("🎤")
        self.setEnabled(True)
        if error:
            QMessageBox.warning(self, "Dictation", error)
        elif text:
            self.editor.insertPlainText(text + " ")
            self.editor.setFocus()

    def stop(self):
        if self.worker is not None:
            self.worker.wait(60000)

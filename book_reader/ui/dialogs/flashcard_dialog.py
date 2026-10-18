"""Review a book's notes as flashcards or quizzes (spaced repetition by Leitner boxes)."""
import random
import textwrap

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from book_reader.services import flashcards


class FlashcardDialog(QDialog):
    MODES = ["Flashcards", "Fill in the blank", "Where is this from?"]

    def __init__(self, parent, builder, theme: dict):
        super().__init__(parent)
        self.b, self.lib, self.bid = builder, builder.library, builder.book_id
        self.all_cards = flashcards.build_cards(builder.entries(), builder.fmt)
        self.sections = [c.chapter for c in self.all_cards if c.chapter]
        self.queue: list = []
        self.i = self.right = self.done_count = 0
        self.finished = False
        self.setWindowTitle("Review notes")
        self.resize(720, 580)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(12)
        head = QLabel(f"Review — {builder.title}")
        head.setObjectName("h2")
        head.setWordWrap(True)
        lay.addWidget(head)

        opts = QHBoxLayout()
        opts.addWidget(QLabel("Mode"))
        self.mode = QComboBox()
        self.mode.addItems(self.MODES)
        opts.addWidget(self.mode)
        self.only_due = QCheckBox("Only cards due")
        self.only_due.setChecked(True)
        opts.addWidget(self.only_due)
        opts.addStretch()
        self.progress = QLabel("")
        self.progress.setObjectName("muted")
        opts.addWidget(self.progress)
        lay.addLayout(opts)

        self.card = QFrame()
        self.card.setObjectName("sidePanel")
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(28, 24, 28, 24)
        cl.setSpacing(14)
        self.meta = QLabel("")
        self.meta.setObjectName("muted")
        self.meta.setWordWrap(True)
        self.prompt = QLabel("")
        self.prompt.setWordWrap(True)
        self.prompt.setTextFormat(Qt.TextFormat.PlainText)
        f = self.prompt.font()
        f.setPointSize(f.pointSize() + 3)
        self.prompt.setFont(f)
        self.answer = QLabel("")
        self.answer.setWordWrap(True)
        self.answer.setTextFormat(Qt.TextFormat.PlainText)
        self.answer.setStyleSheet(f"color:{theme['accent']};")
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type the missing word…")
        self.input.returnPressed.connect(self._check)
        self.feedback = QLabel("")
        self.feedback.setWordWrap(True)
        self.choice_box = QVBoxLayout()
        self.choice_box.setSpacing(8)
        for w in (self.meta, self.prompt, self.answer, self.input, self.feedback):
            cl.addWidget(w)
        cl.addLayout(self.choice_box)
        cl.addStretch()
        lay.addWidget(self.card, 1)

        row = QHBoxLayout()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        self.btn_show = self._button("Show answer", self._reveal, "primary")
        self.btn_again = self._button("Again", lambda: self._grade(False))
        self.btn_good = self._button("Got it", lambda: self._grade(True), "primary")
        self.btn_check = self._button("Check", self._check, "primary")
        self.btn_next = self._button("Next", self._next, "primary")
        row.addWidget(close)
        row.addStretch()
        for b in (self.btn_show, self.btn_again, self.btn_good, self.btn_check, self.btn_next):
            row.addWidget(b)
        lay.addLayout(row)

        self.mode.currentTextChanged.connect(lambda _=None: self._start())
        self.only_due.toggled.connect(lambda _=False: self._start())
        self._start()

    @staticmethod
    def _button(text, slot, name=""):
        b = QPushButton(text)
        if name:
            b.setObjectName(name)
        b.clicked.connect(lambda _=False: slot())
        return b

    # -- session ------------------------------------------------------------- #

    def _pool(self) -> list:
        mode = self.mode.currentText()
        cards = list(self.all_cards)
        if mode == "Fill in the blank":
            cards = [c for c in cards if c.cloze]
        elif mode == "Where is this from?":
            cards = [c for c in cards if c.chapter] if len(set(self.sections)) >= 2 else []
        if self.only_due.isChecked():
            states = self.lib.card_states(self.bid)
            cards = [c for c in cards if flashcards.is_due(states.get(c.key))]
        random.shuffle(cards)
        return cards

    def _hide_controls(self):
        for w in (self.btn_show, self.btn_again, self.btn_good, self.btn_check, self.btn_next,
                  self.answer, self.input):
            w.hide()
        self.feedback.setText("")
        while self.choice_box.count():
            item = self.choice_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _start(self):
        self.queue, self.i, self.right, self.done_count = self._pool(), 0, 0, 0
        self.finished = False
        if not self.queue:
            self._message("Nothing to review here." if not self.all_cards else
                          "No cards due for this mode. Untick “Only cards due” to practise "
                          "anyway, or add more notes.")
        else:
            self._show()

    def _message(self, text: str, restart: bool = False):
        self._hide_controls()
        self.progress.setText("")
        self.meta.setText("")
        self.prompt.setText(text)
        if restart:
            self.finished = True
            self.btn_next.setText("Study again")
            self.btn_next.show()

    def _show(self):
        c = self.queue[self.i]
        mode = self.mode.currentText()
        self._hide_controls()
        self.btn_next.setText("Next")
        self.progress.setText(f"Card {self.i + 1} of {len(self.queue)}")
        if mode == "Flashcards":
            self.meta.setText("")
            self.prompt.setText(c.front)
            self.btn_show.show()
        elif mode == "Fill in the blank":
            self.meta.setText(f"{c.topic}  ·  {c.ref}")
            self.prompt.setText(c.cloze)
            self.input.clear()
            self.input.show()
            self.input.setFocus()
            self.btn_check.show()
        else:
            self.meta.setText(c.topic)
            self.prompt.setText(f"Which section is this from?\n\n“{textwrap.shorten(c.text, 320, placeholder='…')}”")
            for option in flashcards.section_choices(c, self.sections):
                b = QPushButton(textwrap.shorten(option, 80, placeholder="…"))
                b.clicked.connect(lambda _=False, o=option, btn=b: self._pick(o, btn))
                self.choice_box.addWidget(b)

    def _reveal(self):
        c = self.queue[self.i]
        self.answer.setText(c.back)
        self.answer.show()
        self.btn_show.hide()
        self.btn_again.show()
        self.btn_good.show()

    def _check(self):
        if self.input.isHidden():
            return
        c = self.queue[self.i]
        ok = self.input.text().strip().lower() == c.answer.lower()
        self.input.hide()
        self.btn_check.hide()
        self.answer.setText(c.text)
        self.answer.show()
        self._record(ok, "✓ Correct" if ok else f"✗ The missing word was “{c.answer}”")

    def _pick(self, option: str, button):
        c = self.queue[self.i]
        ok = option == c.chapter
        for k in range(self.choice_box.count()):
            self.choice_box.itemAt(k).widget().setEnabled(False)
        button.setText(("✓ " if ok else "✗ ") + button.text())
        self._record(ok, "✓ Correct" if ok else f"✗ It is from “{c.chapter}” ({c.ref})")

    def _record(self, correct: bool, message: str):
        """Quiz modes: store the result and wait for Next."""
        self._save_progress(correct)
        self.feedback.setText(message)
        self.btn_next.show()

    def _grade(self, correct: bool):
        """Flashcards: store the result and move straight on."""
        self._save_progress(correct)
        self._next()

    def _save_progress(self, correct: bool):
        c = self.queue[self.i]
        box = self.lib.card_states(self.bid).get(c.key, (0, 0))[0]
        new_box, due = flashcards.schedule(box, correct)
        self.lib.set_card(self.bid, c.key, new_box, due)
        self.done_count += 1
        self.right += int(correct)

    def _next(self):
        if self.finished:
            self._start()
            return
        self.i += 1
        if self.i >= len(self.queue):
            pct = int(self.right / max(1, self.done_count) * 100)
            self._message(f"Session complete — {self.right} of {self.done_count} correct ({pct}%).\n\n"
                          "Cards you got right come back after a longer break; the others return "
                          "next session.", restart=True)
        else:
            self._show()

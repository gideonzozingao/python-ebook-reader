"""Small Markdown toolbar for a note editor: bold, italic, code, lists, tags, note links, voice."""
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QWidget

from book_reader.ui.widgets.dictation_button import DictationButton


class FormatBar(QWidget):
    def __init__(self, editor, link_picker=None):
        """`link_picker()` should return a [[note:ID|title]] string (or None) to insert."""
        super().__init__()
        self.editor, self.link_picker = editor, link_picker
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        actions = [("B", "Bold  **text**", lambda: self.wrap("**", "**")),
                   ("I", "Italic  *text*", lambda: self.wrap("*", "*")),
                   ("</>", "Code  `text`", lambda: self.wrap("`", "`")),
                   ("•", "Bulleted list", lambda: self.prefix("- ")),
                   ("❝", "Quote", lambda: self.prefix("> ")),
                   ("#", "Add a #tag", lambda: self.insert("#"))]
        if link_picker is not None:
            actions.append(("↗", "Link to another note", self.link_note))
        for text, tip, fn in actions:
            lay.addWidget(self._button(text, tip, fn))
        mic = DictationButton(editor)
        mic.setStyleSheet(self.STYLE)
        lay.addWidget(mic)
        self.mic = mic
        lay.addStretch()

    STYLE = "QToolButton { padding: 3px 9px; min-height: 16px; border-radius: 12px; }"

    def _button(self, text, tip, fn):
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tip)
        b.setStyleSheet(self.STYLE)
        b.clicked.connect(lambda _=False: fn())
        return b

    def insert(self, text: str):
        self.editor.textCursor().insertText(text)
        self.editor.setFocus()

    def wrap(self, before: str, after: str):
        c = self.editor.textCursor()
        if c.hasSelection():
            c.insertText(before + c.selectedText().replace("\u2029", "\n") + after)
        else:
            c.insertText(before + after)
            c.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, len(after))
            self.editor.setTextCursor(c)
        self.editor.setFocus()

    def prefix(self, mark: str):
        c = self.editor.textCursor()
        if c.hasSelection():
            lines = c.selectedText().replace("\u2029", "\n").split("\n")
            c.insertText("\n".join(mark + ln for ln in lines))
        else:
            c.movePosition(QTextCursor.MoveOperation.StartOfBlock)
            c.insertText(mark)
            self.editor.setTextCursor(c)
        self.editor.setFocus()

    def link_note(self):
        markup = self.link_picker() if self.link_picker else None
        if markup:
            self.insert(markup)

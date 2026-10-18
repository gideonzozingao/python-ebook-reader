"""Reader status bar: section, reading time, progress."""
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from book_reader.utils import fmt_duration


class StatusBar(QWidget):
    """Bottom bar: section label, session/total time, progress bar, percentage."""

    def __init__(self):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 6, 18, 8)
        self.left = QLabel("")
        self.left.setObjectName("muted")
        self.time = QLabel("")
        self.time.setObjectName("muted")
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.progress.setFixedSize(220, 5)
        self.pct = QLabel("")
        self.pct.setObjectName("muted")
        lay.addWidget(self.left, 1)
        lay.addWidget(self.time)
        lay.addSpacing(14)
        lay.addWidget(self.progress)
        lay.addWidget(self.pct)

    def set_progress(self, left: str, overall: float, detail: str):
        overall = max(0.0, min(1.0, overall))
        self.left.setText(left)
        self.progress.setValue(int(overall * 1000))
        self.pct.setText(f"{overall * 100:.1f}%   ·   {detail}")

    def set_time(self, session: float, total: float):
        self.time.setText(f"⏱ {fmt_duration(session, True)} this session"
                          f"  ·  {fmt_duration(total)} total")

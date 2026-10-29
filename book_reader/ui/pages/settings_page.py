"""Settings page (⚙ or Ctrl+,): colours and fonts, optional features, updates and backups.

Everything saves the moment you change it and is applied live. The page sits on top of an open
book without closing it; Back returns to where you were.
"""
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from book_reader import __version__
from book_reader.core import features
from book_reader.themes import THEMES
from book_reader.ui import updates
from book_reader.ui.widgets.appearance_panel import AppearancePanel

SECTIONS = ("Appearance", "Features", "Reading", "Updates", "Backup & restore")


class SettingsPage(QWidget):
    backRequested = Signal()
    prefsChanged = Signal()       # something that changes how the app looks or which features show
    backupRequested = Signal()
    restoreRequested = Signal()
    updatesRequested = Signal()

    def __init__(self, library, prefs):
        super().__init__()
        self.library, self.prefs = library, prefs
        self._syncing = True
        self._feature_boxes: dict[str, QCheckBox] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 14)
        root.setSpacing(10)

        top = QHBoxLayout()
        back = QPushButton("←  Back")
        back.setObjectName("tonal")
        back.setToolTip("Back to what you were doing (Esc)")
        back.clicked.connect(self.backRequested.emit)
        title = QLabel("Settings")
        title.setObjectName("h1")
        self.status = QLabel("")
        self.status.setObjectName("muted")
        top.addWidget(back)
        top.addSpacing(8)
        top.addWidget(title)
        top.addStretch()
        top.addWidget(self.status)
        root.addLayout(top)
        QShortcut(QKeySequence("Escape"), self, context=Qt.ShortcutContext.WidgetWithChildrenShortcut
                  ).activated.connect(self.backRequested.emit)
        self._status_timer = QTimer(self, singleShot=True, interval=7000)
        self._status_timer.timeout.connect(lambda: self.status.setText(""))

        body = QHBoxLayout()
        body.setSpacing(16)
        self.nav = QListWidget()
        self.nav.setFixedWidth(210)
        self.nav.setSpacing(2)
        self.nav.addItems(SECTIONS)
        self.stack = QStackedWidget()
        body.addWidget(self.nav)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)

        self.stack.addWidget(self._appearance_section())
        self.stack.addWidget(self._features_section())
        self.stack.addWidget(self._reading_section())
        self.stack.addWidget(self._updates_section())
        self.stack.addWidget(self._backup_section())
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)

        self._appearance_timer = QTimer(self, singleShot=True, interval=100)  # batch slider drags
        self._appearance_timer.timeout.connect(self.prefsChanged.emit)
        self.panel.changed.connect(self._appearance_timer.start)
        self._syncing = False
        self.refresh()

    def set_theme(self, t: dict):
        """Style the section list with the current theme."""
        self.nav.setStyleSheet(
            "QListWidget { background: transparent; border: none; outline: 0; }"
            f"QListWidget::item {{ padding: 10px 14px; border-radius: 10px; color: {t['fg']}; }}"
            f"QListWidget::item:hover {{ background: {t['sel']}; }}"
            f"QListWidget::item:selected {{ background: {t['sel']}; color: {t['accent']}; font-weight: 600; }}")

    # -- building blocks ------------------------------------------------------------------- #

    @staticmethod
    def _muted(text: str = "") -> QLabel:
        label = QLabel(text)
        label.setObjectName("muted")
        label.setWordWrap(True)
        return label

    def _section(self, title: str, intro: str = ""):
        """A scrollable section: returns (widget for the stack, layout to fill)."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(4, 4, 18, 12)
        lay.setSpacing(10)
        head = QLabel(title)
        head.setObjectName("h1")
        lay.addWidget(head)
        if intro:
            lay.addWidget(self._muted(intro))
        scroll.setWidget(inner)
        return scroll, lay

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("sidePanel")
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(6)
        return card, lay

    def _pref_check(self, text: str, key: str, restyle: bool = False) -> QCheckBox:
        box = QCheckBox(text)
        box.toggled.connect(lambda on, k=key: self._save(k, bool(on), restyle))
        return box

    def _save(self, key: str, value, restyle: bool = False):
        if self._syncing:
            return
        self.prefs.set(key, value)
        if restyle:
            self.prefsChanged.emit()

    # -- sections ------------------------------------------------------------------------- #

    def _appearance_section(self) -> QWidget:
        self.panel = AppearancePanel(self.prefs)
        self.panel.setMinimumSize(0, 0)   # it is built for a dialog; here the page decides the size
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.panel)
        return scroll

    def _features_section(self) -> QWidget:
        page, lay = self._section(
            "Features",
            "Switch optional features on or off. Turning one off only hides it: your notes, "
            "maps and reading history are kept, and it comes back as soon as you switch it on.")
        for f in features.FEATURES:
            card, c = self._card()
            title = f.title + (f"   ({f.shortcut})" if f.shortcut else "")
            box = self._pref_check(title, f"feature_{f.name}", restyle=True)
            font = box.font()
            font.setBold(True)
            box.setFont(font)
            c.addWidget(box)
            c.addWidget(self._muted(f.description))
            if f.name == "roadmap":
                self.roadmap_auto = self._pref_check(
                    "Open it automatically when I start a book I haven't read yet", "roadmap_on_open")
                c.addWidget(self.roadmap_auto)
                box.toggled.connect(self.roadmap_auto.setEnabled)
            self._feature_boxes[f.name] = box
            lay.addWidget(card)
        lay.addStretch()
        return page

    def _reading_section(self) -> QWidget:
        page, lay = self._section("Reading")
        card, c = self._card()
        row = QHBoxLayout()
        row.addWidget(QLabel("Daily reading goal"))
        row.addStretch()
        self.goal = QSpinBox()
        self.goal.setRange(1, 600)
        self.goal.setSuffix(" min")
        self.goal.valueChanged.connect(lambda v: self._save("daily_goal", int(v), restyle=True))
        row.addWidget(self.goal)
        c.addLayout(row)
        c.addWidget(self._muted("Used for the goal line in the library and the streaks in Reading Stats."))
        lay.addWidget(card)
        card, c = self._card()
        self.reminder = self._pref_check("Show the reading reminder when the app starts", "show_reminder")
        c.addWidget(self.reminder)
        c.addWidget(self._muted("It shows the last book you read and where you stopped, "
                                "with links to pick up again."))
        lay.addWidget(card)
        lay.addStretch()
        return page

    def _updates_section(self) -> QWidget:
        page, lay = self._section("Updates")
        card, c = self._card()
        self.auto_update = self._pref_check("Check for updates automatically", "auto_update_check")
        c.addWidget(self.auto_update)
        c.addWidget(self._muted("Checked quietly at start-up, at most once a day. Nothing is "
                                "installed without your say-so."))
        lay.addWidget(card)
        card, c = self._card()
        self.version_label = QLabel("")
        self.checked_label = self._muted()
        c.addWidget(self.version_label)
        c.addWidget(self.checked_label)
        row = QHBoxLayout()
        self.btn_check = QPushButton("Check for updates now")
        self.btn_check.setObjectName("primary")
        self.btn_check.clicked.connect(self.updatesRequested.emit)
        row.addWidget(self.btn_check)
        row.addStretch()
        c.addLayout(row)
        self.skipped_row = QWidget()
        s = QHBoxLayout(self.skipped_row)
        s.setContentsMargins(0, 0, 0, 0)
        self.skipped_label = self._muted()
        offer = QPushButton("Offer it again")
        offer.setObjectName("link")
        offer.clicked.connect(self._forget_skipped)
        s.addWidget(self.skipped_label, 1)
        s.addWidget(offer)
        c.addWidget(self.skipped_row)
        self.no_url_note = self._muted(
            "This copy of Book Reader has no update address set, so it cannot look for updates. "
            "(The publisher sets UPDATE_URL; see BUILD.md.)")
        c.addWidget(self.no_url_note)
        lay.addWidget(card)
        lay.addStretch()
        return page

    def _backup_section(self) -> QWidget:
        page, lay = self._section(
            "Backup & restore",
            "A backup is one .zip file with your whole library: books, notes, highlights, "
            "journal, mind maps and reading history.")
        card, c = self._card()
        self.last_backup = QLabel("")
        c.addWidget(self.last_backup)
        row = QHBoxLayout()
        b = QPushButton("Back up library…")
        b.setObjectName("primary")
        b.clicked.connect(self.backupRequested.emit)
        r = QPushButton("Restore from backup…")
        r.clicked.connect(self.restoreRequested.emit)
        row.addWidget(b)
        row.addWidget(r)
        row.addStretch()
        c.addLayout(row)
        c.addWidget(self._muted("Restoring replaces your current library. A safety copy of it is "
                                "saved first, so you can undo a restore."))
        link = QPushButton("Open the safety copies folder")
        link.setObjectName("link")
        link.clicked.connect(self._open_safety_folder)
        c.addWidget(link, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(card)
        lay.addStretch()
        return page

    # -- actions --------------------------------------------------------------------------- #

    def _forget_skipped(self):
        self.prefs.set("skipped_version", "")
        self.refresh()
        self.show_message("You will be told about that version again at the next check")

    def _open_safety_folder(self):
        folder = self.library.root / "safety-backups"
        if folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        else:
            self.show_message("No safety copies yet. They are made automatically before a restore")

    # -- state ------------------------------------------------------------------------------ #

    def show_section(self, name: str):
        if name in SECTIONS:
            self.nav.setCurrentRow(SECTIONS.index(name))

    def show_message(self, text: str):
        self.status.setText(text)
        self._status_timer.start()

    def refresh(self):
        """Show the current preferences (call whenever the page is opened)."""
        v = self.prefs.v
        self.set_theme(THEMES[v["theme"]])
        self._syncing = True
        try:
            self.panel.sync()
            for name, box in self._feature_boxes.items():
                box.setChecked(features.enabled(self.prefs, name))
            self.roadmap_auto.setChecked(bool(v["roadmap_on_open"]))
            self.roadmap_auto.setEnabled(features.enabled(self.prefs, "roadmap"))
            self.goal.setValue(int(v["daily_goal"]))
            self.reminder.setChecked(bool(v["show_reminder"]))
            self.auto_update.setChecked(bool(v["auto_update_check"]))
        finally:
            self._syncing = False
        configured = bool(updates.UPDATE_URL)
        self.version_label.setText(f"Book Reader {__version__}")
        last = float(v["last_update_check"] or 0)
        self.checked_label.setText(
            "Last checked: " + (datetime.fromtimestamp(last).strftime("%d %b %Y, %H:%M")
                                if last > 0 else "never"))
        self.checked_label.setVisible(configured)
        self.btn_check.setEnabled(configured)
        self.no_url_note.setVisible(not configured)
        skipped = str(v["skipped_version"] or "")
        self.skipped_row.setVisible(bool(skipped))
        self.skipped_label.setText(f"You chose to skip version {skipped}.")
        self.last_backup.setText("Last backup: " + (str(v["last_backup"]) or "never"))

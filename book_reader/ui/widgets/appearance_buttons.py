"""The toolbar buttons shared by every page: light/dark switch, Appearance dialog and Settings."""
from PySide6.QtWidgets import QToolButton


def appearance_buttons(page) -> list[QToolButton]:
    """`page` needs the signals modeToggleRequested, appearanceRequested and settingsRequested."""
    mode = QToolButton()
    mode.setText("◐")
    mode.setToolTip("Switch between light and dark mode (Ctrl+Shift+L)")
    mode.clicked.connect(lambda: page.modeToggleRequested.emit())
    aa = QToolButton()
    aa.setText("Aa")
    aa.setToolTip("Quick appearance: colours, mode and fonts")
    bold = aa.font()
    bold.setBold(True)
    aa.setFont(bold)
    aa.clicked.connect(lambda: page.appearanceRequested.emit())
    gear = QToolButton()
    gear.setText("⚙")
    gear.setToolTip("Settings: appearance, features, updates and backups (Ctrl+,)")
    gear.clicked.connect(lambda: page.settingsRequested.emit())
    return [mode, aa, gear]

"""The two toolbar buttons shared by every page: light/dark switch and the Appearance dialog."""
from PySide6.QtWidgets import QToolButton


def appearance_buttons(page) -> list[QToolButton]:
    """`page` needs the signals modeToggleRequested and appearanceRequested."""
    mode = QToolButton()
    mode.setText("◐")
    mode.setToolTip("Switch between light and dark mode (Ctrl+Shift+L)")
    mode.clicked.connect(lambda: page.modeToggleRequested.emit())
    aa = QToolButton()
    aa.setText("Aa")
    aa.setToolTip("Appearance: colours, mode and fonts (Ctrl+,)")
    bold = aa.font()
    bold.setBold(True)
    aa.setFont(bold)
    aa.clicked.connect(lambda: page.appearanceRequested.emit())
    return [mode, aa]

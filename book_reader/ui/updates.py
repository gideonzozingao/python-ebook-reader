"""Checks for new versions in the background and walks the user through installing one.

Nothing is ever installed without the user clicking "Install and restart"."""
import time

from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox

from book_reader import __version__
from book_reader.constants import UPDATE_URL
from book_reader.services import updater
from book_reader.ui.background import CANCELLED, Job
from book_reader.ui.dialogs.update_dialog import DownloadDialog, UpdateDialog

CHECK_EVERY = 24 * 3600   # seconds between automatic checks


class UpdateManager(QObject):
    checked = Signal()   # a check finished (found something, nothing, or failed)

    def __init__(self, window, prefs):
        super().__init__(window)
        self.win, self.prefs = window, prefs
        self._job = None
        self._manual = False
        self._progress = None
        self._info = None

    # -- entry points ------------------------------------------------------------------ #

    def check_on_startup(self):
        """Quietly, at most once a day, and only if the user has not turned it off."""
        updater.cleanup()
        if not UPDATE_URL or not self.prefs.v["auto_update_check"]:
            return
        if time.time() - float(self.prefs.v["last_update_check"]) < CHECK_EVERY:
            return
        self._check(manual=False)

    def check_now(self):
        """'Check for updates…' menu item: always says what happened."""
        if not UPDATE_URL:
            QMessageBox.information(
                self.win, "Check for updates",
                "Update checking is not set up in this copy of Book Reader.\n\n"
                "The publisher sets the update address (UPDATE_URL in constants.py; see BUILD.md).")
            return
        self._check(manual=True)

    # -- checking ----------------------------------------------------------------------- #

    def _check(self, manual: bool):
        if self._job is not None:
            return   # a check is already running
        self._manual = manual
        if manual:
            QApplication.setOverrideCursor(Qt.CursorShape.BusyCursor)
        self._job = Job(self, lambda job: updater.check(UPDATE_URL))
        self._job.done.connect(self._checked)
        self._job.start()

    def _checked(self, info, error: str):
        try:
            self._handle_check(info, error)
        finally:
            self.checked.emit()

    def _handle_check(self, info, error: str):
        self._job = None
        manual = self._manual
        if manual:
            QApplication.restoreOverrideCursor()
        if error:
            if manual:
                QMessageBox.warning(self.win, "Check for updates",
                                    f"Could not check for updates.\n\n{error}")
            return
        self.prefs.set("last_update_check", time.time())
        if info is None:
            if manual:
                QMessageBox.information(self.win, "Check for updates",
                                        f"You have the latest version of Book Reader ({__version__}).")
            return
        if not manual and info.version == self.prefs.v["skipped_version"]:
            return   # the user said "skip this version"
        self._offer(info)

    def _offer(self, info, tries: int = 0):
        if QApplication.activeModalWidget() is not None and tries < 20:
            # another dialog (e.g. the start-up reminder) is open: ask again in a moment
            QTimer.singleShot(15000, lambda: self._offer(info, tries + 1))
            return
        dlg = UpdateDialog(self.win, info, __version__, updater.installable(info))
        dlg.exec()
        choice = dlg.choice
        dlg.deleteLater()   # don't leave a hidden dialog behind for the rest of the session
        if choice == "skip":
            self.prefs.set("skipped_version", info.version)
        elif choice == "install":
            self._install(info)

    # -- installing --------------------------------------------------------------------- #

    def _install(self, info):
        if not updater.installable(info):
            target = info.page or info.url
            if target:
                QDesktopServices.openUrl(QUrl(target))
            return
        self._info = info
        dlg = DownloadDialog(self.win, f"Downloading Book Reader {info.version}…")
        job = Job(self, lambda j: updater.download(info, j.report, j.is_cancelled))
        job.progress.connect(self._on_progress)
        job.done.connect(self._downloaded)
        dlg.canceled.connect(job.cancel)
        self._progress, self._job = dlg, job
        dlg.open()
        job.start()

    def _on_progress(self, done, total):
        if self._progress is not None:
            self._progress.set_progress(done, total)

    def _downloaded(self, path, error: str):
        dlg, self._progress, self._job = self._progress, None, None
        if dlg is not None:
            dlg.finish()
            dlg.deleteLater()
        if error == CANCELLED:
            return
        info = self._info
        if error:
            box = QMessageBox(QMessageBox.Icon.Warning, "Update failed",
                              f"The update could not be installed.\n\n{error}", parent=self.win)
            ok = box.addButton(QMessageBox.StandardButton.Ok)
            web = box.addButton("Open download page", QMessageBox.ButtonRole.ActionRole) \
                if info and (info.page or info.url) else None
            box.exec()
            if web is not None and box.clickedButton() is web:
                QDesktopServices.openUrl(QUrl(info.page or info.url))
            return
        try:
            updater.launch_installer(path)
        except OSError as exc:
            QMessageBox.warning(self.win, "Update failed",
                                f"The update was downloaded but could not be started "
                                f"({exc}).\n\nYou can run it yourself:\n{path}")
            return
        self.win.close()                         # saves reading positions, closes books
        QTimer.singleShot(0, QApplication.quit)  # the installer takes over from here

"""Background worker so the startup update check never blocks the UI."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app.update_check import ReleaseInfo, check_for_update


class UpdateCheckWorker(QThread):
    update_found = Signal(object)  # ReleaseInfo

    def run(self) -> None:
        release: ReleaseInfo | None = check_for_update()
        if release is not None:
            self.update_found.emit(release)

"""Background worker that talks to the Fluke meter off the UI thread."""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from app import licensing
from fluke54 import FlukeMeter
from fluke54.models import LogSession


class DownloadWorker(QThread):
    succeeded = Signal(object)  # LogSession
    failed = Signal(str)

    def __init__(self, license_key: str | None, log_index: int = 1, parent=None):
        super().__init__(parent)
        self._license_key = license_key
        self._log_index = log_index

    def run(self) -> None:
        # Re-checked here, not just at the button, so this worker can never
        # be driven to talk to the meter through some other unlicensed path.
        if not licensing.is_licensed(self._license_key):
            self.failed.emit("No valid license for this machine. Activate one from the Settings tab.")
            return

        try:
            with FlukeMeter() as meter:
                session: LogSession = meter.download_memory(index=self._log_index)
            self.succeeded.emit(session)
        except Exception as e:  # noqa: BLE001 -- surface any failure to the UI, not fabricate success
            self.failed.emit(str(e))

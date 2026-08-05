"""Simulate clicking 'Download Profile' in the real UI and verify the graph,
stats, and recent-profiles list update correctly. Requires the meter in
'Ir SEnd' mode."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.theme import STYLESHEET  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()

    result = {"done": False, "failed_message": None}

    def on_finished():
        result["done"] = True

    window._download_button.clicked.connect(lambda: None)  # ensure signal wiring untouched
    window._on_download_clicked()
    window._worker.finished.connect(on_finished)

    deadline = time.monotonic() + 20.0
    while not result["done"] and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.05)

    if not result["done"]:
        print("TIMEOUT waiting for download to finish")
        return 1

    print(f"Meter status label: {window._meter_status_label.text()!r}")
    print(f"Peak: {window._peak_value_label.text()}  Exit: {window._exit_value_label.text()}  "
          f"Duration: {window._duration_value_label.text()}  Points: {window._points_value_label.text()}")
    print(f"Recent profiles count: {window._recent_list.count()}")
    print(f"Graph curves plotted: {len(window._graph._curves)}")

    window.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

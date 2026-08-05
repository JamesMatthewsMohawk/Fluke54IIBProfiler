"""Construct the main window without entering the event loop, to catch
import/runtime errors before a real interactive launch."""
from __future__ import annotations

import sys
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
    print("MainWindow constructed and shown without error.")
    print(f"Tunnels in combo: {[window._tunnel_combo.itemText(i) for i in range(window._tunnel_combo.count())]}")
    print(f"Recent runs listed: {window._recent_list.count()}")

    app.processEvents()
    window.close()
    print("Closed cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

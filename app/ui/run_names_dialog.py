"""Dialog to collect a tunnel name per run when a download bundles more than one.

The meter concatenates every run logged since the last clear/download into
a single QD response (see fluke54/parser.py's run-boundary marker), so a
download can come back holding more than one tunnel's data at once. Each
one needs its own tunnel name before it can be saved as a separate run.
"""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QVBoxLayout, QWidget


class RunNamesDialog(QDialog):
    def __init__(
        self,
        run_summaries: list[tuple[int, float, float]],
        default_first_tunnel: str,
        unit: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Name Each Detected Run")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        intro = QLabel(
            f"This download contains {len(run_summaries)} separate logged runs -- the "
            "meter was started and stopped more than once before this download. Give "
            "each one a tunnel name:"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._edits: list[QLineEdit] = []
        for i, (sample_count, lo, hi) in enumerate(run_summaries):
            caption = QLabel(f"Run {i + 1} — {sample_count} samples, {lo:.1f}–{hi:.1f}°{unit}")
            caption.setObjectName("SectionLabel")
            edit = QLineEdit(default_first_tunnel if i == 0 else "")
            edit.setPlaceholderText("e.g. 3 or Superba A")
            edit.textChanged.connect(self._update_ok_enabled)
            layout.addWidget(caption)
            layout.addWidget(edit)
            self._edits.append(edit)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self._update_ok_enabled()

    def _update_ok_enabled(self) -> None:
        all_named = all(edit.text().strip() for edit in self._edits)
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(all_named)

    def tunnel_names(self) -> list[str]:
        return [edit.text().strip() for edit in self._edits]

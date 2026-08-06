"""Point-and-click license key issuer -- packaged separately from the main
app (see LicenseKeyMaker.spec). Keep this off of any customer-facing
release; it's an internal tool for whoever holds license_signing_key.pem."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from license_key_logic import generate_keypair, has_signing_key, issue_key, private_key_path  # noqa: E402

try:
    from app.ui.theme import STYLESHEET  # noqa: E402
except ImportError:
    STYLESHEET = ""


def _card(*widgets: QWidget, title: str | None = None) -> QFrame:
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setSpacing(8)
    if title:
        label = QLabel(title)
        label.setObjectName("SectionLabel")
        layout.addWidget(label)
    for w in widgets:
        layout.addWidget(w)
    return frame


class LicenseKeyMakerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Superba Tunnel Profiler -- License Key Maker")
        self.resize(560, 420)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("License Key Maker")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        self._key_status_label = QLabel()
        self._key_path_label = QLabel(str(private_key_path()))
        self._key_path_label.setWordWrap(True)
        self._keygen_button = QPushButton("Generate Signing Key (one-time setup)")
        self._keygen_button.setObjectName("SecondaryButton")
        self._keygen_button.clicked.connect(self._on_keygen_clicked)
        layout.addWidget(_card(
            self._key_status_label, self._key_path_label, self._keygen_button,
            title="Signing Key",
        ))

        self._customer_edit = QLineEdit()
        self._customer_edit.setPlaceholderText("e.g. Bridgeport Plant (for your own records only)")
        self._machine_id_edit = QLineEdit()
        self._machine_id_edit.setPlaceholderText("Machine ID from the app's Settings tab")

        issue_button = QPushButton("Generate Key")
        issue_button.clicked.connect(self._on_issue_clicked)

        self._output_edit = QTextEdit()
        self._output_edit.setReadOnly(True)
        self._output_edit.setPlaceholderText("The generated key will appear here.")
        self._output_edit.setMaximumHeight(90)

        copy_button = QPushButton("Copy Key to Clipboard")
        copy_button.setObjectName("SecondaryButton")
        copy_button.clicked.connect(self._on_copy_clicked)

        layout.addWidget(_card(
            QLabel("Customer / Site Name"), self._customer_edit,
            QLabel("Machine ID"), self._machine_id_edit,
            issue_button, self._output_edit, copy_button,
            title="Issue a License Key",
        ))

        layout.addStretch(1)
        self._refresh_key_status()

    def _refresh_key_status(self) -> None:
        exists = has_signing_key()
        self._key_status_label.setText("Ready" if exists else "No signing key found yet -- generate one below.")
        self._keygen_button.setEnabled(not exists)

    def _on_keygen_clicked(self) -> None:
        confirm = QMessageBox.question(
            self, "Generate Signing Key",
            "This creates a brand-new signing key. Do this once, ever, on one machine.\n\n"
            "If you already have a signing key elsewhere, do NOT generate a second one -- "
            "keys issued under one signing key aren't valid under another, since the app "
            "only trusts the public half baked into it.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            public_key_hex = generate_keypair()
        except FileExistsError as e:
            QMessageBox.warning(self, "Signing Key Already Exists", str(e))
            self._refresh_key_status()
            return

        self._refresh_key_status()
        QMessageBox.information(
            self, "Signing Key Created",
            f"Wrote {private_key_path()}.\n\nBack this file up somewhere safe -- losing it means "
            f"you can't issue new keys without invalidating every key issued so far.\n\n"
            f"Public key hex (only needed if rebuilding the main app):\n{public_key_hex}",
        )

    def _on_issue_clicked(self) -> None:
        customer = self._customer_edit.text().strip()
        machine_id = self._machine_id_edit.text().strip()
        if not customer or not machine_id:
            QMessageBox.warning(self, "Missing Info", "Enter both a customer/site name and a machine ID.")
            return

        try:
            key = issue_key(machine_id)
        except (ValueError, FileNotFoundError) as e:
            QMessageBox.warning(self, "Couldn't Generate Key", str(e))
            return

        self._output_edit.setPlainText(key)

    def _on_copy_clicked(self) -> None:
        text = self._output_edit.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)

    window = LicenseKeyMakerWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

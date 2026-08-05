"""Main window for the Superba Tunnel Profiler."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app import database
from app.tunnel import BELT_SPEEDS_M_PER_MIN, build_profile
from fluke54.connection import find_fluke_port
from fluke54.models import LogSession

from .download_worker import DownloadWorker
from .graph_widget import ProfileGraphWidget

LOG_INDEX = 1
SAMPLE_INTERVAL_S = 1.0


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


def _stat_block(label_text: str) -> tuple[QFrame, QLabel]:
    frame = QFrame()
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    value_label = QLabel("--")
    value_label.setObjectName("StatValue")
    caption_label = QLabel(label_text)
    caption_label.setObjectName("StatLabel")
    layout.addWidget(value_label)
    layout.addWidget(caption_label)
    return frame, value_label


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Superba Tunnel Profiler")
        self.resize(1200, 800)

        self._conn = database.get_connection()
        database.init_db(self._conn)

        self._worker: DownloadWorker | None = None
        self._last_session: LogSession | None = None

        self._build_ui()
        self._reload_tunnels()
        self._reload_recent_runs()

    # ---------------------------------------------------------------- UI

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        title = QLabel("Superba Tunnel Profiler")
        title.setObjectName("TitleLabel")
        root_layout.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, stretch=1)

        splitter.addWidget(self._build_control_panel())
        splitter.addWidget(self._build_main_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 900])

        self.statusBar().showMessage("Idle")

    def _build_control_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMaximumWidth(300)
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        self._tunnel_combo = QComboBox()
        layout.addWidget(_card(self._tunnel_combo, title="Tunnel"))

        speed_widget = QWidget()
        speed_layout = QVBoxLayout(speed_widget)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        self._speed_group = QButtonGroup(self)
        for speed in BELT_SPEEDS_M_PER_MIN:
            radio = QRadioButton(f"{speed:.0f} m/min")
            radio.setProperty("speed_value", speed)
            self._speed_group.addButton(radio)
            speed_layout.addWidget(radio)
        buttons = self._speed_group.buttons()
        if buttons:
            buttons[0].setChecked(True)
        layout.addWidget(_card(speed_widget, title="Belt Speed"))

        self._meter_status_label = QLabel("Idle")
        port = find_fluke_port()
        self._port_label = QLabel(port or "Not detected")
        layout.addWidget(_card(self._meter_status_label, self._port_label, title="Meter"))

        self._download_button = QPushButton("Download Profile")
        self._download_button.clicked.connect(self._on_download_clicked)
        layout.addWidget(self._download_button)

        self._export_button = QPushButton("Export Graph as PNG")
        self._export_button.setObjectName("SecondaryButton")
        self._export_button.clicked.connect(self._on_export_png_clicked)
        layout.addWidget(self._export_button)

        self._clear_graph_button = QPushButton("Clear Graph")
        self._clear_graph_button.setObjectName("SecondaryButton")
        self._clear_graph_button.clicked.connect(self._on_clear_graph_clicked)
        layout.addWidget(self._clear_graph_button)

        layout.addStretch(1)
        return panel

    def _build_main_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        self._graph = ProfileGraphWidget()
        layout.addWidget(self._graph, stretch=3)

        stats_row = QHBoxLayout()
        peak_frame, self._peak_value_label = _stat_block("Peak Temp (C)")
        exit_frame, self._exit_value_label = _stat_block("Exit Temp (C)")
        duration_frame, self._duration_value_label = _stat_block("Duration")
        points_frame, self._points_value_label = _stat_block("Points")
        for frame in (peak_frame, exit_frame, duration_frame, points_frame):
            stats_row.addWidget(_card(frame))
        layout.addLayout(stats_row)

        recent_label = QLabel("RECENT PROFILES")
        recent_label.setObjectName("SectionLabel")
        layout.addWidget(recent_label)

        self._recent_list = QListWidget()
        self._recent_list.itemDoubleClicked.connect(self._on_recent_item_double_clicked)
        layout.addWidget(self._recent_list, stretch=1)

        return panel

    # ------------------------------------------------------------ actions

    def _reload_tunnels(self) -> None:
        self._tunnel_combo.clear()
        for tunnel in database.list_tunnels(self._conn):
            self._tunnel_combo.addItem(tunnel.name, userData=tunnel.id)

    def _reload_recent_runs(self) -> None:
        self._recent_list.clear()
        for run in database.list_runs(self._conn, limit=50):
            text = (f"{run.run_date}  |  {run.tunnel_name}  |  "
                    f"{run.belt_speed_m_per_min:.0f} m/min  |  "
                    f"peak {run.peak_temp_c:.1f}C  |  exit {run.exit_temp_c:.1f}C")
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, run.id)
            self._recent_list.addItem(item)

    def _selected_belt_speed(self) -> float:
        checked = self._speed_group.checkedButton()
        return float(checked.property("speed_value")) if checked else BELT_SPEEDS_M_PER_MIN[0]

    def _on_download_clicked(self) -> None:
        self._download_button.setEnabled(False)
        self._meter_status_label.setText("Downloading... (ensure meter shows 'Ir SEnd')")
        self.statusBar().showMessage("Downloading from meter...")

        self._worker = DownloadWorker(log_index=LOG_INDEX)
        self._worker.succeeded.connect(self._on_download_succeeded)
        self._worker.failed.connect(self._on_download_failed)
        self._worker.finished.connect(lambda: self._download_button.setEnabled(True))
        self._worker.start()

    def _on_download_succeeded(self, session: LogSession) -> None:
        self._last_session = session
        self._meter_status_label.setText(f"Connected -- {len(session.readings)} readings")
        self.statusBar().showMessage("Download complete", 5000)

        if not session.readings:
            QMessageBox.warning(self, "No Data", "The meter returned zero readings.")
            return

        belt_speed = self._selected_belt_speed()
        points = build_profile(session.readings, belt_speed, sample_interval_s=SAMPLE_INTERVAL_S)

        tunnel_id = self._tunnel_combo.currentData()
        run = database.create_run(self._conn, tunnel_id=tunnel_id, belt_speed_m_per_min=belt_speed, points=points)

        self._graph.clear_profiles()
        label = f"{run.tunnel_name} ({run.run_date})"
        self._graph.plot_profile(run.id, [p.distance_m for p in points], [p.temperature_c for p in points], label)

        self._peak_value_label.setText(f"{run.peak_temp_c:.2f}")
        self._exit_value_label.setText(f"{run.exit_temp_c:.2f}")
        duration_s = points[-1].elapsed_time_s if points else 0.0
        self._duration_value_label.setText(f"{duration_s:.0f} s")
        self._points_value_label.setText(str(run.measurement_count))

        self._reload_recent_runs()

    def _on_download_failed(self, message: str) -> None:
        self._meter_status_label.setText("Error")
        self.statusBar().showMessage("Download failed", 5000)
        QMessageBox.critical(
            self, "Download Failed",
            f"{message}\n\nMake sure the meter is showing 'Ir SEnd' "
            f"(SHIFT + RECALL on the meter) and the cable is connected.",
        )

    def _on_recent_item_double_clicked(self, item: QListWidgetItem) -> None:
        run_id = item.data(Qt.ItemDataRole.UserRole)
        runs = {r.id: r for r in database.list_runs(self._conn, limit=200)}
        run = runs.get(run_id)
        if run is None:
            return
        measurements = database.get_measurements(self._conn, run_id)
        if not measurements:
            return

        label = f"{run.tunnel_name} ({run.run_date})"
        self._graph.plot_profile(
            run.id,
            [m.distance_m for m in measurements],
            [m.temperature_c for m in measurements],
            label,
        )
        self._peak_value_label.setText(f"{run.peak_temp_c:.2f}")
        self._exit_value_label.setText(f"{run.exit_temp_c:.2f}")
        self._duration_value_label.setText(f"{measurements[-1].elapsed_time_s:.0f} s")
        self._points_value_label.setText(str(run.measurement_count))

    def _on_export_png_clicked(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Graph", "profile.png", "PNG Images (*.png)")
        if path:
            self._graph.export_png(path)
            self.statusBar().showMessage(f"Exported to {path}", 5000)

    def _on_clear_graph_clicked(self) -> None:
        self._graph.clear_profiles()
        for label in (self._peak_value_label, self._exit_value_label,
                      self._duration_value_label, self._points_value_label):
            label.setText("--")

    def closeEvent(self, event) -> None:
        self._conn.close()
        super().closeEvent(event)

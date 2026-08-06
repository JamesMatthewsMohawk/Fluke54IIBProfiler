"""Main window for the Superba Tunnel Profiler."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app import database, licensing
from app.data_export import export_runs_to_csv, export_runs_to_excel
from app.models import Run
from app.profile_builder import build_profile
from app.units import convert_from_celsius
from fluke54.connection import find_fluke_port
from fluke54.models import LogSession, Reading

from .database_tab import DatabaseTabWidget
from .download_worker import DownloadWorker
from .graph_widget import ProfileGraphWidget
from .run_names_dialog import RunNamesDialog

LOG_INDEX = 1
SAMPLE_INTERVAL_S = 1.0


@dataclass
class _ActivePlot:
    """A run currently overlaid on the graph, kept in Celsius for unit-toggle replots."""
    run: Run
    elapsed_time_s: list[float]
    temperature_c: list[float]


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


def _unit_radio_row(parent: QWidget, default_unit: str = "C") -> tuple[QWidget, QButtonGroup]:
    group = QButtonGroup(parent)
    row_widget = QWidget()
    row = QHBoxLayout(row_widget)
    row.setContentsMargins(0, 0, 0, 0)
    for unit in ("C", "F"):
        radio = QRadioButton(f"°{unit}")
        radio.setProperty("unit_value", unit)
        if unit == default_unit:
            radio.setChecked(True)
        group.addButton(radio)
        row.addWidget(radio)
    return row_widget, group


def _set_item_active_style(item: QListWidgetItem, color: str | None) -> None:
    """Mark a recent-run list item as plotted (or not) on the graph.

    QListWidgetItem.setBackground() is silently ignored once a QSS
    stylesheet is applied to the app -- the item view paints ::item
    background from the stylesheet, not the item's brush. Foreground
    (text) color isn't overridden by the stylesheet's unselected
    ::item rule, so that's what carries the highlight instead, tinted
    to match the item's chart curve color.
    """
    font = item.font()
    font.setBold(color is not None)
    item.setFont(font)
    item.setForeground(QColor(color) if color else QBrush())


def _run_label(run: Run) -> str:
    location = f"{run.plant} / {run.tunnel}" if run.plant else run.tunnel
    return f"{location} ({run.run_date})"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Superba Tunnel Profiler")
        self.resize(1200, 800)

        self._conn = database.get_connection()
        database.init_db(self._conn)

        self._worker: DownloadWorker | None = None
        self._last_session: LogSession | None = None

        self._settings = QSettings("SuperbaProfiler", "TunnelProfiler")
        self._display_unit = str(self._settings.value("display_unit", "C"))
        self._license_key = str(self._settings.value("license_key", ""))

        self._active_plots: dict[int, _ActivePlot] = {}
        self._recent_items: dict[int, QListWidgetItem] = {}

        self._build_ui()
        self._graph.set_temperature_unit(self._display_unit)
        self._reload_recent_runs()
        self._database_tab.refresh()
        self._refresh_license_gate()

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

        tabs = QTabWidget()
        root_layout.addWidget(tabs, stretch=1)
        self._tabs = tabs

        self._chart_tab_index = tabs.addTab(self._build_chart_tab(), "Chart")

        self._database_tab = DatabaseTabWidget(self._conn, lambda: self._display_unit)
        self._database_tab.open_run_requested.connect(self._on_open_run_from_database)
        tabs.addTab(self._database_tab, "Database")

        tabs.addTab(self._build_download_tab(), "Download")
        tabs.addTab(self._build_settings_tab(), "Settings")

        self.statusBar().showMessage("Idle")

    def _build_chart_tab(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_chart_actions_panel())
        splitter.addWidget(self._build_chart_main_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 960])
        return splitter

    def _build_chart_actions_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMaximumWidth(260)
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        self._export_button = QPushButton("Export Graph as PNG")
        self._export_button.setObjectName("SecondaryButton")
        self._export_button.clicked.connect(self._on_export_png_clicked)
        layout.addWidget(self._export_button)

        self._export_data_csv_button = QPushButton("Export Plotted Data (CSV)")
        self._export_data_csv_button.setObjectName("SecondaryButton")
        self._export_data_csv_button.clicked.connect(self._on_export_plotted_csv_clicked)
        layout.addWidget(self._export_data_csv_button)

        self._export_data_excel_button = QPushButton("Export Plotted Data (Excel)")
        self._export_data_excel_button.setObjectName("SecondaryButton")
        self._export_data_excel_button.clicked.connect(self._on_export_plotted_excel_clicked)
        layout.addWidget(self._export_data_excel_button)

        self._clear_graph_button = QPushButton("Clear Graph")
        self._clear_graph_button.setObjectName("SecondaryButton")
        self._clear_graph_button.clicked.connect(self._on_clear_graph_clicked)
        layout.addWidget(self._clear_graph_button)

        layout.addStretch(1)
        return panel

    def _build_chart_main_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(12)

        self._graph = ProfileGraphWidget()
        layout.addWidget(self._graph, stretch=3)

        drag_hint = QLabel("Drag a curve to shift it in time (start/end alignment) · double-click a curve to reset it")
        drag_hint.setObjectName("HintLabel")
        layout.addWidget(drag_hint)

        recent_label = QLabel("RECENT PROFILES")
        recent_label.setObjectName("SectionLabel")
        layout.addWidget(recent_label)

        self._recent_list = QListWidget()
        self._recent_list.itemDoubleClicked.connect(self._on_recent_item_double_clicked)
        layout.addWidget(self._recent_list, stretch=1)

        return panel

    def _build_download_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        content.setMaximumWidth(360)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        plant_label = QLabel("Plant")
        plant_label.setObjectName("SectionLabel")
        self._plant_edit = QLineEdit(str(self._settings.value("last_plant", "")))
        self._plant_edit.setPlaceholderText("e.g. North Plant")

        tunnel_label = QLabel("Tunnel")
        tunnel_label.setObjectName("SectionLabel")
        self._tunnel_edit = QLineEdit(str(self._settings.value("last_tunnel", "")))
        self._tunnel_edit.setPlaceholderText("e.g. 3 or Superba A")

        content_layout.addWidget(_card(
            plant_label, self._plant_edit, tunnel_label, self._tunnel_edit,
            title="Location",
        ))

        self._meter_status_label = QLabel("Idle")
        port = find_fluke_port()
        self._port_label = QLabel(port or "Not detected")

        source_unit_caption = QLabel("Meter Showed (at log time)")
        source_unit_caption.setObjectName("SectionLabel")
        source_unit_row, self._source_unit_group = _unit_radio_row(self, "C")

        content_layout.addWidget(_card(
            self._meter_status_label, self._port_label,
            source_unit_caption, source_unit_row,
            title="Meter",
        ))

        self._download_button = QPushButton("Download Profile")
        self._download_button.clicked.connect(self._on_download_clicked)
        content_layout.addWidget(self._download_button)

        self._license_gate_label = QLabel("Meter downloads require a license -- activate one in Settings.")
        self._license_gate_label.setObjectName("HintLabel")
        self._license_gate_label.setWordWrap(True)
        content_layout.addWidget(self._license_gate_label)

        content_layout.addStretch(1)
        layout.addWidget(content)
        layout.addStretch(1)
        return panel

    def _build_settings_tab(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        content.setMaximumWidth(360)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        display_unit_row, self._display_unit_group = _unit_radio_row(self, self._display_unit)
        self._display_unit_group.buttonClicked.connect(self._on_display_unit_changed)
        content_layout.addWidget(_card(display_unit_row, title="Display Unit"))

        self._license_status_label = QLabel()
        machine_id_label = QLabel(f"Machine ID: {licensing.get_machine_id()}")
        machine_id_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        machine_id_label.setWordWrap(True)

        self._license_key_edit = QLineEdit(self._license_key)
        self._license_key_edit.setPlaceholderText("KOTPRO-...")

        activate_button = QPushButton("Activate")
        activate_button.setObjectName("SecondaryButton")
        activate_button.clicked.connect(self._on_activate_license_clicked)

        content_layout.addWidget(_card(
            self._license_status_label, machine_id_label, self._license_key_edit, activate_button,
            title="License",
        ))

        content_layout.addStretch(1)
        layout.addWidget(content)
        layout.addStretch(1)
        return panel

    # ------------------------------------------------------------ actions

    def _reload_recent_runs(self) -> None:
        self._recent_list.clear()
        self._recent_items = {}
        for run in database.list_runs(self._conn, limit=50):
            item = QListWidgetItem(self._format_run_summary(run))
            item.setData(Qt.ItemDataRole.UserRole, run.id)
            self._recent_list.addItem(item)
            self._recent_items[run.id] = item
        self._apply_active_highlights()

    def _format_run_summary(self, run: Run) -> str:
        peak = convert_from_celsius(run.peak_temp_c, self._display_unit)
        location = f"{run.plant}  |  {run.tunnel}" if run.plant else run.tunnel
        return (f"{run.run_date}  |  {location}  |  "
                f"peak {peak:.1f}°{self._display_unit}"
                f"  |  logged °{run.source_unit}")

    def _apply_active_highlights(self) -> None:
        for run_id, item in self._recent_items.items():
            color = self._graph.get_color(run_id) if run_id in self._active_plots else None
            _set_item_active_style(item, color)

    def _selected_source_unit(self) -> str:
        checked = self._source_unit_group.checkedButton()
        return str(checked.property("unit_value")) if checked else "C"

    def _refresh_license_gate(self) -> None:
        licensed = licensing.is_licensed(self._license_key)
        self._license_status_label.setText("Licensed" if licensed else "Not Activated")
        self._download_button.setEnabled(licensed)
        self._license_gate_label.setVisible(not licensed)

    def _on_activate_license_clicked(self) -> None:
        key = self._license_key_edit.text().strip()
        if not licensing.is_licensed(key):
            QMessageBox.warning(
                self, "Invalid License",
                "That key isn't valid for this machine. Double check it was issued for this "
                "machine's ID (shown above), with no missing characters.",
            )
            return

        self._license_key = key
        self._settings.setValue("license_key", key)
        self._refresh_license_gate()
        QMessageBox.information(self, "License Activated", "Meter downloads are now enabled.")

    def _on_download_clicked(self) -> None:
        if not licensing.is_licensed(self._license_key):
            QMessageBox.warning(self, "Not Licensed", "Activate a valid license in the Settings tab first.")
            return
        if not self._tunnel_edit.text().strip():
            QMessageBox.warning(self, "Tunnel Required", "Enter a tunnel name/number before downloading.")
            return

        self._download_button.setEnabled(False)
        self._meter_status_label.setText("Downloading... (ensure meter shows 'Ir SEnd')")
        self.statusBar().showMessage("Downloading from meter...")

        self._worker = DownloadWorker(license_key=self._license_key, log_index=LOG_INDEX)
        self._worker.succeeded.connect(self._on_download_succeeded)
        self._worker.failed.connect(self._on_download_failed)
        self._worker.finished.connect(lambda: self._download_button.setEnabled(licensing.is_licensed(self._license_key)))
        self._worker.start()

    def _on_download_succeeded(self, session: LogSession) -> None:
        self._last_session = session
        self._meter_status_label.setText(f"Connected -- {len(session.readings)} readings")
        self.statusBar().showMessage("Download complete", 5000)

        if not session.readings:
            QMessageBox.warning(self, "No Data", "The meter returned zero readings.")
            return

        runs_readings = session.split_runs()
        plant = self._plant_edit.text().strip()
        source_unit = self._selected_source_unit()

        if len(runs_readings) > 1:
            tunnel_names = self._prompt_for_run_names(runs_readings)
            if tunnel_names is None:
                self.statusBar().showMessage("Download not saved -- runs weren't named", 5000)
                return
        else:
            tunnel_names = [self._tunnel_edit.text().strip()]

        self._graph.clear_profiles()
        self._active_plots.clear()

        for readings, tunnel in zip(runs_readings, tunnel_names):
            points = build_profile(readings, sample_interval_s=SAMPLE_INTERVAL_S)
            run = database.create_run(
                self._conn, plant=plant, tunnel=tunnel, points=points, source_unit=source_unit,
            )
            elapsed_time_s = [p.elapsed_time_s for p in points]
            temperature_c = [p.temperature_c for p in points]
            self._plot_run(run, elapsed_time_s, temperature_c)

        self._settings.setValue("last_plant", plant)
        self._settings.setValue("last_tunnel", tunnel_names[0])

        self._reload_recent_runs()
        self._database_tab.refresh()
        self._tabs.setCurrentIndex(self._chart_tab_index)

    def _prompt_for_run_names(self, runs_readings: list[list[Reading]]) -> list[str] | None:
        """Ask for a tunnel name per detected run. None means the user cancelled."""
        unit = self._display_unit
        summaries = []
        for readings in runs_readings:
            temps = [convert_from_celsius(r.temperature_c, unit) for r in readings]
            summaries.append((len(readings), min(temps), max(temps)))

        dialog = RunNamesDialog(summaries, self._tunnel_edit.text().strip(), unit, parent=self)
        if dialog.exec() != RunNamesDialog.DialogCode.Accepted:
            return None
        return dialog.tunnel_names()

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

        if run_id in self._active_plots:
            self._unplot_run(run_id)
            return

        run = database.get_run(self._conn, run_id)
        if run is None:
            return
        measurements = database.get_measurements(self._conn, run_id)
        if not measurements:
            return

        elapsed_time_s = [m.elapsed_time_s for m in measurements]
        temperature_c = [m.temperature_c for m in measurements]
        self._plot_run(run, elapsed_time_s, temperature_c)

    def _on_open_run_from_database(self, run_id: int) -> None:
        run = database.get_run(self._conn, run_id)
        if run is None:
            return
        measurements = database.get_measurements(self._conn, run_id)
        if not measurements:
            return

        self._graph.clear_profiles()
        self._active_plots.clear()
        elapsed_time_s = [m.elapsed_time_s for m in measurements]
        temperature_c = [m.temperature_c for m in measurements]
        self._plot_run(run, elapsed_time_s, temperature_c)

        self._tabs.setCurrentIndex(self._chart_tab_index)

    def _plot_run(self, run: Run, elapsed_time_s: list[float], temperature_c: list[float]) -> None:
        self._active_plots[run.id] = _ActivePlot(
            run=run, elapsed_time_s=elapsed_time_s, temperature_c=temperature_c,
        )
        temperature_display = [convert_from_celsius(t, self._display_unit) for t in temperature_c]
        self._graph.plot_profile(run.id, elapsed_time_s, temperature_display, _run_label(run))

        item = self._recent_items.get(run.id)
        if item is not None:
            _set_item_active_style(item, self._graph.get_color(run.id))

    def _unplot_run(self, run_id: int) -> None:
        self._active_plots.pop(run_id, None)
        self._graph.remove_profile(run_id)

        item = self._recent_items.get(run_id)
        if item is not None:
            _set_item_active_style(item, None)

    def _on_display_unit_changed(self, button) -> None:
        unit = str(button.property("unit_value"))
        if unit == self._display_unit:
            return
        self._display_unit = unit
        self._settings.setValue("display_unit", unit)
        self._graph.set_temperature_unit(unit)

        for run_id, active in self._active_plots.items():
            temperature_display = [convert_from_celsius(t, unit) for t in active.temperature_c]
            self._graph.plot_profile(run_id, active.elapsed_time_s, temperature_display, _run_label(active.run))

        self._reload_recent_runs()
        self._database_tab.refresh()

    def _on_export_png_clicked(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Graph", "profile.png", "PNG Images (*.png)")
        if path:
            self._graph.export_png(path)
            self.statusBar().showMessage(f"Exported to {path}", 5000)

    def _plotted_runs_for_export(self) -> list[tuple[Run, list[tuple[float, float]]]]:
        return [
            (
                active.run,
                [
                    (t + self._graph.get_offset(run_id), temp)
                    for t, temp in zip(active.elapsed_time_s, active.temperature_c)
                ],
            )
            for run_id, active in self._active_plots.items()
        ]

    def _on_export_plotted_csv_clicked(self) -> None:
        runs = self._plotted_runs_for_export()
        if not runs:
            QMessageBox.information(self, "Nothing to Export", "No runs are currently plotted on the graph.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Plotted Data", "plotted_data.csv", "CSV Files (*.csv)")
        if not path:
            return
        export_runs_to_csv(path, runs)
        self.statusBar().showMessage(f"Exported to {path}", 5000)

    def _on_export_plotted_excel_clicked(self) -> None:
        runs = self._plotted_runs_for_export()
        if not runs:
            QMessageBox.information(self, "Nothing to Export", "No runs are currently plotted on the graph.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Plotted Data", "plotted_data.xlsx", "Excel Files (*.xlsx)")
        if not path:
            return
        export_runs_to_excel(path, runs, self._display_unit)
        self.statusBar().showMessage(f"Exported to {path}", 5000)

    def _on_clear_graph_clicked(self) -> None:
        self._graph.clear_profiles()
        self._active_plots.clear()
        self._apply_active_highlights()

    def closeEvent(self, event) -> None:
        self._conn.close()
        super().closeEvent(event)

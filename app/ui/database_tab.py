"""Database tab: search stored runs and open/export/print one of them."""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import database
from app.data_export import export_runs_to_csv, export_runs_to_excel
from app.models import Measurement, Run
from app.units import convert_from_celsius

COLUMNS = ["Date", "Plant", "Tunnel", "Peak", "Points", "Logged"]


class DatabaseTabWidget(QWidget):
    """Search/filter stored runs; double-click one to view it on the graph."""

    open_run_requested = Signal(int)

    def __init__(
        self,
        conn: sqlite3.Connection,
        get_display_unit: Callable[[], str],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._conn = conn
        self._get_display_unit = get_display_unit
        self._runs_by_row: list[Run] = []

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        filter_row = QHBoxLayout()

        self._plant_edit = QLineEdit()
        self._plant_edit.setPlaceholderText("Plant contains...")
        self._plant_edit.returnPressed.connect(self._run_search)

        self._tunnel_edit = QLineEdit()
        self._tunnel_edit.setPlaceholderText("Tunnel contains...")
        self._tunnel_edit.returnPressed.connect(self._run_search)

        self._date_from_check = QCheckBox("From")
        self._date_from_edit = QDateEdit(QDate.currentDate().addMonths(-1))
        self._date_from_edit.setCalendarPopup(True)
        self._date_from_edit.setEnabled(False)
        self._date_from_check.toggled.connect(self._date_from_edit.setEnabled)
        self._date_from_check.toggled.connect(self._run_search)

        self._date_to_check = QCheckBox("To")
        self._date_to_edit = QDateEdit(QDate.currentDate())
        self._date_to_edit.setCalendarPopup(True)
        self._date_to_edit.setEnabled(False)
        self._date_to_check.toggled.connect(self._date_to_edit.setEnabled)
        self._date_to_check.toggled.connect(self._run_search)

        search_button = QPushButton("Search")
        search_button.clicked.connect(self._run_search)

        clear_button = QPushButton("Clear")
        clear_button.setObjectName("SecondaryButton")
        clear_button.clicked.connect(self._clear_filters)

        for w in (
            QLabel("Plant"), self._plant_edit,
            QLabel("Tunnel"), self._tunnel_edit,
            self._date_from_check, self._date_from_edit,
            self._date_to_check, self._date_to_edit,
            search_button, clear_button,
        ):
            filter_row.addWidget(w)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self._table = QTableWidget(0, len(COLUMNS))
        self._table.setHorizontalHeaderLabels(COLUMNS)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.itemDoubleClicked.connect(self._on_row_double_clicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_table_context_menu)
        layout.addWidget(self._table, stretch=1)

        actions_row = QHBoxLayout()
        self._result_count_label = QLabel("")
        self._result_count_label.setObjectName("SectionLabel")
        actions_row.addWidget(self._result_count_label)
        actions_row.addStretch(1)

        self._export_button = QPushButton("Export Data (CSV)")
        self._export_button.setObjectName("SecondaryButton")
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(lambda: self._export_run_csv(self._selected_run()))
        actions_row.addWidget(self._export_button)

        self._print_button = QPushButton("Print Report")
        self._print_button.setObjectName("SecondaryButton")
        self._print_button.setEnabled(False)
        self._print_button.clicked.connect(self._on_print_clicked)
        actions_row.addWidget(self._print_button)

        layout.addLayout(actions_row)

    # ------------------------------------------------------------ search

    def _clear_filters(self) -> None:
        self._plant_edit.clear()
        self._tunnel_edit.clear()
        self._date_from_check.setChecked(False)
        self._date_to_check.setChecked(False)
        self._run_search()

    def _run_search(self) -> None:
        date_from = (
            self._date_from_edit.date().toString("yyyy-MM-dd") if self._date_from_check.isChecked() else None
        )
        date_to = (
            self._date_to_edit.date().toString("yyyy-MM-dd") if self._date_to_check.isChecked() else None
        )
        runs = database.search_runs(
            self._conn,
            plant=self._plant_edit.text().strip(),
            tunnel=self._tunnel_edit.text().strip(),
            date_from=date_from,
            date_to=date_to,
        )
        self._populate_table(runs)

    def refresh(self) -> None:
        """Re-run the current search -- call after any run is added/changed."""
        self._run_search()

    def _populate_table(self, runs: list[Run]) -> None:
        self._runs_by_row = runs
        unit = self._get_display_unit()

        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(runs))
        for row, run in enumerate(runs):
            peak = convert_from_celsius(run.peak_temp_c, unit)
            values = [
                run.run_date, run.plant, run.tunnel,
                f"{peak:.1f}°{unit}",
                str(run.measurement_count), f"°{run.source_unit}",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, run.id)
                self._table.setItem(row, col, item)
        self._table.setSortingEnabled(True)
        self._result_count_label.setText(f"{len(runs)} run{'s' if len(runs) != 1 else ''}")
        self._on_selection_changed()

    # ------------------------------------------------------- selection/actions

    def _selected_run(self) -> Run | None:
        selection_model = self._table.selectionModel()
        rows = selection_model.selectedRows() if selection_model else []
        if not rows:
            return None
        run_id = self._table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        return next((r for r in self._runs_by_row if r.id == run_id), None)

    def _on_selection_changed(self) -> None:
        has_selection = self._selected_run() is not None
        self._export_button.setEnabled(has_selection)
        self._print_button.setEnabled(has_selection)

    def _on_row_double_clicked(self, item: QTableWidgetItem) -> None:
        run_id = item.data(Qt.ItemDataRole.UserRole)
        if run_id is not None:
            self.open_run_requested.emit(run_id)

    def _on_table_context_menu(self, pos) -> None:
        item = self._table.itemAt(pos)
        if item is None:
            return
        self._table.selectRow(item.row())
        run = self._selected_run()
        if run is None:
            return

        menu = QMenu(self)
        export_png_action = menu.addAction("Export as PNG...")
        export_csv_action = menu.addAction("Export to CSV...")
        export_excel_action = menu.addAction("Export to Excel...")
        chosen = menu.exec(self._table.viewport().mapToGlobal(pos))
        if chosen is export_png_action:
            self._export_run_png(run)
        elif chosen is export_csv_action:
            self._export_run_csv(run)
        elif chosen is export_excel_action:
            self._export_run_excel(run)

    def _export_run_png(self, run: Run | None) -> None:
        if run is None:
            return
        measurements = database.get_measurements(self._conn, run.id)
        if not measurements:
            QMessageBox.warning(self, "No Data", "This run has no measurements to export.")
            return
        default_name = f"{run.plant}_{run.tunnel}_{run.run_date}".replace(":", "-").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(self, "Export Run Graph", f"{default_name}.png", "PNG Images (*.png)")
        if not path:
            return

        graph = self._build_run_graph(run, measurements, self._get_display_unit())
        try:
            graph.export_png(path, width=1400)
        finally:
            graph.deleteLater()
        QMessageBox.information(self, "Export Complete", f"Graph exported to:\n{path}")

    def _export_run_csv(self, run: Run | None) -> None:
        if run is None:
            return
        measurements = database.get_measurements(self._conn, run.id)
        default_name = f"{run.plant}_{run.tunnel}_{run.run_date}".replace(":", "-").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(self, "Export Run Data", f"{default_name}.csv", "CSV Files (*.csv)")
        if not path:
            return
        export_runs_to_csv(path, [(run, [(m.elapsed_time_s, m.temperature_c) for m in measurements])])
        QMessageBox.information(self, "Export Complete", f"Run data exported to:\n{path}")

    def _export_run_excel(self, run: Run | None) -> None:
        if run is None:
            return
        measurements = database.get_measurements(self._conn, run.id)
        default_name = f"{run.plant}_{run.tunnel}_{run.run_date}".replace(":", "-").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(self, "Export Run Data", f"{default_name}.xlsx", "Excel Files (*.xlsx)")
        if not path:
            return
        export_runs_to_excel(
            path,
            [(run, [(m.elapsed_time_s, m.temperature_c) for m in measurements])],
            self._get_display_unit(),
        )
        QMessageBox.information(self, "Export Complete", f"Run data exported to:\n{path}")

    def _on_print_clicked(self) -> None:
        run = self._selected_run()
        if run is None:
            return
        measurements = database.get_measurements(self._conn, run.id)
        if not measurements:
            QMessageBox.warning(self, "No Data", "This run has no measurements to print.")
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return

        unit = self._get_display_unit()
        image = self._render_graph_image(run, measurements, unit)
        self._paint_report(printer, run, unit, image)

    def _build_run_graph(self, run: Run, measurements: list[Measurement], unit: str):
        # Imported locally: a temporary, throwaway graph is only needed here
        # (print/PNG export), kept out of this tab's normal import cost.
        from .graph_widget import ProfileGraphWidget

        graph = ProfileGraphWidget()
        graph.resize(900, 500)
        graph.set_temperature_unit(unit)
        temps = [convert_from_celsius(m.temperature_c, unit) for m in measurements]
        graph.plot_profile(run.id, [m.elapsed_time_s for m in measurements], temps, "")
        return graph

    def _render_graph_image(self, run: Run, measurements: list[Measurement], unit: str) -> QImage:
        graph = self._build_run_graph(run, measurements, unit)

        tmp_path = Path(tempfile.gettempdir()) / f"superba_print_{run.id}.png"
        try:
            graph.export_png(str(tmp_path), width=1400)
            image = QImage(str(tmp_path))
        finally:
            tmp_path.unlink(missing_ok=True)
            graph.deleteLater()
        return image

    def _paint_report(self, printer: QPrinter, run: Run, unit: str, image: QImage) -> None:
        peak = convert_from_celsius(run.peak_temp_c, unit)
        min_t = convert_from_celsius(run.min_temp_c, unit)

        painter = QPainter(printer)
        try:
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            margin = 40
            x = page_rect.left() + margin
            y = page_rect.top() + margin
            width = page_rect.width() - 2 * margin

            title_font = painter.font()
            title_font.setPointSize(16)
            title_font.setBold(True)
            painter.setFont(title_font)
            location = f"{run.plant} / {run.tunnel}" if run.plant else run.tunnel
            painter.drawText(int(x), int(y), int(width), 30, Qt.AlignmentFlag.AlignLeft, location)
            y += 40

            body_font = painter.font()
            body_font.setPointSize(10)
            body_font.setBold(False)
            painter.setFont(body_font)
            lines = [
                f"Run date: {run.run_date}",
                f"Peak temp: {peak:.1f}°{unit}    Min temp: {min_t:.1f}°{unit}",
                f"Measurement points: {run.measurement_count}    Meter displayed: °{run.source_unit} at log time",
            ]
            for line in lines:
                painter.drawText(int(x), int(y), int(width), 20, Qt.AlignmentFlag.AlignLeft, line)
                y += 22
            y += 20

            if not image.isNull():
                available_height = page_rect.height() - (y - page_rect.top()) - margin
                scale = min(width / image.width(), available_height / image.height())
                draw_w = int(image.width() * scale)
                draw_h = int(image.height() * scale)
                scaled = image.scaled(
                    draw_w, draw_h,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
                )
                painter.drawImage(int(x), int(y), scaled)
        finally:
            painter.end()

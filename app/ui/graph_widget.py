"""Temperature-vs-distance profile graph, built on pyqtgraph."""
from __future__ import annotations

import pyqtgraph as pg
import pyqtgraph.exporters
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

CURVE_COLORS = ["#3f8cff", "#e0524d", "#3fbf6f", "#f2b705", "#a86ff0", "#00c2c2"]

pg.setConfigOption("background", "#22262b")
pg.setConfigOption("foreground", "#e4e7eb")


class ProfileGraphWidget(QWidget):
    """Distance (m) on X, Temperature (C) on Y. Supports overlaying multiple runs."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setLabel("bottom", "Distance", units="m")
        self._plot_widget.setLabel("left", "Temperature", units=None)
        self._plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self._plot_widget.setMouseEnabled(x=True, y=True)
        self._plot_widget.addLegend(offset=(10, 10))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot_widget)

        self._curves: dict[int, pg.PlotDataItem] = {}
        self._next_color_index = 0

        self._v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("#8c94a0", width=1))
        self._h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen("#8c94a0", width=1))
        self._v_line.setVisible(False)
        self._h_line.setVisible(False)
        self._plot_widget.addItem(self._v_line, ignoreBounds=True)
        self._plot_widget.addItem(self._h_line, ignoreBounds=True)

        self._crosshair_label = pg.TextItem(color="#e4e7eb", anchor=(0, 1))
        self._crosshair_label.setVisible(False)
        self._plot_widget.addItem(self._crosshair_label)

        self._proxy = pg.SignalProxy(
            self._plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved
        )

    def clear_profiles(self) -> None:
        for curve in self._curves.values():
            self._plot_widget.removeItem(curve)
        self._curves.clear()
        self._next_color_index = 0
        if self._plot_widget.plotItem.legend is not None:
            self._plot_widget.plotItem.legend.clear()

    def plot_profile(self, run_id: int, distance_m: list[float], temperature_c: list[float], label: str) -> None:
        if run_id in self._curves:
            self._plot_widget.removeItem(self._curves[run_id])

        color = CURVE_COLORS[self._next_color_index % len(CURVE_COLORS)]
        self._next_color_index += 1

        curve = self._plot_widget.plot(
            distance_m, temperature_c, pen=pg.mkPen(color, width=2), name=label,
        )
        self._curves[run_id] = curve

    def remove_profile(self, run_id: int) -> None:
        curve = self._curves.pop(run_id, None)
        if curve is not None:
            self._plot_widget.removeItem(curve)

    def export_png(self, path: str) -> None:
        exporter = pg.exporters.ImageExporter(self._plot_widget.plotItem)
        exporter.export(path)

    def _on_mouse_moved(self, event) -> None:
        pos = event[0]
        if not self._plot_widget.sceneBoundingRect().contains(pos):
            self._v_line.setVisible(False)
            self._h_line.setVisible(False)
            self._crosshair_label.setVisible(False)
            return

        view_box = self._plot_widget.plotItem.vb
        mouse_point = view_box.mapSceneToView(pos)
        x, y = mouse_point.x(), mouse_point.y()

        self._v_line.setPos(x)
        self._h_line.setPos(y)
        self._v_line.setVisible(True)
        self._h_line.setVisible(True)

        self._crosshair_label.setText(f"{x:.2f} m, {y:.2f}")
        self._crosshair_label.setPos(x, y)
        self._crosshair_label.setVisible(True)

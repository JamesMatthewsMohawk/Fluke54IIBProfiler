"""Temperature-vs-time profile graph, built on pyqtgraph."""
from __future__ import annotations

import pyqtgraph as pg
import pyqtgraph.exporters
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

CURVE_COLORS = ["#3f8cff", "#e0524d", "#3fbf6f", "#f2b705", "#a86ff0", "#00c2c2"]
DEFAULT_X_RANGE_S = (0.0, 60.0)
Y_RANGE_BY_UNIT = {"C": (0.0, 145.0), "F": (0.0, 300.0)}

pg.setConfigOption("background", "#22262b")
pg.setConfigOption("foreground", "#e4e7eb")


class ProfileGraphWidget(QWidget):
    """Time (s) on X, Temperature on Y. Supports overlaying multiple runs.

    Each run keeps the same curve color for as long as the widget lives,
    even across remove_profile/plot_profile cycles, so a list entry's
    highlight color always matches its curve if it's re-added.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._temp_unit = "C"

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setLabel("bottom", "Time", units="s")
        self._plot_widget.setLabel("left", "Temperature")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self._plot_widget.setMouseEnabled(x=True, y=True)
        self._plot_widget.addLegend(offset=(10, 10))
        self._plot_widget.setXRange(*DEFAULT_X_RANGE_S, padding=0)
        self._apply_y_range()

        # Dragging/scrolling directly on the Y-axis strip forwards to the
        # ViewBox as a single-axis rescale (pyqtgraph's built-in "axis edge"
        # gesture) -- block just that, so the axis itself is inert while
        # ordinary in-plot wheel/drag zoom on Y still works normally.
        y_axis = self._plot_widget.getAxis("left")
        y_axis.mouseDragEvent = self._ignore_axis_event
        y_axis.wheelEvent = self._ignore_axis_event

        # A plain in-plot wheel scroll normally scales X and Y together in
        # one step (pyqtgraph's default when both axes are mouse-enabled).
        # That coupling made zooming feel broken -- an in-progress X zoom
        # would visibly reverse/stall once Y's fixed range hit its bound.
        # Force each wheel tick to a single axis instead: plain scroll only
        # ever touches X (identical to the pre-Y-zoom behavior), Ctrl+scroll
        # only touches Y.
        view_box = self._plot_widget.plotItem.vb
        view_box.wheelEvent = self._make_single_axis_wheel_event(view_box)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plot_widget)

        self._curves: dict[int, pg.PlotDataItem] = {}
        self._colors: dict[int, str] = {}
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

        # Hide the OS cursor while it's over the plot -- the crosshair lines
        # already track the pointer, so the arrow cursor is just visual noise.
        self._plot_widget.viewport().installEventFilter(self)

    def set_temperature_unit(self, unit: str) -> None:
        self._temp_unit = unit
        self._plot_widget.setLabel("left", f"Temperature (°{unit})")
        self._apply_y_range()

    def get_color(self, run_id: int) -> str | None:
        return self._colors.get(run_id)

    def _apply_y_range(self) -> None:
        """Bound the Y axis to the unit's fixed span, resetting to the full view.

        yMin/yMax stop the view from panning past the meaningful range;
        maxYRange stops zooming out past the full span. Zooming in is left
        unrestricted so mouse-wheel/drag zoom on Y still works.
        """
        lo, hi = Y_RANGE_BY_UNIT[self._temp_unit]
        span = hi - lo
        self._plot_widget.setLimits(yMin=lo, yMax=hi, maxYRange=span)
        self._plot_widget.setYRange(lo, hi, padding=0)

    @staticmethod
    def _ignore_axis_event(event, *args, **kwargs) -> None:
        event.ignore()

    @staticmethod
    def _make_single_axis_wheel_event(view_box: pg.ViewBox):
        def _wheel_event(event, axis=None):
            forced_axis = 1 if event.modifiers() & Qt.KeyboardModifier.ControlModifier else 0
            pg.ViewBox.wheelEvent(view_box, event, axis=forced_axis)

        return _wheel_event

    def clear_profiles(self) -> None:
        for curve in self._curves.values():
            self._plot_widget.removeItem(curve)
        self._curves.clear()
        self._colors.clear()
        self._next_color_index = 0
        if self._plot_widget.plotItem.legend is not None:
            self._plot_widget.plotItem.legend.clear()

    def plot_profile(self, run_id: int, elapsed_time_s: list[float], temperature: list[float], label: str) -> None:
        if run_id in self._curves:
            self._plot_widget.removeItem(self._curves[run_id])
            legend = self._plot_widget.plotItem.legend
            if legend is not None:
                legend.removeItem(self._curves[run_id].name())

        color = self._colors.get(run_id)
        if color is None:
            color = CURVE_COLORS[self._next_color_index % len(CURVE_COLORS)]
            self._next_color_index += 1
            self._colors[run_id] = color

        curve = self._plot_widget.plot(
            elapsed_time_s, temperature, pen=pg.mkPen(color, width=2), name=label,
        )
        self._curves[run_id] = curve

    def remove_profile(self, run_id: int) -> None:
        curve = self._curves.pop(run_id, None)
        if curve is not None:
            self._plot_widget.removeItem(curve)
            legend = self._plot_widget.plotItem.legend
            if legend is not None:
                legend.removeItem(curve.name())

    def export_png(self, path: str, width: int | None = None) -> None:
        """Export the current view to a PNG.

        width overrides pyqtgraph's default export size (which otherwise
        follows the widget's on-screen layout size -- falling back to a low
        640x480 default for a widget that was never actually shown, e.g. a
        throwaway graph built just to render a print image).
        """
        exporter = pg.exporters.ImageExporter(self._plot_widget.plotItem)
        if width is not None:
            exporter.parameters()["width"] = width
        exporter.export(path)

    def eventFilter(self, obj, event) -> bool:
        if obj is self._plot_widget.viewport():
            if event.type() == QEvent.Type.Enter:
                obj.setCursor(Qt.CursorShape.BlankCursor)
            elif event.type() == QEvent.Type.Leave:
                obj.unsetCursor()
                self._v_line.setVisible(False)
                self._h_line.setVisible(False)
                self._crosshair_label.setVisible(False)
        return super().eventFilter(obj, event)

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

        self._crosshair_label.setText(f"{x:.1f} s, {y:.2f}°{self._temp_unit}")
        self._crosshair_label.setPos(x, y)
        self._crosshair_label.setVisible(True)

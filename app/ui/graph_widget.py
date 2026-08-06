"""Temperature-vs-time profile graph, built on pyqtgraph."""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
import pyqtgraph.exporters
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

CURVE_COLORS = ["#3f8cff", "#e0524d", "#3fbf6f", "#f2b705", "#a86ff0", "#00c2c2"]
DEFAULT_X_RANGE_S = (0.0, 60.0)
Y_RANGE_BY_UNIT = {"C": (0.0, 195.0), "F": (0.0, 390.0)}
DRAG_HIT_PIXELS = 10.0

pg.setConfigOption("background", "#22262b")
pg.setConfigOption("foreground", "#e4e7eb")


class ProfileGraphWidget(QWidget):
    """Time (s) on X, Temperature on Y. Supports overlaying multiple runs.

    Each run keeps the same curve color for as long as the widget lives,
    even across remove_profile/plot_profile cycles, so a list entry's
    highlight color always matches its curve if it's re-added. The same
    is true of a run's time offset (see drag-to-align below).

    Since each run's logging start time is set manually on the meter,
    overlaid runs often don't line up. Click-and-drag directly on a
    curve to nudge it left/right in time (temperature is left alone);
    double-click a curve to reset its offset back to zero.
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

        self._base_x: dict[int, list[float]] = {}
        self._base_y: dict[int, list[float]] = {}
        self._offsets: dict[int, float] = {}

        self._drag_run_id: int | None = None
        self._drag_start_view_x = 0.0
        self._drag_start_offset = 0.0

        self._offset_label = pg.TextItem(anchor=(0, 1))
        self._offset_label.setVisible(False)
        self._plot_widget.addItem(self._offset_label, ignoreBounds=True)

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
        self._base_x.clear()
        self._base_y.clear()
        self._offsets.clear()
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

        self._base_x[run_id] = elapsed_time_s
        self._base_y[run_id] = temperature
        offset = self._offsets.get(run_id, 0.0)

        curve = self._plot_widget.plot(
            [t + offset for t in elapsed_time_s], temperature, pen=pg.mkPen(color, width=2), name=label,
        )
        self._curves[run_id] = curve

    def remove_profile(self, run_id: int) -> None:
        curve = self._curves.pop(run_id, None)
        if curve is not None:
            self._plot_widget.removeItem(curve)
            legend = self._plot_widget.plotItem.legend
            if legend is not None:
                legend.removeItem(curve.name())
        self._base_x.pop(run_id, None)
        self._base_y.pop(run_id, None)

    def get_offset(self, run_id: int) -> float:
        """Seconds this run's curve has been dragged from its logged start time."""
        return self._offsets.get(run_id, 0.0)

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
            elif event.type() == QEvent.Type.MouseButtonPress:
                if self._try_start_drag(event):
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                if self._drag_run_id is not None:
                    self._update_drag(event)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if self._drag_run_id is not None:
                    self._end_drag()
                    return True
            elif event.type() == QEvent.Type.MouseButtonDblClick:
                if self._try_reset_offset(event):
                    return True
        return super().eventFilter(obj, event)

    def _scene_pos(self, event) -> "pg.Point":
        return self._plot_widget.mapToScene(event.position().toPoint())

    def _curve_at_scene_pos(self, scene_pos) -> int | None:
        """Nearest run_id whose curve passes within DRAG_HIT_PIXELS of scene_pos."""
        view_box = self._plot_widget.plotItem.vb
        view_pos = view_box.mapSceneToView(scene_pos)
        px_w, px_h = view_box.viewPixelSize()
        if not px_w or not px_h:
            return None

        best_run_id = None
        best_dist_px = DRAG_HIT_PIXELS
        for run_id, curve in self._curves.items():
            x_data, y_data = curve.getData()
            if x_data is None or len(x_data) == 0:
                continue
            dist_px = np.min(np.hypot((x_data - view_pos.x()) / px_w, (y_data - view_pos.y()) / px_h))
            if dist_px < best_dist_px:
                best_dist_px = dist_px
                best_run_id = run_id
        return best_run_id

    def _try_start_drag(self, event) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        scene_pos = self._scene_pos(event)
        run_id = self._curve_at_scene_pos(scene_pos)
        if run_id is None:
            return False

        view_box = self._plot_widget.plotItem.vb
        self._drag_run_id = run_id
        self._drag_start_view_x = view_box.mapSceneToView(scene_pos).x()
        self._drag_start_offset = self._offsets.get(run_id, 0.0)
        self._plot_widget.viewport().setCursor(Qt.CursorShape.SizeHorCursor)
        self._show_offset_label(run_id, self._drag_start_offset)
        return True

    def _update_drag(self, event) -> None:
        view_box = self._plot_widget.plotItem.vb
        current_x = view_box.mapSceneToView(self._scene_pos(event)).x()
        new_offset = self._drag_start_offset + (current_x - self._drag_start_view_x)
        self._apply_offset(self._drag_run_id, new_offset)
        self._show_offset_label(self._drag_run_id, new_offset)

    def _end_drag(self) -> None:
        self._drag_run_id = None
        self._offset_label.setVisible(False)
        self._plot_widget.viewport().setCursor(Qt.CursorShape.BlankCursor)

    def _try_reset_offset(self, event) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False
        run_id = self._curve_at_scene_pos(self._scene_pos(event))
        if run_id is None:
            return False
        self._apply_offset(run_id, 0.0)
        return True

    def _apply_offset(self, run_id: int, offset_s: float) -> None:
        self._offsets[run_id] = offset_s
        curve = self._curves.get(run_id)
        base_x = self._base_x.get(run_id)
        if curve is None or base_x is None:
            return
        curve.setData([t + offset_s for t in base_x], self._base_y[run_id])

    def _show_offset_label(self, run_id: int, offset_s: float) -> None:
        (x_min, _), (_, y_max) = self._plot_widget.plotItem.vb.viewRange()
        curve = self._curves.get(run_id)
        name = curve.name() if curve is not None else f"Run {run_id}"
        sign = "+" if offset_s >= 0 else ""
        self._offset_label.setText(f"{name}: {sign}{offset_s:.1f}s")
        self._offset_label.setColor(self._colors.get(run_id, "#e4e7eb"))
        self._offset_label.setPos(x_min, y_max)
        self._offset_label.setVisible(True)

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

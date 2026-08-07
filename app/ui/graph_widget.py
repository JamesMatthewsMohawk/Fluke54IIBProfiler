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
_TIME_LEGEND_IDLE = "Time: --"

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

    Hovering shows a dot on each curve at the current time (interpolated
    between that curve's own samples, so it sits exactly on the drawn
    line even between points) and appends each curve's live value to its
    legend entry, alongside a "Time: ..." row -- rather than one
    generic crosshair reading tied to the raw mouse position, which
    doesn't mean anything specific when multiple runs are overlaid.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._temp_unit = "C"

        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setLabel("bottom", "Time", units="s")
        self._plot_widget.setLabel("left", "Temperature")
        self._plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self._plot_widget.setMouseEnabled(x=True, y=True)
        legend = self._plot_widget.addLegend(offset=(10, 10))
        self._plot_widget.setXRange(*DEFAULT_X_RANGE_S, padding=0)
        self._apply_y_range()

        # pyqtgraph legends are click-and-drag movable by default, with no
        # public flag to disable it -- and a drag started near the legend
        # (right next to the curve-drag feature below) easily relocates it
        # by accident, leaving it anywhere over the plot. Pin it in place.
        legend.mouseDragEvent = self._ignore_axis_event

        view_box = self._plot_widget.plotItem.vb

        # A plain in-plot wheel scroll normally scales X and Y together in
        # one step (pyqtgraph's default when both axes are mouse-enabled).
        # That coupling made zooming feel broken -- an in-progress X zoom
        # would visibly reverse/stall once Y's fixed range hit its bound.
        # Force each wheel tick to a single axis instead: plain scroll only
        # ever touches X (identical to the pre-Y-zoom behavior), Ctrl+scroll
        # only touches Y.
        view_box.wheelEvent = self._make_single_axis_wheel_event(view_box)

        # Left-drag or scroll directly on the Y-axis strip mirrors the
        # X-axis strip's existing behavior (pyqtgraph's default AxisItem
        # gesture, never blocked there): drag to pan, scroll to zoom --
        # except scrolling here always zooms Y with no Ctrl needed, since
        # hovering the Y numbers unambiguously means "adjust Y". That needs
        # calling ViewBox.wheelEvent directly rather than through the
        # Ctrl-aware override just above, which would otherwise ignore the
        # forced axis and zoom X on a plain scroll.
        y_axis = self._plot_widget.getAxis("left")
        y_axis.wheelEvent = self._make_fixed_axis_wheel_event(view_box, axis=1)

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
        self._v_line.setVisible(False)
        self._plot_widget.addItem(self._v_line, ignoreBounds=True)

        self._value_dots: dict[int, pg.ScatterPlotItem] = {}

        # A name-only, dataless curve purely so the legend can carry a live
        # "Time: ..." row alongside each curve's live temperature -- see
        # _on_mouse_moved.
        self._time_legend_item = self._plot_widget.plot([], [], pen=pg.mkPen(None), name=_TIME_LEGEND_IDLE)

        self._proxy = pg.SignalProxy(
            self._plot_widget.scene().sigMouseMoved, rateLimit=60, slot=self._on_mouse_moved
        )

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

    @staticmethod
    def _make_fixed_axis_wheel_event(view_box: pg.ViewBox, axis: int):
        def _wheel_event(event):
            pg.ViewBox.wheelEvent(view_box, event, axis=axis)

        return _wheel_event

    def clear_profiles(self) -> None:
        for curve in self._curves.values():
            self._plot_widget.removeItem(curve)
        for dot in self._value_dots.values():
            self._plot_widget.removeItem(dot)
        self._curves.clear()
        self._value_dots.clear()
        self._colors.clear()
        self._base_x.clear()
        self._base_y.clear()
        self._offsets.clear()
        self._next_color_index = 0
        legend = self._plot_widget.plotItem.legend
        if legend is not None:
            legend.clear()  # also drops the Time row -- re-add it below
            legend.addItem(self._time_legend_item, _TIME_LEGEND_IDLE)

    def plot_profile(self, run_id: int, elapsed_time_s: list[float], temperature: list[float], label: str) -> None:
        if run_id in self._curves:
            old_curve = self._curves[run_id]
            self._plot_widget.removeItem(old_curve)
            legend = self._plot_widget.plotItem.legend
            if legend is not None:
                # Matched by item identity, not name text: a legend label
                # left mid-hover holds "name — value", not the plain name.
                legend.removeItem(old_curve)

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

        if run_id not in self._value_dots:
            dot = pg.ScatterPlotItem(size=10, brush=pg.mkBrush(color), pen=pg.mkPen("#e4e7eb", width=1))
            self._plot_widget.addItem(dot, ignoreBounds=True)
            self._value_dots[run_id] = dot

    def remove_profile(self, run_id: int) -> None:
        curve = self._curves.pop(run_id, None)
        if curve is not None:
            self._plot_widget.removeItem(curve)
            legend = self._plot_widget.plotItem.legend
            if legend is not None:
                legend.removeItem(curve)
        self._base_x.pop(run_id, None)
        self._base_y.pop(run_id, None)

        dot = self._value_dots.pop(run_id, None)
        if dot is not None:
            self._plot_widget.removeItem(dot)

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
            if event.type() == QEvent.Type.Leave:
                self._hide_crosshair()
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
        self._plot_widget.viewport().unsetCursor()

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
            self._hide_crosshair()
            return

        view_box = self._plot_widget.plotItem.vb
        x = view_box.mapSceneToView(pos).x()

        self._v_line.setPos(x)
        self._v_line.setVisible(True)
        self._set_legend_text(self._time_legend_item, f"Time: {x:.1f} s")

        for run_id, curve in self._curves.items():
            dot = self._value_dots.get(run_id)
            if dot is None:
                continue
            x_data, y_data = curve.getData()
            if len(x_data) == 0 or x < x_data[0] or x > x_data[-1]:
                dot.setData([], [])
                self._set_legend_text(curve, curve.name())
                continue
            y_val = float(np.interp(x, x_data, y_data))
            dot.setData([x], [y_val])
            self._set_legend_text(curve, f"{curve.name()} — {y_val:.1f}°{self._temp_unit}")

    def _hide_crosshair(self) -> None:
        self._v_line.setVisible(False)
        self._set_legend_text(self._time_legend_item, _TIME_LEGEND_IDLE)
        for run_id, dot in self._value_dots.items():
            dot.setData([], [])
            curve = self._curves.get(run_id)
            if curve is not None:
                self._set_legend_text(curve, curve.name())

    def _set_legend_text(self, item: pg.PlotDataItem, text: str) -> None:
        legend = self._plot_widget.plotItem.legend
        if legend is None:
            return
        for sample, label in legend.items:
            if sample.item is item:
                label.setText(text)
                return

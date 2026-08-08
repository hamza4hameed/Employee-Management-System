import os
import sys
from typing import List, Dict, Any, Optional

os.environ.setdefault("MPLBACKEND", "Qt5Agg")
os.environ.setdefault("QT_QPA_PLATFORM", "windows")

# NOTE: We deliberately do NOT call matplotlib.use() at module import time.
# Doing so can segfault the process on Python 3.13 + PyQt5 if either (a) no
# QApplication exists yet, or (b) QApplication was created with a non-"windows"
# QPA platform (e.g. offscreen / minimal) but the Qt5Agg backend still tries
# to attach to native window handles. Instead we defer matplotlib.use() and
# the FigureCanvasQTAgg import into _ensure_canvas(), which is only invoked
# when the user explicitly navigates to the Analytics tab -- at that point
# QApplication is fully alive with the real windows platform.
try:
    import matplotlib
except Exception:  # pragma: no cover
    matplotlib = None  # type: ignore

_FigureCanvasQTAgg = None
_MPL_BACKEND_PINNED = False


def _pin_mpl_backend_once() -> bool:
    global _MPL_BACKEND_PINNED
    if matplotlib is None:
        return False
    if _MPL_BACKEND_PINNED:
        return True
    try:
        matplotlib.use("Qt5Agg", force=True)
        _MPL_BACKEND_PINNED = True
        return True
    except Exception:
        return False


def _get_canvas_cls():
    global _FigureCanvasQTAgg
    if _FigureCanvasQTAgg is None:
        if not _pin_mpl_backend_once():
            raise RuntimeError("Matplotlib Qt5Agg backend could not be enabled.")
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
        _FigureCanvasQTAgg = FigureCanvasQTAgg
    return _FigureCanvasQTAgg


from matplotlib.figure import Figure

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
)

import database
from csv_utils import compute_department_aggregates

LIGHT_PALETTE = {
    "bg": "#ffffff",
    "axes_bg": "#f9fafb",
    "text": "#111827",
    "muted": "#6b7280",
    "grid": "#e5e7eb",
    "bar": "#2563eb",
    "hbar": "#10b981",
}

DARK_PALETTE = {
    "bg": "#111827",
    "axes_bg": "#0f172a",
    "text": "#e5e7eb",
    "muted": "#9ca3af",
    "grid": "#374151",
    "bar": "#3b82f6",
    "hbar": "#34d399",
}

_DISABLED_ANALYTICS_MSG = (
    "Analytics charts are disabled for this session.\n\n"
    "This usually happens if the Matplotlib + PyQt5 backend combination is "
    "not stable on this machine.\n"
    "All other features (employee records, CSV import/export, search and "
    "filtering) remain fully functional."
)


class AnalyticsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_rows: List[Dict[str, Any]] = []
        self._palette = LIGHT_PALETTE
        self._canvas_built: bool = False
        self._canvas_placeholder: Optional[QFrame] = None
        self._disabled: bool = False
        self._ph_label: Optional[QLabel] = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        card = QFrame(self)
        card.setProperty("class", "card")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title = QLabel("Analytics")
        title.setProperty("class", "cardTitle")

        subtitle = QLabel("Departmental headcount and compensation trends.")
        subtitle.setProperty("class", "cardSubtitle")
        subtitle.setWordWrap(True)

        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header_row.addLayout(title_col, 1)

        self.refresh_button = QPushButton("Refresh Charts")
        self.refresh_button.setProperty("class", "secondaryButton")
        self.refresh_button.setCursor(Qt.PointingHandCursor)
        self.refresh_button.clicked.connect(self._on_refresh_charts_clicked)
        header_row.addWidget(self.refresh_button)

        layout.addLayout(header_row)

        self.summary_label = QLabel("")
        self.summary_label.setProperty("class", "cardSubtitle")
        layout.addWidget(self.summary_label)

        # Figure object itself is pure-python-in-memory, safe to construct
        # even if we never attach a Qt-backed canvas to it.
        try:
            self.figure = Figure(figsize=(8, 6), tight_layout=True)
        except Exception:
            self.figure = None
        self.canvas: Any = None

        self._canvas_placeholder = QFrame()
        self._canvas_placeholder.setProperty("class", "card")
        placeholder_layout = QVBoxLayout(self._canvas_placeholder)
        placeholder_layout.setAlignment(Qt.AlignCenter)
        self._ph_label = QLabel(
            "Charts will render when you click 'Refresh Charts'\n"
            "(they are not loaded on startup for maximum compatibility)."
        )
        self._ph_label.setAlignment(Qt.AlignCenter)
        self._ph_label.setProperty("class", "cardSubtitle")
        self._ph_label.setWordWrap(True)
        self._ph_label.setStyleSheet(
            "QLabel { color: palette(mid); font-size: 13px; padding: 20px; }"
        )
        placeholder_layout.addWidget(self._ph_label)
        self._canvas_placeholder.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        layout.addWidget(self._canvas_placeholder, 1)

        root.addWidget(card)

    def _mark_disabled(self, reason: str = "") -> None:
        self._disabled = True
        self.refresh_button.setEnabled(False)
        if self._ph_label is not None:
            msg = _DISABLED_ANALYTICS_MSG
            if reason:
                msg = msg + "\n\nReason: " + str(reason)
            self._ph_label.setText(msg)
            self._ph_label.setStyleSheet(
                "QLabel { color: #b91c1c; font-size: 13px; padding: 20px; }"
            )

    def _ensure_canvas(self) -> bool:
        if self._disabled:
            return False
        if self._canvas_built and self.canvas is not None:
            return True
        if self.figure is None:
            self._mark_disabled("Matplotlib Figure() could not be constructed.")
            return False
        platform = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
        if platform in ("minimal", "offscreen"):
            return False
        parent_layout = self._canvas_placeholder.parentWidget().layout()
        try:
            CanvasCls = _get_canvas_cls()
            self.canvas = CanvasCls(self.figure)
            self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.canvas.updateGeometry()
            idx = parent_layout.indexOf(self._canvas_placeholder)
            if idx >= 0:
                parent_layout.removeWidget(self._canvas_placeholder)
                self._canvas_placeholder.hide()
                parent_layout.insertWidget(idx, self.canvas, 1)
            self._canvas_built = True
            return True
        except Exception as exc:
            self._mark_disabled(str(exc))
            try:
                from PyQt5.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    "Analytics Charts Disabled",
                    "Matplotlib could not build the canvas:\n{}\n\n"
                    "Charts are disabled for this session. The rest of the app "
                    "works normally.\nIf you want charts, try updating "
                    "matplotlib (pip install --upgrade matplotlib) or install "
                    "PySide2 and use that instead of PyQt5.".format(exc),
                )
            except Exception:
                pass
            return False

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def set_theme(self, theme: str) -> None:
        self._palette = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE
        # Only paint the in-memory figure (never build a canvas on theme toggle;
        # toggling can happen at any time during MainWindow init and we must
        # stay crash-safe on Python 3.13 + PyQt5.)
        if self._last_rows:
            self._render_into_figure_only(self._last_rows)
            self._draw_if_ready_or_update_placeholder()
        else:
            self.refresh()

    def refresh(self) -> None:
        """Safe background refresh: NEVER builds a canvas.

        Reads data from DB, renders into the pure in-memory matplotlib
        Figure() object, and either redraws an existing canvas (if one was
        already built previously) OR updates the text placeholder message.
        Triggered automatically from MainWindow on tab-switch and on employee
        data_changed signals -- must never segfault, never try to attach
        a new Qt canvas.
        """
        rows = database.get_all_employees()
        self._render_into_figure_only(rows)
        self._draw_if_ready_or_update_placeholder()

    def _on_refresh_charts_clicked(self) -> None:
        """User-initiated button click. The ONLY place that is allowed to
        call _ensure_canvas() and build FigureCanvasQTAgg for the first time.
        """
        rows = database.get_all_employees()
        self._render_into_figure_only(rows)
        if not self._ensure_canvas():
            self._update_placeholder_message()
            return
        try:
            self.canvas.draw_idle()
        except Exception as exc:
            self._mark_disabled("draw_idle() failed: {}".format(exc))

    def _update_placeholder_message(self) -> None:
        if self._disabled or self._ph_label is None:
            return
        if self._canvas_built:
            return
        n = len(self._last_rows)
        depts, counts, avgs = compute_department_aggregates(self._last_rows)
        summary_parts = [
            "Data loaded: {} employee{} across {} department{}.".format(
                n, "" if n == 1 else "s",
                len(depts), "" if len(depts) == 1 else "s",
            ),
            "",
            "Click the 'Refresh Charts' button (top-right of this card) to",
            "render the bar charts (Matplotlib canvas is not built on startup",
            "for maximum compatibility).",
        ]
        self._ph_label.setText("\n".join(summary_parts))

    def _draw_if_ready_or_update_placeholder(self) -> None:
        if self.canvas is not None and self._canvas_built:
            try:
                self.canvas.draw_idle()
            except Exception as exc:
                self._mark_disabled("draw_idle() failed: {}".format(exc))
            return
        self._update_placeholder_message()

    def _render_into_figure_only(self, rows: List[Dict[str, Any]]) -> None:
        """Pure-memory render step. Never touches any Qt widget / canvas."""
        self._last_rows = rows
        pal = self._palette
        departments, counts, avg_salaries = compute_department_aggregates(rows)

        self.summary_label.setText(
            "Total employees: {}  ·  Departments: {}".format(
                len(rows), len(departments)
            )
        )

        if self.figure is None:
            # Figure couldn't be constructed earlier; nothing to draw.
            return

        try:
            self.figure.clear()
            self.figure.set_facecolor(pal["bg"])

            ax1 = self.figure.add_subplot(2, 1, 1)
            self._render_count_chart(ax1, departments, counts, pal)

            ax2 = self.figure.add_subplot(2, 1, 2)
            self._render_salary_chart(ax2, departments, avg_salaries, pal)

            self.figure.tight_layout(pad=3.0)
        except Exception as exc:
            # Figure-level matplotlib failures are non-fatal; just disable
            # charts for this session and show a message on placeholder.
            self._mark_disabled("Matplotlib render error: {}".format(exc))

    # ------------------------------------------------------------------
    # Renderers
    # ------------------------------------------------------------------
    def _render_count_chart(self, ax, departments: List[str], counts: List[int], pal: Dict[str, str]) -> None:
        ax.set_facecolor(pal["axes_bg"])
        bars = ax.bar(departments, counts, color=pal["bar"], edgecolor="none", zorder=3)

        for spine in ax.spines.values():
            spine.set_color(pal["grid"])
        ax.tick_params(axis="x", colors=pal["text"], labelsize=9)
        ax.tick_params(axis="y", colors=pal["text"], labelsize=9)
        for label in ax.get_xticklabels():
            label.set_rotation(20)
            label.set_ha("right")

        max_count = max(counts) if counts else 1
        ax.set_ylim(0, max(int(max_count * 1.20), 1))

        ax.grid(axis="y", linestyle="--", color=pal["grid"], alpha=0.6, zorder=0)
        ax.set_axisbelow(True)

        ax.set_title("Employee Count by Department", color=pal["text"], fontsize=12, fontweight="bold", pad=12)
        ax.set_ylabel("Employees", color=pal["muted"], fontsize=10)

        for bar, value in zip(bars, counts):
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                height + (max_count * 0.02),
                str(value),
                ha="center",
                va="bottom",
                color=pal["text"],
                fontsize=9,
                fontweight="semibold",
            )

    def _render_salary_chart(self, ax, departments: List[str], avg_salaries: List[float], pal: Dict[str, str]) -> None:
        ax.set_facecolor(pal["axes_bg"])
        y_positions = list(range(len(departments)))
        bars = ax.barh(y_positions, avg_salaries, color=pal["hbar"], edgecolor="none", zorder=3)

        ax.set_yticks(y_positions)
        ax.set_yticklabels(departments, color=pal["text"], fontsize=9)
        ax.tick_params(axis="x", colors=pal["text"], labelsize=9)

        for spine in ax.spines.values():
            spine.set_color(pal["grid"])

        ax.invert_yaxis()
        max_salary = max(avg_salaries) if avg_salaries else 1.0
        ax.set_xlim(0, max_salary * 1.20 if max_salary > 0 else 1)

        ax.grid(axis="x", linestyle="--", color=pal["grid"], alpha=0.6, zorder=0)
        ax.set_axisbelow(True)

        ax.set_title(
            "Average Salary by Department",
            color=pal["text"],
            fontsize=12,
            fontweight="bold",
            pad=12,
        )
        ax.set_xlabel("Average Salary (USD)", color=pal["muted"], fontsize=10)

        for bar, value in zip(bars, avg_salaries):
            ax.text(
                bar.get_width() + (max_salary * 0.015),
                bar.get_y() + bar.get_height() / 2,
                "${:,.0f}".format(value),
                va="center",
                ha="left",
                color=pal["text"],
                fontsize=9,
                fontweight="semibold",
            )

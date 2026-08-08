import os
import sys
from typing import List, Dict, Any, Optional

# ---------------------------------------------------------------------------
# Crash diagnostics (best-effort faulthandler so that any 0xC0000005 access
# violations during FigureCanvasQTAgg construction still leave a readable log.
# ---------------------------------------------------------------------------
_FAULT_LOG = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "chart_crash.log"
)
try:
    import faulthandler
    if callable(getattr(faulthandler, "is_enabled", None)) and not faulthandler.is_enabled():
        try:
            _fault_file = open(_FAULT_LOG, "a", encoding="utf-8")
            faulthandler.enable(file=_fault_file, all_threads=True)
        except Exception:
            pass
except Exception:
    pass

os.environ.setdefault("MPLBACKEND", "Qt5Agg")
os.environ.setdefault("QT_QPA_PLATFORM", "windows")

# ---------------------------------------------------------------------------
# Rendering strategy:
#
# DEFAULT -> use pure-Qt bar charts.  Matplotlib canvas is opt-in only via
# environment variable EMPLOYEE_APP_USE_MATPLOTLIB=1
#
# Matplotlib Qt5Agg is known to segfault on many Python 3.13 + PyQt5 Windows
# installs (exit code 0xC0000005 with zero Python traceback).  We cannot catch a
# segfault from pure Python, so the safe default is to never touch matplotlib
# canvas logic at runtime unless the user explicitly asks for it.
# ---------------------------------------------------------------------------
_USE_MATPLOTLIB = (
    os.environ.get("EMPLOYEE_APP_USE_MATPLOTLIB", "").strip().lower()
    in ("1", "true", "yes", "on")
)

# Lazy matplotlib backend + canvas loader (only used when user opts-in AND
# clicks Refresh Charts). Figure itself is pure-in-memory; only the canvas
# attachment causes segfault risk.
try:
    import matplotlib  # noqa: F401 (presence check only)
    _MATPLOTLIB_AVAILABLE = True
except Exception:
    _MATPLOTLIB_AVAILABLE = False

_FigureCanvasQTAgg = None
_MPL_BACKEND_PINNED = False


def _pin_mpl_backend_once() -> bool:
    global _MPL_BACKEND_PINNED
    if not _MATPLOTLIB_AVAILABLE:
        return False
    if _MPL_BACKEND_PINNED:
        return True
    try:
        import matplotlib
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


try:
    from matplotlib.figure import Figure
except Exception:
    Figure = None  # type: ignore

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QSizePolicy,
    QScrollArea,
    QGridLayout,
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
        self._disabled: bool = False
        self._qt_charts_container: Optional[QWidget] = None
        self._qt_charts_layout: Optional[QVBoxLayout] = None
        self._figure = None  # type: ignore
        self.canvas: Any = None
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

        if _MATPLOTLIB_AVAILABLE and Figure is not None and _USE_MATPLOTLIB:
            try:
                self._figure = Figure(figsize=(8, 6), tight_layout=True)
            except Exception:
                self._figure = None
        self.canvas = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self._qt_charts_container = QWidget()
        self._qt_charts_layout = QVBoxLayout(self._qt_charts_container)
        self._qt_charts_layout.setContentsMargins(0, 0, 0, 0)
        self._qt_charts_layout.setSpacing(24)
        scroll.setWidget(self._qt_charts_container)
        layout.addWidget(scroll, 1)

        root.addWidget(card)

    def _mark_disabled(self, reason: str = "") -> None:
        self._disabled = True
        self.refresh_button.setEnabled(False)
        self.summary_label.setText(_DISABLED_ANALYTICS_MSG + (("\nReason: " + str(reason)) if reason else ""))
        self.summary_label.setStyleSheet("QLabel { color: #b91c1c; font-size: 13px; padding: 10px; }")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def set_theme(self, theme: str) -> None:
        self._palette = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE
        if self._last_rows:
            self._render_qt_native_charts(self._last_rows)
            if _USE_MATPLOTLIB and self._canvas_built:
                self._render_into_figure_only(self._last_rows)
                if self.canvas is not None:
                    try:
                        self.canvas.draw_idle()
                    except Exception as exc:
                        self._mark_disabled("draw_idle() failed: {}".format(exc))
        else:
            self.refresh()

    def refresh(self) -> None:
        rows = database.get_all_employees()
        self._last_rows = rows
        self._render_qt_native_charts(rows)

    def _on_refresh_charts_clicked(self) -> None:
        rows = database.get_all_employees()
        self._last_rows = rows
        self._render_qt_native_charts(rows)
        if _USE_MATPLOTLIB:
            self._render_into_figure_only(rows)
            if not self._ensure_canvas():
                return
            try:
                self.canvas.draw_idle()
            except Exception as exc:
                self._mark_disabled("draw_idle() failed: {}".format(exc))

    # ------------------------------------------------------------------
    # Qt-NATIVE bar chart renderer (zero matplotlib dependency, safe always)
    # ------------------------------------------------------------------
    def _clear_layout(self, target_layout) -> None:
        if target_layout is None:
            return
        while target_layout.count():
            child = target_layout.takeAt(0)
            w = child.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
            else:
                sub_layout = child.layout()
                if sub_layout is not None:
                    self._clear_layout(sub_layout)

    def _render_qt_native_charts(self, rows: List[Dict[str, Any]]) -> None:
        pal = self._palette
        departments, counts, avg_salaries = compute_department_aggregates(rows)
        self.summary_label.setText(
            "Total employees: {}  \u00b7  Departments: {}".format(
                len(rows), len(departments)
            )
        )
        container_layout = self._qt_charts_layout
        self._clear_layout(container_layout)
        if not departments:
            empty = QLabel(
                "No employee records to chart yet. Add employees first to see charts."
            )
            empty.setAlignment(Qt.AlignCenter)
            empty.setProperty("class", "cardSubtitle")
            empty.setStyleSheet(
                "QLabel {{ color: {}; padding: 40px 0; font-size: 14px; }}".format(
                    pal["muted"]
                )
            )
            container_layout.addWidget(empty)
            return

        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)

        # ----- Chart 1: Employee Count by Department (vertical bars)
        chart1_title = QLabel("Employee Count by Department")
        chart1_title.setProperty("class", "cardTitle")
        chart1_title.setFont(title_font)
        chart1_title.setStyleSheet("QLabel {{ color: {}; }}".format(pal["text"]))
        chart1_title.setContentsMargins(0, 0, 0, 4)
        container_layout.addWidget(chart1_title)

        chart1 = QFrame()
        chart1.setProperty("class", "card")
        chart1.setObjectName("countChart")
        chart1.setMinimumHeight(260)
        count_grid = QGridLayout(chart1)
        count_grid.setContentsMargins(16, 20, 16, 16)
        count_grid.setHorizontalSpacing(14)
        count_grid.setVerticalSpacing(6)
        max_count = max(counts) if counts else 1
        for col, (dept, cnt) in enumerate(zip(departments, counts)):
            ratio = cnt / max_count if max_count else 0.0
            bar_wrap = QWidget()
            wrap_layout = QVBoxLayout(bar_wrap)
            wrap_layout.setContentsMargins(0, 0, 0, 0)
            wrap_layout.setSpacing(4)
            wrap_layout.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)

            val_lbl = QLabel(str(cnt))
            val_lbl.setAlignment(Qt.AlignCenter)
            val_lbl.setStyleSheet(
                "QLabel {{ color: {}; font-weight: 700; font-size: 13px; }}".format(
                    pal["text"]
                )
            )

            bar_fill = QFrame()
            bar_h = max(6, int(160 * ratio))
            bar_fill.setFixedHeight(bar_h)
            bar_fill.setMinimumWidth(36)
            bar_fill.setStyleSheet(
                "QFrame {{ background-color: {}; border-radius: 6px; }}".format(
                    pal["bar"]
                )
            )
            bar_fill.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            short_name = dept if len(dept) <= 14 else dept[:12] + "\u2026"
            dept_lbl = QLabel(short_name)
            dept_lbl.setAlignment(Qt.AlignCenter)
            dept_lbl.setWordWrap(True)
            dept_lbl.setStyleSheet(
                "QLabel {{ color: {}; font-size: 11px; }}".format(pal["muted"])
            )

            wrap_layout.addWidget(val_lbl, 0, Qt.AlignHCenter)
            wrap_layout.addWidget(bar_fill, 0, Qt.AlignHCenter | Qt.AlignBottom)
            wrap_layout.addWidget(dept_lbl, 0, Qt.AlignHCenter)
            count_grid.addWidget(bar_wrap, 0, col, Qt.AlignBottom)
        container_layout.addWidget(chart1)

        # ----- Chart 2: Average Salary per Department (horizontal bars)
        chart2_title = QLabel("Average Salary per Department")
        chart2_title.setProperty("class", "cardTitle")
        chart2_title.setFont(title_font)
        chart2_title.setStyleSheet("QLabel {{ color: {}; }}".format(pal["text"]))
        chart2_title.setContentsMargins(0, 18, 0, 4)
        container_layout.addWidget(chart2_title)

        chart2 = QFrame()
        chart2.setProperty("class", "card")
        chart2.setMinimumHeight(max(140, 60 + len(departments) * 48))
        salary_grid = QGridLayout(chart2)
        salary_grid.setContentsMargins(16, 20, 16, 16)
        salary_grid.setHorizontalSpacing(12)
        salary_grid.setVerticalSpacing(10)
        max_sal = max(avg_salaries) if avg_salaries else 1.0
        for row_idx, (dept, avg) in enumerate(zip(departments, avg_salaries)):
            ratio = avg / max_sal if max_sal else 0.0
            dept_lbl = QLabel(dept)
            dept_lbl.setStyleSheet(
                "QLabel {{ color: {}; font-size: 12px; font-weight: 600; }}".format(
                    pal["text"]
                )
            )
            dept_lbl.setMinimumWidth(140)

            bar_wrap = QWidget()
            bar_wrap_l = QHBoxLayout(bar_wrap)
            bar_wrap_l.setContentsMargins(0, 0, 0, 0)
            bar_fill = QFrame()
            bar_fill.setFixedHeight(20)
            bar_w = max(40, int(320 * ratio))
            bar_fill.setFixedWidth(bar_w)
            bar_fill.setStyleSheet(
                "QFrame {{ background-color: {}; border-radius: 6px; }}".format(
                    pal["hbar"]
                )
            )
            bar_wrap_l.addWidget(bar_fill, 0, Qt.AlignVCenter | Qt.AlignLeft)
            bar_wrap_l.addStretch(1)

            val_lbl = QLabel("${:,.0f}".format(avg))
            val_lbl.setStyleSheet(
                "QLabel {{ color: {}; font-size: 12px; font-weight: 700; }}".format(
                    pal["text"]
                )
            )
            salary_grid.addWidget(
                dept_lbl, row_idx, 0, Qt.AlignVCenter | Qt.AlignRight
            )
            salary_grid.addWidget(
                bar_wrap, row_idx, 1, Qt.AlignVCenter | Qt.AlignLeft
            )
            salary_grid.addWidget(
                val_lbl, row_idx, 2, Qt.AlignVCenter | Qt.AlignLeft
            )
        container_layout.addWidget(chart2)

    # ------------------------------------------------------------------
    # Matplotlib-only code (opt-in path only)
    # ------------------------------------------------------------------
    def _ensure_canvas(self) -> bool:
        if not _USE_MATPLOTLIB:
            return False
        if self._disabled:
            return False
        if self._canvas_built and self.canvas is not None:
            return True
        if self._figure is None:
            self._mark_disabled("Matplotlib Figure() could not be constructed.")
            return False
        platform = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
        if platform in ("minimal", "offscreen"):
            return False
        scroll = self._qt_charts_container.parent()
        parent_layout = None
        if scroll is not None and hasattr(scroll, "parentWidget"):
            grand = scroll.parentWidget()
            if grand is not None:
                parent_layout = grand.layout()
        try:
            try:
                import faulthandler
                try:
                    faulthandler.dump_traceback_later(
                        15, repeat=False, file=open(_FAULT_LOG, "a")
                    )
                except Exception:
                    pass
            except Exception:
                pass
            CanvasCls = _get_canvas_cls()
            self.canvas = CanvasCls(self._figure)
            try:
                import faulthandler
                try:
                    faulthandler.cancel_dump_traceback_later()
                except Exception:
                    pass
            except Exception:
                pass
            self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.canvas.updateGeometry()
            if parent_layout is not None:
                idx = parent_layout.indexOf(self._qt_charts_container)
                if idx >= 0:
                    parent_layout.insertWidget(idx, self.canvas, 1)
                else:
                    parent_layout.addWidget(self.canvas, 1)
            self._canvas_built = True
            return True
        except Exception as exc:
            try:
                import faulthandler
                try:
                    faulthandler.cancel_dump_traceback_later()
                except Exception:
                    pass
            except Exception:
                pass
            self._mark_disabled(str(exc))
            try:
                from PyQt5.QtWidgets import QMessageBox

                warn = (
                    "Matplotlib could not build the canvas:\n{}\n\n"
                    "Charts disabled for this session; pure-Qt charts are still "
                    "shown.\n"
                    "If you want Matplotlib canvases, try updating packages:\n"
                    "    pip install --upgrade matplotlib PyQt5\n\n"
                    "A crash traceback (if any) was written to:\n{}"
                ).format(exc, _FAULT_LOG)
                QMessageBox.warning(self, "Analytics Charts Disabled", warn)
            except Exception:
                pass
            return False

    def _render_into_figure_only(self, rows: List[Dict[str, Any]]) -> None:
        if self._figure is None:
            return
        pal = self._palette
        departments, counts, avg_salaries = compute_department_aggregates(rows)
        self.summary_label.setText(
            "Total employees: {}  \u00b7  Departments: {}".format(
                len(rows), len(departments)
            )
        )
        try:
            self._figure.clear()
            self._figure.set_facecolor(pal["bg"])
            ax1 = self._figure.add_subplot(2, 1, 1)
            self._render_count_chart(ax1, departments, counts, pal)
            ax2 = self._figure.add_subplot(2, 1, 2)
            self._render_salary_chart(ax2, departments, avg_salaries, pal)
            self._figure.tight_layout(pad=3.0)
        except Exception as exc:
            self._mark_disabled("Matplotlib render error: {}".format(exc))

    # ------------------------------------------------------------------
    # Matplotlib renderers (opt-in path only)
    # ------------------------------------------------------------------
    def _render_count_chart(
        self, ax, departments: List[str], counts: List[int], pal: Dict[str, str]
    ) -> None:
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
        ax.set_title(
            "Employee Count by Department",
            color=pal["text"],
            fontsize=12,
            fontweight="bold",
            pad=12,
        )
        ax.set_ylabel("Employees", color=pal["muted"], fontsize=10)
        for mpl_bar, value in zip(bars, counts):
            height = mpl_bar.get_height()
            ax.text(
                mpl_bar.get_x() + mpl_bar.get_width() / 2,
                height + (max_count * 0.02),
                str(value),
                ha="center",
                va="bottom",
                color=pal["text"],
                fontsize=9,
                fontweight="semibold",
            )

    def _render_salary_chart(
        self, ax, departments: List[str], avg_salaries: List[float], pal: Dict[str, str]
    ) -> None:
        ax.set_facecolor(pal["axes_bg"])
        y_positions = list(range(len(departments)))
        bars = ax.barh(
            y_positions, avg_salaries, color=pal["hbar"], edgecolor="none", zorder=3
        )
        ax.set_yticks(y_positions)
        ax.set_yticklabels(departments)
        ax.invert_yaxis()
        for spine in ax.spines.values():
            spine.set_color(pal["grid"])
        ax.tick_params(axis="x", colors=pal["text"], labelsize=9)
        ax.tick_params(axis="y", colors=pal["text"], labelsize=9)
        max_sal = max(avg_salaries) if avg_salaries else 1
        ax.set_xlim(0, max_sal * 1.20)
        ax.grid(axis="x", linestyle="--", color=pal["grid"], alpha=0.6, zorder=0)
        ax.set_axisbelow(True)
        ax.set_title(
            "Average Salary per Department",
            color=pal["text"],
            fontsize=12,
            fontweight="bold",
            pad=12,
        )
        ax.set_xlabel("Average Salary (USD)", color=pal["muted"], fontsize=10)
        for bar, bar_val in zip(bars, avg_salaries):
            width = bar.get_width()
            ax.text(
                width + (max_sal * 0.015),
                bar.get_y() + bar.get_height() / 2,
                "${:,.0f}".format(bar_val),
                ha="left",
                va="center",
                color=pal["text"],
                fontsize=9,
                fontweight="semibold",
            )

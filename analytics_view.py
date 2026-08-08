from typing import List, Dict, Any, Optional

import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
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


class AnalyticsView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_rows: List[Dict[str, Any]] = []
        self._palette = LIGHT_PALETTE
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
        self.refresh_button.clicked.connect(self.refresh)
        header_row.addWidget(self.refresh_button)

        layout.addLayout(header_row)

        self.summary_label = QLabel("")
        self.summary_label.setProperty("class", "cardSubtitle")
        layout.addWidget(self.summary_label)

        self.figure = Figure(figsize=(8, 6), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas.updateGeometry()
        layout.addWidget(self.canvas, 1)

        root.addWidget(card)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def set_theme(self, theme: str) -> None:
        self._palette = DARK_PALETTE if theme == "dark" else LIGHT_PALETTE
        if self._last_rows:
            self.render_charts(self._last_rows)
        else:
            self.refresh()

    def refresh(self) -> None:
        rows = database.get_all_employees()
        self.render_charts(rows)

    def render_charts(self, rows: List[Dict[str, Any]]) -> None:
        self._last_rows = rows
        pal = self._palette
        departments, counts, avg_salaries = compute_department_aggregates(rows)

        self.summary_label.setText(
            "Total employees: {}  ·  Departments: {}".format(
                len(rows), len(departments)
            )
        )

        self.figure.clear()
        self.figure.set_facecolor(pal["bg"])

        ax1 = self.figure.add_subplot(2, 1, 1)
        self._render_count_chart(ax1, departments, counts, pal)

        ax2 = self.figure.add_subplot(2, 1, 2)
        self._render_salary_chart(ax2, departments, avg_salaries, pal)

        self.figure.tight_layout(pad=3.0)
        self.canvas.draw_idle()

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

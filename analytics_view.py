"""
analytics_view.py — Business Dashboard for the Employee Management System.

Renders a pure-Qt dashboard with:
  • Summary KPI cards (total / active / inactive / on-leave / departments)
  • Department analytics table with bar-chart column and % distribution
  • Salary analytics (total / average / min / max per department)
  • CSV export of the summary report

No Matplotlib dependency is required.  All charts are drawn with plain Qt widgets.
"""
from __future__ import annotations

import csv
import os
from typing import Any, Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QThread, QSize
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import database
from icon_utils import get_icon
from logger import logger

# ---------------------------------------------------------------------------
# Palette helpers
# ---------------------------------------------------------------------------
LIGHT = {
    "card_bg": "#ffffff",
    "card_border": "#e2e8f0",
    "page_bg": "#f1f5f9",
    "text": "#0f172a",
    "muted": "#64748b",
    "bar_primary": "#2563eb",
    "bar_accent": "#059669",
    "bar_track": "#e2e8f0",
    "kpi_total": ("#eff6ff", "#1d4ed8", "#bfdbfe"),   # (bg, text, border)
    "kpi_active": ("#f0fdf4", "#15803d", "#bbf7d0"),
    "kpi_inactive": ("#fefce8", "#a16207", "#fde047"),
    "kpi_leave": ("#fff7ed", "#c2410c", "#fed7aa"),
    "kpi_depts": ("#faf5ff", "#6d28d9", "#ddd6fe"),
    "header_bg": "#f8fafc",
    "header_text": "#475569",
    "row_alt": "#f8fafc",
    "divider": "#e2e8f0",
}
DARK = {
    "card_bg": "#111827",
    "card_border": "#1f2937",
    "page_bg": "#0a0f1d",
    "text": "#f8fafc",
    "muted": "#94a3b8",
    "bar_primary": "#3b82f6",
    "bar_accent": "#10b981",
    "bar_track": "#334155",
    "kpi_total": ("#172554", "#93c5fd", "#1e3a8a"),
    "kpi_active": ("#052e16", "#86efac", "#14532d"),
    "kpi_inactive": ("#422006", "#fde047", "#713f12"),
    "kpi_leave": ("#431407", "#fdba74", "#7c2d12"),
    "kpi_depts": ("#2e1065", "#c4b5fd", "#4c1d95"),
    "header_bg": "#1e293b",
    "header_text": "#cbd5e1",
    "row_alt": "#0b0f19",
    "divider": "#1f2937",
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _fmt_salary(v: float) -> str:
    return f"${v:,.0f}"


def _compute_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Crunch all metrics from the raw employee list returned by database.get_all_employees()."""
    total = len(rows)
    by_status: Dict[str, int] = {}
    dept_emp: Dict[str, List[float]] = {}

    for r in rows:
        status = str(r.get("status") or "Active")
        by_status[status] = by_status.get(status, 0) + 1
        dept = str(r.get("department") or "Unassigned")
        sal = float(r.get("salary") or 0.0)
        dept_emp.setdefault(dept, []).append(sal)

    active = by_status.get("Active", 0)
    inactive = by_status.get("Inactive", 0) + by_status.get("Terminated", 0)
    on_leave = total - active - inactive
    num_depts = len(dept_emp)

    all_salaries = [s for sals in dept_emp.values() for s in sals]
    total_salary = sum(all_salaries)
    avg_salary = total_salary / len(all_salaries) if all_salaries else 0.0
    min_salary = min(all_salaries) if all_salaries else 0.0
    max_salary = max(all_salaries) if all_salaries else 0.0

    dept_stats: List[Dict[str, Any]] = []
    for dept, sals in sorted(dept_emp.items(), key=lambda kv: -len(kv[1])):
        dept_stats.append({
            "dept": dept,
            "count": len(sals),
            "pct": round(len(sals) / total * 100, 1) if total else 0.0,
            "total_sal": sum(sals),
            "avg_sal": sum(sals) / len(sals) if sals else 0.0,
            "min_sal": min(sals),
            "max_sal": max(sals),
        })

    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "on_leave": on_leave,
        "num_depts": num_depts,
        "total_salary": total_salary,
        "avg_salary": avg_salary,
        "min_salary": min_salary,
        "max_salary": max_salary,
        "dept_stats": dept_stats,
        "by_status": by_status,
    }


# ---------------------------------------------------------------------------
# Background worker for analytics computation
# ---------------------------------------------------------------------------
class _AnalyticsWorker(QThread):
    """Computes dashboard stats on a background thread via SQL aggregation."""
    finished = pyqtSignal(dict)
    errored = pyqtSignal(str)

    def run(self):
        try:
            stats = database.get_analytics_stats_sql()
            self.finished.emit(stats)
        except Exception as exc:
            logger.error("Analytics worker error: %s", exc, exc_info=True)
            self.errored.emit(str(exc))


# ---------------------------------------------------------------------------
# Inline horizontal bar
# ---------------------------------------------------------------------------
class _InlineBar(QWidget):
    def __init__(self, ratio: float, color_fill: str, color_track: str, parent=None):
        super().__init__(parent)
        self._ratio = max(0.0, min(1.0, ratio))
        self._color_fill = color_fill
        self._color_track = color_track
        self.setFixedHeight(10)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _rebuild(self, ratio: float, color_fill: str, color_track: str) -> None:
        self._ratio = max(0.0, min(1.0, ratio))
        self._color_fill = color_fill
        self._color_track = color_track
        self.update()

    # Custom paint via child widgets is simpler with Qt layouts:
    # We compose two QFrames inside an HBoxLayout.
    def setup_bars(self, ratio: float, color_fill: str, color_track: str, parent_widget) -> QWidget:
        """Factory: returns a ready-made bar widget. Used instead of paint events."""
        container = QWidget(parent_widget)
        container.setFixedHeight(10)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lyt = QHBoxLayout(container)
        lyt.setContentsMargins(0, 0, 0, 0)
        lyt.setSpacing(0)

        fill = QFrame(container)
        fill.setFixedHeight(8)
        fill.setStyleSheet(f"QFrame {{ background-color: {color_fill}; border-radius: 4px; }}")
        fill.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # We'll set fill width dynamically by stretch ratio
        # Using a spacer trick: fill gets ratio, track gets 1-ratio
        track = QFrame(container)
        track.setFixedHeight(8)
        track.setStyleSheet(f"QFrame {{ background-color: {color_track}; border-radius: 4px; }}")

        lyt.addWidget(fill, max(1, int(ratio * 100)))
        lyt.addWidget(track, max(1, int((1.0 - ratio) * 100)))
        return container


# ---------------------------------------------------------------------------
# KPI card
# ---------------------------------------------------------------------------
def _make_kpi_card(label: str, value: str, sub: str, bg: str, text_color: str, border: str, icon_name: str = "") -> QFrame:
    card = QFrame()
    card.setObjectName("kpiCard")
    card.setStyleSheet(
        f"QFrame#kpiCard {{ background-color: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
    )
    card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    card.setFixedHeight(94)

    lyt = QVBoxLayout(card)
    lyt.setContentsMargins(16, 12, 16, 12)
    lyt.setSpacing(2)

    top_row = QHBoxLayout()
    top_row.setContentsMargins(0, 0, 0, 0)
    top_row.setSpacing(6)

    lbl = QLabel(label)
    lbl.setStyleSheet(f"QLabel {{ color: {text_color}; font-size: 11px; font-weight: 700; letter-spacing: 0.4px; background: transparent; border: none; }}")
    top_row.addWidget(lbl, 1)

    if icon_name:
        ico = get_icon(icon_name)
        if not ico.isNull():
            ico_lbl = QLabel()
            ico_lbl.setPixmap(ico.pixmap(22, 22))
            ico_lbl.setStyleSheet("background: transparent; border: none;")
            top_row.addWidget(ico_lbl, 0, Qt.AlignRight | Qt.AlignVCenter)

    val_lbl = QLabel(value)
    val_lbl.setStyleSheet(f"QLabel {{ color: {text_color}; font-size: 22px; font-weight: 700; background: transparent; border: none; }}")

    sub_lbl = QLabel(sub)
    sub_lbl.setStyleSheet(f"QLabel {{ color: {text_color}; font-size: 11px; opacity: 0.85; background: transparent; border: none; }}")

    lyt.addLayout(top_row)
    lyt.addWidget(val_lbl)
    lyt.addWidget(sub_lbl)
    return card


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------
def _section_title(text: str, pal: dict) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"QLabel {{ color: {pal['text']}; font-size: 14px; font-weight: 700; "
        f"border: none; background: transparent; padding: 0; margin: 0; }}"
    )
    return lbl


# ---------------------------------------------------------------------------
# Main view
# ---------------------------------------------------------------------------
class AnalyticsView(QWidget):
    """Business dashboard — pure Qt, no Matplotlib required."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pal = LIGHT
        self._stats: Dict[str, Any] = {}
        self._raw_rows: List[Dict[str, Any]] = []
        self._worker: Optional[_AnalyticsWorker] = None
        # Thread safety for worker access
        from threading import Lock
        self._worker_lock = Lock()
        self._build_ui()

    # ------------------------------------------------------------------
    # Public API (called by MainWindow)
    # ------------------------------------------------------------------
    def set_theme(self, theme: str) -> None:
        self._pal = DARK if theme == "dark" else LIGHT
        if not self.isVisible():
            self._theme_dirty = True
            return
        self._theme_dirty = False
        self.setUpdatesEnabled(False)
        try:
            if self._stats:
                self._render(self._stats)
            else:
                self.refresh()
        finally:
            self.setUpdatesEnabled(True)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if getattr(self, "_theme_dirty", False):
            self._theme_dirty = False
            self.setUpdatesEnabled(False)
            try:
                if self._stats:
                    self._render(self._stats)
                else:
                    self.refresh()
            finally:
                self.setUpdatesEnabled(True)

    def refresh(self) -> None:
        win = self.window()
        if hasattr(win, "_theme"):
            self._pal = DARK if getattr(win, "_theme") == "dark" else LIGHT

        # Show loading state and compute stats on background thread
        self._show_loading()

        # Cancel any in-progress worker
        with self._worker_lock:
            if self._worker is not None and self._worker.isRunning():
                self._worker.quit()
                self._worker.wait(500)

            self._worker = _AnalyticsWorker(self)
            self._worker.finished.connect(self._on_stats_ready)
            self._worker.errored.connect(self._on_stats_error)
            self._worker.start()

    @pyqtSlot(dict)
    def _on_stats_ready(self, stats: Dict[str, Any]) -> None:
        self._stats = stats
        self._raw_rows = []  # no longer needed in memory
        self._render(self._stats)
        with self._worker_lock:
            self._worker = None

    @pyqtSlot(str)
    def _on_stats_error(self, msg: str) -> None:
        self._show_error("Could not load employee data. Please check the database connection.")
        with self._worker_lock:
            self._worker = None

    def cleanup_workers(self) -> None:
        """Safely cancel and wait on any background analytics worker during shutdown."""
        with self._worker_lock:
            if self._worker is not None and self._worker.isRunning():
                self._worker.quit()
                self._worker.wait(1000)

    def _show_loading(self) -> None:
        self._clear_content()
        lbl = QLabel("Loading analytics…")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"QLabel {{ color: {self._pal['muted']}; font-size: 14px; padding: 60px; background: transparent; }}"
        )
        self._content_lyt.addWidget(lbl)
        self._content_lyt.addStretch(1)

    # ------------------------------------------------------------------
    # UI skeleton (built once)
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Outer card wraps everything
        self._outer_card = QFrame(self)
        self._outer_card.setProperty("class", "card")
        self._outer_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer_lyt = QVBoxLayout(self._outer_card)
        outer_lyt.setContentsMargins(20, 18, 20, 18)
        outer_lyt.setSpacing(12)

        # --- header row ---
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self._title_lbl = QLabel("Executive Dashboard")
        self._title_lbl.setProperty("class", "cardTitle")
        self._subtitle_lbl = QLabel("Live overview of headcount, departments, and compensation.")
        self._subtitle_lbl.setProperty("class", "cardSubtitle")
        title_col.addWidget(self._title_lbl)
        title_col.addWidget(self._subtitle_lbl)
        header_row.addLayout(title_col, 1)

        self._export_btn = QPushButton("Export Report")
        self._export_btn.setIcon(get_icon("export_csv.png"))
        self._export_btn.setIconSize(QSize(18, 18))
        self._export_btn.setProperty("class", "primaryButton")
        self._export_btn.setCursor(Qt.PointingHandCursor)
        self._export_btn.setFixedHeight(34)
        self._export_btn.clicked.connect(self._on_export)

        header_row.addWidget(self._export_btn)
        outer_lyt.addLayout(header_row)

        # divider
        div = QFrame()
        div.setProperty("class", "divider")
        div.setFixedHeight(1)
        outer_lyt.addWidget(div)

        # --- scrollable content area ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._content = QWidget()
        self._content.setStyleSheet("QWidget { background: transparent; }")
        self._content_lyt = QVBoxLayout(self._content)
        self._content_lyt.setContentsMargins(0, 4, 0, 4)
        self._content_lyt.setSpacing(20)
        scroll.setWidget(self._content)

        outer_lyt.addWidget(scroll, 1)
        root.addWidget(self._outer_card)

    def _clear_content(self) -> None:
        lyt = self._content_lyt
        while lyt.count():
            item = lyt.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _show_error(self, msg: str) -> None:
        self._clear_content()
        lbl = QLabel(msg)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("QLabel { color: #b91c1c; font-size: 13px; padding: 40px; background: transparent; }")
        lbl.setWordWrap(True)
        self._content_lyt.addWidget(lbl)

    def _render(self, stats: Dict[str, Any]) -> None:
        self.setUpdatesEnabled(False)
        try:
            self._clear_content()
            pal = self._pal

            if stats.get("total", 0) == 0:
                self._render_empty(pal)
                return

            self._render_kpi_row(stats, pal)
            self._render_quick_actions(pal)
            self._render_dept_section(stats, pal)
            self._render_salary_section(stats, pal)
            self._render_status_breakdown(stats, pal)
            self._content_lyt.addStretch(1)
        finally:
            self.setUpdatesEnabled(True)

    def _render_quick_actions(self, pal: dict) -> None:
        action_frame = QFrame()
        action_frame.setStyleSheet(
            f"QFrame {{ background-color: {pal['card_bg']}; border: 1px solid {pal['card_border']}; border-radius: 8px; }}"
        )
        row = QHBoxLayout(action_frame)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(10)

        quick_lbl = QLabel("Quick Actions:")
        quick_lbl.setStyleSheet(f"QLabel {{ color: {pal['muted']}; font-size: 12px; font-weight: 600; background: transparent; border: none; }}")
        row.addWidget(quick_lbl)

        btn_add_emp = QPushButton("Add Employee")
        btn_add_emp.setIcon(get_icon("add.png"))
        btn_add_emp.setIconSize(QSize(16, 16))
        btn_add_emp.setObjectName("quickAddEmpBtn")
        btn_add_emp.setProperty("class", "primaryButton")
        btn_add_emp.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: #ffffff !important; border: 1px solid #1d4ed8; font-weight: 600; font-size: 13px; border-radius: 6px; padding: 6px 14px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
            "QPushButton:pressed { background-color: #1e40af; }"
        )
        btn_add_emp.setCursor(Qt.PointingHandCursor)
        btn_add_emp.setFixedHeight(32)
        btn_add_emp.clicked.connect(self._action_add_employee)

        btn_add_dept = QPushButton("Add Department")
        btn_add_dept.setIcon(get_icon("departments.png"))
        btn_add_dept.setIconSize(QSize(16, 16))
        btn_add_dept.setProperty("class", "secondaryButton")
        btn_add_dept.setStyleSheet(
            f"QPushButton {{ background-color: {pal['card_bg']}; color: {pal['text']}; border: 1px solid {pal['card_border']}; font-weight: 500; font-size: 13px; border-radius: 6px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background-color: {pal['header_bg']}; border-color: {pal['muted']}; }}"
        )
        btn_add_dept.setCursor(Qt.PointingHandCursor)
        btn_add_dept.setFixedHeight(32)
        btn_add_dept.clicked.connect(self._action_add_department)

        btn_view_dir = QPushButton("Employee Directory")
        btn_view_dir.setIcon(get_icon("employees.png"))
        btn_view_dir.setIconSize(QSize(16, 16))
        btn_view_dir.setProperty("class", "secondaryButton")
        btn_view_dir.setStyleSheet(
            f"QPushButton {{ background-color: {pal['card_bg']}; color: {pal['text']}; border: 1px solid {pal['card_border']}; font-weight: 500; font-size: 13px; border-radius: 6px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background-color: {pal['header_bg']}; border-color: {pal['muted']}; }}"
        )
        btn_view_dir.setCursor(Qt.PointingHandCursor)
        btn_view_dir.setFixedHeight(32)
        btn_view_dir.clicked.connect(lambda: self._navigate_window("employees"))

        btn_view_rep = QPushButton("Generate Reports")
        btn_view_rep.setIcon(get_icon("reports.png"))
        btn_view_rep.setIconSize(QSize(16, 16))
        btn_view_rep.setProperty("class", "secondaryButton")
        btn_view_rep.setStyleSheet(
            f"QPushButton {{ background-color: {pal['card_bg']}; color: {pal['text']}; border: 1px solid {pal['card_border']}; font-weight: 500; font-size: 13px; border-radius: 6px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background-color: {pal['header_bg']}; border-color: {pal['muted']}; }}"
        )
        btn_view_rep.setCursor(Qt.PointingHandCursor)
        btn_view_rep.setFixedHeight(32)
        btn_view_rep.clicked.connect(lambda: self._navigate_window("reports"))

        row.addWidget(btn_add_emp)
        row.addWidget(btn_add_dept)
        row.addWidget(btn_view_dir)
        row.addWidget(btn_view_rep)
        row.addStretch(1)

        self._content_lyt.addWidget(action_frame)

    def _navigate_window(self, section: str) -> None:
        win = self.window()
        if hasattr(win, "_navigate_to"):
            win._navigate_to(section)

    def _action_add_employee(self) -> None:
        win = self.window()
        if hasattr(win, "_navigate_to"):
            win._navigate_to("employees")
        if hasattr(win, "employee_view") and hasattr(win.employee_view, "_on_add_clicked"):
            win.employee_view._on_add_clicked()

    def _action_add_department(self) -> None:
        win = self.window()
        if hasattr(win, "_navigate_to"):
            win._navigate_to("departments")
        if hasattr(win, "department_view") and hasattr(win.department_view, "_on_add_clicked"):
            win.department_view._on_add_clicked()

    def _render_empty(self, pal: dict) -> None:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {pal['card_bg']}; border: 1px solid {pal['card_border']}; border-radius: 10px; }}"
        )
        lyt = QVBoxLayout(frame)
        lyt.setContentsMargins(40, 60, 40, 60)
        lyt.setAlignment(Qt.AlignCenter)

        icon = QLabel("📊")
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("QLabel { font-size: 40px; background: transparent; border: none; }")

        title = QLabel("No Data Yet")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"QLabel {{ color: {pal['text']}; font-size: 18px; font-weight: 700; background: transparent; border: none; }}")

        sub = QLabel("Add employee records to see headcount, department, and salary analytics.")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"QLabel {{ color: {pal['muted']}; font-size: 13px; background: transparent; border: none; }}")

        lyt.addWidget(icon)
        lyt.addSpacing(8)
        lyt.addWidget(title)
        lyt.addSpacing(4)
        lyt.addWidget(sub)
        self._content_lyt.addWidget(frame)

    # ── KPI Cards ─────────────────────────────────────────────────────
    def _render_kpi_row(self, stats: Dict[str, Any], pal: dict) -> None:
        total = stats["total"]
        active = stats["active"]
        inactive = stats["inactive"]
        on_leave = stats["on_leave"]
        num_depts = stats["num_depts"]

        kpis = [
            ("TOTAL EMPLOYEES", str(total), "All records", *pal["kpi_total"], "total_employees"),
            ("ACTIVE", str(active), f"{round(active/total*100) if total else 0}% of workforce", *pal["kpi_active"], "active_employees"),
            ("INACTIVE / TERMINATED", str(inactive), "Deactivated records", *pal["kpi_inactive"], "terminated"),
            ("ON LEAVE / OTHER", str(on_leave), "Non-active, non-inactive", *pal["kpi_leave"], "on_leave"),
            ("DEPARTMENTS", str(num_depts), "Organizational units", *pal["kpi_depts"], "departments"),
        ]

        row = QHBoxLayout()
        row.setSpacing(10)
        for label, value, sub, bg, text_color, border, icon_name in kpis:
            card = _make_kpi_card(label, value, sub, bg, text_color, border, icon_name)
            row.addWidget(card)

        wrapper = QWidget()
        wrapper.setStyleSheet("QWidget { background: transparent; }")
        wrapper.setLayout(row)
        self._content_lyt.addWidget(wrapper)

    # ── Department Section ─────────────────────────────────────────────
    def _render_dept_section(self, stats: Dict[str, Any], pal: dict) -> None:
        dept_stats = stats["dept_stats"]
        if not dept_stats:
            return

        section = QFrame()
        section.setStyleSheet(
            f"QFrame {{ background-color: {pal['card_bg']}; border: 1px solid {pal['card_border']}; border-radius: 10px; }}"
        )
        lyt = QVBoxLayout(section)
        lyt.setContentsMargins(18, 16, 18, 16)
        lyt.setSpacing(10)

        lyt.addWidget(_section_title("Department Overview", pal))

        # Table header
        hdr = QHBoxLayout()
        hdr.setSpacing(0)
        for text, stretch in [("Department", 3), ("Employees", 1), ("Distribution", 3), ("%", 1)]:
            h = QLabel(text)
            h.setStyleSheet(
                f"QLabel {{ color: {pal['header_text']}; font-size: 11px; font-weight: 700; "
                f"background: {pal['header_bg']}; border: none; padding: 6px 10px; }}"
            )
            hdr.addWidget(h, stretch)
        lyt.addLayout(hdr)

        # Divider
        d = QFrame()
        d.setFrameShape(QFrame.HLine)
        d.setStyleSheet(f"QFrame {{ border: none; background: {pal['divider']}; min-height:1px; max-height:1px; }}")
        lyt.addWidget(d)

        max_count = max((ds["count"] for ds in dept_stats), default=1)

        for idx, ds in enumerate(dept_stats):
            ratio = ds["count"] / max_count if max_count else 0.0
            row_bg = pal["row_alt"] if idx % 2 == 1 else pal["card_bg"]

            row_w = QWidget()
            row_w.setStyleSheet(f"QWidget {{ background: {row_bg}; border: none; }}")
            row_lyt = QHBoxLayout(row_w)
            row_lyt.setContentsMargins(10, 6, 10, 6)
            row_lyt.setSpacing(0)

            dept_lbl = QLabel(ds["dept"])
            dept_lbl.setStyleSheet(f"QLabel {{ color: {pal['text']}; font-size: 13px; font-weight: 600; background: transparent; border: none; }}")

            cnt_lbl = QLabel(str(ds["count"]))
            cnt_lbl.setAlignment(Qt.AlignCenter)
            cnt_lbl.setStyleSheet(f"QLabel {{ color: {pal['text']}; font-size: 13px; background: transparent; border: none; }}")

            # Mini bar
            bar_container = QWidget()
            bar_container.setStyleSheet("QWidget { background: transparent; border: none; }")
            bar_lyt = QHBoxLayout(bar_container)
            bar_lyt.setContentsMargins(6, 0, 6, 0)
            bar_lyt.setSpacing(0)

            fill_pct = max(1, int(ratio * 100))
            track_pct = max(1, 100 - fill_pct)

            fill = QFrame(bar_container)
            fill.setFixedHeight(8)
            fill.setStyleSheet(f"QFrame {{ background: {pal['bar_primary']}; border-radius: 4px; border: none; }}")
            fill.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            track = QFrame(bar_container)
            track.setFixedHeight(8)
            track.setStyleSheet(f"QFrame {{ background: {pal['bar_track']}; border-radius: 4px; border: none; }}")
            track.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            bar_lyt.addWidget(fill, fill_pct)
            bar_lyt.addWidget(track, track_pct)

            pct_lbl = QLabel(f"{ds['pct']}%")
            pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            pct_lbl.setStyleSheet(f"QLabel {{ color: {pal['muted']}; font-size: 12px; background: transparent; border: none; }}")

            row_lyt.addWidget(dept_lbl, 3)
            row_lyt.addWidget(cnt_lbl, 1)
            row_lyt.addWidget(bar_container, 3)
            row_lyt.addWidget(pct_lbl, 1)

            lyt.addWidget(row_w)

        self._content_lyt.addWidget(section)

    # ── Salary Section ─────────────────────────────────────────────────
    def _render_salary_section(self, stats: Dict[str, Any], pal: dict) -> None:
        dept_stats = stats["dept_stats"]
        if not dept_stats:
            return

        # Top summary cards
        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)

        sal_cards = [
            ("TOTAL PAYROLL", _fmt_salary(stats["total_salary"]), "Sum of all salaries"),
            ("AVERAGE SALARY", _fmt_salary(stats["avg_salary"]), "Mean across all employees"),
            ("LOWEST SALARY", _fmt_salary(stats["min_salary"]), "Minimum on record"),
            ("HIGHEST SALARY", _fmt_salary(stats["max_salary"]), "Maximum on record"),
        ]

        for label, value, sub in sal_cards:
            card = QFrame()
            card.setStyleSheet(
                f"QFrame {{ background-color: {pal['card_bg']}; border: 1px solid {pal['card_border']}; border-radius: 10px; }}"
            )
            card.setFixedHeight(84)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 14, 16, 14)
            cl.setSpacing(3)

            lbl = QLabel(label)
            lbl.setStyleSheet(f"QLabel {{ color: {pal['muted']}; font-size: 10px; font-weight: 700; background: transparent; border: none; }}")
            val = QLabel(value)
            val.setStyleSheet(f"QLabel {{ color: {pal['text']}; font-size: 20px; font-weight: 800; background: transparent; border: none; }}")
            slbl = QLabel(sub)
            slbl.setStyleSheet(f"QLabel {{ color: {pal['muted']}; font-size: 10px; background: transparent; border: none; }}")

            cl.addWidget(lbl)
            cl.addWidget(val)
            cl.addWidget(slbl)
            summary_row.addWidget(card)

        w = QWidget()
        w.setStyleSheet("QWidget { background: transparent; }")
        w.setLayout(summary_row)
        self._content_lyt.addWidget(w)

        # Per-department salary table
        section = QFrame()
        section.setStyleSheet(
            f"QFrame {{ background-color: {pal['card_bg']}; border: 1px solid {pal['card_border']}; border-radius: 10px; }}"
        )
        lyt = QVBoxLayout(section)
        lyt.setContentsMargins(18, 16, 18, 16)
        lyt.setSpacing(10)

        lyt.addWidget(_section_title("Salary by Department", pal))

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(0)
        cols = [("Department", 3), ("Avg Salary", 2), ("Min", 2), ("Max", 2), ("Distribution", 4)]
        for text, stretch in cols:
            h = QLabel(text)
            h.setStyleSheet(
                f"QLabel {{ color: {pal['header_text']}; font-size: 11px; font-weight: 700; "
                f"background: {pal['header_bg']}; border: none; padding: 6px 10px; }}"
            )
            hdr.addWidget(h, stretch)
        lyt.addLayout(hdr)

        d = QFrame()
        d.setFrameShape(QFrame.HLine)
        d.setStyleSheet(f"QFrame {{ border: none; background: {pal['divider']}; min-height:1px; max-height:1px; }}")
        lyt.addWidget(d)

        max_avg = max((ds["avg_sal"] for ds in dept_stats), default=1.0) or 1.0

        for idx, ds in enumerate(dept_stats):
            ratio = ds["avg_sal"] / max_avg if max_avg else 0.0
            row_bg = pal["row_alt"] if idx % 2 == 1 else pal["card_bg"]

            row_w = QWidget()
            row_w.setStyleSheet(f"QWidget {{ background: {row_bg}; border: none; }}")
            row_lyt = QHBoxLayout(row_w)
            row_lyt.setContentsMargins(10, 6, 10, 6)
            row_lyt.setSpacing(0)

            def _lbl(text, align=Qt.AlignLeft):
                l = QLabel(text)
                l.setAlignment(align | Qt.AlignVCenter)
                l.setStyleSheet(f"QLabel {{ color: {pal['text']}; font-size: 12px; background: transparent; border: none; }}")
                return l

            bar_c = QWidget()
            bar_c.setStyleSheet("QWidget { background: transparent; border: none; }")
            bl = QHBoxLayout(bar_c)
            bl.setContentsMargins(6, 0, 6, 0)
            bl.setSpacing(0)
            fill_pct = max(1, int(ratio * 100))
            track_pct = max(1, 100 - fill_pct)
            fill = QFrame(bar_c)
            fill.setFixedHeight(8)
            fill.setStyleSheet(f"QFrame {{ background: {pal['bar_accent']}; border-radius: 4px; border: none; }}")
            fill.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            track = QFrame(bar_c)
            track.setFixedHeight(8)
            track.setStyleSheet(f"QFrame {{ background: {pal['bar_track']}; border-radius: 4px; border: none; }}")
            track.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            bl.addWidget(fill, fill_pct)
            bl.addWidget(track, track_pct)

            row_lyt.addWidget(_lbl(ds["dept"]), 3)
            row_lyt.addWidget(_lbl(_fmt_salary(ds["avg_sal"])), 2)
            row_lyt.addWidget(_lbl(_fmt_salary(ds["min_sal"])), 2)
            row_lyt.addWidget(_lbl(_fmt_salary(ds["max_sal"])), 2)
            row_lyt.addWidget(bar_c, 4)
            lyt.addWidget(row_w)

        self._content_lyt.addWidget(section)

    # ── Status Breakdown ───────────────────────────────────────────────
    def _render_status_breakdown(self, stats: Dict[str, Any], pal: dict) -> None:
        by_status = stats.get("by_status", {})
        if not by_status:
            return

        total = stats["total"] or 1
        section = QFrame()
        section.setStyleSheet(
            f"QFrame {{ background-color: {pal['card_bg']}; border: 1px solid {pal['card_border']}; border-radius: 10px; }}"
        )
        lyt = QVBoxLayout(section)
        lyt.setContentsMargins(18, 16, 18, 16)
        lyt.setSpacing(10)

        lyt.addWidget(_section_title("Headcount by Status", pal))

        colors = ["#2563eb", "#16a34a", "#ea580c", "#7c3aed", "#ca8a04", "#0e7490"]
        for idx, (status, count) in enumerate(sorted(by_status.items(), key=lambda kv: -kv[1])):
            ratio = count / total
            color = colors[idx % len(colors)]
            row_bg = pal["row_alt"] if idx % 2 == 1 else pal["card_bg"]

            row_w = QWidget()
            row_w.setStyleSheet(f"QWidget {{ background: {row_bg}; border: none; }}")
            row_lyt = QHBoxLayout(row_w)
            row_lyt.setContentsMargins(10, 6, 10, 6)
            row_lyt.setSpacing(8)

            dot = QFrame()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"QFrame {{ background: {color}; border-radius: 5px; border: none; }}")

            slbl = QLabel(status)
            slbl.setStyleSheet(f"QLabel {{ color: {pal['text']}; font-size: 13px; font-weight: 600; background: transparent; border: none; }}")

            cnt = QLabel(str(count))
            cnt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            cnt.setStyleSheet(f"QLabel {{ color: {pal['text']}; font-size: 13px; background: transparent; border: none; }}")

            fill_pct = max(1, int(ratio * 100))
            track_pct = max(1, 100 - fill_pct)
            bar_c = QWidget()
            bar_c.setStyleSheet("QWidget { background: transparent; border: none; }")
            bl = QHBoxLayout(bar_c)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(0)
            fill = QFrame(bar_c)
            fill.setFixedHeight(8)
            fill.setStyleSheet(f"QFrame {{ background: {color}; border-radius: 4px; border: none; }}")
            fill.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            track = QFrame(bar_c)
            track.setFixedHeight(8)
            track.setStyleSheet(f"QFrame {{ background: {pal['bar_track']}; border-radius: 4px; border: none; }}")
            track.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            bl.addWidget(fill, fill_pct)
            bl.addWidget(track, track_pct)

            pct_lbl = QLabel(f"{ratio*100:.1f}%")
            pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            pct_lbl.setFixedWidth(48)
            pct_lbl.setStyleSheet(f"QLabel {{ color: {pal['muted']}; font-size: 12px; background: transparent; border: none; }}")

            row_lyt.addWidget(dot, 0, Qt.AlignVCenter)
            row_lyt.addWidget(slbl, 2)
            row_lyt.addWidget(bar_c, 5)
            row_lyt.addWidget(cnt, 0)
            row_lyt.addWidget(pct_lbl, 0)
            lyt.addWidget(row_w)

        self._content_lyt.addWidget(section)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _on_export(self) -> None:
        if not self._stats:
            QMessageBox.information(self, "No Data", "Refresh the dashboard before exporting.", QMessageBox.Ok)
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Analytics Report", "analytics_report.csv", "CSV (*.csv);;All Files (*)"
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"

        try:
            self._write_report_csv(path, self._stats)
            QMessageBox.information(self, "Export Complete", f"Report saved to:\n{path}", QMessageBox.Ok)
        except Exception as exc:
            QMessageBox.critical(self, "Export Failed", str(exc), QMessageBox.Ok)

    def _write_report_csv(self, path: str, stats: Dict[str, Any]) -> None:
        def _clean(val: Any) -> str:
            s = str(val) if val is not None else ""
            if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
                return "'" + s
            return s

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["EMPLOYEE MANAGEMENT SYSTEM — ANALYTICS REPORT"])
            w.writerow([])

            # Summary
            w.writerow(["SUMMARY"])
            w.writerow(["Metric", "Value"])
            w.writerow(["Total Employees", _clean(stats["total"])])
            w.writerow(["Active", _clean(stats["active"])])
            w.writerow(["Inactive / Terminated", _clean(stats["inactive"])])
            w.writerow(["On Leave / Other", _clean(stats["on_leave"])])
            w.writerow(["Departments", _clean(stats["num_depts"])])
            w.writerow(["Total Payroll", _clean(_fmt_salary(stats["total_salary"]))])
            w.writerow(["Average Salary", _clean(_fmt_salary(stats["avg_salary"]))])
            w.writerow(["Minimum Salary", _clean(_fmt_salary(stats["min_salary"]))])
            w.writerow(["Maximum Salary", _clean(_fmt_salary(stats["max_salary"]))])
            w.writerow([])

            # Status breakdown
            w.writerow(["STATUS BREAKDOWN"])
            w.writerow(["Status", "Count", "Percentage"])
            total = stats["total"] or 1
            for status, count in sorted(stats["by_status"].items(), key=lambda kv: -kv[1]):
                w.writerow([_clean(status), _clean(count), _clean(f"{count/total*100:.1f}%")])
            w.writerow([])

            # Department stats
            w.writerow(["DEPARTMENT ANALYTICS"])
            w.writerow(["Department", "Employees", "%", "Avg Salary", "Min Salary", "Max Salary", "Total Salary"])
            for ds in stats["dept_stats"]:
                w.writerow([
                    _clean(ds["dept"]),
                    _clean(ds["count"]),
                    _clean(f"{ds['pct']}%"),
                    _clean(_fmt_salary(ds["avg_sal"])),
                    _clean(_fmt_salary(ds["min_sal"])),
                    _clean(_fmt_salary(ds["max_sal"])),
                    _clean(_fmt_salary(ds["total_sal"])),
                ])

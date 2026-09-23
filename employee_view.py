import math
from typing import Dict, Any, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot, QSize
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QAbstractItemView,
    QSizePolicy,
    QFileDialog,
    QMenu,
    QApplication,
    QProgressDialog,
    QSpinBox,
)
import os

import database
from database import EMPLOYEE_STATUSES
from employee_form import EmployeeFormDialog
from employee_detail import EmployeeDetailsDialog
from csv_utils import export_table_to_csv, import_csv_to_db, import_csv_to_db_chunked, CsvImportError
from icon_utils import get_icon
from logger import logger

TABLE_COLUMNS = [
    ("id", "ID"),
    ("emp_code", "Code"),
    ("name", "Name"),
    ("email", "Email"),
    ("department", "Department"),
    ("position", "Position"),
    ("status", "Status"),
    ("salary", "Salary"),
    ("hire_date", "Hire Date"),
]


class SortableTableWidgetItem(QTableWidgetItem):
    def __init__(self, text: str, sort_key: Any = None):
        super().__init__(text)
        self.sort_key = sort_key if sort_key is not None else text

    def __lt__(self, other):
        if isinstance(other, SortableTableWidgetItem):
            try:
                return self.sort_key < other.sort_key
            except TypeError:
                return str(self.sort_key) < str(other.sort_key)
        return super().__lt__(other)


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------
class _ImportWorker(QThread):
    """Runs CSV import on a background thread with progress signals."""
    progress = pyqtSignal(int, int, int, int)  # processed, total, inserted, skipped
    finished_ok = pyqtSignal(int, int, list)   # inserted, skipped, errors
    finished_err = pyqtSignal(str)             # error message

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            inserted, skipped, errors = import_csv_to_db_chunked(
                self._path,
                skip_duplicates=True,
                chunk_size=1000,
                progress_callback=self._on_progress,
                is_cancelled=lambda: self._cancelled,
            )
            self.finished_ok.emit(inserted, skipped, errors)
        except FileNotFoundError:
            self.finished_err.emit(f"File not found:\n{self._path}")
        except PermissionError:
            self.finished_err.emit("Permission denied reading the file.")
        except CsvImportError as exc:
            detail = "\n".join(exc.errors[:10])
            self.finished_err.emit(f"{exc}\n\n{detail}")
        except Exception as exc:
            self.finished_err.emit(str(exc))

    def _on_progress(self, processed, total, inserted, skipped):
        self.progress.emit(processed, total, inserted, skipped)


class _ExportWorker(QThread):
    """Runs CSV export on a background thread."""
    progress = pyqtSignal(int, int)      # written, total
    finished_ok = pyqtSignal(int)        # total written
    finished_err = pyqtSignal(str)

    def __init__(self, query, dept, status, path, parent=None):
        super().__init__(parent)
        self._query = query
        self._dept = dept
        self._status = status
        self._path = path
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            if self._cancelled:
                return
            rows = database.search_employees(
                query=self._query, department=self._dept, status=self._status
            )
            if self._cancelled:
                return
            n = export_table_to_csv(rows, self._path)
            if not self._cancelled:
                self.finished_ok.emit(n)
        except PermissionError:
            self.finished_err.emit(
                f"File '{os.path.basename(self._path)}' is in use or not writable."
            )
        except Exception as exc:
            self.finished_err.emit(str(exc))


class EmployeeView(QWidget):
    data_changed = pyqtSignal()
    status_message = pyqtSignal(str, int)

    PAGE_SIZES = [50, 100, 250, 500]
    DEFAULT_PAGE_SIZE = 100

    def __init__(self, parent=None, lazy: bool = False):
        super().__init__(parent)
        self._initialized = False
        self._current_rows: List[Dict[str, Any]] = []
        self._page = 0
        self._page_size = self.DEFAULT_PAGE_SIZE
        self._total_count = 0
        self._import_worker: Optional[_ImportWorker] = None
        self._export_worker: Optional[_ExportWorker] = None
        # Thread safety for worker access
        from threading import Lock
        self._worker_lock = Lock()
        self._build_ui()
        if not lazy:
            self.refresh()
        self._initialized = True

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        card = QFrame(self)
        card.setProperty("class", "card")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(6)

        # ── Row 1: Title + Bulk Action Buttons ──
        header_row = QHBoxLayout()
        header_row.setSpacing(6)

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        page_title = QLabel("Employees")
        page_title.setProperty("class", "cardTitle")
        page_title.setStyleSheet("font-size: 14px; font-weight: 700; margin: 0; padding: 0;")
        page_sub = QLabel("Search, add, view, update, and manage employee records.")
        page_sub.setProperty("class", "cardSubtitle")
        page_sub.setStyleSheet("font-size: 11px; margin: 0; padding: 0;")
        title_col.addWidget(page_title)
        title_col.addWidget(page_sub)
        header_row.addLayout(title_col, 1)

        self.import_button = QPushButton("Import CSV")
        self.import_button.setIcon(get_icon("import_csv.png"))
        self.import_button.setIconSize(QSize(18, 18))
        self.import_button.setProperty("class", "secondaryButton")
        self.import_button.setCursor(Qt.PointingHandCursor)
        self.import_button.setFixedHeight(28)
        self.import_button.clicked.connect(self._on_import_csv)

        self.export_button = QPushButton("Export CSV")
        self.export_button.setIcon(get_icon("export_csv.png"))
        self.export_button.setIconSize(QSize(18, 18))
        self.export_button.setProperty("class", "secondaryButton")
        self.export_button.setCursor(Qt.PointingHandCursor)
        self.export_button.setFixedHeight(28)
        self.export_button.clicked.connect(self._on_export_csv)

        self.add_button = QPushButton("Add Employee")
        self.add_button.setIcon(get_icon("add.png"))
        self.add_button.setIconSize(QSize(18, 18))
        self.add_button.setProperty("class", "primaryButton")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setFixedHeight(28)
        self.add_button.clicked.connect(self._on_add_clicked)

        header_row.addWidget(self.import_button)
        header_row.addWidget(self.export_button)
        header_row.addWidget(self.add_button)
        card_layout.addLayout(header_row)

        # ── Divider ──
        div = QFrame()
        div.setProperty("class", "divider")
        div.setFixedHeight(1)
        card_layout.addWidget(div)

        # ── Row 2: Search + Filters ──
        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by name, code, email, or position…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedHeight(28)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(400)
        self._search_timer.timeout.connect(self._on_filter_changed)
        self.search_edit.textChanged.connect(lambda: self._search_timer.start())

        self.dept_combo = QComboBox()
        self.dept_combo.setFixedHeight(28)
        self.dept_combo.setMinimumWidth(130)
        self._populate_dept_combo()
        self.dept_combo.currentIndexChanged.connect(self._on_filter_changed)

        self.status_combo = QComboBox()
        self.status_combo.setFixedHeight(28)
        self.status_combo.setMinimumWidth(110)
        self.status_combo.addItem("All Statuses", None)
        for s in EMPLOYEE_STATUSES:
            self.status_combo.addItem(s, s)
        self.status_combo.currentIndexChanged.connect(self._on_filter_changed)

        self.reset_button = QPushButton("Reset")
        self.reset_button.setIcon(get_icon("refresh.png"))
        self.reset_button.setIconSize(QSize(16, 16))
        self.reset_button.setProperty("class", "secondaryButton")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.setFixedHeight(28)
        self.reset_button.setMinimumWidth(70)
        self.reset_button.clicked.connect(self._on_reset_clicked)

        filter_row.addWidget(self.search_edit, 3)
        filter_row.addWidget(self.dept_combo, 2)
        filter_row.addWidget(self.status_combo, 2)
        filter_row.addWidget(self.reset_button)
        card_layout.addLayout(filter_row)

        # ── Row 3: Selection actions + count ──
        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        self.view_btn = QPushButton("View Details")
        self.view_btn.setIcon(get_icon("view_details.png"))
        self.view_btn.setIconSize(QSize(16, 16))
        self.view_btn.setProperty("class", "secondaryButton")
        self.view_btn.setCursor(Qt.PointingHandCursor)
        self.view_btn.setFixedHeight(26)
        self.view_btn.setEnabled(False)
        self.view_btn.clicked.connect(self._on_view_selected)

        self.edit_button = QPushButton("Edit")
        self.edit_button.setIcon(get_icon("edit_details.png"))
        self.edit_button.setIconSize(QSize(16, 16))
        self.edit_button.setProperty("class", "secondaryButton")
        self.edit_button.setCursor(Qt.PointingHandCursor)
        self.edit_button.setFixedHeight(26)
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self._on_edit_selected)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setIcon(get_icon("delete.png"))
        self.delete_button.setIconSize(QSize(16, 16))
        self.delete_button.setProperty("class", "dangerButton")
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.setFixedHeight(26)
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._on_delete_selected)

        self.count_label = QLabel("0 employees")
        self.count_label.setProperty("class", "cardSubtitle")
        self.count_label.setStyleSheet("font-size: 11px;")
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        action_row.addWidget(self.view_btn)
        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.delete_button)
        action_row.addStretch(1)
        action_row.addWidget(self.count_label)
        card_layout.addLayout(action_row)

        # ── Table ──
        self.table = QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _, label in TABLE_COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        self._configure_column_widths(header)
        header.setStretchLastSection(True)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setMinimumHeight(180)
        card_layout.addWidget(self.table, 1)

        # ── Pagination bar ──
        self._pagination_bar = QFrame(card)
        pag_layout = QHBoxLayout(self._pagination_bar)
        pag_layout.setContentsMargins(0, 2, 0, 0)
        pag_layout.setSpacing(6)

        self._page_info_label = QLabel("Page 1 of 1")
        self._page_info_label.setProperty("class", "cardSubtitle")
        self._page_info_label.setStyleSheet("font-size: 11px;")

        self._first_btn = QPushButton(" ")
        self._first_btn.setIcon(get_icon("first.svg"))
        self._first_btn.setIconSize(QSize(16, 16))
        self._first_btn.setProperty("class", "secondaryButton")
        self._first_btn.setCursor(Qt.PointingHandCursor)
        self._first_btn.setFixedHeight(24)
        self._first_btn.setFixedWidth(64)
        self._first_btn.clicked.connect(self._on_first_page)

        self._prev_btn = QPushButton("")
        self._prev_btn.setIcon(get_icon("previous.svg"))
        self._prev_btn.setIconSize(QSize(16, 16))
        self._prev_btn.setProperty("class", "secondaryButton")
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.setFixedHeight(24)
        self._prev_btn.setFixedWidth(64)
        self._prev_btn.clicked.connect(self._on_prev_page)

        self._next_btn = QPushButton("")
        self._next_btn.setIcon(get_icon("next.svg"))
        self._next_btn.setIconSize(QSize(16, 16))
        self._next_btn.setLayoutDirection(Qt.RightToLeft)
        self._next_btn.setProperty("class", "secondaryButton")
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.setFixedHeight(24)
        self._next_btn.setFixedWidth(64)
        self._next_btn.clicked.connect(self._on_next_page)

        self._last_btn = QPushButton("")
        self._last_btn.setIcon(get_icon("last.svg"))
        self._last_btn.setIconSize(QSize(16, 16))
        self._last_btn.setLayoutDirection(Qt.RightToLeft)
        self._last_btn.setProperty("class", "secondaryButton")
        self._last_btn.setCursor(Qt.PointingHandCursor)
        self._last_btn.setFixedHeight(24)
        self._last_btn.setFixedWidth(64)
        self._last_btn.clicked.connect(self._on_last_page)

        # Page size combo
        page_size_label = QLabel("Rows/page:")
        page_size_label.setProperty("class", "cardSubtitle")
        page_size_label.setStyleSheet("font-size: 11px;")
        self._page_size_combo = QComboBox()
        self._page_size_combo.setFixedHeight(24)
        self._page_size_combo.setFixedWidth(64)
        for ps in self.PAGE_SIZES:
            self._page_size_combo.addItem(str(ps), ps)
        default_idx = self.PAGE_SIZES.index(self.DEFAULT_PAGE_SIZE)
        self._page_size_combo.setCurrentIndex(default_idx)
        self._page_size_combo.currentIndexChanged.connect(self._on_page_size_changed)

        pag_layout.addWidget(self._first_btn)
        pag_layout.addWidget(self._prev_btn)
        pag_layout.addWidget(self._page_info_label)
        pag_layout.addWidget(self._next_btn)
        pag_layout.addWidget(self._last_btn)
        pag_layout.addStretch(1)
        pag_layout.addWidget(page_size_label)
        pag_layout.addWidget(self._page_size_combo)

        card_layout.addWidget(self._pagination_bar)

        # ── Empty State ──
        self.empty_state_frame = QFrame(card)
        empty_layout = QVBoxLayout(self.empty_state_frame)
        empty_layout.setContentsMargins(40, 40, 40, 40)
        empty_layout.setSpacing(10)
        empty_layout.setAlignment(Qt.AlignCenter)

        self.empty_icon = QLabel("🔍", self.empty_state_frame)
        self.empty_icon.setStyleSheet("font-size: 32px; background: transparent;")
        self.empty_icon.setAlignment(Qt.AlignCenter)

        self.empty_title = QLabel("No Employees Found")
        self.empty_title.setStyleSheet("QLabel { font-size: 15px; font-weight: 700; color: #0f172a; }")
        self.empty_title.setAlignment(Qt.AlignCenter)

        self.empty_subtitle = QLabel("No records match the current search or filter.")
        self.empty_subtitle.setProperty("class", "cardSubtitle")
        self.empty_subtitle.setAlignment(Qt.AlignCenter)
        self.empty_subtitle.setWordWrap(True)

        self.empty_action_btn = QPushButton("Clear Filters")
        self.empty_action_btn.setProperty("class", "primaryButton")
        self.empty_action_btn.setCursor(Qt.PointingHandCursor)
        self.empty_action_btn.setFixedHeight(28)

        empty_layout.addWidget(self.empty_icon, 0, Qt.AlignHCenter)
        empty_layout.addWidget(self.empty_title, 0, Qt.AlignHCenter)
        empty_layout.addWidget(self.empty_subtitle, 0, Qt.AlignHCenter)
        empty_layout.addSpacing(4)
        empty_layout.addWidget(self.empty_action_btn, 0, Qt.AlignHCenter)

        self.empty_state_frame.setVisible(False)
        card_layout.addWidget(self.empty_state_frame, 1)

        root.addWidget(card)

    def _configure_column_widths(self, header: QHeaderView) -> None:
        widths = {
            "id": 45,
            "emp_code": 85,
            "name": 140,
            "email": 170,
            "department": 120,
            "position": 130,
            "status": 80,
            "salary": 90,
            "hire_date": 90,
        }
        for i, (key, _) in enumerate(TABLE_COLUMNS):
            if key in widths:
                header.resizeSection(i, widths[key])

    def _populate_dept_combo(self) -> None:
        prev = self.dept_combo.currentData()
        self.dept_combo.blockSignals(True)
        self.dept_combo.clear()
        self.dept_combo.addItem("All Departments", None)
        try:
            for dept in database.get_departments():
                self.dept_combo.addItem(dept, dept)
        except Exception as exc:
            logger.warning("Could not fetch departments for filter: %s", exc)
        if prev is not None:
            idx = self.dept_combo.findData(prev)
            if idx >= 0:
                self.dept_combo.setCurrentIndex(idx)
        self.dept_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------
    @property
    def _total_pages(self) -> int:
        if self._total_count == 0:
            return 1
        return max(1, math.ceil(self._total_count / self._page_size))

    def _update_pagination_controls(self) -> None:
        page_num = self._page + 1
        total_pages = self._total_pages
        self._page_info_label.setText(f"Page {page_num:,} of {total_pages:,}")
        self._prev_btn.setEnabled(self._page > 0)
        self._first_btn.setEnabled(self._page > 0)
        self._next_btn.setEnabled(page_num < total_pages)
        self._last_btn.setEnabled(page_num < total_pages)

        # Update count label to show range
        start = self._page * self._page_size + 1
        end = min(start + self._page_size - 1, self._total_count)
        if self._total_count == 0:
            self.count_label.setText("0 employees")
        else:
            self.count_label.setText(f"Showing {start:,}–{end:,} of {self._total_count:,}")

    def _on_prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._apply_filters()

    def _on_next_page(self) -> None:
        if self._page + 1 < self._total_pages:
            self._page += 1
            self._apply_filters()

    def _on_first_page(self) -> None:
        if self._page != 0:
            self._page = 0
            self._apply_filters()

    def _on_last_page(self) -> None:
        last = self._total_pages - 1
        if self._page != last:
            self._page = last
            self._apply_filters()

    def _on_page_size_changed(self) -> None:
        new_size = self._page_size_combo.currentData()
        if new_size and new_size != self._page_size:
            self._page_size = new_size
            self._page = 0
            self._apply_filters()

    # ------------------------------------------------------------------
    # Data loading (paginated)
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._populate_dept_combo()
        self._apply_filters()

    def _on_filter_changed(self) -> None:
        self._page = 0  # reset to first page on filter change
        self._apply_filters()

    def _apply_filters(self) -> None:
        query = self.search_edit.text().strip() or None
        dept = self.dept_combo.currentData()
        status = self.status_combo.currentData()
        try:
            rows, total = database.search_employees_paginated(
                query=query, department=dept, status=status,
                page=self._page, page_size=self._page_size,
            )
        except Exception as exc:
            logger.error("DB search error: %s", exc, exc_info=True)
            QMessageBox.critical(self, "Database Error", "Failed to search employees.", QMessageBox.Ok)
            rows, total = [], 0

        # Clamp page if out of bounds (e.g. after deletion of last item on a page)
        max_page = max(0, math.ceil(total / self._page_size) - 1) if total > 0 else 0
        if self._page > max_page and total > 0:
            self._page = max_page
            try:
                rows, total = database.search_employees_paginated(
                    query=query, department=dept, status=status,
                    page=self._page, page_size=self._page_size,
                )
            except Exception as exc:
                logger.error("DB search error: %s", exc, exc_info=True)

        self._current_rows = rows
        self._total_count = total
        self._render_table(rows)
        self._update_pagination_controls()

        has_data = total > 0
        self.table.setVisible(has_data)
        self._pagination_bar.setVisible(has_data)
        self.empty_state_frame.setVisible(not has_data)
        if not has_data:
            if query or dept or status:
                self.empty_title.setText("No Matches Found")
                self.empty_subtitle.setText("No employee records match your active search or filter.")
                self.empty_action_btn.setText("Clear Filters")
                try:
                    self.empty_action_btn.clicked.disconnect()
                except Exception:
                    pass
                self.empty_action_btn.clicked.connect(self._on_reset_clicked)
            else:
                self.empty_title.setText("No Employees Registered")
                self.empty_subtitle.setText("There are no employee records yet. Add your first employee to get started.")
                self.empty_action_btn.setText("Add Employee")
                try:
                    self.empty_action_btn.clicked.disconnect()
                except Exception:
                    pass
                self.empty_action_btn.clicked.connect(self._on_add_clicked)

    def _render_table(self, rows: List[Dict[str, Any]]) -> None:
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(rows))
            for r_idx, emp in enumerate(rows):
                emp_id = emp.get("id") or 0
                for c_idx, (key, _) in enumerate(TABLE_COLUMNS):
                    raw = emp.get(key)
                    if key == "salary":
                        num = float(raw or 0.0)
                        item = SortableTableWidgetItem(f"${num:,.2f}", sort_key=num)
                        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    elif key == "id":
                        item = SortableTableWidgetItem(str(emp_id), sort_key=int(emp_id))
                        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    elif key == "status":
                        s = str(raw or "Active")
                        item = SortableTableWidgetItem(s, sort_key=s.lower())
                        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                    else:
                        s = "" if raw is None else str(raw)
                        item = SortableTableWidgetItem(s, sort_key=s.lower())
                        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                    item.setData(Qt.UserRole, emp_id)
                    self.table.setItem(r_idx, c_idx, item)
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        has = len(self.table.selectedItems()) > 0
        self.view_btn.setEnabled(has)
        self.edit_button.setEnabled(has)
        self.delete_button.setEnabled(has)

    def _get_selected_employee(self) -> Optional[Dict[str, Any]]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        emp_id = item.data(Qt.UserRole)
        for emp in self._current_rows:
            if emp.get("id") == emp_id:
                return emp
        if emp_id is not None:
            return database.get_employee_by_id(int(emp_id))
        return None

    def _on_view_selected(self) -> None:
        emp = self._get_selected_employee()
        if emp:
            self._on_view_details_clicked(emp)

    def _on_edit_selected(self) -> None:
        emp = self._get_selected_employee()
        if emp:
            self._on_edit_clicked(emp)

    def _on_delete_selected(self) -> None:
        emp = self._get_selected_employee()
        if emp:
            self._on_delete_clicked(emp)

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        item = self.table.item(row, 0)
        if item:
            emp_id = item.data(Qt.UserRole)
            emp = next((e for e in self._current_rows if e.get("id") == emp_id), None)
            if emp is None and emp_id is not None:
                emp = database.get_employee_by_id(int(emp_id))
            if emp:
                self._on_view_details_clicked(emp)

    def _on_view_details_clicked(self, emp: Dict[str, Any]) -> None:
        emp_id = emp.get("id")
        if emp_id is not None:
            fresh = database.get_employee_by_id(int(emp_id))
            if fresh:
                emp = fresh
        dlg = EmployeeDetailsDialog(employee=emp, parent=self)
        dlg.exec_()
        if dlg.edit_requested:
            self._on_edit_clicked(emp)

    def _show_context_menu(self, pos) -> None:
        item = self.table.itemAt(pos)
        if not item:
            return
        self.table.selectRow(item.row())
        self.table.setCurrentItem(item)
        emp_id = self.table.item(item.row(), 0).data(Qt.UserRole)
        emp = next((e for e in self._current_rows if e.get("id") == emp_id), None)
        if emp is None and emp_id is not None:
            emp = database.get_employee_by_id(int(emp_id))
        if not emp:
            return
        menu = QMenu(self)
        view_a = menu.addAction(get_icon("view_details.png"), "View Details")
        edit_a = menu.addAction(get_icon("edit_details.png"), "Edit Employee")
        del_a = menu.addAction(get_icon("delete.png"), "Delete Employee")
        menu.addSeparator()
        copy_code_a = menu.addAction("Copy Employee Code")
        copy_email_a = menu.addAction("Copy Email Address")
        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if action == view_a:
            self._on_view_details_clicked(emp)
        elif action == edit_a:
            self._on_edit_clicked(emp)
        elif action == del_a:
            self._on_delete_clicked(emp)
        elif action == copy_code_a:
            QApplication.clipboard().setText(str(emp.get("emp_code", "")))
            self.status_message.emit("Employee code copied", 2000)
        elif action == copy_email_a:
            QApplication.clipboard().setText(str(emp.get("email", "")))
            self.status_message.emit("Email copied", 2000)

    def _on_reset_clicked(self) -> None:
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self.dept_combo.blockSignals(True)
        self.dept_combo.setCurrentIndex(0)
        self.dept_combo.blockSignals(False)
        self.status_combo.blockSignals(True)
        self.status_combo.setCurrentIndex(0)
        self.status_combo.blockSignals(False)
        self._page = 0
        self._apply_filters()

    def _on_add_clicked(self) -> None:
        dlg = EmployeeFormDialog(self)
        if dlg.exec_() != EmployeeFormDialog.Accepted:
            return
        values = dlg.get_values()
        try:
            new_id = database.add_employee(**values)
        except Exception as exc:
            msg = str(exc)
            if "UNIQUE" in msg.upper():
                msg = f"Employee code '{values.get('emp_code')}' already exists."
            else:
                logger.error("Unexpected error adding employee: %s", exc, exc_info=True)
                msg = "An unexpected error occurred. Please try again or contact your administrator."
            QMessageBox.critical(self, "Could Not Add Employee", msg, QMessageBox.Ok)
            return
        self.refresh()
        self.data_changed.emit()
        self._scroll_to_id(new_id)
        self.status_message.emit(f"Added {values['name']} ({values['emp_code']})", 3000)

    def _on_edit_clicked(self, emp: Dict[str, Any]) -> None:
        emp_id = emp.get("id")
        if emp_id is not None:
            fresh = database.get_employee_by_id(int(emp_id))
            if fresh:
                emp = fresh
        dlg = EmployeeFormDialog(self, employee=emp)
        if dlg.exec_() != EmployeeFormDialog.Accepted:
            return
        values = dlg.get_values()
        edit_id = dlg.employee_id()
        if edit_id is None:
            return
        try:
            ok = database.update_employee(emp_id=edit_id, **values)
        except Exception as exc:
            msg = str(exc)
            if "UNIQUE" in msg.upper():
                msg = f"Employee code '{values.get('emp_code')}' already exists."
            else:
                logger.error("Unexpected error updating employee %s: %s", emp_id, exc, exc_info=True)
                msg = "An unexpected error occurred. Please try again or contact your administrator."
            QMessageBox.critical(self, "Could Not Update Employee", msg, QMessageBox.Ok)
            return
        if not ok:
            QMessageBox.warning(self, "Not Found", "The employee record was not found.", QMessageBox.Ok)
        self.refresh()
        if ok:
            self.data_changed.emit()
            self._scroll_to_id(edit_id)
            self.status_message.emit(f"Updated {values['name']}", 3000)

    def _on_delete_clicked(self, emp: Dict[str, Any]) -> None:
        emp_id = emp.get("id")
        if emp_id is None:
            return
        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Permanently delete employee record?\n\n"
            f"• Name: {emp.get('name', '')}\n"
            f"• Code: {emp.get('emp_code', '')}\n\n"
            "This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            ok = database.delete_employee(int(emp_id))
        except Exception as exc:
            QMessageBox.critical(self, "Could Not Delete", "A database error occurred.", QMessageBox.Ok)
            return
        self.refresh()
        self.data_changed.emit()
        self.status_message.emit(f"Deleted {emp.get('name', '')}", 3000)

    def _scroll_to_id(self, emp_id: int) -> None:
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.data(Qt.UserRole) == emp_id:
                self.table.selectRow(r)
                self.table.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                break

    # ------------------------------------------------------------------
    # CSV Export (background thread)
    # ------------------------------------------------------------------
    def _on_export_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export to CSV", "employees.csv", "CSV (*.csv);;All Files (*)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"

        query = self.search_edit.text().strip() or None
        dept = self.dept_combo.currentData()
        status = self.status_combo.currentData()

        # Show progress dialog
        self._export_progress = QProgressDialog(
            "Exporting employee data…", "Cancel", 0, 0, self
        )
        self._export_progress.setWindowTitle("Exporting")
        self._export_progress.setWindowModality(Qt.WindowModal)
        self._export_progress.setMinimumDuration(0)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryButton")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedHeight(28)
        self._export_progress.setCancelButton(cancel_btn)

        self._export_progress.show()

        with self._worker_lock:
            self._export_worker = _ExportWorker(query, dept, status, path, self)
            self._export_worker.finished_ok.connect(self._on_export_done)
            self._export_worker.finished_err.connect(self._on_export_error)
            self._export_progress.canceled.connect(self._export_worker.cancel)
            self._export_worker.start()

    @pyqtSlot(int)
    def _on_export_done(self, n: int) -> None:
        if hasattr(self, "_export_progress") and self._export_progress is not None:
            self._export_progress.close()
        with self._worker_lock:
            self._export_worker = None
        self.status_message.emit(f"Exported {n:,} rows", 4000)

    @pyqtSlot(str)
    def _on_export_error(self, msg: str) -> None:
        if hasattr(self, "_export_progress") and self._export_progress is not None:
            self._export_progress.close()
        with self._worker_lock:
            self._export_worker = None
        QMessageBox.critical(self, "Export Failed", msg, QMessageBox.Ok)

    # ------------------------------------------------------------------
    # CSV Import (background thread with progress)
    # ------------------------------------------------------------------
    def _on_import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import from CSV", "", "CSV (*.csv);;All Files (*)")
        if not path:
            return

        # Show progress dialog
        self._import_progress = QProgressDialog(
            "Preparing import…", "Cancel", 0, 100, self
        )
        self._import_progress.setWindowTitle("Importing CSV")
        self._import_progress.setWindowModality(Qt.WindowModal)
        self._import_progress.setMinimumDuration(0)
        self._import_progress.setValue(0)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryButton")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedHeight(28)
        self._import_progress.setCancelButton(cancel_btn)

        self._import_progress.show()

        with self._worker_lock:
            self._import_worker = _ImportWorker(path, self)
            self._import_worker.progress.connect(self._on_import_progress)
            self._import_worker.finished_ok.connect(self._on_import_done)
            self._import_worker.finished_err.connect(self._on_import_error)
            self._import_progress.canceled.connect(self._import_worker.cancel)
            self._import_worker.start()

    @pyqtSlot(int, int, int, int)
    def _on_import_progress(self, processed: int, total: int, inserted: int, skipped: int) -> None:
        if hasattr(self, "_import_progress") and self._import_progress is not None:
            self._import_progress.setMaximum(total)
            self._import_progress.setValue(processed)
            pct = int(processed / total * 100) if total > 0 else 0
            self._import_progress.setLabelText(
                f"Processing row {processed:,} of {total:,} ({pct}%)\n"
                f"Inserted: {inserted:,}  |  Skipped: {skipped:,}"
            )

    @pyqtSlot(int, int, list)
    def _on_import_done(self, inserted: int, skipped: int, errors: list) -> None:
        if hasattr(self, "_import_progress") and self._import_progress is not None:
            self._import_progress.close()
        with self._worker_lock:
            self._import_worker = None

        self.refresh()
        if inserted > 0:
            self.data_changed.emit()
        base = f"Imported {inserted:,} new employees. Skipped: {skipped:,}."
        self.status_message.emit(base, 5000)
        if errors:
            err_block = "\n".join(errors[:12])
            QMessageBox.warning(self, "Import Completed with Warnings", f"{base}\n\nDetails:\n{err_block}", QMessageBox.Ok)

    @pyqtSlot(str)
    def _on_import_error(self, msg: str) -> None:
        if hasattr(self, "_import_progress") and self._import_progress is not None:
            self._import_progress.close()
        with self._worker_lock:
            self._import_worker = None
        QMessageBox.critical(self, "Import Failed", msg, QMessageBox.Ok)

    def cleanup_workers(self) -> None:
        """Safely wait on any background workers during window shutdown."""
        with self._worker_lock:
            if self._import_worker is not None and self._import_worker.isRunning():
                self._import_worker.cancel()
                self._import_worker.wait(1000)
            if self._export_worker is not None and self._export_worker.isRunning():
                self._export_worker.cancel()
                self._export_worker.wait(1000)


from typing import Dict, Any, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
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
)

import database
from employee_form import EmployeeFormDialog, DEPARTMENTS
from csv_utils import export_table_to_csv, import_csv_to_db, CsvImportError


TABLE_COLUMNS = [
    ("id", "ID"),
    ("emp_code", "Code"),
    ("name", "Name"),
    ("email", "Email"),
    ("department", "Department"),
    ("position", "Position"),
    ("salary", "Salary"),
    ("hire_date", "Hire Date"),
    ("__actions__", "Actions"),
]


class EmployeeView(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initialized = False
        self._current_rows = []
        self._build_ui()
        self.refresh()
        self._initialized = True

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        card = QFrame(self)
        card.setProperty("class", "card")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        page_title = QLabel("Employees")
        page_title.setProperty("class", "cardTitle")
        page_sub = QLabel("Search, add, update, and delete employee records.")
        page_sub.setProperty("class", "cardSubtitle")
        page_sub.setWordWrap(True)
        title_col.addWidget(page_title)
        title_col.addWidget(page_sub)

        header_row.addLayout(title_col, 1)

        self.import_button = QPushButton("Import CSV")
        self.import_button.setProperty("class", "secondaryButton")
        self.import_button.setCursor(Qt.PointingHandCursor)
        self.import_button.clicked.connect(self._on_import_csv)
        header_row.addWidget(self.import_button)

        self.export_button = QPushButton("Export to CSV")
        self.export_button.setProperty("class", "secondaryButton")
        self.export_button.setCursor(Qt.PointingHandCursor)
        self.export_button.clicked.connect(self._on_export_csv)
        header_row.addWidget(self.export_button)

        self.add_button = QPushButton("+ Add Employee")
        self.add_button.setProperty("class", "primaryButton")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.clicked.connect(self._on_add_clicked)
        header_row.addWidget(self.add_button)

        card_layout.addLayout(header_row)

        # Filter bar
        filter_bar = QFrame()
        filter_bar.setStyleSheet(
            "QFrame { background-color: transparent; }"
        )
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(10)

        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search code, name, email, position...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_filter_changed)

        dept_label = QLabel("Department:")
        self.dept_combo = QComboBox()
        self.dept_combo.setMinimumWidth(200)
        self._populate_dept_combo()
        self.dept_combo.currentIndexChanged.connect(self._on_filter_changed)

        self.reset_button = QPushButton("Reset Filters")
        self.reset_button.setProperty("class", "secondaryButton")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.clicked.connect(self._on_reset_clicked)

        self.count_label = QLabel("0 employees")
        self.count_label.setProperty("class", "cardSubtitle")
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        filter_layout.addWidget(search_label)
        filter_layout.addWidget(self.search_edit, 1)
        filter_layout.addSpacing(6)
        filter_layout.addWidget(dept_label)
        filter_layout.addWidget(self.dept_combo, 0)
        filter_layout.addWidget(self.reset_button)
        filter_layout.addSpacing(10)
        filter_layout.addWidget(self.count_label, 0)

        card_layout.addWidget(filter_bar)

        # Table
        self.table = QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _, label in TABLE_COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        self._configure_column_widths(header)
        header.setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(len(TABLE_COLUMNS) - 1, QHeaderView.Fixed)
        self.table.setColumnWidth(len(TABLE_COLUMNS) - 1, 160)

        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_layout.addWidget(self.table, 1)

        root.addWidget(card)

    def _configure_column_widths(self, header: QHeaderView) -> None:
        widths = {
            "id": 60,
            "emp_code": 100,
            "name": 180,
            "email": 220,
            "department": 140,
            "position": 150,
            "salary": 110,
            "hire_date": 110,
        }
        for i, (key, _) in enumerate(TABLE_COLUMNS):
            if key in widths:
                header.resizeSection(i, widths[key])

    def _populate_dept_combo(self) -> None:
        self.dept_combo.blockSignals(True)
        self.dept_combo.clear()
        self.dept_combo.addItem("All Departments", None)
        for d in DEPARTMENTS:
            self.dept_combo.addItem(d, d)

        try:
            existing = set()
            for emp in database.get_all_employees():
                dept = emp.get("department")
                if dept and dept not in existing and dept not in DEPARTMENTS:
                    existing.add(dept)
                    self.dept_combo.addItem(dept, dept)
        except Exception:
            pass
        self.dept_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Data loading + table population
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._populate_dept_combo()
        self._apply_filters()
        if getattr(self, "_initialized", True):
            self.data_changed.emit()

    def _on_filter_changed(self) -> None:
        self._apply_filters()

    def _apply_filters(self) -> None:
        query = self.search_edit.text().strip() or None
        dept = self.dept_combo.currentData()
        try:
            rows = database.search_employees(query=query, department=dept)
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", str(exc), QMessageBox.Ok)
            rows = []
        self._current_rows = rows
        self._render_table(rows)
        self.count_label.setText(
            "{} employee{}".format(len(rows), "" if len(rows) == 1 else "s")
        )

    def _render_table(self, rows: List[Dict[str, Any]]) -> None:
        self.table.setRowCount(0)
        for r_idx, emp in enumerate(rows):
            self.table.insertRow(r_idx)
            for c_idx, (key, _) in enumerate(TABLE_COLUMNS):
                if key == "__actions__":
                    self.table.setCellWidget(r_idx, c_idx, self._make_action_cell(emp))
                    continue
                if key == "salary":
                    value = "${:,.2f}".format(float(emp.get(key) or 0.0))
                else:
                    value = "" if emp.get(key) is None else str(emp.get(key))
                item = QTableWidgetItem(value)
                if key == "id":
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                elif key == "salary":
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                else:
                    item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                item.setData(Qt.UserRole, emp.get("id"))
                self.table.setItem(r_idx, c_idx, item)
        self.table.resizeRowsToContents()

    def _make_action_cell(self, emp: Dict[str, Any]) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        edit_btn = QPushButton("Edit")
        edit_btn.setProperty("class", "secondaryButton")
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.setFixedHeight(26)
        edit_btn.clicked.connect(lambda _=False, e=emp: self._on_edit_clicked(e))

        del_btn = QPushButton("Delete")
        del_btn.setProperty("class", "dangerButton")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setFixedHeight(26)
        del_btn.clicked.connect(lambda _=False, e=emp: self._on_delete_clicked(e))

        layout.addStretch(1)
        layout.addWidget(edit_btn)
        layout.addWidget(del_btn)
        layout.addStretch(1)
        return container

    # ------------------------------------------------------------------
    # Toolbar actions
    # ------------------------------------------------------------------
    def _on_reset_clicked(self) -> None:
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)

        self.dept_combo.blockSignals(True)
        self.dept_combo.setCurrentIndex(0)
        self.dept_combo.blockSignals(False)

        self._apply_filters()

    def _on_add_clicked(self) -> None:
        dialog = EmployeeFormDialog(self)
        if dialog.exec_() != EmployeeFormDialog.Accepted:
            return
        values = dialog.get_values()
        try:
            new_id = database.add_employee(
                emp_code=values["emp_code"],
                name=values["name"],
                email=values["email"],
                department=values["department"],
                position=values["position"],
                salary=values["salary"],
                hire_date=values["hire_date"],
            )
        except Exception as exc:
            msg = str(exc)
            if "UNIQUE" in msg.upper() and "EMP_CODE" in msg.upper():
                msg = "An employee with this Employee Code already exists."
            elif "UNIQUE" in msg.upper():
                msg = "A database unique constraint was violated: {}".format(msg)
            QMessageBox.critical(self, "Could Not Add Employee", msg, QMessageBox.Ok)
            return
        self.refresh()
        self._scroll_to_id(new_id)

    def _on_edit_clicked(self, emp: Dict[str, Any]) -> None:
        dialog = EmployeeFormDialog(self, employee=emp)
        if dialog.exec_() != EmployeeFormDialog.Accepted:
            return
        values = dialog.get_values()
        emp_id = dialog.employee_id()
        if emp_id is None:
            return
        try:
            ok = database.update_employee(
                emp_id=emp_id,
                emp_code=values["emp_code"],
                name=values["name"],
                email=values["email"],
                department=values["department"],
                position=values["position"],
                salary=values["salary"],
                hire_date=values["hire_date"],
            )
        except Exception as exc:
            msg = str(exc)
            if "UNIQUE" in msg.upper() and "EMP_CODE" in msg.upper():
                msg = "An employee with this Employee Code already exists."
            QMessageBox.critical(self, "Could Not Update Employee", msg, QMessageBox.Ok)
            return
        if not ok:
            QMessageBox.warning(
                self,
                "Not Updated",
                "The employee was not updated. It may have been deleted already.",
                QMessageBox.Ok,
            )
        self.refresh()
        self._scroll_to_id(emp_id)

    def _on_delete_clicked(self, emp: Dict[str, Any]) -> None:
        emp_id = emp.get("id")
        emp_name = emp.get("name", "")
        emp_code = emp.get("emp_code", "")
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete {} ({})? This cannot be undone.".format(
                emp_name, emp_code
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            ok = database.delete_employee(int(emp_id))
        except Exception as exc:
            QMessageBox.critical(self, "Could Not Delete Employee", str(exc), QMessageBox.Ok)
            return
        if not ok:
            QMessageBox.information(
                self,
                "Not Deleted",
                "The employee was not deleted. It may have been removed already.",
                QMessageBox.Ok,
            )
        self.refresh()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _scroll_to_id(self, emp_id: int) -> None:
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is not None and int(item.text()) == int(emp_id):
                self.table.selectRow(r)
                self.table.scrollToItem(
                    self.table.item(r, 0),
                    hint=QAbstractItemView.PositionAtCenter,
                )
                break

    # ------------------------------------------------------------------
    # CSV Import / Export
    # ------------------------------------------------------------------
    def _on_export_csv(self) -> None:
        rows = list(self._current_rows)
        if not rows:
            confirm = QMessageBox.question(
                self,
                "Empty Table",
                "There are no rows currently visible. Export an empty CSV anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return

        default_name = "employees.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Employees to CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path = path + ".csv"

        try:
            written = export_table_to_csv(rows, path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Export Failed",
                "Could not write CSV file:\n{}".format(exc),
                QMessageBox.Ok,
            )
            return

        QMessageBox.information(
            self,
            "Export Complete",
            "Successfully exported {} row{} to:\n{}".format(
                written, "" if written == 1 else "s", path
            ),
            QMessageBox.Ok,
        )

    def _on_import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Employees from CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        try:
            inserted, skipped, errors = import_csv_to_db(path, skip_duplicates=True)
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "Import Failed", str(exc), QMessageBox.Ok)
            return
        except CsvImportError as exc:
            detail = "\n".join(exc.errors[:10])
            extra = "" if len(exc.errors) <= 10 else "\n... and {} more.".format(len(exc.errors) - 10)
            QMessageBox.critical(
                self,
                "Import Failed",
                "{}\n{}".format(str(exc), detail + extra).strip(),
                QMessageBox.Ok,
            )
            return
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Import Failed",
                "Could not process CSV file:\n{}".format(exc),
                QMessageBox.Ok,
            )
            return

        self.refresh()

        summary = "Imported {} new employee{}.\nSkipped (duplicates/errors): {}.\n\nRows processed: {}.".format(
            inserted,
            "" if inserted == 1 else "s",
            skipped,
            inserted + skipped,
        )
        icon = QMessageBox.Information
        title = "Import Complete"
        if errors:
            icon = QMessageBox.Warning
            title = "Import Completed with Warnings"
            err_block = "\n".join(errors[:15])
            if len(errors) > 15:
                err_block += "\n... and {} more issue(s).".format(len(errors) - 15)
            summary += "\n\nDetails:\n{}".format(err_block)

        box = QMessageBox(icon, title, summary, QMessageBox.Ok, self)
        box.setWindowTitle(title)
        box.setText(summary)
        box.exec_()

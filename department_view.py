from typing import Dict, Any, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QTableWidget,
    QHeaderView,
    QMessageBox,
    QAbstractItemView,
    QSizePolicy,
    QMenu,
    QDialog,
    QComboBox,
    QFormLayout,
    QPlainTextEdit,
)

import database
from department_form import DepartmentFormDialog
from employee_view import SortableTableWidgetItem
from icon_utils import get_icon
from logger import logger

DEPT_TABLE_COLUMNS = [
    ("id", "ID"),
    ("name", "Department Name"),
    ("description", "Description"),
    ("employee_count", "Employees"),
    ("created_at", "Created"),
]


class ReassignDepartmentDialog(QDialog):
    def __init__(self, dept_name: str, emp_count: int, available_depts: List[str], parent=None):
        super().__init__(parent)
        self.dept_name = dept_name
        self.emp_count = emp_count
        self.available_depts = available_depts
        self.selected_target: Optional[str] = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.setWindowTitle("Reassign Employees Before Deletion")
        self.setMinimumSize(440, 280)
        self.resize(460, 300)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        card = QFrame(self)
        card.setObjectName("formCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(14)

        title = QLabel(f"Delete '{self.dept_name}'?", card)
        title.setObjectName("formTitle")

        msg = QLabel(
            f"This department has <b>{self.emp_count} employee(s)</b> assigned.<br>"
            "Please select a department to reassign them to before deleting:",
            card,
        )
        msg.setTextFormat(Qt.RichText)
        msg.setWordWrap(True)

        form = QFormLayout()
        form.setSpacing(10)
        self.target_combo = QComboBox(card)
        self.target_combo.setFixedHeight(34)
        for d in self.available_depts:
            if d.lower() != self.dept_name.lower():
                self.target_combo.addItem(d, d)
        form.addRow("Reassign to:", self.target_combo)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.cancel_btn = QPushButton("Cancel", card)
        self.cancel_btn.setProperty("class", "secondaryButton")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setFixedHeight(34)
        self.cancel_btn.clicked.connect(self.reject)
        self.confirm_btn = QPushButton("Reassign & Delete", card)
        self.confirm_btn.setIcon(get_icon("delete.png"))
        self.confirm_btn.setIconSize(QSize(18, 18))
        self.confirm_btn.setProperty("class", "dangerButton")
        self.confirm_btn.setCursor(Qt.PointingHandCursor)
        self.confirm_btn.setFixedHeight(34)
        self.confirm_btn.clicked.connect(self._on_confirm)
        btn_row.addStretch(1)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.confirm_btn)

        card_layout.addWidget(title)
        card_layout.addWidget(msg)
        card_layout.addSpacing(4)
        card_layout.addLayout(form)
        card_layout.addStretch(1)
        card_layout.addLayout(btn_row)
        root.addWidget(card)

    def _on_confirm(self) -> None:
        target = self.target_combo.currentText().strip()
        if not target:
            QMessageBox.warning(self, "No Target", "Please select a target department.", QMessageBox.Ok)
            return
        self.selected_target = target
        self.accept()


class DepartmentView(QWidget):
    data_changed = pyqtSignal()
    status_message = pyqtSignal(str, int)

    def __init__(self, parent=None, lazy: bool = False):
        super().__init__(parent)
        self._all_depts: List[Dict] = []
        self._current_rows: List[Dict] = []
        self._build_ui()
        if not lazy:
            self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        card = QFrame(self)
        card.setProperty("class", "card")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(12)

        # ── Row 1: Title + Add button ──
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        page_title = QLabel("Departments")
        page_title.setProperty("class", "cardTitle")
        page_sub = QLabel("Manage organizational units, descriptions, and department assignments.")
        page_sub.setProperty("class", "cardSubtitle")
        page_sub.setWordWrap(True)
        title_col.addWidget(page_title)
        title_col.addWidget(page_sub)
        header_row.addLayout(title_col, 1)

        self.add_button = QPushButton("Add Department")
        self.add_button.setIcon(get_icon("add.png"))
        self.add_button.setIconSize(QSize(20, 20))
        self.add_button.setProperty("class", "primaryButton")
        self.add_button.setCursor(Qt.PointingHandCursor)
        self.add_button.setFixedHeight(34)
        self.add_button.clicked.connect(self._on_add_clicked)
        header_row.addWidget(self.add_button)
        card_layout.addLayout(header_row)

        # ── Divider ──
        div = QFrame()
        div.setProperty("class", "divider")
        div.setFixedHeight(1)
        card_layout.addWidget(div)

        # ── Row 2: Search ──
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search by department name or description…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedHeight(34)
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self._apply_filter)
        self.search_edit.textChanged.connect(lambda: self._search_timer.start())

        self.reset_button = QPushButton("Reset")
        self.reset_button.setIcon(get_icon("refresh.png"))
        self.reset_button.setIconSize(QSize(16, 16))
        self.reset_button.setProperty("class", "secondaryButton")
        self.reset_button.setCursor(Qt.PointingHandCursor)
        self.reset_button.setFixedHeight(34)
        self.reset_button.setMinimumWidth(72)
        self.reset_button.clicked.connect(self._on_reset_clicked)

        filter_row.addWidget(self.search_edit, 1)
        filter_row.addWidget(self.reset_button)
        card_layout.addLayout(filter_row)

        # ── Row 3: Selection Actions + count ──
        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        self.edit_button = QPushButton("Edit")
        self.edit_button.setIcon(get_icon("edit_details.png"))
        self.edit_button.setIconSize(QSize(16, 16))
        self.edit_button.setProperty("class", "secondaryButton")
        self.edit_button.setCursor(Qt.PointingHandCursor)
        self.edit_button.setFixedHeight(32)
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(self._on_edit_selected)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setIcon(get_icon("delete.png"))
        self.delete_button.setIconSize(QSize(16, 16))
        self.delete_button.setProperty("class", "dangerButton")
        self.delete_button.setCursor(Qt.PointingHandCursor)
        self.delete_button.setFixedHeight(32)
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self._on_delete_selected)

        self.count_label = QLabel("0 departments")
        self.count_label.setProperty("class", "cardSubtitle")
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        action_row.addWidget(self.edit_button)
        action_row.addWidget(self.delete_button)
        action_row.addStretch(1)
        action_row.addWidget(self.count_label)
        card_layout.addLayout(action_row)

        # ── Table ──
        self.table = QTableWidget(0, len(DEPT_TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _, label in DEPT_TABLE_COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        for i, (key, _) in enumerate(DEPT_TABLE_COLUMNS):
            widths = {"id": 60, "name": 220, "description": 320, "employee_count": 120, "created_at": 140}
            if key in widths:
                header.resizeSection(i, widths[key])
        header.setStretchLastSection(True)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card_layout.addWidget(self.table, 1)

        # ── Empty State ──
        self.empty_state_frame = QFrame(card)
        empty_layout = QVBoxLayout(self.empty_state_frame)
        empty_layout.setContentsMargins(40, 60, 40, 60)
        empty_layout.setSpacing(12)
        empty_layout.setAlignment(Qt.AlignCenter)

        self.empty_icon = QLabel("🏢", self.empty_state_frame)
        self.empty_icon.setStyleSheet("font-size: 36px; background: transparent;")
        self.empty_icon.setAlignment(Qt.AlignCenter)

        self.empty_title = QLabel("No Departments Found")
        self.empty_title.setStyleSheet("QLabel { font-size: 16px; font-weight: 700; color: #0f172a; }")
        self.empty_title.setAlignment(Qt.AlignCenter)

        self.empty_subtitle = QLabel("No departments match your current search.")
        self.empty_subtitle.setProperty("class", "cardSubtitle")
        self.empty_subtitle.setAlignment(Qt.AlignCenter)

        self.empty_action_btn = QPushButton("Clear Search")
        self.empty_action_btn.setProperty("class", "primaryButton")
        self.empty_action_btn.setCursor(Qt.PointingHandCursor)
        self.empty_action_btn.setFixedHeight(34)

        empty_layout.addWidget(self.empty_icon, 0, Qt.AlignHCenter)
        empty_layout.addWidget(self.empty_title, 0, Qt.AlignHCenter)
        empty_layout.addWidget(self.empty_subtitle, 0, Qt.AlignHCenter)
        empty_layout.addSpacing(6)
        empty_layout.addWidget(self.empty_action_btn, 0, Qt.AlignHCenter)
        self.empty_state_frame.setVisible(False)
        card_layout.addWidget(self.empty_state_frame, 1)

        root.addWidget(card)

    def refresh(self) -> None:
        try:
            self._all_depts = database.get_all_departments()
        except Exception as exc:
            logger.error("Error loading departments: %s", exc, exc_info=True)
            self._all_depts = []
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self.search_edit.text().strip().lower()
        filtered = [
            d for d in self._all_depts
            if not query or query in str(d.get("name", "")).lower() or query in str(d.get("description", "")).lower()
        ]
        self._current_rows = filtered
        self._render_table(filtered)
        n = len(filtered)
        self.count_label.setText(f"{n} department{'' if n == 1 else 's'}")

        has_data = n > 0
        self.table.setVisible(has_data)
        self.empty_state_frame.setVisible(not has_data)
        if not has_data:
            if query:
                self.empty_title.setText("No Matches")
                self.empty_subtitle.setText("No departments match your search keyword.")
                self.empty_action_btn.setText("Clear Search")
                try:
                    self.empty_action_btn.clicked.disconnect()
                except Exception:
                    pass
                self.empty_action_btn.clicked.connect(self._on_reset_clicked)
            else:
                self.empty_title.setText("No Departments")
                self.empty_subtitle.setText("Add your first department.")
                self.empty_action_btn.setText("Add Department")
                try:
                    self.empty_action_btn.clicked.disconnect()
                except Exception:
                    pass
                self.empty_action_btn.clicked.connect(self._on_add_clicked)

    def _render_table(self, rows: List[Dict]) -> None:
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)
        try:
            self.table.setRowCount(len(rows))
            for r_idx, dept in enumerate(rows):
                dept_id = dept.get("id") or 0
                for c_idx, (key, _) in enumerate(DEPT_TABLE_COLUMNS):
                    raw = dept.get(key)
                    if key == "id":
                        item = SortableTableWidgetItem(str(dept_id), sort_key=int(dept_id))
                        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    elif key == "employee_count":
                        n = int(raw or 0)
                        item = SortableTableWidgetItem(str(n), sort_key=n)
                        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    else:
                        s = "" if raw is None else str(raw)
                        item = SortableTableWidgetItem(s, sort_key=s.lower())
                        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                    item.setData(Qt.UserRole, dept_id)
                    self.table.setItem(r_idx, c_idx, item)
        finally:
            self.table.setSortingEnabled(True)
            self.table.setUpdatesEnabled(True)
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        has = len(self.table.selectedItems()) > 0
        self.edit_button.setEnabled(has)
        self.delete_button.setEnabled(has)

    def _get_selected_department(self) -> Optional[Dict]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        dept_id = item.data(Qt.UserRole)
        return next((d for d in self._current_rows if d.get("id") == dept_id), None)

    def _on_reset_clicked(self) -> None:
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self._apply_filter()

    def _on_add_clicked(self) -> None:
        dlg = DepartmentFormDialog(self)
        if dlg.exec_() != DepartmentFormDialog.Accepted:
            return
        values = dlg.get_values()
        try:
            database.add_department(name=values["name"], description=values["description"])
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not create department:\n{exc}", QMessageBox.Ok)
            return
        self.refresh()
        self.data_changed.emit()
        self.status_message.emit(f"Department '{values['name']}' created.", 3000)

    def _on_edit_selected(self) -> None:
        dept = self._get_selected_department()
        if dept:
            self._on_edit_clicked(dept)

    def _on_cell_double_clicked(self, row: int, col: int) -> None:
        item = self.table.item(row, 0)
        if item:
            dept_id = item.data(Qt.UserRole)
            dept = next((d for d in self._current_rows if d.get("id") == dept_id), None)
            if dept:
                self._on_edit_clicked(dept)

    def _on_edit_clicked(self, dept: Dict) -> None:
        dlg = DepartmentFormDialog(self, department=dept)
        if dlg.exec_() != DepartmentFormDialog.Accepted:
            return
        values = dlg.get_values()
        dept_id = dlg.department_id()
        if dept_id is None:
            return
        try:
            database.update_department(dept_id=dept_id, new_name=values["name"], description=values["description"])
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not update department:\n{exc}", QMessageBox.Ok)
            return
        self.refresh()
        self.data_changed.emit()
        self.status_message.emit(f"Department '{values['name']}' updated.", 3000)

    def _on_delete_selected(self) -> None:
        dept = self._get_selected_department()
        if dept:
            self._on_delete_clicked(dept)

    def _on_delete_clicked(self, dept: Dict) -> None:
        dept_id = int(dept["id"])
        dept_name = str(dept["name"])
        emp_count = int(dept.get("employee_count") or 0)

        if emp_count > 0:
            available = [d["name"] for d in self._all_depts if str(d["id"]) != str(dept_id)]
            if not available:
                QMessageBox.warning(self, "Cannot Delete",
                    f"'{dept_name}' has {emp_count} employees and no other department exists to reassign them to.",
                    QMessageBox.Ok)
                return
            dlg = ReassignDepartmentDialog(dept_name=dept_name, emp_count=emp_count, available_depts=available, parent=self)
            if dlg.exec_() != ReassignDepartmentDialog.Accepted or not dlg.selected_target:
                return
            try:
                database.delete_department(dept_id=dept_id, reassign_to=dlg.selected_target)
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Could not delete department:\n{exc}", QMessageBox.Ok)
                return
            self.refresh()
            self.data_changed.emit()
            self.status_message.emit(f"Deleted '{dept_name}', reassigned {emp_count} employees.", 4000)
        else:
            confirm = QMessageBox.question(self, "Confirm Delete",
                f"Permanently delete department '{dept_name}'?\n\nThis cannot be undone.",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if confirm != QMessageBox.Yes:
                return
            try:
                database.delete_department(dept_id=dept_id)
            except Exception as exc:
                QMessageBox.critical(self, "Error", f"Could not delete:\n{exc}", QMessageBox.Ok)
                return
            self.refresh()
            self.data_changed.emit()
            self.status_message.emit(f"Department '{dept_name}' deleted.", 3000)

    def _show_context_menu(self, pos) -> None:
        item = self.table.itemAt(pos)
        if not item:
            return
        self.table.selectRow(item.row())
        self.table.setCurrentItem(item)
        dept_id = self.table.item(item.row(), 0).data(Qt.UserRole)
        dept = next((d for d in self._current_rows if d.get("id") == dept_id), None)
        if not dept:
            return
        menu = QMenu(self)
        edit_a = menu.addAction(get_icon("edit_details.png"), "Edit Department")
        del_a = menu.addAction(get_icon("delete.png"), "Delete Department")
        action = menu.exec_(self.table.viewport().mapToGlobal(pos))
        if action == edit_a:
            self._on_edit_clicked(dept)
        elif action == del_a:
            self._on_delete_clicked(dept)

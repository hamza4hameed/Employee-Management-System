import math
import re
from typing import Dict, Any, Optional

from PyQt5.QtCore import Qt, QDate, QRegularExpression
from PyQt5.QtGui import QRegularExpressionValidator
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QDateEdit,
    QComboBox,
    QPushButton,
    QFrame,
    QMessageBox,
    QSizePolicy,
)

import database
from database import EMPLOYEE_STATUSES
from icon_utils import get_icon
from logger import logger

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_CODE_RE = re.compile(r"^[A-Za-z0-9_\-]{2,32}$")
_MIN_DATE = QDate(1900, 1, 1)
_MAX_DATE = QDate(2100, 12, 31)


def _make_required_label(text: str) -> QLabel:
    lbl = QLabel(f"{text} <span style='color:#ef4444; font-weight:700;'>*</span>")
    lbl.setTextFormat(Qt.RichText)
    return lbl


class EmployeeFormDialog(QDialog):
    def __init__(
        self,
        parent=None,
        employee: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(parent)
        self._employee: Optional[Dict[str, Any]] = employee
        self._is_edit: bool = employee is not None
        self._validated_values: Optional[Dict[str, Any]] = None

        self._build_ui()
        self._setup_validators()
        if self._is_edit:
            self._populate_from_employee()
        else:
            self._apply_new_employee_defaults()

        self.setWindowTitle(
            f"Edit Employee - {employee.get('emp_code', '')}"
            if self._is_edit
            else "Add New Employee"
        )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setMinimumSize(480, 620)
        self.resize(500, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("formCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 24, 30, 24)
        card_layout.setSpacing(16)

        title = QLabel("Employee Details", card)
        title.setObjectName("formTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Edit the employee information below." if self._is_edit else "Fill in the required fields marked with * to register an employee.",
            card,
        )
        subtitle.setObjectName("formSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.code_edit = QLineEdit(card)
        self.code_edit.setFixedHeight(34)
        self.code_edit.setPlaceholderText("e.g. EMP-101")
        self.code_edit.setToolTip("Unique identifier (2-32 characters, letters, digits, dashes)")
        self.code_edit.setMaxLength(32)

        self.name_edit = QLineEdit(card)
        self.name_edit.setFixedHeight(34)
        self.name_edit.setPlaceholderText("Full legal name")
        self.name_edit.setToolTip("Employee's full name (up to 100 characters)")
        self.name_edit.setMaxLength(100)

        self.email_edit = QLineEdit(card)
        self.email_edit.setFixedHeight(34)
        self.email_edit.setPlaceholderText("name@company.com")
        self.email_edit.setToolTip("Work or personal email address")
        self.email_edit.setMaxLength(120)

        self.dept_combo = QComboBox(card)
        self.dept_combo.setFixedHeight(34)
        self.dept_combo.setEditable(True)
        if self.dept_combo.lineEdit():
            self.dept_combo.lineEdit().setMaxLength(60)
        depts = database.get_departments()
        self.dept_combo.addItems(depts)

        self.position_edit = QLineEdit(card)
        self.position_edit.setFixedHeight(34)
        self.position_edit.setPlaceholderText("e.g. Senior Software Engineer")
        self.position_edit.setToolTip("Job role or position title")
        self.position_edit.setMaxLength(80)

        self.status_combo = QComboBox(card)
        self.status_combo.setFixedHeight(34)
        self.status_combo.addItems(EMPLOYEE_STATUSES)
        self.status_combo.setToolTip("Current employment standing (e.g. Active, On Leave)")

        self.salary_spin = QDoubleSpinBox(card)
        self.salary_spin.setFixedHeight(34)
        self.salary_spin.setRange(0.0, 100_000_000.0)
        self.salary_spin.setDecimals(2)
        self.salary_spin.setSingleStep(1000.0)
        self.salary_spin.setPrefix("$ ")
        self.salary_spin.setToolTip("Gross annual compensation in USD")

        self.hire_date = QDateEdit(card)
        self.hire_date.setFixedHeight(34)
        self.hire_date.setCalendarPopup(True)
        self.hire_date.setDisplayFormat("yyyy-MM-dd")
        self.hire_date.setDateRange(_MIN_DATE, _MAX_DATE)
        self.hire_date.setDate(QDate.currentDate())
        self.hire_date.setToolTip("Official start date with the company (YYYY-MM-DD)")

        form.addRow(_make_required_label("Employee Code:"), self.code_edit)
        form.addRow(_make_required_label("Full Name:"), self.name_edit)
        form.addRow(_make_required_label("Email Address:"), self.email_edit)
        form.addRow(_make_required_label("Department:"), self.dept_combo)
        form.addRow(_make_required_label("Job Position:"), self.position_edit)
        form.addRow(_make_required_label("Employment Status:"), self.status_combo)
        form.addRow(_make_required_label("Annual Salary:"), self.salary_spin)
        form.addRow(_make_required_label("Hire Date:"), self.hire_date)

        req_note = QLabel("<span style='color:#ef4444; font-weight:700;'>*</span> Required fields", card)
        req_note.setProperty("class", "cardSubtitle")
        req_note.setStyleSheet("QLabel { font-size: 11px; color: #94a3b8; }")

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        self.cancel_btn = QPushButton("Cancel", card)
        self.cancel_btn.setProperty("class", "secondaryButton")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Save Employee" if not self._is_edit else "Save Changes", card)
        self.save_btn.setIcon(get_icon("add.png" if not self._is_edit else "edit_details.png"))
        self.save_btn.setProperty("class", "primaryButton")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setFixedHeight(36)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)

        buttons_row.addWidget(req_note)
        buttons_row.addStretch(1)
        buttons_row.addWidget(self.cancel_btn)
        buttons_row.addWidget(self.save_btn)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(4)
        card_layout.addLayout(form)
        card_layout.addStretch(1)
        card_layout.addLayout(buttons_row)

        root.addWidget(card)

        # Explicit tab order for seamless keyboard navigation
        self.setTabOrder(self.code_edit, self.name_edit)
        self.setTabOrder(self.name_edit, self.email_edit)
        self.setTabOrder(self.email_edit, self.dept_combo)
        self.setTabOrder(self.dept_combo, self.position_edit)
        self.setTabOrder(self.position_edit, self.status_combo)
        self.setTabOrder(self.status_combo, self.salary_spin)
        self.setTabOrder(self.salary_spin, self.hire_date)
        self.setTabOrder(self.hire_date, self.save_btn)
        self.setTabOrder(self.save_btn, self.cancel_btn)

        self.code_edit.setFocus()

    def _setup_validators(self) -> None:
        email_re = QRegularExpression(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
        self.email_edit.setValidator(QRegularExpressionValidator(email_re, self))

        self.salary_spin.setLocale(self.locale())

        code_re = QRegularExpression(r"^[A-Za-z0-9_\-]{2,32}$")
        self.code_edit.setValidator(QRegularExpressionValidator(code_re, self))

    def _apply_new_employee_defaults(self) -> None:
        self.salary_spin.setValue(50000.0)
        self.hire_date.setDate(QDate.currentDate())
        if self.dept_combo.count() > 0:
            self.dept_combo.setCurrentIndex(0)
        self.status_combo.setCurrentText("Active")

    def _populate_from_employee(self) -> None:
        if self._employee is None:
            return
        self.code_edit.setText(str(self._employee.get("emp_code", "")))
        self.name_edit.setText(str(self._employee.get("name", "")))
        self.email_edit.setText(str(self._employee.get("email", "")))

        dept = str(self._employee.get("department", ""))
        idx = self.dept_combo.findText(dept, Qt.MatchFixedString)
        if idx >= 0:
            self.dept_combo.setCurrentIndex(idx)
        else:
            self.dept_combo.setEditText(dept)

        self.position_edit.setText(str(self._employee.get("position", "")))

        status = str(self._employee.get("status", "Active"))
        s_idx = self.status_combo.findText(status, Qt.MatchFixedString)
        if s_idx >= 0:
            self.status_combo.setCurrentIndex(s_idx)

        try:
            sal = float(self._employee.get("salary") or 0.0)
            if not math.isnan(sal) and not math.isinf(sal):
                self.salary_spin.setValue(sal)
        except (ValueError, TypeError):
            self.salary_spin.setValue(0.0)

        hire_str = str(self._employee.get("hire_date", ""))
        qd = QDate.fromString(hire_str, "yyyy-MM-dd")
        if qd.isValid():
            self.hire_date.setDate(qd)

    # ------------------------------------------------------------------
    # Validation + save
    # ------------------------------------------------------------------
    def _collect_values(self) -> Dict[str, Any]:
        return {
            "emp_code": self.code_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "department": self.dept_combo.currentText().strip(),
            "position": self.position_edit.text().strip(),
            "status": self.status_combo.currentText().strip() or "Active",
            "salary": float(self.salary_spin.value()),
            "hire_date": self.hire_date.date().toString("yyyy-MM-dd"),
        }

    def _validate(self, values: Dict[str, Any]) -> Optional[str]:
        # 1. Employee Code
        if not values["emp_code"]:
            return "Employee Code is required."
        if not _CODE_RE.match(values["emp_code"]):
            return "Employee Code must be 2-32 alphanumeric characters (underscores and hyphens allowed)."

        # Duplicate check against DB
        current_id = self.employee_id()
        if database.employee_code_exists(values["emp_code"], exclude_id=current_id):
            return f"Employee Code '{values['emp_code']}' is already in use by another employee."

        # 2. Name
        if not values["name"]:
            return "Full Name is required."
        if len(values["name"]) > 100:
            return "Name cannot exceed 100 characters."

        # 3. Email
        if not values["email"]:
            return "Email Address is required."
        if len(values["email"]) > 120:
            return "Email address cannot exceed 120 characters."
        if not _EMAIL_RE.match(values["email"]):
            return "Please enter a valid email address (e.g. user@company.com)."

        # 4. Department
        if not values["department"]:
            return "Department is required."
        if len(values["department"]) > 60:
            return "Department name cannot exceed 60 characters."

        # 5. Position
        if not values["position"]:
            return "Job Position is required."
        if len(values["position"]) > 80:
            return "Position title cannot exceed 80 characters."

        # 6. Status
        if not values["status"]:
            return "Employment Status is required."
        if values["status"] not in EMPLOYEE_STATUSES:
            return f"Status must be one of: {', '.join(EMPLOYEE_STATUSES)}."

        # 7. Salary
        sal = values["salary"]
        if math.isnan(sal) or math.isinf(sal) or sal < 0:
            return "Salary must be a non-negative number."
        if sal > 100_000_000.0:
            return "Salary exceeds maximum allowed value ($100,000,000)."

        # 8. Hire Date
        qd = self.hire_date.date()
        if not qd.isValid() or qd < _MIN_DATE or qd > _MAX_DATE:
            return "Hire date must be a valid date between 1900-01-01 and 2100-12-31."

        return None

    def _on_save(self) -> None:
        values = self._collect_values()
        err = self._validate(values)
        if err:
            QMessageBox.warning(self, "Invalid Input", err, QMessageBox.Ok)
            self._focus_first_error(values, err)
            return
        self._validated_values = values
        self.accept()

    def _focus_first_error(self, values: Dict[str, Any], err_msg: str) -> None:
        if "Code" in err_msg:
            self.code_edit.setFocus()
            self.code_edit.selectAll()
        elif "Name" in err_msg:
            self.name_edit.setFocus()
            self.name_edit.selectAll()
        elif "Email" in err_msg:
            self.email_edit.setFocus()
            self.email_edit.selectAll()
        elif "Department" in err_msg:
            self.dept_combo.setFocus()
        elif "Position" in err_msg:
            self.position_edit.setFocus()
            self.position_edit.selectAll()
        elif "Status" in err_msg:
            self.status_combo.setFocus()
        elif "Salary" in err_msg:
            self.salary_spin.setFocus()
            self.salary_spin.selectAll()
        elif "Hire date" in err_msg:
            self.hire_date.setFocus()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_edit(self) -> bool:
        return self._is_edit

    def employee_id(self) -> Optional[int]:
        if self._employee is None:
            return None
        return self._employee.get("id")

    def get_values(self) -> Dict[str, Any]:
        return self._validated_values or self._collect_values()

from typing import Dict, Any, Optional

from PyQt5.QtCore import Qt, QRegExp
from PyQt5.QtGui import QRegExpValidator, QDoubleValidator, QIntValidator
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
from PyQt5.QtCore import QDate


DEPARTMENTS = [
    "Engineering",
    "Sales",
    "Marketing",
    "Human Resources",
    "Finance",
    "Operations",
    "Support",
    "Legal",
]


DEFAULT_POSITIONS = [
    "Developer",
    "Senior Developer",
    "Engineer",
    "Manager",
    "Account Executive",
    "Analyst",
    "HR Partner",
    "Designer",
    "Support Specialist",
    "Director",
]


class EmployeeFormDialog(QDialog):
    def __init__(
        self,
        parent=None,
        employee: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(parent)
        self._employee: Optional[Dict[str, Any]] = employee
        self._is_edit: bool = employee is not None

        self._build_ui()
        self._setup_validators()
        if self._is_edit:
            self._populate_from_employee()

        self.setWindowTitle(
            "Edit Employee - {}".format(employee.get("emp_code", ""))
            if self._is_edit
            else "Add Employee"
        )

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setFixedSize(480, 560)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("formCard")
        card.setStyleSheet(
            """
            QFrame#formCard {
                background-color: palette(window);
                border: 1px solid palette(mid);
                border-radius: 10px;
            }
            QLabel#formTitle {
                color: palette(window-text);
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#formSubtitle {
                color: palette(mid);
                font-size: 12px;
            }
            """
        )
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 24, 30, 24)
        card_layout.setSpacing(16)

        title = QLabel("Employee Details", card)
        title.setObjectName("formTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Edit the employee information below." if self._is_edit else "Fill in the new employee information.",
            card,
        )
        subtitle.setObjectName("formSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight)

        self.code_edit = QLineEdit(card)
        self.code_edit.setPlaceholderText("e.g. EMP001")

        self.name_edit = QLineEdit(card)
        self.name_edit.setPlaceholderText("Full name")

        self.email_edit = QLineEdit(card)
        self.email_edit.setPlaceholderText("name@company.com")

        self.dept_combo = QComboBox(card)
        self.dept_combo.setEditable(True)
        self.dept_combo.addItems(DEPARTMENTS)

        self.position_edit = QLineEdit(card)
        self.position_edit.setPlaceholderText("e.g. Senior Developer")

        self.salary_spin = QDoubleSpinBox(card)
        self.salary_spin.setRange(0.0, 10_000_000.0)
        self.salary_spin.setDecimals(2)
        self.salary_spin.setSingleStep(1000.0)
        self.salary_spin.setPrefix("$ ")

        self.hire_date = QDateEdit(card)
        self.hire_date.setCalendarPopup(True)
        self.hire_date.setDisplayFormat("yyyy-MM-dd")
        self.hire_date.setDate(QDate.currentDate())

        form.addRow("Employee Code:", self.code_edit)
        form.addRow("Name:", self.name_edit)
        form.addRow("Email:", self.email_edit)
        form.addRow("Department:", self.dept_combo)
        form.addRow("Position:", self.position_edit)
        form.addRow("Salary:", self.salary_spin)
        form.addRow("Hire Date:", self.hire_date)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        self.cancel_btn = QPushButton("Cancel", card)
        self.cancel_btn.setProperty("class", "secondaryButton")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Save", card)
        self.save_btn.setProperty("class", "primaryButton")
        self.save_btn.setCursor(Qt.PointingHandCursor)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._on_save)

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

        self.code_edit.setFocus()

    def _setup_validators(self) -> None:
        email_re = QRegExp(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
        self.email_edit.setValidator(QRegExpValidator(email_re, self))

        salary_validator = QDoubleValidator(0.0, 10_000_000.0, 2, self)
        salary_validator.setNotation(QDoubleValidator.StandardNotation)
        self.salary_spin.setLocale(self.locale())

        code_re = QRegExp(r"^[A-Za-z0-9_\-]{2,32}$")
        self.code_edit.setValidator(QRegExpValidator(code_re, self))

    def _populate_from_employee(self) -> None:
        assert self._employee is not None
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
        self.salary_spin.setValue(float(self._employee.get("salary") or 0.0))

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
            "salary": float(self.salary_spin.value()),
            "hire_date": self.hire_date.date().toString("yyyy-MM-dd"),
        }

    def _validate(self, values: Dict[str, Any]) -> Optional[str]:
        if not values["emp_code"]:
            return "Employee Code is required."
        if len(values["emp_code"]) < 2:
            return "Employee Code must be at least 2 characters."
        if not values["name"]:
            return "Name is required."
        if not values["email"]:
            return "Email is required."

        email_re = QRegExp(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
        if not email_re.exactMatch(values["email"]):
            return "Please enter a valid email address (e.g. user@company.com)."

        if not values["department"]:
            return "Department is required."
        if not values["position"]:
            return "Position is required."
        if values["salary"] < 0:
            return "Salary must be a non-negative number."
        if not values["hire_date"]:
            return "Hire Date is required."
        return None

    def _on_save(self) -> None:
        values = self._collect_values()
        err = self._validate(values)
        if err:
            QMessageBox.warning(self, "Invalid Input", err, QMessageBox.Ok)
            self._focus_first_error(values)
            return
        self.accept()

    def _focus_first_error(self, values: Dict[str, Any]) -> None:
        if not values["emp_code"]:
            self.code_edit.setFocus()
        elif not values["name"]:
            self.name_edit.setFocus()
        elif not values["email"]:
            self.email_edit.setFocus()
        elif not values["department"]:
            self.dept_combo.setFocus()
        elif not values["position"]:
            self.position_edit.setFocus()
        else:
            self.salary_spin.setFocus()

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
        return self._collect_values()

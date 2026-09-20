from typing import Dict, Any, Optional

from PyQt5.QtCore import Qt, QTimer, QSize
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QApplication,
    QSizePolicy,
)

from icon_utils import get_icon

STATUS_COLORS = {
    "Active": {"bg": "rgba(16, 185, 129, 0.12)", "border": "#10b981", "text": "#047857"},
    "On Leave": {"bg": "rgba(245, 158, 11, 0.12)", "border": "#f59e0b", "text": "#b45309"},
    "Inactive": {"bg": "rgba(107, 114, 128, 0.12)", "border": "#6b7280", "text": "#374151"},
    "Terminated": {"bg": "rgba(239, 68, 68, 0.12)", "border": "#ef4444", "text": "#b91c1c"},
    "Probation": {"bg": "rgba(59, 130, 246, 0.12)", "border": "#3b82f6", "text": "#1d4ed8"},
}


class EmployeeDetailsDialog(QDialog):
    """A clean, modern modal dialog displaying comprehensive employee details."""

    def __init__(self, employee: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._employee = dict(employee)
        self.edit_requested = False
        self._build_ui()

    def _build_ui(self) -> None:
        emp_code = str(self._employee.get("emp_code", ""))
        emp_name = str(self._employee.get("name", ""))
        status = str(self._employee.get("status", "Active"))

        self.setWindowTitle(f"Employee Profile - {emp_code}")
        self.setMinimumSize(520, 520)
        self.resize(540, 540)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("formCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(18)

        # Profile Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)
        header_layout.setAlignment(Qt.AlignCenter)

        name_label = QLabel(emp_name, card)
        name_label.setObjectName("formTitle")
        name_label.setAlignment(Qt.AlignCenter)

        pos_dept = " · ".join(
            filter(
                None,
                [
                    str(self._employee.get("position", "")),
                    str(self._employee.get("department", "")),
                ],
            )
        )
        sub_label = QLabel(pos_dept, card)
        sub_label.setObjectName("formSubtitle")
        sub_label.setAlignment(Qt.AlignCenter)

        badges_row = QHBoxLayout()
        badges_row.setSpacing(8)
        badges_row.setAlignment(Qt.AlignCenter)

        code_badge = QLabel(f"Code: {emp_code}", card)
        code_badge.setStyleSheet(
            "QLabel { background-color: #2563eb; color: #ffffff; font-weight: 700; "
            "font-size: 11px; padding: 4px 12px; border-radius: 10px; }"
        )

        st_cfg = STATUS_COLORS.get(status, STATUS_COLORS["Active"])
        status_badge = QLabel(f"● {status}", card)
        status_badge.setStyleSheet(
            f"QLabel {{ background-color: {st_cfg['bg']}; color: {st_cfg['text']}; "
            f"border: 1px solid {st_cfg['border']}; font-weight: 700; "
            "font-size: 11px; padding: 4px 12px; border-radius: 10px; }"
        )

        badges_row.addWidget(code_badge)
        badges_row.addWidget(status_badge)

        header_layout.addWidget(name_label, 0, Qt.AlignHCenter)
        header_layout.addWidget(sub_label, 0, Qt.AlignHCenter)
        header_layout.addLayout(badges_row)

        card_layout.addLayout(header_layout)

        # Divider
        divider = QFrame(card)
        divider.setProperty("class", "divider")
        divider.setFixedHeight(1)
        card_layout.addWidget(divider)

        # Details Grid
        grid_frame = QFrame(card)
        grid_frame.setStyleSheet("QFrame { background-color: transparent; }")
        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(10, 4, 10, 4)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)

        try:
            raw_salary = float(str(self._employee.get("salary") or 0.0).replace("$", "").replace(",", "").strip())
        except (ValueError, TypeError):
            raw_salary = 0.0
        annual_str = f"${raw_salary:,.2f}"
        monthly_str = f"${(raw_salary / 12.0):,.2f} / mo"

        items = [
            ("Employee ID:", str(self._employee.get("id", ""))),
            ("Employee Code:", emp_code),
            ("Full Legal Name:", emp_name),
            ("Email Address:", str(self._employee.get("email", ""))),
            ("Department:", str(self._employee.get("department", ""))),
            ("Job Position:", str(self._employee.get("position", ""))),
            ("Employment Status:", status),
            ("Annual Compensation:", f"{annual_str}  ({monthly_str})"),
            ("Hire Date:", str(self._employee.get("hire_date", ""))),
        ]

        for row_idx, (label_txt, value_txt) in enumerate(items):
            lbl = QLabel(label_txt)
            lbl.setProperty("class", "cardSubtitle")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            val = QLabel(value_txt)
            val.setProperty("class", "cardTitle")
            val.setStyleSheet("QLabel { font-size: 13px; font-weight: 500; }")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)

            grid.addWidget(lbl, row_idx, 0)
            grid.addWidget(val, row_idx, 1)

        card_layout.addWidget(grid_frame)
        card_layout.addStretch(1)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.copy_btn = QPushButton("Copy Profile", card)
        self.copy_btn.setIcon(get_icon("copy.svg"))
        self.copy_btn.setIconSize(QSize(18, 18))
        self.copy_btn.setProperty("class", "secondaryButton")
        self.copy_btn.setCursor(Qt.PointingHandCursor)
        self.copy_btn.setFixedHeight(36)
        self.copy_btn.clicked.connect(self._on_copy_summary)

        self.edit_btn = QPushButton("Edit Employee", card)
        self.edit_btn.setIcon(get_icon("edit_details.png"))
        self.edit_btn.setIconSize(QSize(18, 18))
        self.edit_btn.setProperty("class", "primaryButton")
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        self.edit_btn.setFixedHeight(36)
        self.edit_btn.clicked.connect(self._on_edit_clicked)

        self.close_btn = QPushButton("Close", card)
        self.close_btn.setProperty("class", "secondaryButton")
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFixedHeight(36)
        self.close_btn.clicked.connect(self.accept)

        btn_row.addWidget(self.copy_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.close_btn)

        card_layout.addLayout(btn_row)
        root.addWidget(card)

    def _on_copy_summary(self) -> None:
        summary = (
            f"Employee Code: {self._employee.get('emp_code')}\n"
            f"Name: {self._employee.get('name')}\n"
            f"Email: {self._employee.get('email')}\n"
            f"Department: {self._employee.get('department')}\n"
            f"Position: {self._employee.get('position')}\n"
            f"Status: {self._employee.get('status', 'Active')}\n"
            f"Salary: ${float(self._employee.get('salary') or 0.0):,.2f}\n"
            f"Hire Date: {self._employee.get('hire_date')}"
        )
        QApplication.clipboard().setText(summary)
        self.copy_btn.setText("Copied!")
        QTimer.singleShot(2000, lambda: self.copy_btn.setText("Copy Profile"))

    def _on_edit_clicked(self) -> None:
        self.edit_requested = True
        self.accept()

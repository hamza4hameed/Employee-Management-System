from typing import Dict, Any, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QFrame,
    QMessageBox,
    QSizePolicy,
)

import database
from icon_utils import get_icon
from logger import logger


class DepartmentFormDialog(QDialog):
    """Refined department create/edit modal with clear validation and tab order."""

    def __init__(
        self,
        parent=None,
        department: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(parent)
        self._dept: Optional[Dict[str, Any]] = department
        self._is_edit: bool = department is not None
        self._validated_values: Optional[Dict[str, Any]] = None

        self._build_ui()
        if self._is_edit:
            self._populate_from_department()

        self.setWindowTitle(
            f"Edit Department - {department.get('name', '')}"
            if self._is_edit
            else "Add New Department"
        )

    def _build_ui(self) -> None:
        self.setMinimumSize(440, 370)
        self.resize(460, 390)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("formCard")
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(16)

        title = QLabel("Department Details", card)
        title.setObjectName("formTitle")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Update the department name and description below."
            if self._is_edit
            else "Enter a unique department name to organize your organization's teams.",
            card,
        )
        subtitle.setObjectName("formSubtitle")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        req_name_lbl = QLabel("Department Name <span style='color:#ef4444; font-weight:700;'>*</span>")
        req_name_lbl.setTextFormat(Qt.RichText)

        self.name_edit = QLineEdit(card)
        self.name_edit.setFixedHeight(34)
        self.name_edit.setPlaceholderText("e.g. Artificial Intelligence & ML")
        self.name_edit.setMaxLength(60)
        self.name_edit.setToolTip("Unique department name (up to 60 characters)")

        self.desc_edit = QPlainTextEdit(card)
        self.desc_edit.setPlaceholderText("Brief description of this department's function...")
        self.desc_edit.setMaximumHeight(90)
        self.desc_edit.setToolTip("Optional summary (up to 255 characters)")

        form.addRow(req_name_lbl, self.name_edit)
        form.addRow("Description:", self.desc_edit)

        req_note = QLabel("<span style='color:#ef4444; font-weight:700;'>*</span> Required field", card)
        req_note.setProperty("class", "cardSubtitle")
        req_note.setStyleSheet("QLabel { font-size: 11px; color: #94a3b8; }")

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        self.cancel_btn = QPushButton("Cancel", card)
        self.cancel_btn.setProperty("class", "secondaryButton")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.clicked.connect(self.reject)

        self.save_btn = QPushButton("Save Department" if not self._is_edit else "Save Changes", card)
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

        # Tab order
        self.setTabOrder(self.name_edit, self.desc_edit)
        self.setTabOrder(self.desc_edit, self.save_btn)
        self.setTabOrder(self.save_btn, self.cancel_btn)

        self.name_edit.setFocus()

    def _populate_from_department(self) -> None:
        if self._dept is None:
            return
        self.name_edit.setText(str(self._dept.get("name", "")))
        self.desc_edit.setPlainText(str(self._dept.get("description", "")))

    def _collect_values(self) -> Dict[str, Any]:
        return {
            "name": self.name_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip()[:255],
        }

    def _validate(self, values: Dict[str, Any]) -> Optional[str]:
        name = values.get("name", "")
        if not name:
            return "Department Name is required."
        if len(name) < 2:
            return "Department Name must be at least 2 characters."
        if len(name) > 60:
            return "Department Name cannot exceed 60 characters."

        # Duplicate name check
        current_id = self.department_id()
        if database.department_name_exists(name, exclude_id=current_id):
            return f"A department named '{name}' already exists. Please choose a distinct name."

        return None

    def _on_save(self) -> None:
        values = self._collect_values()
        err = self._validate(values)
        if err:
            QMessageBox.warning(self, "Invalid Input", err, QMessageBox.Ok)
            self.name_edit.setFocus()
            self.name_edit.selectAll()
            return
        self._validated_values = values
        self.accept()

    def is_edit(self) -> bool:
        return self._is_edit

    def department_id(self) -> Optional[int]:
        if self._dept is None:
            return None
        return self._dept.get("id")

    def get_values(self) -> Dict[str, Any]:
        return self._validated_values or self._collect_values()

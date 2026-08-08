import sys
from typing import Optional, Dict, Any

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QMessageBox,
    QSizePolicy,
)

import database


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_user: Optional[Dict[str, Any]] = None
        self._build_ui()
        self._center_on_screen()

    def _build_ui(self) -> None:
        self.setWindowTitle("Employee Management System - Login")
        self.setFixedSize(460, 380)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(40, 30, 40, 30)
        root_layout.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("loginCard")
        card.setStyleSheet(
            """
            QFrame#loginCard {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
            }
            QLabel#titleLabel {
                color: #1f2937;
                font-size: 20px;
                font-weight: 600;
            }
            QLabel#subtitleLabel {
                color: #6b7280;
                font-size: 12px;
            }
            QLineEdit {
                padding: 10px 12px;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 13px;
                selection-background-color: #2563eb;
            }
            QLineEdit:focus {
                border: 1px solid #2563eb;
            }
            QPushButton#loginButton {
                background-color: #2563eb;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton#loginButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton#loginButton:pressed {
                background-color: #1e40af;
            }
            QPushButton#cancelButton {
                background-color: #f3f4f6;
                color: #1f2937;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 10px 16px;
                font-size: 13px;
            }
            QPushButton#cancelButton:hover {
                background-color: #e5e7eb;
            }
            QLabel {
                font-size: 13px;
                color: #1f2937;
            }
            """
        )
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 28, 32, 28)
        card_layout.setSpacing(18)

        title = QLabel("Employee Management System", card)
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Please sign in to continue", card)
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignCenter)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignRight)

        self.username_edit = QLineEdit(card)
        self.username_edit.setPlaceholderText("Enter your username")
        self.username_edit.setClearButtonEnabled(True)

        self.password_edit = QLineEdit(card)
        self.password_edit.setPlaceholderText("Enter your password")
        self.password_edit.setEchoMode(QLineEdit.Password)

        form.addRow("Username:", self.username_edit)
        form.addRow("Password:", self.password_edit)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        self.cancel_button = QPushButton("Cancel", card)
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.clicked.connect(self.reject)

        self.login_button = QPushButton("Login", card)
        self.login_button.setObjectName("loginButton")
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self._on_login_clicked)

        buttons_row.addWidget(self.cancel_button)
        buttons_row.addWidget(self.login_button)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(6)
        card_layout.addLayout(form)
        card_layout.addSpacing(6)
        card_layout.addLayout(buttons_row)
        card_layout.addStretch(1)

        root_layout.addWidget(card)

        self.username_edit.setFocus()

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = (geo.width() - self.width()) // 2
        y = (geo.height() - self.height()) // 2
        self.move(x, y)

    def _on_login_clicked(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()

        if not username or not password:
            QMessageBox.warning(
                self,
                "Missing Credentials",
                "Please enter both username and password.",
                QMessageBox.Ok,
            )
            if not username:
                self.username_edit.setFocus()
            else:
                self.password_edit.setFocus()
            return

        result = database.verify_login(username, password)
        if result is None:
            QMessageBox.warning(
                self,
                "Invalid Credentials",
                "The username or password you entered is incorrect.",
                QMessageBox.Ok,
            )
            self.password_edit.selectAll()
            self.password_edit.setFocus()
            return

        user_id, user_name, user_role = result
        self.current_user = {
            "id": user_id,
            "username": user_name,
            "role": user_role,
        }
        self.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    database.init_db()
    database.insert_default_admin()

    dialog = LoginDialog()
    result = dialog.exec_()

    if result == QDialog.Accepted:
        QMessageBox.information(
            None,
            "Login Successful",
            "Welcome, {}!\nRole: {}".format(
                dialog.current_user["username"], dialog.current_user["role"]
            ),
            QMessageBox.Ok,
        )
    else:
        QMessageBox.information(
            None,
            "Login Cancelled",
            "You cancelled the login. The application will now exit.",
            QMessageBox.Ok,
        )
        return 0

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())

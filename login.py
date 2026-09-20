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
from icon_utils import get_icon
from logger import logger


class FirstRunPasswordDialog(QDialog):
    """Dialog shown on first launch to set the administrator password."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._password_set = False
        self._build_ui()
        self._center_on_screen()

    def _build_ui(self) -> None:
        self.setWindowTitle("Administrator Password Setup")
        self.setFixedSize(480, 380)
        self.setModal(True)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("loginCard")
        card.setStyleSheet(
            """
            QFrame#loginCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            QLabel#titleLabel {
                color: #0f172a;
                font-size: 17px;
                font-weight: 700;
            }
            QLabel#subtitleLabel {
                color: #64748b;
                font-size: 12px;
            }
            QLabel#errorLabel {
                color: #b91c1c;
                background-color: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QLabel.fieldLabel {
                color: #334155;
                font-size: 13px;
                font-weight: 600;
            }
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-size: 13px;
                selection-background-color: #2563eb;
                background-color: #ffffff;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 1.5px solid #2563eb;
            }
            QPushButton#setPasswordButton {
                background-color: #2563eb;
                color: white;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 9px 18px;
                font-size: 13px;
                font-weight: 600;
                min-width: 90px;
            }
            QPushButton#setPasswordButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton#setPasswordButton:pressed {
                background-color: #1e40af;
            }
            QPushButton#setPasswordButton:disabled {
                background-color: #93c5fd;
                border-color: #93c5fd;
                color: #ffffff;
            }
            """
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 28, 32, 28)
        card_layout.setSpacing(14)

        # Title
        title = QLabel("First-Time Setup Required", card)
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel(
            "Create an administrator password to secure your Employee Management System.\n\n"
            "This password will be required for all future logins.",
            card
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        # Error label
        self.error_label = QLabel("", card)
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        card_layout.addWidget(self.error_label)

        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        pass_label = QLabel("New Password:", card)
        pass_label.setProperty("class", "fieldLabel")

        self.password_edit = QLineEdit(card)
        self.password_edit.setFixedHeight(36)
        self.password_edit.setPlaceholderText("Minimum 8 characters")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setClearButtonEnabled(True)
        self.password_edit.textChanged.connect(self._clear_error)

        confirm_label = QLabel("Confirm Password:", card)
        confirm_label.setProperty("class", "fieldLabel")

        self.confirm_edit = QLineEdit(card)
        self.confirm_edit.setFixedHeight(36)
        self.confirm_edit.setPlaceholderText("Re-enter password")
        self.confirm_edit.setEchoMode(QLineEdit.Password)
        self.confirm_edit.setClearButtonEnabled(True)
        self.confirm_edit.textChanged.connect(self._clear_error)
        self.confirm_edit.returnPressed.connect(self._on_set_password)

        form.addRow(pass_label, self.password_edit)
        form.addRow(confirm_label, self.confirm_edit)

        card_layout.addLayout(form)

        # Requirements note
        req_note = QLabel(
            "• Minimum 8 characters\n"
            "• Cannot be a common password",
            card
        )
        req_note.setStyleSheet("QLabel { color: #64748b; font-size: 11px; }")
        card_layout.addWidget(req_note)

        # Button
        self.set_password_btn = QPushButton("Set Password", card)
        self.set_password_btn.setObjectName("setPasswordButton")
        self.set_password_btn.setFixedHeight(36)
        self.set_password_btn.setCursor(Qt.PointingHandCursor)
        self.set_password_btn.setDefault(True)
        self.set_password_btn.clicked.connect(self._on_set_password)

        card_layout.addStretch(1)
        card_layout.addWidget(self.set_password_btn, 0, Qt.AlignCenter)

        root_layout.addWidget(card)

        self.setTabOrder(self.password_edit, self.confirm_edit)
        self.setTabOrder(self.confirm_edit, self.set_password_btn)
        self.password_edit.setFocus()

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def _clear_error(self) -> None:
        if self.error_label.isVisible():
            self.error_label.setVisible(False)

    def _on_set_password(self) -> None:
        password = self.password_edit.text()
        confirm = self.confirm_edit.text()

        # Validation
        if not password:
            self._show_error("Please enter a password.")
            self.password_edit.setFocus()
            return

        if len(password) < 8:
            self._show_error("Password must be at least 8 characters long.")
            self.password_edit.setFocus()
            self.password_edit.selectAll()
            return

        if password != confirm:
            self._show_error("Passwords do not match. Please try again.")
            self.confirm_edit.setFocus()
            self.confirm_edit.selectAll()
            return

        # Check for common weak passwords
        common_passwords = ["password", "password123", "admin123", "12345678", "qwerty123"]
        if password.lower() in common_passwords:
            self._show_error("Please choose a stronger password. Avoid common passwords.")
            self.password_edit.setFocus()
            self.password_edit.selectAll()
            return

        # Set password
        self.set_password_btn.setEnabled(False)
        self.set_password_btn.setText("Setting password...")
        QApplication.processEvents()

        try:
            success = database.set_admin_password(password)
            if success:
                self._password_set = True
                QMessageBox.information(
                    self,
                    "Password Set Successfully",
                    "Your administrator password has been created.\n\n"
                    "You can now sign in with your new password.",
                    QMessageBox.Ok,
                )
                self.accept()
            else:
                self._show_error("Failed to set password. Please try again.")
                self.set_password_btn.setEnabled(True)
                self.set_password_btn.setText("Set Password")
        except Exception as exc:
            logger.error("Error setting admin password: %s", exc, exc_info=True)
            self._show_error("An error occurred. Please try again.")
            self.set_password_btn.setEnabled(True)
            self.set_password_btn.setText("Set Password")

    def password_set(self) -> bool:
        return self._password_set


class LoginDialog(QDialog):
    """Refined, accessible login dialog with clear validation and loading states."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_user: Optional[Dict[str, Any]] = None
        self._build_ui()
        self._center_on_screen()

    def _build_ui(self) -> None:
        self.setWindowTitle("Sign In - Employee Management System")
        self.setFixedSize(450, 420)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setAlignment(Qt.AlignCenter)

        card = QFrame(self)
        card.setObjectName("loginCard")
        card.setStyleSheet(
            """
            QFrame#loginCard {
                background-color: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            QLabel#badgeLabel {
                background-color: #2563eb;
                color: #ffffff;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#titleLabel {
                color: #0f172a;
                font-size: 19px;
                font-weight: 700;
            }
            QLabel#subtitleLabel {
                color: #64748b;
                font-size: 12px;
            }
            QLabel#errorLabel {
                color: #b91c1c;
                background-color: #fef2f2;
                border: 1px solid #fecaca;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 500;
            }
            QLabel.fieldLabel {
                color: #334155;
                font-size: 13px;
                font-weight: 600;
            }
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                font-size: 13px;
                selection-background-color: #2563eb;
                background-color: #ffffff;
                color: #0f172a;
            }
            QLineEdit:focus {
                border: 1.5px solid #2563eb;
            }
            QPushButton#loginButton {
                background-color: #2563eb;
                color: white;
                border: 1px solid #1d4ed8;
                border-radius: 6px;
                padding: 9px 18px;
                font-size: 13px;
                font-weight: 600;
                min-width: 90px;
            }
            QPushButton#loginButton:hover {
                background-color: #1d4ed8;
            }
            QPushButton#loginButton:pressed {
                background-color: #1e40af;
            }
            QPushButton#loginButton:disabled {
                background-color: #93c5fd;
                border-color: #93c5fd;
                color: #ffffff;
            }
            QPushButton#cancelButton {
                background-color: #ffffff;
                color: #334155;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 9px 18px;
                font-size: 13px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton#cancelButton:hover {
                background-color: #f8fafc;
                border-color: #94a3b8;
            }
            """
        )
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 28, 32, 28)
        card_layout.setSpacing(14)

        # App badge / icon
        badge_row = QHBoxLayout()
        badge_row.setAlignment(Qt.AlignCenter)
        badge = QLabel("EMS", card)
        badge.setObjectName("badgeLabel")
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignCenter)
        badge_row.addWidget(badge)
        card_layout.addLayout(badge_row)

        title = QLabel("Employee Management System", card)
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("Sign in with your credentials to access the workspace", card)
        subtitle.setObjectName("subtitleLabel")
        subtitle.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        # Inline error notification label
        self.error_label = QLabel("", card)
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        card_layout.addWidget(self.error_label)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        user_label = QLabel("Username:", card)
        user_label.setProperty("class", "fieldLabel")

        self.username_edit = QLineEdit(card)
        self.username_edit.setFixedHeight(36)
        self.username_edit.setPlaceholderText("Enter username (e.g. admin)")
        self.username_edit.setClearButtonEnabled(True)
        self.username_edit.textChanged.connect(self._clear_error)
        self.username_edit.returnPressed.connect(lambda: self.password_edit.setFocus())

        pass_label = QLabel("Password:", card)
        pass_label.setProperty("class", "fieldLabel")

        self.password_edit = QLineEdit(card)
        self.password_edit.setFixedHeight(36)
        self.password_edit.setPlaceholderText("Enter password")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.textChanged.connect(self._clear_error)
        self.password_edit.returnPressed.connect(self._on_login_clicked)

        form.addRow(user_label, self.username_edit)
        form.addRow(pass_label, self.password_edit)

        card_layout.addSpacing(2)
        card_layout.addLayout(form)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(10)

        self.cancel_button = QPushButton("Cancel", card)
        self.cancel_button.setObjectName("cancelButton")
        self.cancel_button.setFixedHeight(36)
        self.cancel_button.setCursor(Qt.PointingHandCursor)
        self.cancel_button.clicked.connect(self.reject)

        self.login_button = QPushButton("Sign In", card)
        self.login_button.setIcon(get_icon("user.png"))
        self.login_button.setObjectName("loginButton")
        self.login_button.setFixedHeight(36)
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self._on_login_clicked)

        buttons_row.addStretch(1)
        buttons_row.addWidget(self.cancel_button)
        buttons_row.addWidget(self.login_button)

        card_layout.addSpacing(6)
        card_layout.addLayout(buttons_row)
        card_layout.addStretch(1)

        root_layout.addWidget(card)

        # Tab order
        self.setTabOrder(self.username_edit, self.password_edit)
        self.setTabOrder(self.password_edit, self.login_button)
        self.setTabOrder(self.login_button, self.cancel_button)

        self.username_edit.setFocus()

    def _center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def _clear_error(self) -> None:
        if self.error_label.isVisible():
            self.error_label.setVisible(False)

    def _on_login_clicked(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()

        if not username or not password:
            self._show_error("Please enter both username and password.")
            if not username:
                self.username_edit.setFocus()
            else:
                self.password_edit.setFocus()
            return

        # Loading / disabled state
        self._clear_error()
        self.login_button.setEnabled(False)
        self.login_button.setText("Signing in...")
        QApplication.processEvents()

        try:
            result = database.verify_login(username, password)
        except Exception as exc:
            logger.error("Database error verifying login for user '%s': %s", username, exc, exc_info=True)
            self.login_button.setEnabled(True)
            self.login_button.setText("Sign In")
            self._show_error("Could not connect to the database. Please try again or contact your administrator.")
            return

        if result is None:
            self.login_button.setEnabled(True)
            self.login_button.setText("Sign In")
            self._show_error("The username or password you entered is incorrect.")
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

    # Check if first-run password setup is required
    if database.admin_requires_password_setup():
        setup_dialog = FirstRunPasswordDialog()
        result = setup_dialog.exec_()
        if result != QDialog.Accepted or not setup_dialog.password_set():
            # User cancelled or failed - exit application
            QMessageBox.information(
                None,
                "Setup Required",
                "You must create an administrator password to use this application.\n\n"
                "The application will now exit.",
                QMessageBox.Ok,
            )
            return 1

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


if __name__ == "__main__":
    sys.exit(main())

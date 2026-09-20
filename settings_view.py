import datetime
import os
from typing import Dict, Any, Optional

from PyQt5.QtCore import Qt, pyqtSignal, QSize
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QMessageBox,
    QFileDialog,
    QScrollArea,
    QSizePolicy,
    QDialog,
    QFormLayout,
)

import database
import csv_utils
from icon_utils import get_icon
from logger import logger, get_log_dir


class ChangePasswordDialog(QDialog):
    """Dialog for changing the current user's password."""

    def __init__(self, user_id: int, username: str, parent=None):
        super().__init__(parent)
        self._user_id = user_id
        self._username = username
        self._build_ui()
        self._center_on_screen()

    def _build_ui(self) -> None:
        self.setWindowTitle("Change Password")
        self.setFixedSize(420, 300)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(12)

        # Title
        title = QLabel(f"Change Password for {self._username}")
        title.setStyleSheet("font-size: 15px; font-weight: 700;")
        root.addWidget(title)

        # Form
        form = QFormLayout()
        form.setSpacing(10)

        self.current_edit = QLineEdit()
        self.current_edit.setEchoMode(QLineEdit.Password)
        self.current_edit.setPlaceholderText("Enter current password")
        self.current_edit.setFixedHeight(32)

        self.new_edit = QLineEdit()
        self.new_edit.setEchoMode(QLineEdit.Password)
        self.new_edit.setPlaceholderText("Minimum 8 characters")
        self.new_edit.setFixedHeight(32)

        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.Password)
        self.confirm_edit.setPlaceholderText("Re-enter new password")
        self.confirm_edit.setFixedHeight(32)

        form.addRow("Current Password:", self.current_edit)
        form.addRow("New Password:", self.new_edit)
        form.addRow("Confirm Password:", self.confirm_edit)

        root.addLayout(form)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #b91c1c; font-size: 12px;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        root.addWidget(self.error_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setProperty("class", "secondaryButton")
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setFixedHeight(32)
        cancel_btn.clicked.connect(self.reject)

        self.change_btn = QPushButton("Change Password")
        self.change_btn.setProperty("class", "primaryButton")
        self.change_btn.setCursor(Qt.PointingHandCursor)
        self.change_btn.setFixedHeight(32)
        self.change_btn.clicked.connect(self._on_change)

        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(self.change_btn)
        root.addLayout(btn_row)

        self.setTabOrder(self.current_edit, self.new_edit)
        self.setTabOrder(self.new_edit, self.confirm_edit)
        self.setTabOrder(self.confirm_edit, self.change_btn)
        self.current_edit.setFocus()

    def _center_on_screen(self) -> None:
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.y() + (geo.height() - self.height()) // 2
        self.move(x, y)

    def _show_error(self, msg: str) -> None:
        self.error_label.setText(msg)
        self.error_label.setVisible(True)

    def _on_change(self) -> None:
        current = self.current_edit.text()
        new_pwd = self.new_edit.text()
        confirm = self.confirm_edit.text()

        if not current:
            self._show_error("Please enter your current password.")
            self.current_edit.setFocus()
            return

        if len(new_pwd) < 8:
            self._show_error("New password must be at least 8 characters.")
            self.new_edit.setFocus()
            return

        if new_pwd != confirm:
            self._show_error("New passwords do not match.")
            self.confirm_edit.setFocus()
            return

        # Check for weak passwords
        common = ["password", "password123", "admin123", "12345678", "qwerty123"]
        if new_pwd.lower() in common:
            self._show_error("Please choose a stronger password.")
            self.new_edit.setFocus()
            return

        from PyQt5.QtWidgets import QApplication

        self.change_btn.setEnabled(False)
        self.change_btn.setText("Changing...")
        QApplication.processEvents()

        success, msg = database.change_user_password(self._user_id, current, new_pwd)
        
        if success:
            QMessageBox.information(self, "Success", "Your password has been changed successfully.", QMessageBox.Ok)
            self.accept()
        else:
            self._show_error(msg)
            self.change_btn.setEnabled(True)
            self.change_btn.setText("Change Password")


class SettingsView(QWidget):
    data_changed = pyqtSignal()
    status_message = pyqtSignal(str, int)  # message, timeout_ms

    def __init__(self, parent=None, lazy: bool = False, user: Optional[Dict[str, Any]] = None):
        super().__init__(parent)
        self._current_user: Dict[str, Any] = user or {}
        self._build_ui()
        if not lazy:
            self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 20)
        container_layout.setSpacing(18)

        # ── Card 1: Database Backup & Recovery ──
        backup_card = QFrame(container)
        backup_card.setProperty("class", "card")
        backup_layout = QVBoxLayout(backup_card)
        backup_layout.setContentsMargins(24, 22, 24, 22)
        backup_layout.setSpacing(14)

        b_title = QLabel("Database Backup & Safe Recovery", backup_card)
        b_title.setProperty("class", "cardTitle")
        b_sub = QLabel(
            "Create standalone snapshot backups of your entire SQLite database or safely restore previous backups. "
            "All backup and restore operations run locally with automated integrity verification.",
            backup_card,
        )
        b_sub.setProperty("class", "cardSubtitle")
        b_sub.setWordWrap(True)

        backup_layout.addWidget(b_title)
        backup_layout.addWidget(b_sub)
        backup_layout.addSpacing(6)

        b_btn_row = QHBoxLayout()
        b_btn_row.setSpacing(12)

        self.backup_btn = QPushButton("Create Database Backup", backup_card)
        self.backup_btn.setIcon(get_icon("create_backup.png"))
        self.backup_btn.setIconSize(QSize(18, 18))
        self.backup_btn.setProperty("class", "primaryButton")
        self.backup_btn.setCursor(Qt.PointingHandCursor)
        self.backup_btn.setFixedHeight(34)
        self.backup_btn.clicked.connect(self._on_create_backup)

        self.restore_btn = QPushButton("Restore from Backup...", backup_card)
        self.restore_btn.setIcon(get_icon("restore_backup.png"))
        self.restore_btn.setIconSize(QSize(18, 18))
        self.restore_btn.setProperty("class", "secondaryButton")
        self.restore_btn.setCursor(Qt.PointingHandCursor)
        self.restore_btn.setFixedHeight(34)
        self.restore_btn.clicked.connect(self._on_restore_backup)

        b_btn_row.addWidget(self.backup_btn)
        b_btn_row.addWidget(self.restore_btn)
        b_btn_row.addStretch(1)

        backup_layout.addLayout(b_btn_row)
        container_layout.addWidget(backup_card)

        # ── Card 1.5: User Account ──
        user_card = QFrame(container)
        user_card.setProperty("class", "card")
        user_layout = QVBoxLayout(user_card)
        user_layout.setContentsMargins(24, 22, 24, 22)
        user_layout.setSpacing(14)

        u_title = QLabel("User Account", user_card)
        u_title.setProperty("class", "cardTitle")
        
        username = self._current_user.get("username", "Unknown")
        role = self._current_user.get("role", "user").title()
        
        u_sub = QLabel(
            f"Logged in as: {username} ({role})",
            user_card,
        )
        u_sub.setProperty("class", "cardSubtitle")
        u_sub.setWordWrap(True)

        user_layout.addWidget(u_title)
        user_layout.addWidget(u_sub)
        user_layout.addSpacing(6)

        u_btn_row = QHBoxLayout()
        u_btn_row.setSpacing(12)

        self.change_pwd_btn = QPushButton("Change Password...", user_card)
        self.change_pwd_btn.setIcon(get_icon("settings.png"))
        self.change_pwd_btn.setIconSize(QSize(18, 18))
        self.change_pwd_btn.setProperty("class", "secondaryButton")
        self.change_pwd_btn.setCursor(Qt.PointingHandCursor)
        self.change_pwd_btn.setFixedHeight(34)
        self.change_pwd_btn.clicked.connect(self._on_change_password)

        u_btn_row.addWidget(self.change_pwd_btn)
        u_btn_row.addStretch(1)

        user_layout.addLayout(u_btn_row)
        container_layout.addWidget(user_card)

        # ── Card 2: CSV Data Tools ──
        csv_card = QFrame(container)
        csv_card.setProperty("class", "card")
        csv_layout = QVBoxLayout(csv_card)
        csv_layout.setContentsMargins(24, 22, 24, 22)
        csv_layout.setSpacing(14)

        csv_title = QLabel("CSV Bulk Data Operations", csv_card)
        csv_title.setProperty("class", "cardTitle")
        csv_sub = QLabel(
            "Export all employee records to a spreadsheet-compatible CSV file or import records in bulk with formula protection and duplicate validation.",
            csv_card,
        )
        csv_sub.setProperty("class", "cardSubtitle")
        csv_sub.setWordWrap(True)

        csv_layout.addWidget(csv_title)
        csv_layout.addWidget(csv_sub)
        csv_layout.addSpacing(6)

        csv_btn_row = QHBoxLayout()
        csv_btn_row.setSpacing(12)

        self.csv_export_btn = QPushButton("Export Employees to CSV", csv_card)
        self.csv_export_btn.setIcon(get_icon("export_csv.png"))
        self.csv_export_btn.setIconSize(QSize(18, 18))
        self.csv_export_btn.setProperty("class", "secondaryButton")
        self.csv_export_btn.setCursor(Qt.PointingHandCursor)
        self.csv_export_btn.setFixedHeight(34)
        self.csv_export_btn.clicked.connect(self._on_csv_export)

        self.csv_import_btn = QPushButton("Import Employees from CSV", csv_card)
        self.csv_import_btn.setIcon(get_icon("import_csv.png"))
        self.csv_import_btn.setIconSize(QSize(18, 18))
        self.csv_import_btn.setProperty("class", "secondaryButton")
        self.csv_import_btn.setCursor(Qt.PointingHandCursor)
        self.csv_import_btn.setFixedHeight(34)
        self.csv_import_btn.clicked.connect(self._on_csv_import)

        csv_btn_row.addWidget(self.csv_export_btn)
        csv_btn_row.addWidget(self.csv_import_btn)
        csv_btn_row.addStretch(1)

        csv_layout.addLayout(csv_btn_row)
        container_layout.addWidget(csv_card)

        # ── Card 3: Live System Health & Database Stats ──
        stats_card = QFrame(container)
        stats_card.setProperty("class", "card")
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(24, 22, 24, 22)
        stats_layout.setSpacing(14)

        s_title = QLabel("System & Database Health", stats_card)
        s_title.setProperty("class", "cardTitle")
        stats_layout.addWidget(s_title)

        self.stats_grid_frame = QFrame(stats_card)
        self.stats_grid_frame.setStyleSheet("QFrame { background-color: transparent; }")
        self.stats_grid = QGridLayout(self.stats_grid_frame)
        self.stats_grid.setContentsMargins(0, 8, 0, 0)
        self.stats_grid.setHorizontalSpacing(24)
        self.stats_grid.setVerticalSpacing(10)

        stats_layout.addWidget(self.stats_grid_frame)
        container_layout.addWidget(stats_card)

        # ── Card 4: Danger Zone / Delete Complete Data ──
        danger_card = QFrame(container)
        danger_card.setProperty("class", "card")
        danger_layout = QVBoxLayout(danger_card)
        danger_layout.setContentsMargins(24, 22, 24, 22)
        danger_layout.setSpacing(14)

        d_title = QLabel("Danger Zone: Delete Complete Data", danger_card)
        d_title.setProperty("class", "cardTitle")
        d_title.setStyleSheet("QLabel { color: #dc2626; font-weight: 700; font-size: 14px; }")

        d_sub = QLabel(
            "Permanently erase all employee records and reset department data. "
            "This action is irreversible and restores the database to an initial clean state. "
            "You will be prompted to create an optional safety backup before proceeding.",
            danger_card,
        )
        d_sub.setProperty("class", "cardSubtitle")
        d_sub.setWordWrap(True)

        danger_layout.addWidget(d_title)
        danger_layout.addWidget(d_sub)
        danger_layout.addSpacing(6)

        d_btn_row = QHBoxLayout()
        d_btn_row.setSpacing(12)

        self.delete_data_btn = QPushButton("Delete Complete Data", danger_card)
        self.delete_data_btn.setIcon(get_icon("delete_db.svg"))
        self.delete_data_btn.setIconSize(QSize(18, 18))
        self.delete_data_btn.setProperty("class", "dangerButton")
        self.delete_data_btn.setCursor(Qt.PointingHandCursor)
        self.delete_data_btn.setFixedHeight(34)
        self.delete_data_btn.clicked.connect(self._on_delete_complete_data)

        d_btn_row.addWidget(self.delete_data_btn)
        d_btn_row.addStretch(1)

        danger_layout.addLayout(d_btn_row)
        container_layout.addWidget(danger_card)

        # ── Card 5: Privacy & Data Storage Info ──
        privacy_card = QFrame(container)
        privacy_card.setProperty("class", "card")
        privacy_layout = QVBoxLayout(privacy_card)
        privacy_layout.setContentsMargins(24, 22, 24, 22)
        privacy_layout.setSpacing(10)

        priv_title = QLabel("Data Privacy & Storage", privacy_card)
        priv_title.setProperty("class", "cardTitle")

        from app_meta import DATA_NOTICE, APP_NAME
        priv_body = QLabel(
            f"{DATA_NOTICE}\n\n"
            f"{APP_NAME} does not connect to the internet, does not send telemetry, "
            f"and does not share data with third parties.",
            privacy_card,
        )
        priv_body.setProperty("class", "cardSubtitle")
        priv_body.setWordWrap(True)

        privacy_layout.addWidget(priv_title)
        privacy_layout.addWidget(priv_body)
        container_layout.addWidget(privacy_card)

        container_layout.addStretch(1)
        scroll.setWidget(container)
        root.addWidget(scroll)
        self._apply_role_restrictions()

    def _apply_role_restrictions(self) -> None:
        """Hide or disable destructive controls for non-admin users."""
        is_admin = self._current_user.get("role", "user").lower() == "admin"
        # Danger zone: only admins may delete all data or restore backups
        self.delete_data_btn.setEnabled(is_admin)
        self.restore_btn.setEnabled(is_admin)
        if not is_admin:
            self.delete_data_btn.setToolTip("Admin access required.")
            self.restore_btn.setToolTip("Admin access required.")

    def refresh(self) -> None:
        """Fetch live database statistics and update the health grid."""
        stats = database.get_database_stats()

        # Clear existing grid widgets
        while self.stats_grid.count():
            item = self.stats_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        items = [
            ("Database Storage:", stats.get("db_path", "N/A")),
            ("File Size on Disk:", stats.get("size_str", "0 KB")),
            ("Registered Employees:", f"{stats.get('employee_count', 0):,} records"),
            ("Active Departments:", f"{stats.get('department_count', 0):,} departments"),
            ("User Accounts:", f"{stats.get('user_count', 0):,} users"),
            ("SQLite Engine Version:", str(stats.get("sqlite_version", "N/A"))),
            ("Application Logs Location:", os.path.join(get_log_dir(), "app.log")),
        ]

        for row_idx, (label_txt, val_txt) in enumerate(items):
            lbl = QLabel(label_txt)
            lbl.setProperty("class", "cardSubtitle")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            val = QLabel(val_txt)
            val.setProperty("class", "cardTitle")
            val.setStyleSheet("QLabel { font-size: 12px; font-weight: 500; }")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)

            self.stats_grid.addWidget(lbl, row_idx, 0)
            self.stats_grid.addWidget(val, row_idx, 1)

    # ------------------------------------------------------------------
    # Backup Handler
    # ------------------------------------------------------------------
    def _on_create_backup(self) -> None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"employee_backup_{ts}.db"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Database Backup",
            default_name,
            "SQLite Database (*.db);;All Files (*)",
        )
        if not path:
            return

        if not path.lower().endswith(".db"):
            path += ".db"

        try:
            database.create_backup(path)
            size_bytes = os.path.getsize(path)
            size_str = f"{size_bytes / (1024 * 1024):.2f} MB" if size_bytes >= 1024 * 1024 else f"{size_bytes / 1024:.1f} KB"

            QMessageBox.information(
                self,
                "Backup Successful",
                f"Database backup was created successfully!\n\n"
                f"• Saved To: {path}\n"
                f"• Size: {size_str}",
                QMessageBox.Ok,
            )
            self.status_message.emit(f"Backup created: {os.path.basename(path)}", 4000)
        except Exception as exc:
            logger.error("Failed to create database backup: %s", exc, exc_info=True)
            QMessageBox.critical(
                self,
                "Backup Failed",
                f"Could not create database backup:\n{exc}",
                QMessageBox.Ok,
            )

    # ------------------------------------------------------------------
    # Safe Restore Handler
    # ------------------------------------------------------------------
    def _on_restore_backup(self) -> None:
        if self._current_user.get("role", "user").lower() != "admin":
            QMessageBox.warning(self, "Access Denied", "Only administrators can restore a backup.", QMessageBox.Ok)
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Database Backup to Restore",
            "",
            "SQLite Databases (*.db *.sqlite *.sqlite3);;All Files (*)",
        )
        if not path:
            return

        # 1. Pre-restore validation
        is_valid, val_msg, meta = database.validate_backup(path)
        if not is_valid:
            QMessageBox.critical(
                self,
                "Invalid Backup File",
                f"The selected file cannot be restored:\n\n{val_msg}",
                QMessageBox.Ok,
            )
            return

        # 2. Strong warning confirmation
        emp_count = meta.get("employee_count", 0)
        dept_count = meta.get("department_count", 0)
        mod_time = meta.get("modified_time", "Unknown")

        confirm = QMessageBox.warning(
            self,
            "Confirm Database Restore",
            f"<b>WARNING: Restoring a backup will completely replace all current employee and department records.</b><br><br>"
            f"<b>Backup Summary:</b><br>"
            f"• File: {os.path.basename(path)}<br>"
            f"• Modified: {mod_time}<br>"
            f"• Employees in Backup: {emp_count:,}<br>"
            f"• Departments in Backup: {dept_count:,}<br><br>"
            f"<i>An automated safety snapshot of your current database will be saved before restore.</i><br><br>"
            f"Are you sure you want to proceed with restoring this backup?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        # 3. Perform atomic restore
        ok, res_msg = database.restore_backup(path, create_pre_restore_snapshot=True)
        if not ok:
            QMessageBox.critical(
                self,
                "Restore Failed",
                f"Could not restore database:\n\n{res_msg}",
                QMessageBox.Ok,
            )
            return

        QMessageBox.information(
            self,
            "Restore Completed",
            res_msg,
            QMessageBox.Ok,
        )

        self.refresh()
        self.data_changed.emit()
        self.status_message.emit("Database restored successfully.", 5000)

    # ------------------------------------------------------------------
    # CSV Bulk Export / Import
    # ------------------------------------------------------------------
    def _on_csv_export(self) -> None:
        try:
            rows = database.get_all_employees()
        except Exception as exc:
            logger.error("Could not fetch employees for CSV export: %s", exc)
            QMessageBox.critical(self, "Export Failed", "Database error fetching employee records.", QMessageBox.Ok)
            return

        default_name = f"employees_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export All Employees to CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"

        try:
            written = csv_utils.export_table_to_csv(rows, path)
            self.status_message.emit(f"Exported {written:,} rows to {os.path.basename(path)}", 4000)
            QMessageBox.information(
                self,
                "CSV Export Completed",
                f"Successfully exported {written:,} employee records to:\n{path}",
                QMessageBox.Ok,
            )
        except PermissionError as exc:
            logger.error("CSV Export permission error: %s", exc)
            QMessageBox.critical(
                self,
                "Export Failed - File in Use",
                f"Could not write to '{os.path.basename(path)}'. Please make sure the file is not currently open in another program.",
                QMessageBox.Ok,
            )
        except Exception as exc:
            logger.error("CSV Export error: %s", exc, exc_info=True)
            QMessageBox.critical(self, "Export Failed", f"Could not export CSV file:\n{exc}", QMessageBox.Ok)

    def _on_csv_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Employees from CSV",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        try:
            inserted, skipped, errors = csv_utils.import_csv_to_db(path, skip_duplicates=True)
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "Import Failed", f"File not found:\n{path}", QMessageBox.Ok)
            return
        except csv_utils.CsvImportError as exc:
            detail = "\n".join(exc.errors[:10])
            extra = "" if len(exc.errors) <= 10 else f"\n... and {len(exc.errors) - 10} more."
            QMessageBox.critical(self, "Import Failed", f"{exc}\n\n{detail + extra}".strip(), QMessageBox.Ok)
            return
        except Exception as exc:
            logger.error("CSV Import error: %s", exc, exc_info=True)
            QMessageBox.critical(self, "Import Failed", f"Could not process CSV file:\n{exc}", QMessageBox.Ok)
            return

        self.refresh()
        self.data_changed.emit()

        base = f"Imported {inserted:,} new employee{'' if inserted == 1 else 's'}. Skipped duplicates/errors: {skipped:,}."
        self.status_message.emit(base, 5000)

        if not errors:
            QMessageBox.information(self, "Import Successful", base, QMessageBox.Ok)
            return

        err_block = "\n".join(errors[:15])
        if len(errors) > 15:
            err_block += f"\n... and {len(errors) - 15} more issue(s)."
        summary = f"{base}\n\nDetails:\n{err_block}"

        QMessageBox.warning(self, "Import Completed with Warnings", summary, QMessageBox.Ok)

    # ------------------------------------------------------------------
    # Change Password Handler
    # ------------------------------------------------------------------
    def _on_change_password(self) -> None:
        """Open the change password dialog."""
        user_id = self._current_user.get("id")
        username = self._current_user.get("username", "User")
        
        if not user_id:
            QMessageBox.warning(self, "Error", "Could not identify current user.", QMessageBox.Ok)
            return
        
        dlg = ChangePasswordDialog(user_id, username, self)
        if dlg.exec_() == dlg.Accepted:
            self.status_message.emit("Password changed successfully.", 3000)

    # ------------------------------------------------------------------
    # Complete Data Deletion & Wipe Handler
    # ------------------------------------------------------------------
    def _on_delete_complete_data(self) -> None:
        if self._current_user.get("role", "user").lower() != "admin":
            QMessageBox.warning(self, "Access Denied", "Only administrators can delete all data.", QMessageBox.Ok)
            return
        stats = database.get_database_stats()
        emp_count = stats.get("employee_count", 0)
        dept_count = stats.get("department_count", 0)

        # Step 1: Warning & Ask for Backup
        backup_prompt = QMessageBox(self)
        backup_prompt.setWindowTitle("Delete Complete Data - Backup Safety Check")
        backup_prompt.setIcon(QMessageBox.Warning)
        backup_prompt.setText("You are about to permanently delete all employee records from the database.")
        backup_prompt.setInformativeText(
            f"Current database records:\n"
            f"  • {emp_count:,} Employees\n"
            f"  • {dept_count} Departments\n\n"
            f"Would you like to create a database backup before proceeding with deletion?"
        )
        btn_backup = backup_prompt.addButton("Yes, Create Backup First", QMessageBox.AcceptRole)
        btn_no_backup = backup_prompt.addButton("No, Proceed Without Backup", QMessageBox.DestructiveRole)
        btn_cancel = backup_prompt.addButton("Cancel", QMessageBox.RejectRole)
        backup_prompt.setDefaultButton(btn_backup)

        backup_prompt.exec_()
        clicked = backup_prompt.clickedButton()

        if clicked == btn_cancel or clicked is None:
            return

        if clicked == btn_backup:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"employee_pre_delete_backup_{ts}.db"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Safety Backup Before Deletion",
                default_name,
                "SQLite Database (*.db);;All Files (*)",
            )
            if not path:
                return
            if not path.lower().endswith(".db"):
                path += ".db"

            ok = database.create_backup(path)
            if not ok:
                QMessageBox.critical(
                    self,
                    "Backup Failed",
                    "Could not create the safety backup. Data deletion has been cancelled for your safety.",
                    QMessageBox.Ok,
                )
                return
            QMessageBox.information(
                self,
                "Backup Created",
                f"Safety backup saved successfully to:\n{path}\n\nNow proceeding to final deletion confirmation.",
                QMessageBox.Ok,
            )

        # Step 2: Final Confirmation
        final_confirm = QMessageBox.question(
            self,
            "FINAL CONFIRMATION - Delete All Data",
            f"Are you ABSOLUTELY SURE you want to delete all {emp_count:,} employee records?\n\n"
            f"This action CANNOT be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if final_confirm != QMessageBox.Yes:
            return

        # Perform deletion
        success, msg, counts = database.clear_all_data(preserve_users=True, reset_default_depts=True)
        if success:
            QMessageBox.information(
                self,
                "Data Deleted",
                f"Complete data wipe successful!\n\n"
                f"• {counts['employees']:,} employee records were permanently removed.\n"
                f"• Departments were reset to standard defaults.\n"
                f"• Database storage was vacuumed and optimized.",
                QMessageBox.Ok,
            )
            self.refresh()
            self.data_changed.emit()
            self.status_message.emit("All employee records were deleted from the database.", 4000)
        else:
            logger.error("Data deletion failed: %s", msg)
            QMessageBox.critical(
                self,
                "Error Deleting Data",
                "An unexpected error occurred while deleting data. Please check the application log for details.",
                QMessageBox.Ok,
            )

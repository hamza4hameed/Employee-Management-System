import os
import sys
import traceback
from typing import Dict, Any, Optional

# Set env var hints only. DO NOT call matplotlib.use() here — doing so before
# QApplication is fully alive (and on the real "windows" platform) can segfault
# on Python 3.13 + PyQt5. Matplotlib backend pinning is deferred until the
# first real canvas build inside AnalyticsView._ensure_canvas(), at which
# point QApplication is 100% alive and rendering to a real platform.
os.environ.setdefault("MPLBACKEND", "Qt5Agg")
os.environ.setdefault("QT_QPA_PLATFORM", "windows")
os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QStackedWidget,
    QButtonGroup,
    QSizePolicy,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
    QComboBox,
    QDialog,
)

import database
import app_meta
from login import LoginDialog
from employee_view import EmployeeView
from analytics_view import AnalyticsView
from department_view import DepartmentView
from settings_view import SettingsView
from icon_utils import get_icon, set_icon_color
from logger import logger


LIGHT_QSS = """
QWidget {
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Tahoma, sans-serif;
    color: #1f2937;
}

QMainWindow, QWidget#rootWidget {
    background-color: #f1f5f9;
}

QFrame#sidebar {
    background-color: #0f274a;
    border: none;
}

QLabel#sidebarTitle {
    color: #ffffff;
    font-size: 16px;
    font-weight: 700;
    padding: 16px 20px 4px 20px;
    letter-spacing: 0.3px;
}

QLabel#sidebarSubtitle {
    color: #93c5fd;
    font-size: 11px;
    font-weight: 500;
    padding: 0 20px 14px 20px;
}

QPushButton.navButton {
    background-color: transparent;
    color: #cbd5e1;
    border: none;
    border-left: 4px solid transparent;
    text-align: left;
    padding: 11px 20px;
    font-size: 13px;
    font-weight: 500;
    border-radius: 0px;
}

QPushButton.navButton:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #ffffff;
}

QPushButton.navButton:checked {
    background-color: #1d4ed8;
    color: #ffffff;
    border-left: 4px solid #60a5fa;
    font-weight: 600;
}

QFrame#headerBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}

QLabel#pageTitle {
    color: #0f172a;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.2px;
}

QLabel#userNameLabel {
    color: #0f172a;
    font-size: 13px;
    font-weight: 600;
}

QLabel#userRoleLabel {
    color: #64748b;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#themeToggle, QPushButton#globalRefreshBtn {
    background-color: #f8fafc;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#themeToggle:hover, QPushButton#globalRefreshBtn:hover {
    background-color: #f1f5f9;
    border-color: #94a3b8;
    color: #0f172a;
}

QPushButton#themeToggle:pressed, QPushButton#globalRefreshBtn:pressed {
    background-color: #e2e8f0;
}

QFrame#pageContainer {
    background-color: #f1f5f9;
}

QFrame.card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
}

QLabel.cardTitle {
    color: #0f172a;
    font-size: 15px;
    font-weight: 700;
}

QLabel.cardSubtitle {
    color: #64748b;
    font-size: 12px;
    line-height: 1.4;
}

QPushButton.primaryButton, QPushButton[class="primaryButton"] {
    background-color: #2563eb;
    color: #ffffff !important;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 600;
    outline: none;
}

QPushButton.primaryButton:hover, QPushButton[class="primaryButton"]:hover {
    background-color: #1d4ed8;
    border-color: #1e40af;
}

QPushButton.primaryButton:pressed, QPushButton[class="primaryButton"]:pressed {
    background-color: #1e40af;
}

QPushButton.primaryButton:disabled, QPushButton[class="primaryButton"]:disabled {
    background-color: #cbd5e1;
    border-color: #cbd5e1;
    color: #94a3b8;
}

QPushButton.secondaryButton, QPushButton[class="secondaryButton"] {
    background-color: #ffffff;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 500;
    outline: none;
}

QPushButton.secondaryButton:hover, QPushButton[class="secondaryButton"]:hover {
    background-color: #f8fafc;
    border-color: #94a3b8;
    color: #0f172a;
}

QPushButton.secondaryButton:pressed, QPushButton[class="secondaryButton"]:pressed {
    background-color: #f1f5f9;
}

QPushButton.secondaryButton:disabled, QPushButton[class="secondaryButton"]:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QPushButton.dangerButton, QPushButton[class="dangerButton"] {
    background-color: #dc2626;
    color: #ffffff !important;
    border: 1px solid #b91c1c;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 600;
    outline: none;
}

QPushButton.dangerButton:hover, QPushButton[class="dangerButton"]:hover {
    background-color: #b91c1c;
    border-color: #991b1b;
}

QPushButton.dangerButton:pressed, QPushButton[class="dangerButton"]:pressed {
    background-color: #991b1b;
}

QPushButton.dangerButton:disabled, QPushButton[class="dangerButton"]:disabled {
    background-color: #fca5a5;
    border-color: #fca5a5;
    color: #ffffff;
}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {
    border: 1.5px solid #2563eb;
    background-color: #ffffff;
}

QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDateEdit:disabled {
    background-color: #f8fafc;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #0f172a;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    border: 1px solid #cbd5e1;
    padding: 4px;
    outline: none;
}

QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    color: #0f172a;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    gridline-color: #f1f5f9;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
    outline: none;
}

QTableWidget::item {
    padding: 6px 10px;
    border: none;
}

QTableWidget::item:hover {
    background-color: #f1f5f9;
}

QTableWidget::item:selected {
    background-color: #dbeafe;
    color: #1e3a8a;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid #e2e8f0;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.2px;
}

QTableCornerButton::section {
    background-color: #f8fafc;
    border: none;
    border-bottom: 1px solid #e2e8f0;
}

QScrollBar:vertical {
    background-color: #f1f5f9;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    border-radius: 4px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #f1f5f9;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    border-radius: 4px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QMessageBox {
    background-color: #ffffff;
}

QMessageBox QLabel {
    color: #0f172a;
    font-size: 13px;
    line-height: 1.4;
}

QMessageBox QPushButton {
    min-width: 84px;
    padding: 7px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
}

QMenu {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 4px 0;
}

QMenu::item {
    background-color: transparent;
    color: #0f172a;
    padding: 7px 24px 7px 16px;
    font-size: 13px;
}

QMenu::item:selected {
    background-color: #eff6ff;
    color: #1d4ed8;
}

QMenu::item:disabled {
    color: #94a3b8;
}

QMenu::separator {
    height: 1px;
    background-color: #e2e8f0;
    margin: 4px 8px;
}

QStatusBar {
    background-color: #ffffff;
    color: #64748b;
    border-top: 1px solid #e2e8f0;
    font-size: 12px;
    padding: 3px 8px;
}

QDialog {
    background-color: #f1f5f9;
}

QProgressDialog {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
}

QProgressDialog QLabel {
    color: #0f172a;
    font-size: 13px;
    background: transparent;
}

QProgressDialog QPushButton {
    background-color: #ffffff;
    color: #334155;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
    min-width: 70px;
}

QProgressDialog QPushButton:hover {
    background-color: #f8fafc;
    border-color: #94a3b8;
    color: #0f172a;
}

QProgressDialog QPushButton:pressed {
    background-color: #f1f5f9;
}

QProgressBar {
    background-color: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    text-align: center;
    color: #0f172a;
    font-size: 11px;
    font-weight: 600;
    min-height: 16px;
    max-height: 16px;
}

QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 3px;
}

QFrame#formCard, QFrame#loginCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}

QLabel#formTitle {
    color: #0f172a;
    font-size: 18px;
    font-weight: 700;
}

QLabel#formSubtitle {
    color: #64748b;
    font-size: 12px;
    line-height: 1.4;
}

QFrame.divider {
    background-color: #e2e8f0;
    min-height: 1px;
    max-height: 1px;
    border: none;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QToolTip {
    background-color: #0f172a;
    color: #ffffff;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 11px;
}
"""


DARK_QSS = """
QWidget {
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Tahoma, sans-serif;
    color: #e2e8f0;
}

QMainWindow, QWidget#rootWidget {
    background-color: #0a0f1d;
}

QDialog {
    background-color: #0a0f1d;
}

QProgressDialog {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
}

QProgressDialog QLabel {
    color: #f8fafc;
    font-size: 13px;
    background: transparent;
}

QProgressDialog QPushButton {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
    min-width: 70px;
}

QProgressDialog QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
    color: #ffffff;
}

QProgressDialog QPushButton:pressed {
    background-color: #0f172a;
}

QProgressBar {
    background-color: #0a0f1d;
    border: 1px solid #1f2937;
    border-radius: 4px;
    text-align: center;
    color: #f8fafc;
    font-size: 11px;
    font-weight: 600;
    min-height: 16px;
    max-height: 16px;
}

QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 3px;
}

QFrame#formCard, QFrame#loginCard {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
}

QLabel#formTitle {
    color: #f8fafc;
    font-size: 18px;
    font-weight: 700;
}

QLabel#formSubtitle {
    color: #94a3b8;
    font-size: 12px;
    line-height: 1.4;
}

QFrame#sidebar {
    background-color: #0b1120;
    border: none;
    border-right: 1px solid #1e293b;
}

QLabel#sidebarTitle {
    color: #f8fafc;
    font-size: 16px;
    font-weight: 700;
    padding: 16px 20px 4px 20px;
    letter-spacing: 0.3px;
}

QLabel#sidebarSubtitle {
    color: #60a5fa;
    font-size: 11px;
    font-weight: 500;
    padding: 0 20px 14px 20px;
}

QPushButton.navButton {
    background-color: transparent;
    color: #94a3b8;
    border: none;
    border-left: 4px solid transparent;
    text-align: left;
    padding: 11px 20px;
    font-size: 13px;
    font-weight: 500;
    border-radius: 0px;
}

QPushButton.navButton:hover {
    background-color: #1e293b;
    color: #f8fafc;
}

QPushButton.navButton:checked {
    background-color: #1e293b;
    color: #ffffff;
    border-left: 4px solid #3b82f6;
    font-weight: 600;
}

QFrame#headerBar {
    background-color: #111827;
    border-bottom: 1px solid #1f2937;
}

QLabel#pageTitle {
    color: #f8fafc;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.2px;
}

QLabel#userNameLabel {
    color: #f8fafc;
    font-size: 13px;
    font-weight: 600;
}

QLabel#userRoleLabel {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#themeToggle, QPushButton#globalRefreshBtn {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 600;
}

QPushButton#themeToggle:hover, QPushButton#globalRefreshBtn:hover {
    background-color: #334155;
    border-color: #475569;
    color: #ffffff;
}

QPushButton#themeToggle:pressed, QPushButton#globalRefreshBtn:pressed {
    background-color: #0f172a;
}

QFrame#pageContainer {
    background-color: #0a0f1d;
}

QFrame.card {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
}

QLabel.cardTitle {
    color: #f8fafc;
    font-size: 15px;
    font-weight: 700;
}

QLabel.cardSubtitle {
    color: #94a3b8;
    font-size: 12px;
    line-height: 1.4;
}

QPushButton.primaryButton, QPushButton[class="primaryButton"] {
    background-color: #2563eb;
    color: #ffffff !important;
    border: 1px solid #1d4ed8;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 600;
    outline: none;
}

QPushButton.primaryButton:hover, QPushButton[class="primaryButton"]:hover {
    background-color: #1d4ed8;
    border-color: #1e40af;
}

QPushButton.primaryButton:pressed, QPushButton[class="primaryButton"]:pressed {
    background-color: #1e40af;
}

QPushButton.primaryButton:disabled, QPushButton[class="primaryButton"]:disabled {
    background-color: #334155;
    border-color: #334155;
    color: #64748b;
}

QPushButton.secondaryButton, QPushButton[class="secondaryButton"] {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 7px 14px;
    font-size: 13px;
    font-weight: 500;
    outline: none;
}

QPushButton.secondaryButton:hover, QPushButton[class="secondaryButton"]:hover {
    background-color: #334155;
    border-color: #475569;
    color: #ffffff;
}

QPushButton.secondaryButton:pressed, QPushButton[class="secondaryButton"]:pressed {
    background-color: #0f172a;
}

QPushButton.secondaryButton:disabled, QPushButton[class="secondaryButton"]:disabled {
    background-color: #111827;
    color: #475569;
    border-color: #1f2937;
}

QPushButton.dangerButton, QPushButton[class="dangerButton"] {
    background-color: #dc2626;
    color: #ffffff !important;
    border: 1px solid #b91c1c;
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 600;
    outline: none;
}

QPushButton.dangerButton:hover, QPushButton[class="dangerButton"]:hover {
    background-color: #b91c1c;
    border-color: #991b1b;
}

QPushButton.dangerButton:pressed, QPushButton[class="dangerButton"]:pressed {
    background-color: #991b1b;
}

QPushButton.dangerButton:disabled, QPushButton[class="dangerButton"]:disabled {
    background-color: #7f1d1d;
    border-color: #7f1d1d;
    color: #fca5a5;
}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
    background-color: #0a0f1d;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {
    border: 1.5px solid #3b82f6;
    background-color: #0a0f1d;
}

QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDateEdit:disabled {
    background-color: #0f172a;
    color: #475569;
    border-color: #1e293b;
}

QComboBox::drop-down {
    border: none;
    width: 22px;
}

QComboBox QAbstractItemView {
    background-color: #111827;
    color: #f8fafc;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    border: 1px solid #334155;
    padding: 4px;
    outline: none;
}

QTableWidget {
    background-color: #111827;
    alternate-background-color: #0b0f19;
    color: #f3f4f6;
    border: 1px solid #1f2937;
    border-radius: 6px;
    gridline-color: #1e293b;
    selection-background-color: #1e3a8a;
    selection-color: #dbeafe;
    outline: none;
}

QTableWidget::item {
    padding: 6px 10px;
    border: none;
}

QTableWidget::item:hover {
    background-color: #1e293b;
}

QTableWidget::item:selected {
    background-color: #1e3a8a;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #1e293b;
    color: #cbd5e1;
    padding: 8px 12px;
    border: none;
    border-bottom: 1px solid #334155;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.2px;
}

QTableCornerButton::section {
    background-color: #1e293b;
    border: none;
    border-bottom: 1px solid #334155;
}

QScrollBar:vertical {
    background-color: #0a0f1d;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #334155;
    border-radius: 4px;
    min-height: 28px;
}

QScrollBar::handle:vertical:hover {
    background-color: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #0a0f1d;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #334155;
    border-radius: 4px;
    min-width: 28px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #475569;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

QMessageBox {
    background-color: #111827;
}

QMessageBox QLabel {
    color: #e2e8f0;
    font-size: 13px;
    line-height: 1.4;
}

QMessageBox QPushButton {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid #334155;
    min-width: 84px;
    padding: 7px 16px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
}

QMessageBox QPushButton:hover {
    background-color: #334155;
}

QMessageBox QPushButton:default {
    background-color: #2563eb;
    color: #ffffff;
    border: 1px solid #1d4ed8;
}

QMenu {
    background-color: #111827;
    color: #e2e8f0;
    border: 1px solid #1f2937;
    border-radius: 6px;
    padding: 4px 0;
}

QMenu::item {
    background-color: transparent;
    color: #e2e8f0;
    padding: 7px 24px 7px 16px;
    font-size: 13px;
}

QMenu::item:selected {
    background-color: #2563eb;
    color: #ffffff;
}

QMenu::item:disabled {
    color: #475569;
}

QMenu::separator {
    height: 1px;
    background-color: #1f2937;
    margin: 4px 8px;
}

QScrollArea {
    background-color: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background-color: transparent;
}

QStatusBar {
    background-color: #111827;
    color: #94a3b8;
    border-top: 1px solid #1f2937;
    font-size: 12px;
    padding: 3px 8px;
}

QFrame.divider {
    background-color: #1f2937;
    min-height: 1px;
    max-height: 1px;
    border: none;
}

QToolTip {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 11px;
}
"""


THEMES = {
    "light": LIGHT_QSS,
    "dark": DARK_QSS,
}


class ReportsView(QWidget):
    """Reports and live analytics center with live dataset reporting and CSV export."""

    def __init__(self, parent=None, lazy: bool = False):
        super().__init__(parent)
        self._table_data: list = []
        self._table_headers: list = []
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

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Reports & Summary Center")
        title.setProperty("class", "cardTitle")
        sub = QLabel("Select a report profile to compute live analytics from active company data.")
        sub.setProperty("class", "cardSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(sub)
        header_row.addLayout(title_col, 1)

        self.report_combo = QComboBox()
        self.report_combo.setFixedHeight(34)
        self.report_combo.setMinimumWidth(260)
        self.report_combo.addItems([
            "Payroll & Compensation by Department",
            "Department Headcount & Allocation",
            "Employment Standing Overview",
        ])
        self.report_combo.currentIndexChanged.connect(self.refresh)

        self.export_btn = QPushButton("Export Report (CSV)")
        self.export_btn.setIcon(get_icon("export_csv.png"))
        self.export_btn.setIconSize(QSize(18, 18))
        self.export_btn.setProperty("class", "primaryButton")
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.setFixedHeight(34)
        self.export_btn.clicked.connect(self._on_export_csv)

        header_row.addWidget(self.report_combo)
        header_row.addWidget(self.export_btn)
        layout.addLayout(header_row)

        div = QFrame()
        div.setProperty("class", "divider")
        div.setFixedHeight(1)
        layout.addWidget(div)

        self.table = QTableWidget(0, 0)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        root.addWidget(card)

    def refresh(self) -> None:
        try:
            employees = database.get_all_employees()
        except Exception:
            employees = []

        idx = self.report_combo.currentIndex()
        if idx == 0:
            self._render_payroll_report(employees)
        elif idx == 1:
            self._render_headcount_report(employees)
        else:
            self._render_status_report(employees)

    def _render_payroll_report(self, employees: list) -> None:
        self._table_headers = ["Department", "Employees", "Total Payroll", "Average Salary", "Min Salary", "Max Salary"]
        dept_salaries = {}
        for emp in employees:
            dept = str(emp.get("department") or "Unassigned")
            try:
                sal = float(emp.get("salary") or 0.0)
            except Exception:
                sal = 0.0
            dept_salaries.setdefault(dept, []).append(sal)

        rows = []
        for dept, sals in sorted(dept_salaries.items(), key=lambda kv: kv[0].lower()):
            total = sum(sals)
            avg = total / len(sals) if sals else 0.0
            min_sal = min(sals) if sals else 0.0
            max_sal = max(sals) if sals else 0.0
            rows.append([
                dept,
                str(len(sals)),
                f"${total:,.2f}",
                f"${avg:,.2f}",
                f"${min_sal:,.2f}",
                f"${max_sal:,.2f}",
            ])

        self._populate_table(self._table_headers, rows, right_align_cols=[1, 2, 3, 4, 5])

    def _render_headcount_report(self, employees: list) -> None:
        self._table_headers = ["Department", "Headcount", "Share (%)", "Active", "On Leave", "Inactive"]
        total_emp = len(employees)
        dept_data = {}
        for emp in employees:
            dept = str(emp.get("department") or "Unassigned")
            status = str(emp.get("status") or "Active").lower()
            if dept not in dept_data:
                dept_data[dept] = {"total": 0, "active": 0, "leave": 0, "inactive": 0}
            dept_data[dept]["total"] += 1
            if "leave" in status:
                dept_data[dept]["leave"] += 1
            elif "inactive" in status or "terminated" in status:
                dept_data[dept]["inactive"] += 1
            else:
                dept_data[dept]["active"] += 1

        rows = []
        for dept, counts in sorted(dept_data.items(), key=lambda kv: -kv[1]["total"]):
            n = counts["total"]
            pct = f"{(n / total_emp * 100):.1f}%" if total_emp else "0.0%"
            rows.append([
                dept,
                str(n),
                pct,
                str(counts["active"]),
                str(counts["leave"]),
                str(counts["inactive"]),
            ])

        self._populate_table(self._table_headers, rows, right_align_cols=[1, 2, 3, 4, 5])

    def _render_status_report(self, employees: list) -> None:
        self._table_headers = ["Employment Standing", "Headcount", "Share (%)", "Total Payroll"]
        total_emp = len(employees)
        status_data = {}
        for emp in employees:
            status = str(emp.get("status") or "Active")
            try:
                sal = float(emp.get("salary") or 0.0)
            except Exception:
                sal = 0.0
            if status not in status_data:
                status_data[status] = {"count": 0, "payroll": 0.0}
            status_data[status]["count"] += 1
            status_data[status]["payroll"] += sal

        rows = []
        for status, d in sorted(status_data.items(), key=lambda kv: -kv[1]["count"]):
            c = d["count"]
            pct = f"{(c / total_emp * 100):.1f}%" if total_emp else "0.0%"
            rows.append([
                status,
                str(c),
                pct,
                f"${d['payroll']:,.2f}",
            ])

        self._populate_table(self._table_headers, rows, right_align_cols=[1, 2, 3])

    def _populate_table(self, headers: list, rows: list, right_align_cols: list) -> None:
        self._table_data = rows
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(rows))
        for r_idx, row in enumerate(rows):
            for c_idx, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                align = Qt.AlignVCenter | (Qt.AlignRight if c_idx in right_align_cols else Qt.AlignLeft)
                item.setTextAlignment(align)
                self.table.setItem(r_idx, c_idx, item)

    def _on_export_csv(self) -> None:
        import csv
        import datetime
        from PyQt5.QtWidgets import QFileDialog, QMessageBox

        if not self._table_data:
            QMessageBox.information(self, "No Data", "There is no report data to export.", QMessageBox.Ok)
            return

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_title = self.report_combo.currentText().split()[0].lower()
        default_name = f"report_{report_title}_{ts}.csv"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Report to CSV",
            default_name,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"

        try:
            def _clean(val):
                s = str(val) if val is not None else ""
                if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
                    return "'" + s
                return s

            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(self._table_headers)
                writer.writerows([[_clean(c) for c in r] for r in self._table_data])
            QMessageBox.information(
                self,
                "Export Completed",
                f"Report successfully saved to:\n{path}",
                QMessageBox.Ok,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Could not write CSV file. Please make sure the file is not currently open in another program.",
                QMessageBox.Ok,
            )


class AboutDialog(QDialog):
    """Displays application name, version, data-privacy notice, and developer info."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {app_meta.APP_NAME}")
        self.setFixedSize(440, 320)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(12)

        title = QLabel(app_meta.APP_NAME)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 17px; font-weight: 700;")

        version = QLabel(f"Version {app_meta.APP_VERSION}")
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("font-size: 12px; color: #64748b;")

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("border: none; border-top: 1px solid #e2e8f0; min-height:1px; max-height:1px;")

        desc = QLabel(app_meta.APP_DESCRIPTION)
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 12px;")

        privacy = QLabel(app_meta.DATA_NOTICE)
        privacy.setAlignment(Qt.AlignCenter)
        privacy.setWordWrap(True)
        privacy.setStyleSheet(
            "font-size: 11px; color: #475569; background: #f8fafc; border: 1px solid #e2e8f0; "
            "border-radius: 6px; padding: 8px;"
        )

        close_btn = QPushButton("Close")
        close_btn.setProperty("class", "secondaryButton")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedHeight(34)
        close_btn.clicked.connect(self.accept)

        root.addWidget(title)
        root.addWidget(version)
        root.addWidget(divider)
        root.addWidget(desc)
        root.addWidget(privacy)
        root.addStretch(1)
        root.addWidget(close_btn, 0, Qt.AlignRight)


class MainWindow(QMainWindow):
    def __init__(self, user: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.current_user: Dict[str, Any] = user or {"id": 0, "username": "guest", "role": "user"}
        self.is_logged_out: bool = False
        self._theme: str = "light"
        self._nav_group: Optional[QButtonGroup] = None
        self._page_index: Dict[str, int] = {}
        self.employee_view: Any = None
        self.analytics_view: Any = None
        self._dirty_views: Dict[str, bool] = {
            "dashboard": True,
            "employees": True,
            "departments": True,
            "reports": True,
            "settings": True,
        }

        try:
            self._ui_ready = False
            platform = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
            if platform not in ("minimal", "offscreen"):
                self.setStyleSheet(THEMES.get(self._theme, THEMES["light"]))
            print("[main_window] step 1 _build_ui() ...")
            set_icon_color("#334155")  # light theme initial colour
            self._build_ui()
            self._ui_ready = True
            print("[main_window] step 2 _apply_theme(light) ...")
            self._apply_theme(self._theme)
            print("[main_window] init OK; current_user =", self.current_user.get("username"))
        except Exception as exc:
            tb = traceback.format_exc()
            print("[main_window] EXCEPTION during __init__:")
            print(tb)
            sys.stdout.flush()
            try:
                from PyQt5.QtWidgets import QMessageBox

                QMessageBox.critical(
                    None,
                    "Main Window Failed to Start",
                    "An error occurred while building the main window.\n\n"
                    "Error: {}\n\n{}".format(str(exc), tb),
                )
            except Exception:
                pass
            raise

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    def _apply_theme(self, theme: str) -> None:
        if not getattr(self, "_ui_ready", False):
            return
        platform = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
        if platform in ("minimal", "offscreen"):
            print("[main_window._apply_theme] skipping QSS apply; running on sandbox platform:", platform)
            sys.stdout.flush()
            self._theme = theme
            return

        # Update icon colour *before* rebuilding any icons
        set_icon_color("#ffffff" if theme == "dark" else "#334155")

        qss = THEMES.get(theme, THEMES["light"])
        self.setUpdatesEnabled(False)
        try:
            self.setStyleSheet(qss)
            app = QApplication.instance()
            if app is not None:
                app.setStyleSheet(qss)
        except Exception as exc:
            print("[main_window._apply_theme] setStyleSheet warning (non-fatal):", exc)
            sys.stdout.flush()
        finally:
            self.setUpdatesEnabled(True)
        self._theme = theme

        # Re-apply sidebar nav icons with the new colour
        if hasattr(self, "_nav_buttons"):
            nav_icon_map = {
                "dashboard": "dashboard",
                "employees": "employees",
                "departments": "departments",
                "reports": "reports",
                "settings": "settings",
            }
            for key, btn in self._nav_buttons.items():
                icon_name = nav_icon_map.get(key)
                if icon_name:
                    btn.setIcon(get_icon(icon_name))

        if hasattr(self, "theme_toggle"):
            if theme == "light":
                self.theme_toggle.setText("Dark Mode")
                self.theme_toggle.setIcon(get_icon("dark_theme"))
            else:
                self.theme_toggle.setText("Light Mode")
                self.theme_toggle.setIcon(get_icon("light_theme"))
            self.theme_toggle.setIconSize(QSize(20, 20))

        if hasattr(self, "global_refresh_btn"):
            self.global_refresh_btn.setIcon(get_icon("refresh"))

        if hasattr(self, "analytics_view") and self.analytics_view is not None:
            try:
                self.analytics_view.set_theme(theme)
            except Exception:
                pass
    def _toggle_theme(self) -> None:
        self._apply_theme("dark" if self._theme == "light" else "light")

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        print("[main_window._build_ui] 1/5 setWindowTitle / resize / rootWidget ...")
        sys.stdout.flush()
        self.setWindowTitle(f"{app_meta.APP_NAME} v{app_meta.APP_VERSION}")
        self.resize(1180, 760)
        self.setMinimumSize(QSize(980, 620))

        root = QWidget(self)
        root.setObjectName("rootWidget")
        self.setCentralWidget(root)

        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Resizable sidebar + content area via QSplitter
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setObjectName("mainSplitter")
        self._splitter.setHandleWidth(4)
        self._splitter.setChildrenCollapsible(False)

        print("[main_window._build_ui] 2/5 _build_sidebar() ...")
        sys.stdout.flush()
        sidebar = self._build_sidebar()
        # Remove the fixed width so QSplitter can resize it
        sidebar.setMinimumWidth(180)
        sidebar.setMaximumWidth(400)
        sidebar.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        print("[main_window._build_ui] 3/5 _build_content_area() ...")
        sys.stdout.flush()
        content = self._build_content_area()
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._splitter.addWidget(sidebar)
        self._splitter.addWidget(content)
        self._splitter.setStretchFactor(0, 0)  # sidebar: don't stretch
        self._splitter.setStretchFactor(1, 1)  # content: stretch
        self._splitter.setSizes([240, 940])     # initial split

        # Style the splitter handle to be subtle
        self._splitter.setStyleSheet(
            "QSplitter::handle { background-color: transparent; }"
            "QSplitter::handle:hover { background-color: rgba(59,130,246,0.35); }"
        )

        root_layout.addWidget(self._splitter)

        print("[main_window._build_ui] 4/5 statusBar() ...")
        sys.stdout.flush()
        status = self.statusBar()
        status.showMessage(
            "Logged in as {} \u00b7 Role: {}".format(
                self.current_user.get("username", "guest"),
                self.current_user.get("role", "user"),
            )
        )
        print("[main_window._build_ui] 5/5 done; navigating to dashboard ...")
        sys.stdout.flush()
        self._navigate_to("dashboard")

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        # Width is now managed by the QSplitter; do not use setFixedWidth()

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 16, 0, 16)
        layout.setSpacing(0)

        title = QLabel("Employee MS")
        title.setObjectName("sidebarTitle")
        subtitle = QLabel("Management Dashboard")
        subtitle.setObjectName("sidebarSubtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("QFrame { border: none; border-top: 1px solid rgba(255,255,255,0.1); min-height: 1px; max-height: 1px; }")
        layout.addSpacing(8)
        layout.addWidget(divider)
        layout.addSpacing(12)

        self._nav_buttons: Dict[str, QPushButton] = {}
        nav_items = [
            ("dashboard", "Dashboard", "dashboard.png"),
            ("employees", "Employees", "employees.png"),
            ("departments", "Departments", "departments.png"),
            ("reports", "Reports", "reports.png"),
            ("settings", "Settings", "settings.png"),
        ]
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        for idx, (key, label, icon_name) in enumerate(nav_items):
            btn = QPushButton(label)
            btn.setIcon(get_icon(icon_name))
            btn.setIconSize(QSize(20, 20))
            btn.setProperty("class", "navButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(40)
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda _=False, k=key: self._navigate_to(k))
            self._nav_group.addButton(btn)
            self._nav_buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch(1)

        about_btn = QPushButton("About")
        about_btn.setIcon(get_icon("about.png"))
        about_btn.setIconSize(QSize(18, 18))
        about_btn.setProperty("class", "navButton")
        about_btn.setCursor(Qt.PointingHandCursor)
        about_btn.clicked.connect(self._on_about)
        layout.addWidget(about_btn)

        logout = QPushButton("Log Out")
        logout.setIcon(get_icon("logout.png"))
        logout.setIconSize(QSize(20, 20))
        logout.setProperty("class", "navButton")
        logout.setCursor(Qt.PointingHandCursor)
        logout.clicked.connect(self._on_logout)
        layout.addWidget(logout)

        return sidebar

    def _build_content_area(self) -> QFrame:
        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        content_layout.addWidget(self._build_header(), 0)
        content_layout.addWidget(self._build_page_stack(), 1)
        return content

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("headerBar")
        header.setFixedHeight(54)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(10)

        self.page_title_label = QLabel("Dashboard")
        self.page_title_label.setObjectName("pageTitle")

        layout.addWidget(self.page_title_label, 1)

        self.global_refresh_btn = QPushButton("Refresh")
        self.global_refresh_btn.setIcon(get_icon("refresh.png"))
        self.global_refresh_btn.setIconSize(QSize(20, 20))
        self.global_refresh_btn.setObjectName("globalRefreshBtn")
        self.global_refresh_btn.setToolTip("Refresh workspace data and views")
        self.global_refresh_btn.setCursor(Qt.PointingHandCursor)
        self.global_refresh_btn.setFixedHeight(30)
        self.global_refresh_btn.clicked.connect(self._on_global_refresh)
        layout.addWidget(self.global_refresh_btn)

        self.theme_toggle = QPushButton("Dark Mode" if self._theme == "light" else "Light Mode")
        self.theme_toggle.setIcon(get_icon("dark_theme.png" if self._theme == "light" else "light_theme.png"))
        self.theme_toggle.setIconSize(QSize(20, 20))
        self.theme_toggle.setObjectName("themeToggle")
        self.theme_toggle.setCursor(Qt.PointingHandCursor)
        self.theme_toggle.setFixedHeight(30)
        self.theme_toggle.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_toggle)

        profile = self._build_profile_block()
        layout.addSpacing(6)
        layout.addLayout(profile)

        return header

    def _build_profile_block(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        initials = (self.current_user.get("username") or "U")[:2].upper()
        avatar = QLabel(initials)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(32, 32)
        avatar.setStyleSheet(
            "QLabel { border-radius: 16px; background-color: #2563eb; color: white; font-weight: 700; font-size: 12px; }"
        )

        text_col = QVBoxLayout()
        text_col.setSpacing(1)
        text_col.setContentsMargins(0, 0, 0, 0)

        name_label = QLabel(self.current_user.get("username", "Guest"))
        name_label.setObjectName("userNameLabel")

        role_label = QLabel(self.current_user.get("role", "user").title())
        role_label.setObjectName("userRoleLabel")

        text_col.addWidget(name_label, 0, Qt.AlignVCenter)
        text_col.addWidget(role_label, 0, Qt.AlignVCenter)

        row.addWidget(avatar, 0, Qt.AlignVCenter)
        row.addLayout(text_col)
        return row

    def _build_page_stack(self) -> QFrame:
        container = QFrame()
        container.setObjectName("pageContainer")
        outer = QVBoxLayout(container)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        print("[main_window._build_page_stack] construct EmployeeView() ...")
        sys.stdout.flush()
        self.employee_view = EmployeeView(lazy=True)
        print("[main_window._build_page_stack] construct AnalyticsView() ...")
        sys.stdout.flush()
        self.analytics_view = AnalyticsView()
        print("[main_window._build_page_stack] construct DepartmentView() ...")
        sys.stdout.flush()
        self.department_view = DepartmentView(lazy=True)
        print("[main_window._build_page_stack] construct ReportsView() ...")
        sys.stdout.flush()
        self.reports_view = ReportsView(lazy=True)
        print("[main_window._build_page_stack] construct SettingsView() ...")
        sys.stdout.flush()
        self.settings_view = SettingsView(lazy=True, user=self.current_user)
        print("[main_window._build_page_stack] Views initialized safely.")
        sys.stdout.flush()

        pages = [
            ("dashboard", self.analytics_view),
            ("employees", self.employee_view),
            ("departments", self.department_view),
            ("reports", self.reports_view),
            ("settings", self.settings_view),
        ]

        for key, page in pages:
            index = self.stack.addWidget(page)
            self._page_index[key] = index

        # Connect "analytics" alias to dashboard for backward compatibility
        self._page_index["analytics"] = self._page_index["dashboard"]

        self.employee_view.data_changed.connect(self._on_employee_data_changed)
        self.department_view.data_changed.connect(self._on_department_data_changed)
        self.settings_view.data_changed.connect(self._on_settings_data_changed)

        self.employee_view.status_message.connect(lambda msg, ms=3000: self.statusBar().showMessage(msg, ms))
        self.department_view.status_message.connect(lambda msg, ms=3000: self.statusBar().showMessage(msg, ms))
        self.settings_view.status_message.connect(lambda msg, ms=3000: self.statusBar().showMessage(msg, ms))

        outer.addWidget(self.stack)
        return container

    # ------------------------------------------------------------------
    # Navigation + Actions
    # ------------------------------------------------------------------
    def _get_current_key(self) -> str:
        idx = self.stack.currentIndex()
        for k, v in self._page_index.items():
            if v == idx and k != "analytics":
                return k
        return "dashboard"

    def _navigate_to(self, key: str) -> None:
        if key == "analytics":
            key = "dashboard"
        if key not in self._page_index:
            return
        self.stack.setCurrentIndex(self._page_index[key])
        if hasattr(self, "_nav_buttons") and key in self._nav_buttons:
            self._nav_buttons[key].setChecked(True)

        titles = {
            "dashboard": "Executive Dashboard",
            "employees": "Employee Directory",
            "departments": "Department Management",
            "reports": "Reports & Analytics Center",
            "settings": "Settings & Data Management",
        }
        self.page_title_label.setText(titles.get(key, key.title()))

        # Load/refresh only if dirty or first navigation
        if self._dirty_views.get(key, True):
            if key == "dashboard":
                self.analytics_view.refresh()
            elif key == "departments":
                self.department_view.refresh()
            elif key == "employees":
                self.employee_view.refresh()
            elif key == "reports":
                self.reports_view.refresh()
            elif key == "settings":
                self.settings_view.refresh()
            self._dirty_views[key] = False

    def _on_employee_data_changed(self) -> None:
        for k in ("dashboard", "departments", "reports", "settings"):
            self._dirty_views[k] = True
        curr = self._get_current_key()
        if curr in ("dashboard", "departments", "reports", "settings"):
            self.stack.currentWidget().refresh()
            self._dirty_views[curr] = False

    def _on_department_data_changed(self) -> None:
        for k in ("dashboard", "employees", "reports", "settings"):
            self._dirty_views[k] = True
        curr = self._get_current_key()
        if curr in ("dashboard", "employees", "reports", "settings"):
            self.stack.currentWidget().refresh()
            self._dirty_views[curr] = False

    def _on_settings_data_changed(self) -> None:
        for k in ("dashboard", "employees", "departments", "reports"):
            self._dirty_views[k] = True
        curr = self._get_current_key()
        if curr in ("dashboard", "employees", "departments", "reports"):
            self.stack.currentWidget().refresh()
            self._dirty_views[curr] = False

    def _on_global_refresh(self) -> None:
        """Global refresh trigger for the currently opened screen."""
        if hasattr(self, "stack") and self.stack is not None:
            current = self.stack.currentWidget()
            if current is not None and hasattr(current, "refresh"):
                current.refresh()
                curr_key = self._get_current_key()
                self._dirty_views[curr_key] = False
                title = self.page_title_label.text() if hasattr(self, "page_title_label") else "Screen"
                self.statusBar().showMessage(f"{title} refreshed successfully.", 2500)
                return
        self.statusBar().showMessage("Screen refreshed.", 2000)

    def _on_about(self) -> None:
        dlg = AboutDialog(self)
        dlg.exec_()

    def _on_logout(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Log Out",
            "Are you sure you want to log out?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.is_logged_out = True
            self.current_user = None
            self.close()

    def closeEvent(self, event) -> None:
        """Gracefully wait for any background threads to exit before window closes."""
        try:
            if hasattr(self, "employee_view") and self.employee_view is not None:
                if hasattr(self.employee_view, "cleanup_workers"):
                    self.employee_view.cleanup_workers()
            if hasattr(self, "analytics_view") and self.analytics_view is not None:
                if hasattr(self.analytics_view, "cleanup_workers"):
                    self.analytics_view.cleanup_workers()
        except Exception:
            pass
        super().closeEvent(event)


def _force_foreground_on_windows(hwnd_ptr) -> None:
    """Best-effort Win32 SetForegroundWindow via ctypes.

    PyQt5's raise_() / activateWindow() silently fail if the calling thread
    doesn't own the foreground window (which is almost always the case when
    you launch the app from inside PowerShell or an IDE). This fallback uses
    the Win32 API directly to force the window into Z-order foreground.

    Args:
        hwnd_ptr: result of QWidget.winId() (int/void*). Passing None/0 is a no-op.
    """
    if sys.platform != "win32":
        return
    if not hwnd_ptr:
        return
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.AllowSetForegroundWindow(user32.GetCurrentProcessId())  # only allow this process
        AttachThreadInput = user32.AttachThreadInput
        AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
        AttachThreadInput.restype = wintypes.BOOL

        foreground_hwnd = user32.GetForegroundWindow()
        current_tid = user32.GetCurrentThreadId()
        fg_tid = user32.GetWindowThreadProcessId(foreground_hwnd, None)
        if fg_tid and fg_tid != current_tid:
            AttachThreadInput(current_tid, fg_tid, True)
        SetForegroundWindow = user32.SetForegroundWindow
        SetForegroundWindow.argtypes = [wintypes.HWND]
        SetForegroundWindow.restype = wintypes.BOOL
        BringWindowToTop = user32.BringWindowToTop
        BringWindowToTop.argtypes = [wintypes.HWND]
        BringWindowToTop.restype = wintypes.BOOL
        ShowWindow = user32.ShowWindow
        ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        ShowWindow.restype = wintypes.BOOL
        SW_SHOW = 5
        SW_RESTORE = 9

        hwnd = int(hwnd_ptr)
        ShowWindow(hwnd, SW_RESTORE)
        ShowWindow(hwnd, SW_SHOW)
        BringWindowToTop(hwnd)
        SetForegroundWindow(hwnd)
        if fg_tid and fg_tid != current_tid:
            AttachThreadInput(current_tid, fg_tid, False)
    except Exception:
        # Foreground push is a best-effort UX nicety; never fail startup over it.
        return


def _display_and_confirm_main_window(window: QMainWindow) -> None:
    """Show `window` and force it to foreground."""
    window.show()
    window.showNormal()
    window.raise_()
    window.activateWindow()
    try:
        wid = window.windowHandle()
        if wid is not None:
            wid.requestActivate()
    except Exception:
        pass
    try:
        _force_foreground_on_windows(window.winId())
    except Exception:
        pass


def main() -> int:
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass
    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    try:
        database.init_db()
        database.insert_default_admin()
    except Exception as _exc:
        QMessageBox.critical(
            None,
            "Database Error",
            "Could not initialize the database:\n{}".format(str(_exc)),
        )
        raise

    while True:
        login = LoginDialog()
        login_result = login.exec_()
        if login_result != LoginDialog.Accepted or not login.current_user:
            return 0

        window = MainWindow(user=login.current_user)
        _display_and_confirm_main_window(window)
        app.exec_()
        if not getattr(window, "is_logged_out", False):
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())
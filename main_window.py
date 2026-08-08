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
)

import database
from login import LoginDialog
from employee_view import EmployeeView
from analytics_view import AnalyticsView


LIGHT_QSS = """
* {
    font-family: "Segoe UI", Tahoma, sans-serif;
    color: #1f2937;
}

QMainWindow, QWidget#rootWidget {
    background-color: #f3f4f6;
}

QFrame#sidebar {
    background-color: #1e3a8a;
    border: none;
}

QLabel#sidebarTitle {
    color: #ffffff;
    font-size: 16px;
    font-weight: 700;
    padding: 12px 16px;
}

QLabel#sidebarSubtitle {
    color: #bfdbfe;
    font-size: 11px;
    padding: 0 16px 12px 16px;
}

QPushButton.navButton {
    background-color: transparent;
    color: #dbeafe;
    border: none;
    text-align: left;
    padding: 10px 20px;
    font-size: 13px;
    border-radius: 0px;
}

QPushButton.navButton:hover {
    background-color: #1e40af;
    color: #ffffff;
}

QPushButton.navButton:checked {
    background-color: #2563eb;
    color: #ffffff;
    border-left: 4px solid #93c5fd;
    padding-left: 16px;
    font-weight: 600;
}

QFrame#headerBar {
    background-color: #ffffff;
    border-bottom: 1px solid #e5e7eb;
}

QLabel#pageTitle {
    color: #111827;
    font-size: 18px;
    font-weight: 700;
}

QLabel#userNameLabel {
    color: #111827;
    font-size: 13px;
    font-weight: 600;
}

QLabel#userRoleLabel {
    color: #6b7280;
    font-size: 11px;
}

QPushButton#themeToggle {
    background-color: #f3f4f6;
    color: #111827;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton#themeToggle:hover {
    background-color: #e5e7eb;
}

QFrame#pageContainer {
    background-color: #f3f4f6;
}

QFrame.card {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
}

QLabel.cardTitle {
    color: #111827;
    font-size: 15px;
    font-weight: 700;
}

QLabel.cardSubtitle {
    color: #6b7280;
    font-size: 12px;
}

QPushButton.primaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.primaryButton:hover { background-color: #1d4ed8; }
QPushButton.primaryButton:pressed { background-color: #1e40af; }
QPushButton.primaryButton:disabled { background-color: #9ca3af; }

QPushButton.secondaryButton {
    background-color: #ffffff;
    color: #1f2937;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton.secondaryButton:hover { background-color: #f9fafb; }
QPushButton.secondaryButton:disabled { color: #9ca3af; }

QPushButton.dangerButton {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.dangerButton:hover { background-color: #b91c1c; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
    background-color: #ffffff;
    color: #111827;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {
    border: 1px solid #2563eb;
}

QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #111827;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    border: 1px solid #d1d5db;
    outline: 0;
}

QTableWidget {
    background-color: #ffffff;
    color: #111827;
    border: 1px solid #e5e7eb;
    border-radius: 6px;
    gridline-color: #f3f4f6;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
}

QTableWidget::item { padding: 6px 10px; }

QHeaderView::section {
    background-color: #f9fafb;
    color: #374151;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #e5e7eb;
    font-weight: 600;
    font-size: 12px;
}

QTableCornerButton::section {
    background-color: #f9fafb;
    border: none;
    border-bottom: 1px solid #e5e7eb;
}

QScrollBar:vertical {
    background-color: #f3f4f6;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background-color: #94a3b8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background-color: #f3f4f6;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #cbd5e1;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background-color: #94a3b8; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QMessageBox QLabel { color: #111827; font-size: 13px; }
QMessageBox QPushButton {
    min-width: 80px;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 13px;
}

QStatusBar {
    background-color: #ffffff;
    color: #6b7280;
    border-top: 1px solid #e5e7eb;
}
"""


DARK_QSS = """
* {
    font-family: "Segoe UI", Tahoma, sans-serif;
    color: #e5e7eb;
}

QMainWindow, QWidget#rootWidget {
    background-color: #0f172a;
}

QFrame#sidebar {
    background-color: #111827;
    border: none;
    border-right: 1px solid #1f2937;
}

QLabel#sidebarTitle {
    color: #f9fafb;
    font-size: 16px;
    font-weight: 700;
    padding: 12px 16px;
}

QLabel#sidebarSubtitle {
    color: #94a3b8;
    font-size: 11px;
    padding: 0 16px 12px 16px;
}

QPushButton.navButton {
    background-color: transparent;
    color: #cbd5e1;
    border: none;
    text-align: left;
    padding: 10px 20px;
    font-size: 13px;
    border-radius: 0px;
}

QPushButton.navButton:hover {
    background-color: #1f2937;
    color: #f9fafb;
}

QPushButton.navButton:checked {
    background-color: #374151;
    color: #ffffff;
    border-left: 4px solid #3b82f6;
    padding-left: 16px;
    font-weight: 600;
}

QFrame#headerBar {
    background-color: #111827;
    border-bottom: 1px solid #1f2937;
}

QLabel#pageTitle {
    color: #f9fafb;
    font-size: 18px;
    font-weight: 700;
}

QLabel#userNameLabel {
    color: #f9fafb;
    font-size: 13px;
    font-weight: 600;
}

QLabel#userRoleLabel {
    color: #94a3b8;
    font-size: 11px;
}

QPushButton#themeToggle {
    background-color: #1f2937;
    color: #e5e7eb;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
}

QPushButton#themeToggle:hover {
    background-color: #374151;
}

QFrame#pageContainer {
    background-color: #0f172a;
}

QFrame.card {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 8px;
}

QLabel.cardTitle {
    color: #f9fafb;
    font-size: 15px;
    font-weight: 700;
}

QLabel.cardSubtitle {
    color: #94a3b8;
    font-size: 12px;
}

QPushButton.primaryButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.primaryButton:hover { background-color: #1d4ed8; }
QPushButton.primaryButton:pressed { background-color: #1e40af; }
QPushButton.primaryButton:disabled { background-color: #475569; color: #94a3b8; }

QPushButton.secondaryButton {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #374151;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton.secondaryButton:hover { background-color: #1f2937; }
QPushButton.secondaryButton:disabled { color: #64748b; border-color: #1f2937; }

QPushButton.dangerButton {
    background-color: #dc2626;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}

QPushButton.dangerButton:hover { background-color: #b91c1c; }

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {
    background-color: #0f172a;
    color: #f1f5f9;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QDateEdit:focus {
    border: 1px solid #3b82f6;
}

QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView {
    background-color: #111827;
    color: #e5e7eb;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
    border: 1px solid #374151;
    outline: 0;
}

QTableWidget {
    background-color: #111827;
    color: #e5e7eb;
    border: 1px solid #1f2937;
    border-radius: 6px;
    gridline-color: #1f2937;
    selection-background-color: #1e3a8a;
    selection-color: #dbeafe;
}

QTableWidget::item { padding: 6px 10px; }

QHeaderView::section {
    background-color: #1f2937;
    color: #cbd5e1;
    padding: 8px 10px;
    border: none;
    border-bottom: 1px solid #374151;
    font-weight: 600;
    font-size: 12px;
}

QTableCornerButton::section {
    background-color: #1f2937;
    border: none;
    border-bottom: 1px solid #374151;
}

QScrollBar:vertical {
    background-color: #111827;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #475569;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background-color: #64748b; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background-color: #111827;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background-color: #475569;
    border-radius: 5px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background-color: #64748b; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QMessageBox { background-color: #111827; }
QMessageBox QLabel { color: #e5e7eb; font-size: 13px; }
QMessageBox QPushButton {
    background-color: #1f2937;
    color: #e5e7eb;
    border: 1px solid #374151;
    min-width: 80px;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 13px;
}
QMessageBox QPushButton:hover { background-color: #374151; }
QMessageBox QPushButton:default {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
}

QStatusBar {
    background-color: #111827;
    color: #94a3b8;
    border-top: 1px solid #1f2937;
}
"""


THEMES = {
    "light": LIGHT_QSS,
    "dark": DARK_QSS,
}


def _placeholder_page(title: str, subtitle: str, include_table: bool = False) -> QFrame:
    card = QFrame()
    card.setObjectName("placeholderCard")
    card.setProperty("class", "card")
    card.setStyleSheet("QFrame#placeholderCard { background: palette(window); }")

    layout = QVBoxLayout(card)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(12)

    t = QLabel(title)
    t.setProperty("class", "cardTitle")
    t.setStyleSheet("QLabel { color: palette(window-text); }")

    s = QLabel(subtitle)
    s.setProperty("class", "cardSubtitle")
    s.setStyleSheet("QLabel { color: palette(mid); }")
    s.setWordWrap(True)

    layout.addWidget(t)
    layout.addWidget(s)

    if include_table:
        table = QTableWidget(4, 5)
        table.setHorizontalHeaderLabels(["Code", "Name", "Department", "Position", "Salary"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        sample = [
            ("EMP001", "Alice Johnson", "Engineering", "Senior Dev", "95,000"),
            ("EMP002", "Bob Smith", "Sales", "Account Exec", "78,000"),
            ("EMP003", "Carol Davis", "HR", "HR Partner", "70,000"),
            ("EMP004", "David Lee", "Finance", "Analyst", "72,000"),
        ]
        for r, row in enumerate(sample):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                table.setItem(r, c, item)
        table.verticalHeader().setVisible(False)
        layout.addSpacing(8)
        layout.addWidget(table)

    layout.addStretch(1)
    return card


class MainWindow(QMainWindow):
    def __init__(self, user: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.current_user: Dict[str, Any] = user or {"id": 0, "username": "guest", "role": "user"}
        self._theme: str = "light"
        self._nav_group: Optional[QButtonGroup] = None
        self._page_index: Dict[str, int] = {}
        self.employee_view: Any = None
        self.analytics_view: Any = None

        try:
            self._ui_ready = False
            print("[main_window] step 1 _build_ui() ...")
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
        qss = THEMES.get(theme, THEMES["light"])
        app = QApplication.instance()
        if app is not None:
            try:
                app.setStyleSheet(qss)
            except Exception as exc:
                print("[main_window._apply_theme] setStyleSheet warning (non-fatal):", exc)
                sys.stdout.flush()
        self._theme = theme
        if hasattr(self, "theme_toggle"):
            self.theme_toggle.setText("Dark Mode" if theme == "light" else "Light Mode")
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
        self.setWindowTitle("Employee Management System")
        self.resize(1180, 760)
        self.setMinimumSize(QSize(980, 620))

        root = QWidget(self)
        root.setObjectName("rootWidget")
        self.setCentralWidget(root)

        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        print("[main_window._build_ui] 2/5 _build_sidebar() ...")
        sys.stdout.flush()
        root_layout.addWidget(self._build_sidebar(), 0)
        print("[main_window._build_ui] 3/5 _build_content_area() ...")
        sys.stdout.flush()
        root_layout.addWidget(self._build_content_area(), 1)

        print("[main_window._build_ui] 4/5 statusBar() ...")
        sys.stdout.flush()
        status = self.statusBar()
        status.showMessage(
            "Logged in as {} · Role: {}".format(
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
        sidebar.setFixedWidth(240)

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

        nav_items = [
            ("dashboard", "Dashboard"),
            ("employees", "Employees"),
            ("analytics", "Analytics"),
            ("departments", "Departments"),
            ("reports", "Reports"),
            ("settings", "Settings"),
        ]
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        for idx, (key, label) in enumerate(nav_items):
            btn = QPushButton(label)
            btn.setProperty("class", "navButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(38)
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda _=False, k=key: self._navigate_to(k))
            self._nav_group.addButton(btn)
            layout.addWidget(btn)

        layout.addStretch(1)

        logout = QPushButton("Log Out")
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
        header.setFixedHeight(64)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        self.page_title_label = QLabel("Dashboard")
        self.page_title_label.setObjectName("pageTitle")

        layout.addWidget(self.page_title_label, 1)

        self.theme_toggle = QPushButton("Dark Mode")
        self.theme_toggle.setObjectName("themeToggle")
        self.theme_toggle.setCursor(Qt.PointingHandCursor)
        self.theme_toggle.setFixedHeight(30)
        self.theme_toggle.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_toggle)

        profile = self._build_profile_block()
        layout.addSpacing(8)
        layout.addLayout(profile)

        return header

    def _build_profile_block(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)

        initials = (self.current_user.get("username") or "U")[:2].upper()
        avatar = QLabel(initials)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setFixedSize(36, 36)
        avatar.setStyleSheet(
            "QLabel { border-radius: 18px; background-color: #2563eb; color: white; font-weight: 700; font-size: 13px; }"
        )

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
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
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        print("[main_window._build_page_stack] construct EmployeeView() ...")
        sys.stdout.flush()
        self.employee_view = EmployeeView()
        print("[main_window._build_page_stack] construct AnalyticsView() ...")
        sys.stdout.flush()
        self.analytics_view = AnalyticsView()
        print("[main_window._build_page_stack] AnalyticsView.__init__ finished safely.")
        sys.stdout.flush()

        pages = [
            ("dashboard", _placeholder_page(
                "Dashboard",
                "Welcome back, {}. This view will show KPIs, headcount stats, and recent activity.".format(
                    self.current_user.get("username", "user")
                ),
                include_table=True,
            )),
            ("employees", self.employee_view),
            ("analytics", self.analytics_view),
            ("departments", _placeholder_page(
                "Departments",
                "View and manage departments and team headcounts.",
            )),
            ("reports", _placeholder_page(
                "Reports",
                "Run payroll, headcount, and attendance reports here.",
            )),
            ("settings", _placeholder_page(
                "Settings",
                "User preferences, application settings, and user management.",
            )),
        ]

        for key, page in pages:
            index = self.stack.addWidget(page)
            self._page_index[key] = index

        self.employee_view.data_changed.connect(self._on_employee_data_changed)

        outer.addWidget(self.stack)
        return container

    # ------------------------------------------------------------------
    # Navigation + Actions
    # ------------------------------------------------------------------
    def _navigate_to(self, key: str) -> None:
        if key not in self._page_index:
            return
        self.stack.setCurrentIndex(self._page_index[key])
        titles = {
            "dashboard": "Dashboard",
            "employees": "Employees",
            "analytics": "Analytics",
            "departments": "Departments",
            "reports": "Reports",
            "settings": "Settings",
        }
        self.page_title_label.setText(titles.get(key, key.title()))
        if key == "analytics":
            self.analytics_view.refresh()

    def _on_employee_data_changed(self) -> None:
        self.analytics_view.refresh()

    def _on_logout(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Log Out",
            "Are you sure you want to log out?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.current_user = None
            self.close()


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
        user32.AllowSetForegroundWindow(-1)  # ASFW_ANY = -1: allow any process
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
    """Show `window`, force it to foreground, then show a always-visible
    confirmation QMessageBox so the user cannot miss that startup succeeded.

    This handles the common "login dialog disappears and nothing appears"
    complaint: either the MainWindow is actually visible on screen, OR the
    user sees a QMessageBox.information() in front of them (modal, always
    topmost-active for the Qt event loop) saying the window is there.
    """
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
    try:
        from PyQt5.QtCore import QTimer
        user = window.current_user or {}
        msg = QMessageBox(window)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Employee Management System Ready")
        msg.setText(
            "Welcome, {}!\n\n"
            "The Employee Management System dashboard is now open and should "
            "be visible on your screen.\n\n"
            "If you do NOT see the dashboard window behind this message, "
            "check your taskbar, press Alt+Tab, or minimize the IDE/terminal "
            "you launched from -- the window exists but was hidden by Windows "
            "Z-ordering.".format(user.get("username", "Guest"))
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setModal(False)
        QTimer.singleShot(1500, msg.show)
    except Exception:
        pass


def main() -> int:
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

    login = LoginDialog()
    login_result = login.exec_()
    if login_result != LoginDialog.Accepted or not login.current_user:
        QMessageBox.information(
            None,
            "Login Cancelled",
            "Login was cancelled or credentials were not provided.\nApplication will exit.",
        )
        return 0

    window = MainWindow(user=login.current_user)
    _display_and_confirm_main_window(window)
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
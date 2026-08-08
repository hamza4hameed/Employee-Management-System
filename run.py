"""Robust launcher for Employee Management System.

Ordering is EXTREMELY important on Python 3.13 + PyQt5:
1. set os.environ for Qt / matplotlib FIRST (before any Qt / mpl import)
   - INCLUDING auto-detected QT_PLUGIN_PATH so qwindows.dll is found.
2. CREATE QApplication instance (empty shell) BEFORE importing ANY app module
3. Only then import database, main_window, employee_view, analytics_view, etc.

Otherwise FigureCanvasQTAgg's module-level import can segfault the process
silently (exit code 0xC0000005) without printing a traceback.

ALSO adds explicit DIAG STEP 1..9 prints so we can pinpoint a silent kill
just from the last printed line.

Run:  python.exe -u run.py
"""

import os
import sys
import traceback
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(_HERE)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

LOG_PATH = os.path.join(_HERE, "startup_error.log")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _step(n: int, text: str) -> None:
    """Print a numbered diagnostic line and flush stdout immediately.

    If the process is killed silently (0xC0000005), the last printed STEP
    number tells us exactly which line was being executed.
    """
    print("[DIAG STEP {}/9] {}".format(n, text))
    sys.stdout.flush()


def _find_qt_plugin_path() -> str:
    """Auto-locate the PyQt5 plugins folder that contains platforms/qwindows.dll.

    On many pip-installed PyQt5 setups on Windows, qwindows.dll exists on disk
    but Qt cannot find it because QT_PLUGIN_PATH is not exported and Qt's
    compiled-in default path points at the wrong folder. The symptom is:
    QApplication creates OK, but QMainWindow.show() silently returns with no
    window visible and the event loop spins forever doing nothing.

    Returns the plugin path (including \\platforms parent) if found, else "".
    """
    candidates = []
    # Candidate 1: standard PyQt5 wheels place plugins here
    if hasattr(sys, "prefix"):
        candidates.append(
            os.path.join(sys.prefix, "Lib", "site-packages", "PyQt5", "Qt5", "plugins")
        )
    # Candidate 2: virtualenv / venv
    if hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix:
        candidates.append(
            os.path.join(sys.base_prefix, "Lib", "site-packages", "PyQt5", "Qt5", "plugins")
        )
    # Candidate 3: PyQt5 packages sometimes expose __file__
    try:
        import PyQt5 as _PyQt5
        if hasattr(_PyQt5, "__file__") and _PyQt5.__file__:
            candidates.append(
                os.path.join(os.path.dirname(_PyQt5.__file__), "Qt5", "plugins")
            )
    except Exception:
        pass
    for path in candidates:
        platforms_dir = os.path.join(path, "platforms")
        qwin_dll = os.path.join(platforms_dir, "qwindows.dll")
        if os.path.isdir(platforms_dir) and os.path.isfile(qwin_dll):
            return path
    return ""


# ---------------------------------------------------------------------------
# 1. Environment variables (MUST be set before first Qt / mpl import)
# ---------------------------------------------------------------------------
_step(1, "Setting environment variables (Qt / matplotlib) ...")
os.environ["MPLBACKEND"]          = "Qt5Agg"
os.environ["QT_QPA_PLATFORM"]     = "windows"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

_found_qt_plugins = _find_qt_plugin_path()
if _found_qt_plugins:
    os.environ["QT_PLUGIN_PATH"] = _found_qt_plugins
    _step(1, "  (auto-detected QT_PLUGIN_PATH = " + _found_qt_plugins + ")")
else:
    _step(1, "  (WARNING: could not auto-locate PyQt5 plugins folder. "
         "If windows do not appear, try installing PyQt5: pip install PyQt5)")

# Don't call matplotlib.use() here. analytics_view now pins backend lazily only
# when user clicks Refresh Charts -- safe(r) on Python 3.13 + PyQt5 combos.
try:
    import matplotlib  # noqa: F401  (confirm it's importable only)
except Exception as _e:
    _step(1, "  (matplotlib missing - analytics charts will be disabled: " + str(_e) + ")")


# ---------------------------------------------------------------------------
# 2. Build QApplication IMMEDIATELY
# ---------------------------------------------------------------------------
_step(2, "Creating QApplication instance ...")
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QMessageBox

_app = QApplication.instance() or QApplication(sys.argv)
_app.setFont(QFont("Segoe UI", 10))
_step(2, "  QApplication created. platformName = {}".format(
    getattr(_app, "platformName", lambda: "<?>")()
))


# ---------------------------------------------------------------------------
# Error-reporting helpers (need QApplication to exist already)
# ---------------------------------------------------------------------------
def _fallback_tk_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showerror(
            "Employee Management System - Startup Error", message,
        )
        try:
            root.destroy()
        except Exception:
            pass
    except Exception as exc:
        print("Tk fallback also failed:", exc, file=sys.stderr)
        print("EMPLOYEE-APP STARTUP ERROR:\n" + message, file=sys.stderr)


def _write_log(message: str) -> None:
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n===== {} =====\n".format(
                datetime.now().isoformat(timespec="seconds")
            ))
            f.write(message)
            f.write("\n")
    except Exception as exc:
        print("Could not write log {}: {}".format(LOG_PATH, exc), file=sys.stderr)


# ---------------------------------------------------------------------------
# 3. Import app modules (safe because QApplication + env now set)
# ---------------------------------------------------------------------------
_step(3, "Initializing database + default admin account ...")
import database
database.init_db()
database.insert_default_admin()
_admin_ok = bool(database.verify_login("admin", "admin123"))
_step(3, "  DB init OK. admin/admin123 verify_login = {}".format(
    "OK" if _admin_ok else "FAILED"
))

_step(4, "Importing employee_form / employee_view / csv_utils ...")
import employee_form  # noqa: F401
import employee_view  # noqa: F401
import csv_utils      # noqa: F401
_step(4, "  Employee view / form / CSV modules imported.")

_step(5, "Importing analytics_view ...")
import analytics_view
_step(5, "  Analytics view module imported (NO canvas built yet; user opts in later).")

_step(6, "Importing main_window ...")
import main_window
_step(6, "  main_window module imported.")


# ---------------------------------------------------------------------------
# 4. Launch LoginDialog first, then MainWindow on successful auth
# ---------------------------------------------------------------------------
def _launch() -> int:
    _step(7, "Showing LoginDialog (modal) ... default creds: admin / admin123")
    from login import LoginDialog

    login = LoginDialog()
    result = login.exec_()
    if result != LoginDialog.Accepted or not login.current_user:
        QMessageBox.information(
            None,
            "Login Cancelled",
            "Login was cancelled or credentials were not provided.\n"
            "Application will exit.\n\n"
            "Default account:\n  username: admin\n  password: admin123",
        )
        _step(7, "  Login cancelled by user. Exiting cleanly.")
        return 0
    _step(7, "  Login accepted. username={}, role={}".format(
        login.current_user.get("username"), login.current_user.get("role"),
    ))

    _step(8, "Constructing MainWindow(user=...) ...")
    win = main_window.MainWindow(user=login.current_user)
    _step(8, "  MainWindow.__init__ returned. Geometry={}".format(win.geometry().getRect()))

    _step(9, "Displaying MainWindow + forcing foreground ...")
    try:
        main_window._display_and_confirm_main_window(win)
    except Exception as _show_err:
        # Even if the custom ctypes foreground push crashes for some reason,
        # we still have to show the window via Qt's default calls.
        print("[run.py] _display_and_confirm raised non-fatal:", _show_err)
        sys.stdout.flush()
        win.show()
        win.raise_()
        win.activateWindow()

    # Synchronous MODAL confirmation message box BEFORE starting the main
    # event loop. Qt's exec_() message boxes always use their own nested
    # event loop and ALWAYS become visible on the active desktop (unlike
    # non-modal + QTimer boxes). If the user sees THIS box, MainWindow is
    # definitely alive.
    try:
        user = win.current_user or {}
        _welcome = QMessageBox()
        _welcome.setIcon(QMessageBox.Information)
        _welcome.setWindowTitle("Employee Management System - Ready")
        _welcome.setText(
            "Welcome, {}!\n\n"
            "✓ Login successful\n"
            "✓ Main window created and shown\n"
            "✓ All modules loaded without errors\n\n"
            "Click OK to start using the application.\n\n"
            "If the main dashboard window is NOT visible behind this dialog,\n"
            "press Alt+Tab or minimize the IDE/terminal window you launched from.".format(
                user.get("username", "Guest")
            )
        )
        _welcome.setStandardButtons(QMessageBox.Ok)
        _welcome.setModal(True)
        _step(9, "  Showing synchronous confirmation messagebox ...")
        _welcome.exec_()
    except Exception as _wb_err:
        print("[run.py] Welcome message box failed (non-fatal):", _wb_err)
        sys.stdout.flush()

    _step(9, "  Entering main QApplication event loop (_app.exec_()) ...")
    return _app.exec_()


if __name__ == "__main__":
    try:
        rc = _launch()
        print("[run.py] app exited cleanly with exit code", rc)
        sys.exit(rc)
    except SystemExit:
        raise
    except Exception as exc:
        tb = traceback.format_exc()
        summary = "{}\n\nFull traceback:\n{}".format(str(exc), tb)
        _write_log(summary)
        print("\n" + "=" * 60)
        print("STARTUP ERROR - traceback also written to", LOG_PATH)
        print("=" * 60)
        print(summary)
        print("=" * 60)
        try:
            QMessageBox.critical(
                None,
                "Employee Management System - Startup Error",
                "The app failed to start.\n\n"
                "First error: {}\n\n"
                "See log at: {}\n\n"
                "Full traceback:\n{}".format(str(exc), LOG_PATH, tb),
            )
        except Exception:
            _fallback_tk_error(
                "The app failed to start. First error:\n{}\n\n"
                "Details were written to:\n{}".format(str(exc), LOG_PATH)
            )
        sys.exit(1)

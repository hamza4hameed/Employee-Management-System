"""Robust launcher for Employee Management System.

Ordering is EXTREMELY important on Python 3.13 + PyQt5:
1. set os.environ for Qt / matplotlib FIRST (before any Qt / mpl import)
2. CREATE QApplication instance (empty shell) BEFORE importing ANY app module
3. Only then import database, main_window, employee_view, analytics_view, etc.

Otherwise FigureCanvasQTAgg's module-level import can segfault the process
silently (exit code 0xC0000005) without printing a traceback.

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
# 1. Environment variables (MUST be set before first Qt / mpl import)
# ---------------------------------------------------------------------------
os.environ["MPLBACKEND"]          = "Qt5Agg"
os.environ["QT_QPA_PLATFORM"]     = "windows"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
# If the Qt platform plugin "windows" is ever missing from PyQt5's install,
# you can uncomment the next line and point it at your site-packages PyQt5:
# os.environ["QT_PLUGIN_PATH"] = r"C:\Users\hamza_gooi7rr\AppData\Local\Programs\Python\Python313\Lib\site-packages\PyQt5\Qt5\plugins"

# Force matplotlib backend *now*, still before importing QApplication / widgets.
try:
    import matplotlib
    matplotlib.use("Qt5Agg", force=True)
except Exception as _e:
    print("[run.py] matplotlib backend set-warning (non-fatal):", _e)


# ---------------------------------------------------------------------------
# 2. Build QApplication IMMEDIATELY after matplotlib backend is pinned
# ---------------------------------------------------------------------------
print("[run.py] cwd            =", os.getcwd())
print("[run.py] sys.executable =", sys.executable)
print("[run.py] python version =", sys.version.split()[0])

print("[run.py] Creating QApplication NOW (before any app-module imports) ...")
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QApplication, QMessageBox

_app = QApplication.instance() or QApplication(sys.argv)
_app.setFont(QFont("Segoe UI", 10))
print("[run.py] QApplication created OK. objectName =", _app.objectName())


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
# 3. NOW import app modules (safe because QApplication + backend both exist)
# ---------------------------------------------------------------------------
print("[run.py] importing database ...")
import database
database.init_db()
database.insert_default_admin()
print(
    "[run.py] DB bootstrap OK ; admin verify_login =",
    "OK" if database.verify_login("admin", "admin123") else "FAILED",
)

print("[run.py] importing employee_form / employee_view / csv_utils ...")
import employee_form   # noqa: F401  (side-effect: import safely)
import employee_view   # noqa: F401
import csv_utils       # noqa: F401
print("[run.py] employee_view / forms / csv_utils imported OK.")

print("[run.py] importing analytics_view ...")
import analytics_view
print("[run.py] analytics_view imported OK.")

print("[run.py] importing main_window ...")
import main_window
print("[run.py] main_window imported OK.")


# ---------------------------------------------------------------------------
# 4. Launch LoginDialog first, then MainWindow on successful auth
# ---------------------------------------------------------------------------
def _launch() -> int:
    from login import LoginDialog

    login = LoginDialog()
    result = login.exec_()
    if result != LoginDialog.Accepted or not login.current_user:
        QMessageBox.information(
            None,
            "Login Cancelled",
            "Login was cancelled or credentials were not provided.\n"
            "Application will exit.\n\n"
            "Default account (if you need it):\n  username: admin\n  password: admin123",
        )
        return 0

    win = main_window.MainWindow(user=login.current_user)
    print("[run.py] MainWindow constructor returned OK. Showing + forcing foreground ...")
    sys.stdout.flush()
    main_window._display_and_confirm_main_window(win)
    print("[run.py] MainWindow shown. Entering event loop. Login user =",
          login.current_user.get("username"))
    sys.stdout.flush()
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
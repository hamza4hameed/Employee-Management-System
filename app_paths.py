r"""Unified runtime path resolution.

Paths are relative to the application bundle/source tree for read-only assets,
and user-writable data is stored under %LOCALAPPDATA%\Employee Management System.

Import this module EARLY (before any other app module that constructs paths).
It has NO side effects beyond determining paths and creating user directories
on demand.
"""

import os
import shutil
import sys
import tempfile
from typing import Optional

from app_meta import APP_NAME

APP_DIR_NAME = "Employee Management System"


# ---------------------------------------------------------------------------
# 1. Application (read-only) assets directory
# ---------------------------------------------------------------------------

def get_app_root() -> str:
    """Directory containing application read-only assets (bundled or source).

    Handles PyInstaller bundles:
      - In --onefile mode: sys._MEIPASS holds the extracted resources.
      - In --onedir mode: checks sys._MEIPASS and the executable's directory.
      - In source/dev mode: uses the directory of this file.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and os.path.isdir(os.path.join(meipass, "resources")):
            return meipass
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        if os.path.isdir(os.path.join(exe_dir, "resources")):
            return exe_dir
        if meipass:
            return meipass
        return exe_dir

    return os.path.dirname(os.path.abspath(__file__))


def get_resources_dir() -> str:
    """Path to the ``resources/`` folder (icons, images, etc.)."""
    return os.path.join(get_app_root(), "resources")


def get_icons_dir() -> str:
    """Path to the ``resources/icons/`` folder."""
    return os.path.join(get_resources_dir(), "icons")


def get_sample_data_dir() -> str:
    """Path to the ``sample_data/`` folder (CSV demos, etc.)."""
    root = get_app_root()
    cand = os.path.join(root, "sample_data")
    if os.path.isdir(cand):
        return cand
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        cand_exe = os.path.join(exe_dir, "sample_data")
        if os.path.isdir(cand_exe):
            return cand_exe
    return cand


# ---------------------------------------------------------------------------
# 2. User data (read-write) directories
# ---------------------------------------------------------------------------

def _migrate_legacy_data_dir(target_dir: str, base_dir: str) -> None:
    """Migrate data from legacy unspaced directory if target does not yet exist."""
    legacy_dir = os.path.join(base_dir, "EmployeeManagementSystem")
    if not os.path.isdir(legacy_dir) or os.path.abspath(legacy_dir) == os.path.abspath(target_dir):
        return

    # If target already exists, do not overwrite it
    if os.path.exists(target_dir):
        return

    try:
        os.rename(legacy_dir, target_dir)
    except Exception:
        try:
            shutil.copytree(legacy_dir, target_dir)
        except Exception:
            pass


def _default_user_data_root() -> str:
    """Compute the platform-appropriate user-writable root directory.

    Default on Windows: %LOCALAPPDATA%\\Employee Management System
    Supports automatic migration from legacy unspaced folder if present.
    """
    env_override = os.environ.get("EMS_USER_DATA_DIR", "").strip()
    if env_override:
        return env_override

    base = os.environ.get("LOCALAPPDATA")
    if base and os.path.isdir(base):
        target = os.path.join(base, APP_DIR_NAME)
        _migrate_legacy_data_dir(target, base)
        return target

    # Fallback: user home directory
    home = os.path.expanduser("~")
    if home and os.path.isdir(home):
        local_app_data = os.path.join(home, "AppData", "Local")
        target = os.path.join(local_app_data, APP_DIR_NAME)
        if os.path.isdir(local_app_data):
            _migrate_legacy_data_dir(target, local_app_data)
        return target

    return os.path.join(tempfile.gettempdir(), APP_DIR_NAME)


def _ensure_dir(path: str) -> str:
    """Create directory if it does not exist, with fallback to temp directory."""
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        # Best-effort fallback to temp dir for this specific path
        alt = os.path.join(tempfile.gettempdir(), APP_DIR_NAME, os.path.basename(path))
        os.makedirs(alt, exist_ok=True)
        return alt
    return path


def get_user_data_dir() -> str:
    """Root folder for all user-writable data (DB, logs, backups).

    Default on Windows: ``%LOCALAPPDATA%\\Employee Management System``
    Override by setting the environment variable ``EMS_USER_DATA_DIR``.
    """
    return _ensure_dir(_default_user_data_root())


def get_database_dir() -> str:
    """Directory containing the SQLite database file."""
    return _ensure_dir(os.path.join(get_user_data_dir(), "data"))


def get_database_path() -> str:
    """Full path to the active SQLite database file."""
    return os.path.join(get_database_dir(), "employee_system.db")


def get_log_dir() -> str:
    """Directory for rotating application log files."""
    return _ensure_dir(os.path.join(get_user_data_dir(), "logs"))


def get_backup_dir() -> str:
    """Default directory for manual + auto (pre-restore) DB backups."""
    return _ensure_dir(os.path.join(get_user_data_dir(), "backups"))


# ---------------------------------------------------------------------------
# 3. Diagnostic summary (useful for About / troubleshooting dialogs)
# ---------------------------------------------------------------------------

def get_path_diagnostics() -> dict:
    """Return a plain dict describing all resolved paths for troubleshooting."""
    return {
        "python":         sys.executable,
        "is_frozen":      getattr(sys, "frozen", False),
        "app_root":       get_app_root(),
        "resources_dir":  get_resources_dir(),
        "icons_dir":      get_icons_dir(),
        "sample_data":    get_sample_data_dir(),
        "user_data_dir":  get_user_data_dir(),
        "database_dir":   get_database_dir(),
        "database_path":  get_database_path(),
        "log_dir":        get_log_dir(),
        "backup_dir":     get_backup_dir(),
    }


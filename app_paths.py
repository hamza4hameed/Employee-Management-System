r"""Unified runtime path resolution.

Paths are relative to the source tree for application assets,
and user-writable data is stored under %LOCALAPPDATA%\EmployeeManagementSystem.

Import this module EARLY (before any other app module that constructs paths).
It has NO side effects beyond determining paths and creating user directories
on demand.
"""

import os
import sys
import tempfile
from typing import Optional

from app_meta import APP_SHORT_NAME


# ---------------------------------------------------------------------------
# 1. Application (read-only) assets directory
# ---------------------------------------------------------------------------

def get_app_root() -> str:
    """Directory containing application assets."""
    return os.path.dirname(os.path.abspath(__file__))


def get_resources_dir() -> str:
    """Path to the ``resources/`` folder (icons, images, etc.)."""
    return os.path.join(get_app_root(), "resources")


def get_icons_dir() -> str:
    """Path to the ``resources/icons/`` folder."""
    return os.path.join(get_resources_dir(), "icons")


def get_sample_data_dir() -> str:
    """Path to the ``sample_data/`` folder (CSV demos, etc.)."""
    return os.path.join(get_app_root(), "sample_data")


# ---------------------------------------------------------------------------
# 2. User data (read-write) directories
# ---------------------------------------------------------------------------

def _default_user_data_root() -> str:
    """Compute the platform-appropriate user-writable root directory."""
    env_override = os.environ.get("EMS_USER_DATA_DIR", "").strip()
    if env_override:
        return env_override

    base = os.environ.get("LOCALAPPDATA")
    if base and os.path.isdir(base):
        return os.path.join(base, "EmployeeManagementSystem")

    # Fallback: user home directory
    home = os.path.expanduser("~")
    if home and os.path.isdir(home):
        return os.path.join(home, "AppData", "Local", "EmployeeManagementSystem")

    return os.path.join(tempfile.gettempdir(), "EmployeeManagementSystem")


USER_DATA_ROOT = _default_user_data_root()


def _ensure_dir(path: str) -> str:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        # Best-effort fallback to temp dir for this specific path
        alt = os.path.join(tempfile.gettempdir(), "EmployeeManagementSystem",
                           os.path.basename(path))
        os.makedirs(alt, exist_ok=True)
        return alt
    return path


def get_user_data_dir() -> str:
    """Root folder for all user-writable data (DB, logs, backups).

    Default on Windows: ``%LOCALAPPDATA%\\EmployeeManagementSystem``
    Override by setting the environment variable ``EMS_USER_DATA_DIR``.
    """
    return _ensure_dir(USER_DATA_ROOT)


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

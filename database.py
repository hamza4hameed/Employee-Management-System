import datetime
import hashlib
import hmac
import os
import secrets
import sqlite3
from typing import List, Optional, Dict, Any, Tuple

from app_paths import get_database_path, get_backup_dir
from logger import logger

DB_PATH = get_database_path()

DEFAULT_DEPARTMENTS = [
    ("Engineering", "Software development, QA, and technical infrastructure"),
    ("Product & Design", "Product management, UI/UX design, and research"),
    ("Data Science & AI", "Machine learning, data analytics, and business intelligence"),
    ("Cybersecurity", "Information security, compliance, and systems defense"),
    ("Operations & IT", "IT support, devops, and facilities management"),
    ("Marketing & Sales", "Brand growth, marketing campaigns, and client acquisition"),
    ("Human Resources", "People operations, talent acquisition, and employee relations"),
    ("Finance", "Financial planning, accounting, and payroll oversight"),
    ("Legal", "Corporate governance, contracts, and legal compliance"),
    ("Support", "Customer success and technical helpdesk services"),
]

EMPLOYEE_STATUSES = ["Active", "Inactive", "On Leave", "Terminated", "Probation"]


def _get_connection(db_file: Optional[str] = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_file or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db(db_file: Optional[str] = None) -> None:
    """Initialize SQLite database schema and run safe backward-compatible migrations."""
    conn = _get_connection(db_file)
    try:
        # 1. Users Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                must_change_password INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        # Migration: Add must_change_password column if it doesn't exist
        user_cols = [c["name"] for c in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "must_change_password" not in user_cols:
            logger.info("Migrating users table: adding 'must_change_password' column...")
            conn.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
            logger.info("Migration complete: 'must_change_password' column added.")

        # 2. Employees Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                emp_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                department TEXT NOT NULL,
                position TEXT NOT NULL,
                salary REAL NOT NULL,
                hire_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Active'
            )
            """
        )

        # Migration: Check if 'status' column exists in employees table
        emp_cols = [c["name"] for c in conn.execute("PRAGMA table_info(employees)").fetchall()]
        if "status" not in emp_cols:
            logger.info("Migrating employees table: adding 'status' column...")
            conn.execute("ALTER TABLE employees ADD COLUMN status TEXT NOT NULL DEFAULT 'Active'")
            logger.info("Migration complete: 'status' column added with default 'Active'.")

        # 3. Departments Table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )

        # Seed departments table with presets & existing employee departments
        for dept_name, dept_desc in DEFAULT_DEPARTMENTS:
            conn.execute(
                "INSERT OR IGNORE INTO departments (name, description) VALUES (?, ?)",
                (dept_name, dept_desc),
            )

        # Also pull any existing distinct department names from employee records
        existing_emp_depts = conn.execute(
            "SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != ''"
        ).fetchall()
        for row in existing_emp_depts:
            dept_name = row["department"]
            if dept_name:
                conn.execute(
                    "INSERT OR IGNORE INTO departments (name, description) VALUES (?, ?)",
                    (dept_name, f"Department for {dept_name}"),
                )

        # Performance indexes for large datasets
        conn.execute("CREATE INDEX IF NOT EXISTS idx_emp_department ON employees (department COLLATE NOCASE)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_emp_status ON employees (status COLLATE NOCASE)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_emp_name ON employees (name COLLATE NOCASE)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_emp_email ON employees (email COLLATE NOCASE)")

        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to initialize database: %s", exc, exc_info=True)
        raise
    finally:
        conn.close()


_PBKDF2_ITERATIONS = 100_000
_LEGACY_PBKDF2_ITERATIONS = 600_000


def _hash_password(password: str, salt: Optional[str] = None, iterations: int = _PBKDF2_ITERATIONS) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a random salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations
    )
    return "{}${}${}".format(salt, iterations, key.hex())


def _verify_password(stored_hash: str, password: str) -> Tuple[bool, bool]:
    """Constant-time comparison of a stored hash against candidate password.

    Returns:
        (is_valid, needs_upgrade): Tuple of booleans.
    """
    if not stored_hash or not password:
        return False, False
    if "$" not in stored_hash:
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        is_valid = hmac.compare_digest(stored_hash, legacy)
        return is_valid, True

    parts = stored_hash.split("$")
    if len(parts) == 3:
        salt, iters_str, hash_val = parts
        try:
            iters = int(iters_str)
        except ValueError:
            iters = _PBKDF2_ITERATIONS
        key = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), iters
        )
        is_valid = hmac.compare_digest(hash_val, key.hex())
        return is_valid, (iters != _PBKDF2_ITERATIONS)
    elif len(parts) == 2:
        salt, hash_val = parts
        # Fast path: try standard 100,000 iterations first
        key_100k = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), _PBKDF2_ITERATIONS
        )
        if hmac.compare_digest(hash_val, key_100k.hex()):
            return True, True
        # Legacy fallback: try 600,000 iterations
        key_600k = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), _LEGACY_PBKDF2_ITERATIONS
        )
        if hmac.compare_digest(hash_val, key_600k.hex()):
            return True, True
        return False, False

    return False, False


def insert_default_admin(
    username: str = "admin",
    password: Optional[str] = None,
    role: str = "admin",
    force_first_run_setup: bool = True,
) -> None:
    """Insert the default admin account if it does not already exist.

    For fresh installations, creates admin with a locked temporary password
    that requires the user to set their own password on first launch.

    Args:
        username: Admin username (default: "admin")
        password: Optional password. If None, uses first-run setup flow.
        role: User role (default: "admin")
        force_first_run_setup: If True, requires password setup on first launch.
                               If False, uses legacy behavior with env var fallback.
    """
    conn = _get_connection()
    try:
        existing = conn.execute(
            "SELECT id, must_change_password FROM users WHERE LOWER(username) = LOWER(?)",
            (username.strip(),)
        ).fetchone()

        if existing is None:
            # No admin exists - create with first-run setup requirement
            if password is not None:
                # Explicit password provided - use it
                password_hash = _hash_password(password)
                must_change = 0
            elif force_first_run_setup:
                # First-run setup: create with unusable random password
                # User must set their own password before login
                import secrets
                temp_password = secrets.token_urlsafe(32)
                password_hash = _hash_password(temp_password)
                must_change = 1
                logger.info("Admin account created. First-run password setup required.")
            else:
                # Legacy fallback mode (for automated deployments)
                fallback = os.environ.get("EMS_ADMIN_PASSWORD", "admin123")
                password_hash = _hash_password(fallback)
                must_change = 0
                logger.warning("Admin account created with fallback password. Change immediately in production.")

            conn.execute(
                "INSERT INTO users (username, password_hash, role, must_change_password) VALUES (?, ?, ?, ?)",
                (username, password_hash, role, must_change),
            )
            conn.commit()
        else:
            # Admin already exists - check if migration is needed
            # If must_change_password column is NULL or missing, set to 0 (no change required)
            if existing["must_change_password"] is None:
                conn.execute(
                    "UPDATE users SET must_change_password = 0 WHERE id = ?",
                    (existing["id"],)
                )
                conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to insert default admin: %s", exc, exc_info=True)
        raise
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Retrieve a user row by username."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, role, must_change_password FROM users WHERE LOWER(username) = LOWER(?)",
            (username.strip(),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def admin_requires_password_setup() -> bool:
    """Check if the admin account requires first-run password setup."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT must_change_password FROM users WHERE LOWER(username) = 'admin'"
        ).fetchone()
        if row is None:
            # No admin exists yet - will be created on startup
            return False
        return bool(row["must_change_password"])
    finally:
        conn.close()


def set_admin_password(password: str, username: str = "admin") -> bool:
    """Set the admin password and clear the must_change_password flag.
    
    Used during first-run setup to establish the admin password.
    
    Args:
        password: The new password to set
        username: Admin username (default: "admin")
        
    Returns:
        True if password was set successfully, False otherwise
    """
    if not password or len(password) < 8:
        logger.warning("Password too short - minimum 8 characters required")
        return False
    
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE LOWER(username) = LOWER(?)",
            (_hash_password(password), username.strip()),
        )
        conn.commit()
        success = cursor.rowcount > 0
        if success:
            logger.info("Admin password set successfully for user '%s'", username)
        return success
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to set admin password: %s", exc, exc_info=True)
        return False
    finally:
        conn.close()


def change_user_password(user_id: int, current_password: str, new_password: str) -> Tuple[bool, str]:
    """Change a user's password after verifying the current password.
    
    Args:
        user_id: The ID of the user whose password to change
        current_password: The user's current password (for verification)
        new_password: The new password to set
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not new_password or len(new_password) < 8:
        return False, "New password must be at least 8 characters long."
    
    conn = _get_connection()
    try:
        # Get current user info
        row = conn.execute(
            "SELECT username, password_hash FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        
        if row is None:
            return False, "User not found."
        
        username = row["username"]
        stored_hash = row["password_hash"]
        
        # Verify current password
        is_valid, _ = _verify_password(stored_hash, current_password)
        if not is_valid:
            return False, "Current password is incorrect."
        
        # Check new password is different from current
        is_same, _ = _verify_password(stored_hash, new_password)
        if is_same:
            return False, "New password must be different from the current password."
        
        # Update password
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
            (_hash_password(new_password), user_id),
        )
        conn.commit()
        logger.info("Password changed successfully for user '%s'", username)
        return True, "Password changed successfully."
        
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to change password for user %s: %s", user_id, exc, exc_info=True)
        return False, "An error occurred while changing the password."
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Backup, Safe Restore & System Stats
# ---------------------------------------------------------------------------
def create_backup(target_path: str) -> bool:
    """Perform a native SQLite online backup to target_path safely."""
    dest_dir = os.path.dirname(os.path.abspath(target_path))
    os.makedirs(dest_dir, exist_ok=True)

    source_conn = _get_connection()
    dest_conn = sqlite3.connect(target_path)
    try:
        source_conn.backup(dest_conn)
        dest_conn.close()
        logger.info("Database backup created successfully at '%s'", target_path)
        return True
    except Exception as exc:
        logger.error("Database backup failed: %s", exc, exc_info=True)
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
            except Exception:
                pass
        raise
    finally:
        source_conn.close()


def validate_backup(backup_path: str) -> Tuple[bool, str, Dict[str, Any]]:
    """Inspect and validate a backup database file before restore.

    Returns (is_valid, message, metadata_dict).
    """
    if not os.path.isfile(backup_path):
        return False, "Selected backup file does not exist on disk.", {}

    if os.path.getsize(backup_path) == 0:
        return False, "Selected file is empty (0 bytes).", {}

    conn = None
    try:
        conn = sqlite3.connect(f"file:{backup_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        # 1. Integrity check
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            return False, f"Database integrity check failed: {integrity[0] if integrity else 'unknown error'}", {}

        # 2. Schema check: must have required tables
        tables_res = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = {t["name"] for t in tables_res}

        required_tables = {"users", "employees", "departments"}
        missing_tables = required_tables - table_names
        if missing_tables:
            return False, f"Backup file is missing required tables: {', '.join(sorted(missing_tables))}.", {}

        # 3. Read metadata counts
        emp_count = conn.execute("SELECT COUNT(*) AS c FROM employees").fetchone()["c"]
        dept_count = conn.execute("SELECT COUNT(*) AS c FROM departments").fetchone()["c"]
        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]

        meta = {
            "file_size": os.path.getsize(backup_path),
            "employee_count": emp_count,
            "department_count": dept_count,
            "user_count": user_count,
            "modified_time": datetime.datetime.fromtimestamp(os.path.getmtime(backup_path)).strftime("%Y-%m-%d %H:%M:%S"),
        }
        return True, "Backup file passed all integrity and schema checks.", meta
    except sqlite3.DatabaseError as exc:
        return False, f"Invalid database format: {exc}", {}
    except Exception as exc:
        return False, f"Validation error: {exc}", {}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def restore_backup(backup_path: str, create_pre_restore_snapshot: bool = True) -> Tuple[bool, str]:
    """Atomically restore active database from a validated backup file."""
    is_valid, val_msg, meta = validate_backup(backup_path)
    if not is_valid:
        return False, f"Cannot restore: {val_msg}"

    # 1. Create safety snapshot in user backups directory
    snapshot_path = None
    if create_pre_restore_snapshot and os.path.isfile(DB_PATH):
        try:
            snap_dir = get_backup_dir()
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_path = os.path.abspath(os.path.join(snap_dir, f"pre_restore_auto_snapshot_{ts}.db"))
            create_backup(snapshot_path)
            logger.info("Pre-restore safety snapshot created at '%s'", snapshot_path)
        except Exception as exc:
            logger.warning("Could not create pre-restore safety snapshot: %s", exc)

    # 2. Perform online restore from backup to live database
    backup_conn = None
    live_conn = None
    try:
        backup_conn = sqlite3.connect(backup_path)
        live_conn = _get_connection()
        backup_conn.backup(live_conn)

        # Run init_db to ensure any triggers / migrations are current
        init_db()

        success_msg = f"Database restored successfully ({meta.get('employee_count', 0)} employees, {meta.get('department_count', 0)} departments)."
        if snapshot_path:
            success_msg += f"\n\nA safety snapshot of your previous database was saved to:\n{os.path.basename(snapshot_path)}"
        logger.info("Database restore completed successfully from '%s'", backup_path)
        return True, success_msg
    except Exception as exc:
        logger.error("Restore failed: %s", exc, exc_info=True)
        return False, f"Database restore failed: {exc}"
    finally:
        if backup_conn is not None:
            try:
                backup_conn.close()
            except Exception:
                pass
        if live_conn is not None:
            try:
                live_conn.close()
            except Exception:
                pass


def clear_all_data(
    db_file: Optional[str] = None,
    preserve_users: bool = True,
    reset_default_depts: bool = True,
) -> Tuple[bool, str, Dict[str, int]]:
    """Delete all records from employees and departments, reset sequences, and reclaim space.

    By default, preserves user login accounts so the administrator does not get locked out.
    """
    conn = _get_connection(db_file)
    try:
        cur = conn.cursor()
        emp_count = cur.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
        dept_count = cur.execute("SELECT COUNT(*) FROM departments").fetchone()[0]

        cur.execute("DELETE FROM employees")
        cur.execute("DELETE FROM departments")
        try:
            cur.execute("DELETE FROM sqlite_sequence WHERE name IN ('employees', 'departments')")
        except Exception:
            pass

        if reset_default_depts:
            cur.executemany(
                "INSERT INTO departments (name, description) VALUES (?, ?)",
                DEFAULT_DEPARTMENTS,
            )

        if not preserve_users:
            cur.execute("DELETE FROM users")
            try:
                cur.execute("DELETE FROM sqlite_sequence WHERE name = 'users'")
            except Exception:
                pass

        conn.commit()
        conn.close()

        # Reclaim disk space via VACUUM
        try:
            vac_conn = sqlite3.connect(db_file or DB_PATH)
            vac_conn.execute("VACUUM")
            vac_conn.close()
        except Exception as vac_err:
            logger.warning("VACUUM after clear_all_data non-fatal warning: %s", vac_err)

        msg = f"Successfully purged {emp_count:,} employee records and reset departments."
        logger.info(msg)
        return True, msg, {"employees": emp_count, "departments": dept_count}
    except Exception as exc:
        conn.rollback()
        conn.close()
        err_msg = f"Failed to clear database data: {exc}"
        logger.error(err_msg, exc_info=True)
        return False, err_msg, {"employees": 0, "departments": 0}


def get_database_stats() -> Dict[str, Any]:
    """Return live metrics and statistics about the active SQLite database."""
    size_bytes = os.path.getsize(DB_PATH) if os.path.isfile(DB_PATH) else 0
    size_mb = size_bytes / (1024 * 1024)

    emp_count = 0
    dept_count = 0
    user_count = 0
    sqlite_ver = sqlite3.sqlite_version

    try:
        conn = _get_connection()
        emp_count = conn.execute("SELECT COUNT(*) AS c FROM employees").fetchone()["c"]
        dept_count = conn.execute("SELECT COUNT(*) AS c FROM departments").fetchone()["c"]
        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        conn.close()
    except Exception as exc:
        logger.warning("Could not fetch full DB stats: %s", exc)

    return {
        "db_path": DB_PATH,
        "size_bytes": size_bytes,
        "size_str": f"{size_mb:.2f} MB" if size_mb >= 1.0 else f"{size_bytes / 1024:.1f} KB",
        "employee_count": emp_count,
        "department_count": dept_count,
        "user_count": user_count,
        "sqlite_version": sqlite_ver,
    }


# ---------------------------------------------------------------------------
# Department Management
# ---------------------------------------------------------------------------
def get_all_departments() -> List[Dict[str, Any]]:
    """Return all departments along with the total count of assigned employees."""
    conn = _get_connection()
    try:
        sql = """
        SELECT d.id, d.name, d.description, d.created_at,
               COUNT(e.id) AS employee_count
        FROM departments d
        LEFT JOIN employees e ON LOWER(e.department) = LOWER(d.name)
        GROUP BY d.id, d.name, d.description, d.created_at
        ORDER BY d.name COLLATE NOCASE ASC
        """
        rows = conn.execute(sql).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.error("Error fetching all departments: %s", exc, exc_info=True)
        raise
    finally:
        conn.close()


def get_department_by_id(dept_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, description, created_at FROM departments WHERE id = ?",
            (dept_id,),
        ).fetchone()
        return dict(row) if row else None
    except Exception as exc:
        logger.error("Error fetching department id %s: %s", dept_id, exc, exc_info=True)
        raise
    finally:
        conn.close()


def get_department_by_name(name: str) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, description, created_at FROM departments WHERE LOWER(name) = LOWER(?)",
            (name.strip(),),
        ).fetchone()
        return dict(row) if row else None
    except Exception as exc:
        logger.error("Error fetching department by name '%s': %s", name, exc, exc_info=True)
        raise
    finally:
        conn.close()


def department_name_exists(name: str, exclude_id: Optional[int] = None) -> bool:
    conn = _get_connection()
    try:
        if exclude_id is not None:
            row = conn.execute(
                "SELECT id FROM departments WHERE LOWER(name) = LOWER(?) AND id != ?",
                (name.strip(), exclude_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM departments WHERE LOWER(name) = LOWER(?)",
                (name.strip(),),
            ).fetchone()
        return row is not None
    except Exception as exc:
        logger.error("Error checking department name '%s': %s", name, exc, exc_info=True)
        return False
    finally:
        conn.close()


def add_department(name: str, description: str = "") -> int:
    conn = _get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO departments (name, description) VALUES (?, ?)",
            (name.strip(), description.strip()),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as exc:
        conn.rollback()
        logger.error("Error adding department '%s': %s", name, exc, exc_info=True)
        raise
    finally:
        conn.close()


def update_department(dept_id: int, new_name: str, description: str = "") -> bool:
    """Update department info and safely cascade name changes to associated employees."""
    conn = _get_connection()
    try:
        current = conn.execute(
            "SELECT name FROM departments WHERE id = ?", (dept_id,)
        ).fetchone()
        if not current:
            return False

        old_name = current["name"]
        clean_new_name = new_name.strip()

        # Update department
        cursor = conn.execute(
            "UPDATE departments SET name = ?, description = ? WHERE id = ?",
            (clean_new_name, description.strip(), dept_id),
        )

        # If renamed (even case changes), cascade to employees with old department name
        if old_name != clean_new_name:
            conn.execute(
                "UPDATE employees SET department = ? WHERE LOWER(department) = LOWER(?)",
                (clean_new_name, old_name),
            )

        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        conn.rollback()
        logger.error("Error updating department id %s: %s", dept_id, exc, exc_info=True)
        raise
    finally:
        conn.close()


def delete_department(dept_id: int, reassign_to: Optional[str] = None) -> bool:
    """Delete department, optionally reassigning existing employees to another department."""
    conn = _get_connection()
    try:
        dept = conn.execute(
            "SELECT name FROM departments WHERE id = ?", (dept_id,)
        ).fetchone()
        if not dept:
            return False

        dept_name = dept["name"]

        # Reassign employees if target department provided, otherwise fallback to 'Unassigned'
        if reassign_to:
            clean_reassign = reassign_to.strip()
            conn.execute(
                "INSERT OR IGNORE INTO departments (name, description) VALUES (?, ?)",
                (clean_reassign, f"Department for {clean_reassign}"),
            )
            conn.execute(
                "UPDATE employees SET department = ? WHERE LOWER(department) = LOWER(?)",
                (clean_reassign, dept_name),
            )
        else:
            conn.execute(
                "INSERT OR IGNORE INTO departments (name, description) VALUES ('Unassigned', 'Employees without an assigned department')",
            )
            conn.execute(
                "UPDATE employees SET department = 'Unassigned' WHERE LOWER(department) = LOWER(?)",
                (dept_name,),
            )

        cursor = conn.execute("DELETE FROM departments WHERE id = ?", (dept_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        conn.rollback()
        logger.error("Error deleting department id %s: %s", dept_id, exc, exc_info=True)
        raise
    finally:
        conn.close()


def get_departments() -> List[str]:
    """Return a sorted list of all active department names."""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT name FROM departments ORDER BY name COLLATE NOCASE ASC"
        ).fetchall()
        depts = [r["name"] for r in rows if r["name"]]
        if not depts:
            rows = conn.execute(
                "SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' ORDER BY department ASC"
            ).fetchall()
            depts = [r["department"] for r in rows if r["department"]]
        return depts
    except Exception as exc:
        logger.error("Error fetching department names: %s", exc, exc_info=True)
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Employee Management
# ---------------------------------------------------------------------------
def add_employee(
    emp_code: str,
    name: str,
    email: str,
    department: str,
    position: str,
    salary: float,
    hire_date: str,
    status: str = "Active",
) -> int:
    conn = _get_connection()
    try:
        dept_clean = department.strip()
        conn.execute(
            "INSERT OR IGNORE INTO departments (name, description) VALUES (?, ?)",
            (dept_clean, f"Department for {dept_clean}"),
        )
        cursor = conn.execute(
            """
            INSERT INTO employees (emp_code, name, email, department, position, salary, hire_date, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                emp_code.strip(),
                name.strip(),
                email.strip(),
                dept_clean,
                position.strip(),
                float(salary),
                hire_date.strip(),
                status.strip() if status else "Active",
            ),
        )
        conn.commit()
        return cursor.lastrowid
    except Exception as exc:
        conn.rollback()
        logger.error("Error adding employee '%s': %s", emp_code, exc, exc_info=True)
        raise
    finally:
        conn.close()


def get_all_employees() -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, emp_code, name, email, department, position, salary, hire_date, status
            FROM employees
            ORDER BY id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.error("Error fetching all employees: %s", exc, exc_info=True)
        raise
    finally:
        conn.close()


def get_employee_by_id(emp_id: int) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT id, emp_code, name, email, department, position, salary, hire_date, status "
            "FROM employees WHERE id = ?",
            (emp_id,),
        ).fetchone()
        return dict(row) if row else None
    except Exception as exc:
        logger.error("Error fetching employee by id %s: %s", emp_id, exc, exc_info=True)
        raise
    finally:
        conn.close()


def get_employee_by_code(emp_code: str) -> Optional[Dict[str, Any]]:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT id, emp_code, name, email, department, position, salary, hire_date, status "
            "FROM employees WHERE LOWER(emp_code) = LOWER(?)",
            (emp_code.strip(),),
        ).fetchone()
        return dict(row) if row else None
    except Exception as exc:
        logger.error("Error fetching employee by code '%s': %s", emp_code, exc, exc_info=True)
        raise
    finally:
        conn.close()


def employee_code_exists(emp_code: str, exclude_id: Optional[int] = None) -> bool:
    conn = _get_connection()
    try:
        if exclude_id is not None:
            row = conn.execute(
                "SELECT id FROM employees WHERE LOWER(emp_code) = LOWER(?) AND id != ?",
                (emp_code.strip(), exclude_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT id FROM employees WHERE LOWER(emp_code) = LOWER(?)",
                (emp_code.strip(),),
            ).fetchone()
        return row is not None
    except Exception as exc:
        logger.error("Error checking employee code existence '%s': %s", emp_code, exc, exc_info=True)
        return False
    finally:
        conn.close()


def update_employee(
    emp_id: int,
    emp_code: str,
    name: str,
    email: str,
    department: str,
    position: str,
    salary: float,
    hire_date: str,
    status: str = "Active",
) -> bool:
    conn = _get_connection()
    try:
        dept_clean = department.strip()
        conn.execute(
            "INSERT OR IGNORE INTO departments (name, description) VALUES (?, ?)",
            (dept_clean, f"Department for {dept_clean}"),
        )
        cursor = conn.execute(
            """
            UPDATE employees
            SET emp_code = ?, name = ?, email = ?, department = ?, position = ?, salary = ?, hire_date = ?, status = ?
            WHERE id = ?
            """,
            (
                emp_code.strip(),
                name.strip(),
                email.strip(),
                dept_clean,
                position.strip(),
                float(salary),
                hire_date.strip(),
                status.strip() if status else "Active",
                emp_id,
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        conn.rollback()
        logger.error("Error updating employee id %s: %s", emp_id, exc, exc_info=True)
        raise
    finally:
        conn.close()


def delete_employee(emp_id: int) -> bool:
    conn = _get_connection()
    try:
        cursor = conn.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        conn.rollback()
        logger.error("Error deleting employee id %s: %s", emp_id, exc, exc_info=True)
        raise
    finally:
        conn.close()


def search_employees(
    query: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        sql = "SELECT id, emp_code, name, email, department, position, salary, hire_date, status FROM employees WHERE 1=1"
        params: List[Any] = []

        if query:
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like = "%{}%".format(escaped)
            sql += (" AND (emp_code LIKE ? ESCAPE '\\' OR name LIKE ? ESCAPE '\\'"
                    " OR email LIKE ? ESCAPE '\\' OR position LIKE ? ESCAPE '\\'"
                    " OR department LIKE ? ESCAPE '\\')")
            params.extend([like, like, like, like, like])

        if department:
            sql += " AND LOWER(department) = LOWER(?)"
            params.append(department.strip())

        if status:
            sql += " AND LOWER(status) = LOWER(?)"
            params.append(status.strip())

        sql += " ORDER BY id ASC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        logger.error("Error searching employees (query=%s, dept=%s, status=%s): %s", query, department, status, exc, exc_info=True)
        raise
    finally:
        conn.close()


def _build_search_where(
    query: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
) -> tuple:
    """Build reusable WHERE clause + params for employee search."""
    clauses: List[str] = []
    params: List[Any] = []
    if query:
        # Sanitize query string to prevent LIKE injection
        safe_query = query.strip()
        # Use SQLite parameterized LIKE with proper escaping
        like_pattern = f"%{safe_query}%"
        clauses.append(
            "(emp_code LIKE ? ESCAPE '\\' OR name LIKE ? ESCAPE '\\'"
            " OR email LIKE ? ESCAPE '\\' OR position LIKE ? ESCAPE '\\'"
            " OR department LIKE ? ESCAPE '\\')"
        )
        params.extend([like_pattern, like_pattern, like_pattern, like_pattern, like_pattern])
    if department:
        clauses.append("LOWER(department) = LOWER(?)")
        params.append(department.strip())
    if status:
        clauses.append("LOWER(status) = LOWER(?)")
        params.append(status.strip())
    where = (" AND " + " AND ".join(clauses)) if clauses else ""
    return where, params


def search_employees_paginated(
    query: Optional[str] = None,
    department: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 0,
    page_size: int = 100,
) -> tuple:
    """Return (rows, total_count) for a single page of results.

    Uses SQL LIMIT/OFFSET to avoid transferring hundreds of thousands of rows.
    """
    conn = _get_connection()
    try:
        where, params = _build_search_where(query, department, status)

        # Total count for the current filter
        count_sql = "SELECT COUNT(*) FROM employees WHERE 1=1" + where
        total = conn.execute(count_sql, params).fetchone()[0]

        # Fetch only the requested page
        data_sql = (
            "SELECT id, emp_code, name, email, department, position, salary, hire_date, status "
            "FROM employees WHERE 1=1" + where +
            " ORDER BY id ASC LIMIT ? OFFSET ?"
        )
        offset = page * page_size
        rows = conn.execute(data_sql, params + [page_size, offset]).fetchall()
        return [dict(row) for row in rows], total
    except Exception as exc:
        logger.error(
            "Error in paginated search (query=%s, dept=%s, status=%s, page=%s): %s",
            query, department, status, page, exc, exc_info=True,
        )
        raise
    finally:
        conn.close()


def get_analytics_stats_sql() -> Dict[str, Any]:
    """Compute dashboard statistics entirely in SQL — avoids transferring 395K+ rows to Python.

    Returns a dict with the same shape as the old _compute_stats() helper.
    """
    conn = _get_connection()
    try:
        # 1. Global counts by status
        status_rows = conn.execute(
            "SELECT COALESCE(status, 'Active') AS status, COUNT(*) AS cnt FROM employees GROUP BY status"
        ).fetchall()
        by_status: Dict[str, int] = {r["status"]: r["cnt"] for r in status_rows}
        total = sum(by_status.values())
        active = by_status.get("Active", 0)
        inactive = by_status.get("Inactive", 0) + by_status.get("Terminated", 0)
        on_leave = total - active - inactive

        # 2. Global salary stats
        sal_row = conn.execute(
            "SELECT COALESCE(SUM(salary), 0) AS total_sal, "
            "COALESCE(AVG(salary), 0) AS avg_sal, "
            "COALESCE(MIN(salary), 0) AS min_sal, "
            "COALESCE(MAX(salary), 0) AS max_sal "
            "FROM employees"
        ).fetchone()
        total_salary = float(sal_row["total_sal"])
        avg_salary = float(sal_row["avg_sal"])
        min_salary = float(sal_row["min_sal"])
        max_salary = float(sal_row["max_sal"])

        # 3. Per-department stats
        dept_rows = conn.execute(
            "SELECT COALESCE(department, 'Unassigned') AS dept, "
            "COUNT(*) AS cnt, COALESCE(SUM(salary), 0) AS total_sal, "
            "COALESCE(AVG(salary), 0) AS avg_sal, COALESCE(MIN(salary), 0) AS min_sal, COALESCE(MAX(salary), 0) AS max_sal "
            "FROM employees GROUP BY department ORDER BY cnt DESC"
        ).fetchall()
        num_depts = len(dept_rows)
        dept_stats = []
        for r in dept_rows:
            dept_stats.append({
                "dept": r["dept"],
                "count": r["cnt"],
                "pct": round(r["cnt"] / total * 100, 1) if total else 0.0,
                "total_sal": float(r["total_sal"] or 0.0),
                "avg_sal": float(r["avg_sal"] or 0.0),
                "min_sal": float(r["min_sal"] or 0.0),
                "max_sal": float(r["max_sal"] or 0.0),
            })

        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "on_leave": on_leave,
            "num_depts": num_depts,
            "total_salary": total_salary,
            "avg_salary": avg_salary,
            "min_salary": min_salary,
            "max_salary": max_salary,
            "dept_stats": dept_stats,
            "by_status": by_status,
        }
    except Exception as exc:
        logger.error("Error computing analytics stats: %s", exc, exc_info=True)
        raise
    finally:
        conn.close()


def verify_login(
    username: str, password: str
) -> Optional[Tuple[int, str, str]]:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, role, password_hash FROM users WHERE LOWER(username) = LOWER(?)",
            (username.strip(),),
        ).fetchone()
        if row is None:
            return None
        is_valid, needs_upgrade = _verify_password(row["password_hash"], password)
        if is_valid:
            if needs_upgrade:
                try:
                    new_hash = _hash_password(password)
                    conn.execute(
                        "UPDATE users SET password_hash = ? WHERE id = ?",
                        (new_hash, row["id"]),
                    )
                    conn.commit()
                except Exception as exc:
                    logger.warning("Could not auto-migrate password hash for user %s: %s", username, exc)
            return (row["id"], row["username"], row["role"])
        return None
    except Exception as exc:
        logger.error("Error during verify_login for user '%s': %s", username, exc, exc_info=True)
        raise
    finally:
        conn.close()


def add_employees_batch(employees: List[Dict[str, Any]]) -> int:
    conn = _get_connection()
    try:
        # Pre-register any new departments from the batch
        distinct_depts = {emp["department"].strip() for emp in employees if emp.get("department")}
        for d in distinct_depts:
            conn.execute(
                "INSERT OR IGNORE INTO departments (name, description) VALUES (?, ?)",
                (d, f"Department for {d}"),
            )
        inserted = 0
        for emp in employees:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO employees (emp_code, name, email, department, position, salary, hire_date, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    emp["emp_code"], emp["name"], emp["email"],
                    emp["department"], emp["position"], emp["salary"],
                    emp["hire_date"], emp.get("status", "Active"),
                ),
            )
            if cursor.rowcount > 0:
                inserted += 1
        conn.commit()
        return inserted
    except Exception as exc:
        conn.rollback()
        logger.error("Batch insert failed; rolled back transaction: %s", exc, exc_info=True)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    insert_default_admin()
    print("Database initialized and default admin inserted successfully.")

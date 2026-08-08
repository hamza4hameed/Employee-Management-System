import sqlite3
import hashlib
from typing import List, Optional, Dict, Any, Tuple

DB_PATH = "employee_system.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = _get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user'
            )
            """
        )
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
                hire_date TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def insert_default_admin(
    username: str = "admin",
    password: str = "admin123",
    role: str = "admin",
) -> None:
    conn = _get_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, _hash_password(password), role),
            )
            conn.commit()
    finally:
        conn.close()


def add_employee(
    emp_code: str,
    name: str,
    email: str,
    department: str,
    position: str,
    salary: float,
    hire_date: str,
) -> int:
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO employees (emp_code, name, email, department, position, salary, hire_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (emp_code, name, email, department, position, salary, hire_date),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_all_employees() -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, emp_code, name, email, department, position, salary, hire_date
            FROM employees
            ORDER BY id
            """
        ).fetchall()
        return [dict(row) for row in rows]
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
) -> bool:
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            UPDATE employees
            SET emp_code = ?, name = ?, email = ?, department = ?, position = ?, salary = ?, hire_date = ?
            WHERE id = ?
            """,
            (emp_code, name, email, department, position, salary, hire_date, emp_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def delete_employee(emp_id: int) -> bool:
    conn = _get_connection()
    try:
        cursor = conn.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def search_employees(
    query: Optional[str] = None,
    department: Optional[str] = None,
) -> List[Dict[str, Any]]:
    conn = _get_connection()
    try:
        sql = "SELECT id, emp_code, name, email, department, position, salary, hire_date FROM employees WHERE 1=1"
        params: List[Any] = []

        if query:
            like = f"%{query}%"
            sql += " AND (emp_code LIKE ? OR name LIKE ? OR email LIKE ? OR position LIKE ?)"
            params.extend([like, like, like, like])

        if department:
            sql += " AND department = ?"
            params.append(department)

        sql += " ORDER BY id"
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def verify_login(
    username: str, password: str
) -> Optional[Tuple[int, str, str]]:
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, role, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if row is None:
            return None
        if row["password_hash"] == _hash_password(password):
            return (row["id"], row["username"], row["role"])
        return None
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    insert_default_admin()
    print("Database initialized and default admin inserted successfully.")

import csv
import math
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

import database
from database import EMPLOYEE_STATUSES
from logger import logger

REQUIRED_COLUMNS = {"emp_code", "name", "email", "department", "position", "salary", "hire_date"}
ACCEPTED_COLUMNS = REQUIRED_COLUMNS | {"id", "status"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
CODE_RE = re.compile(r"^[A-Za-z0-9_\-]{2,32}$")


class CsvImportError(Exception):
    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message)
        self.errors = errors or []


def _normalize_header(col: str) -> str:
    return col.strip().lower().replace(" ", "_").replace("-", "_")


def _sanitize_csv_value(val: Any) -> str:
    """Prefix formula-trigger characters to prevent CSV injection in spreadsheets."""
    s = str(val) if val is not None else ""
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + s
    return s


def export_table_to_csv(rows: List[Dict[str, Any]], path: str) -> int:
    fieldnames = ["id", "emp_code", "name", "email", "department", "position", "status", "salary", "hire_date"]
    written = 0
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: _sanitize_csv_value(r.get(k, "")) for k in fieldnames})
            written += 1
    return written


def _parse_flexible_date(raw: str) -> Tuple[Optional[str], Optional[str]]:
    """Flexibly parse a date string in various formats into standardized 'YYYY-MM-DD'."""
    s = raw.strip()
    if not s:
        return None, "hire_date is required."

    # Strip ISO time if present (e.g. '2023-05-12T14:30:00' or '2023-05-12 14:30:00')
    candidates = [s]
    if "T" in s:
        candidates.append(s.split("T")[0].strip())
    elif " " in s:
        parts = s.split()
        if len(parts) >= 2 and ":" in parts[-1]:
            candidates.append(" ".join(parts[:-1]).strip())

    # Common date formats
    formats = [
        "%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
        "%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y",
        "%m/%d/%Y", "%m-%d-%Y", "%m.%d.%Y",
        "%Y%m%d",
        "%d-%b-%Y", "%d/%b/%Y", "%d %b %Y", "%d %b, %Y",
        "%d-%B-%Y", "%d/%B/%Y", "%d %B %Y", "%d %B, %Y",
        "%b-%d-%Y", "%b/%d/%Y", "%b %d %Y", "%b %d, %Y",
        "%B-%d-%Y", "%B/%d/%Y", "%B %d %Y", "%B %d, %Y",
        "%b %d %Y", "%B %d %Y",
        "%Y-%b-%d", "%Y/%b/%d",
        "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S",
    ]

    parsed_dt = None
    for cand in candidates:
        for fmt in formats:
            try:
                parsed_dt = datetime.strptime(cand, fmt)
                break
            except ValueError:
                continue
        if parsed_dt is not None:
            break

    if parsed_dt is None:
        return None, f"hire_date '{raw}' is not recognized. Please use YYYY-MM-DD, DD/MM/YYYY, or MM/DD/YYYY."

    if parsed_dt.year < 1900 or parsed_dt.year > 2100:
        return None, f"hire_date year {parsed_dt.year} must be between 1900 and 2100."

    return parsed_dt.strftime("%Y-%m-%d"), None


def _validate_row(row: Dict[str, Any], line_no: int) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    clean: Dict[str, Any] = {}

    for k in ("emp_code", "name", "email", "department", "position", "hire_date", "status"):
        val = str(row.get(k) or "").strip()
        if val.startswith("'") and len(val) > 1 and val[1] in ('=', '+', '-', '@', '\t', '\r'):
            val = val[1:]
        clean[k] = val

    # Status defaults to 'Active' if omitted
    if not clean["status"]:
        clean["status"] = "Active"
    elif clean["status"].title() in EMPLOYEE_STATUSES:
        clean["status"] = clean["status"].title()

    # Salary
    raw_salary = row.get("salary")
    salary_parsed = None
    if raw_salary is None or str(raw_salary).strip() == "":
        errors.append("Line {}: salary is required.".format(line_no))
    else:
        try:
            raw_str = str(raw_salary).strip().replace("$", "").replace(",", "")
            if raw_str.startswith("'"):
                raw_str = raw_str[1:]
            salary_parsed = float(raw_str)
            if math.isnan(salary_parsed) or math.isinf(salary_parsed):
                raise ValueError("NaN or Infinity is not a valid salary")
            if salary_parsed < 0:
                errors.append("Line {}: salary must be non-negative.".format(line_no))
            elif salary_parsed > 100_000_000.0:
                errors.append("Line {}: salary exceeds maximum allowed value ($100,000,000).".format(line_no))
            clean["salary"] = salary_parsed
        except (TypeError, ValueError):
            errors.append("Line {}: salary '{}' is not a valid number.".format(line_no, raw_salary))

    # Employee code
    if not clean["emp_code"]:
        errors.append("Line {}: emp_code is required.".format(line_no))
    elif not CODE_RE.match(clean["emp_code"]):
        errors.append("Line {}: emp_code '{}' must be 2-32 alphanumeric characters (underscores and hyphens allowed).".format(line_no, clean["emp_code"]))

    # Name
    if not clean["name"]:
        errors.append("Line {}: name is required.".format(line_no))
    elif len(clean["name"]) > 100:
        errors.append("Line {}: name exceeds 100 characters.".format(line_no))

    # Email
    if not clean["email"]:
        errors.append("Line {}: email is required.".format(line_no))
    elif len(clean["email"]) > 120:
        errors.append("Line {}: email exceeds 120 characters.".format(line_no))
    elif not EMAIL_RE.match(clean["email"]):
        errors.append("Line {}: email '{}' is not a valid address.".format(line_no, clean["email"]))

    # Department & Position
    if not clean["department"]:
        errors.append("Line {}: department is required.".format(line_no))
    elif len(clean["department"]) > 60:
        errors.append("Line {}: department name exceeds 60 characters.".format(line_no))

    if not clean["position"]:
        errors.append("Line {}: position is required.".format(line_no))
    elif len(clean["position"]) > 80:
        errors.append("Line {}: position title exceeds 80 characters.".format(line_no))

    # Hire Date (flexible format support)
    formatted_date, date_err = _parse_flexible_date(clean["hire_date"])
    if date_err:
        errors.append(f"Line {line_no}: {date_err}")
    else:
        clean["hire_date"] = formatted_date

    return clean, errors


def _open_csv_file(path: str):
    """Open a CSV file with utf-8-sig, falling back to latin-1 if invalid UTF-8 bytes are encountered."""
    # Try UTF-8 first
    f = None
    try:
        f = open(path, "r", newline="", encoding="utf-8-sig")
        f.read(2048)  # Test reading
        f.seek(0)
        return f
    except UnicodeDecodeError:
        # Ensure the file is closed before trying latin-1
        if f is not None:
            try:
                f.close()
            except Exception:
                pass
        # Fall back to latin-1
        return open(path, "r", newline="", encoding="latin-1")


def import_csv_to_db(path: str, skip_duplicates: bool = True) -> Tuple[int, int, List[str]]:
    if not os.path.isfile(path):
        raise FileNotFoundError("CSV file not found: {}".format(path))

    with _open_csv_file(path) as f:
        reader = csv.reader(f)
        try:
            raw_header = next(reader)
        except StopIteration:
            raise CsvImportError("CSV file is empty.", [])

        header = [_normalize_header(c) for c in raw_header]
        header_set = set(header)
        missing = REQUIRED_COLUMNS - header_set
        if missing:
            raise CsvImportError(
                "CSV is missing required columns: {}.".format(", ".join(sorted(missing))),
                ["Missing columns: {}".format(", ".join(sorted(missing)))],
            )

        dict_reader = csv.DictReader(f, fieldnames=header)

        errors: List[str] = []
        inserted = 0
        skipped = 0
        seen_codes = set()

        conn = database._get_connection()
        try:
            for line_no, raw_row in enumerate(dict_reader, start=2):
                row = {_normalize_header(k): v for k, v in raw_row.items() if k is not None} if raw_row else {}
                clean, row_errors = _validate_row(row, line_no)
                if row_errors:
                    errors.extend(row_errors)
                    continue

                code = clean["emp_code"]
                if code in seen_codes:
                    if skip_duplicates:
                        skipped += 1
                        errors.append("Line {}: duplicate emp_code '{}' in CSV, skipped.".format(line_no, code))
                        continue
                    else:
                        errors.append("Line {}: duplicate emp_code '{}' in CSV.".format(line_no, code))
                        continue
                seen_codes.add(code)

                # Ensure department exists in departments table
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO departments (name, description) VALUES (?, ?)",
                        (clean["department"], f"Department for {clean['department']}"),
                    )
                except Exception:
                    pass

                try:
                    conn.execute(
                        "INSERT INTO employees (emp_code, name, email, department, position, salary, hire_date, status) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            clean["emp_code"], clean["name"], clean["email"],
                            clean["department"], clean["position"], float(clean["salary"]),
                            clean["hire_date"], clean.get("status", "Active"),
                        ),
                    )
                    inserted += 1
                except Exception as exc:
                    msg = str(exc)
                    if "UNIQUE" in msg.upper() and "EMP_CODE" in msg.upper():
                        if skip_duplicates:
                            skipped += 1
                            errors.append(
                                "Line {}: emp_code '{}' already exists in database, skipped.".format(line_no, code)
                            )
                        else:
                            errors.append(
                                "Line {}: emp_code '{}' already exists in database.".format(line_no, code)
                            )
                    else:
                        errors.append("Line {}: {}".format(line_no, msg))
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error("Error during CSV import transaction: %s", exc, exc_info=True)
            raise
        finally:
            conn.close()

    return inserted, skipped, errors


def import_csv_to_db_chunked(
    path: str,
    skip_duplicates: bool = True,
    chunk_size: int = 1000,
    progress_callback=None,
    is_cancelled=None,
) -> Tuple[int, int, List[str]]:
    """Import CSV with chunked commits and progress feedback.

    Args:
        path: Path to the CSV file.
        skip_duplicates: Skip rows with duplicate emp_code.
        chunk_size: Number of rows per commit batch.
        progress_callback: Called as callback(processed, total, inserted, skipped).
        is_cancelled: Callable that returns True if the user cancelled.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError("CSV file not found: {}".format(path))

    # Count total lines first (excluding header)
    total_lines = 0
    with _open_csv_file(path) as f:
        reader = csv.reader(f)
        try:
            raw_header = next(reader)
        except StopIteration:
            raise CsvImportError("CSV file is empty.", [])
        header = [_normalize_header(c) for c in raw_header]
        missing = REQUIRED_COLUMNS - set(header)
        if missing:
            raise CsvImportError(
                "CSV is missing required columns: {}.".format(", ".join(sorted(missing))),
                ["Missing columns: {}".format(", ".join(sorted(missing)))],
            )
        for _ in reader:
            total_lines += 1

    if total_lines == 0:
        return 0, 0, []

    # Now process with chunked commits
    errors: List[str] = []
    inserted = 0
    skipped = 0
    processed = 0
    seen_codes = set()

    with _open_csv_file(path) as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        dict_reader = csv.DictReader(f, fieldnames=header)

        conn = database._get_connection()
        try:
            batch_count = 0
            for line_no, raw_row in enumerate(dict_reader, start=2):
                if is_cancelled and is_cancelled():
                    conn.commit()  # commit what we have
                    break

                row = {_normalize_header(k): v for k, v in raw_row.items() if k is not None} if raw_row else {}
                clean, row_errors = _validate_row(row, line_no)
                if row_errors:
                    errors.extend(row_errors)
                    processed += 1
                    batch_count += 1
                    if batch_count >= chunk_size:
                        conn.commit()
                        batch_count = 0
                        if progress_callback:
                            progress_callback(processed, total_lines, inserted, skipped)
                    continue

                code = clean["emp_code"]
                if code in seen_codes:
                    if skip_duplicates:
                        skipped += 1
                        errors.append("Line {}: duplicate emp_code '{}' in CSV, skipped.".format(line_no, code))
                    processed += 1
                    batch_count += 1
                    if batch_count >= chunk_size:
                        conn.commit()
                        batch_count = 0
                        if progress_callback:
                            progress_callback(processed, total_lines, inserted, skipped)
                    continue
                seen_codes.add(code)

                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO departments (name, description) VALUES (?, ?)",
                        (clean["department"], f"Department for {clean['department']}"),
                    )
                except Exception:
                    pass

                try:
                    conn.execute(
                        "INSERT INTO employees (emp_code, name, email, department, position, salary, hire_date, status) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            clean["emp_code"], clean["name"], clean["email"],
                            clean["department"], clean["position"], float(clean["salary"]),
                            clean["hire_date"], clean.get("status", "Active"),
                        ),
                    )
                    inserted += 1
                except Exception as exc:
                    msg = str(exc)
                    if "UNIQUE" in msg.upper() and "EMP_CODE" in msg.upper():
                        if skip_duplicates:
                            skipped += 1
                            errors.append(
                                "Line {}: emp_code '{}' already exists in database, skipped.".format(line_no, code)
                            )
                        else:
                            errors.append(
                                "Line {}: emp_code '{}' already exists in database.".format(line_no, code)
                            )
                    else:
                        errors.append("Line {}: {}".format(line_no, msg))

                processed += 1
                batch_count += 1
                if batch_count >= chunk_size:
                    conn.commit()
                    batch_count = 0
                    if progress_callback:
                        progress_callback(processed, total_lines, inserted, skipped)

            # Final commit for remaining rows
            conn.commit()
            if progress_callback:
                progress_callback(processed, total_lines, inserted, skipped)
        except Exception as exc:
            conn.rollback()
            logger.error("Error during chunked CSV import: %s", exc, exc_info=True)
            raise
        finally:
            conn.close()

    return inserted, skipped, errors


def compute_department_aggregates(rows: List[Dict[str, Any]]) -> Tuple[List[str], List[int], List[float]]:
    buckets: Dict[str, Tuple[int, float]] = {}
    for r in rows:
        dept = (r.get("department") or "Uncategorized").strip() or "Uncategorized"
        try:
            raw_sal = str(r.get("salary") or "0").replace("$", "").replace(",", "").strip()
            salary = float(raw_sal)
            if math.isnan(salary) or math.isinf(salary) or salary < 0:
                salary = 0.0
        except (TypeError, ValueError):
            salary = 0.0
        count, total = buckets.get(dept, (0, 0.0))
        buckets[dept] = (count + 1, total + salary)

    departments = sorted(buckets.keys())
    counts = [buckets[d][0] for d in departments]
    avg_salaries = [
        round(buckets[d][1] / buckets[d][0], 2) if buckets[d][0] > 0 else 0.0
        for d in departments
    ]
    return departments, counts, avg_salaries


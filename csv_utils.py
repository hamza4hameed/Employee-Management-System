import csv
import os
import re
from typing import Dict, Any, List, Tuple

import database


REQUIRED_COLUMNS = {"emp_code", "name", "email", "department", "position", "salary", "hire_date"}
ACCEPTED_COLUMNS = REQUIRED_COLUMNS | {"id"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


class CsvImportError(Exception):
    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message)
        self.errors = errors or []


def _normalize_header(col: str) -> str:
    return col.strip().lower().replace(" ", "_").replace("-", "_")


def export_table_to_csv(rows: List[Dict[str, Any]], path: str) -> int:
    fieldnames = ["id", "emp_code", "name", "email", "department", "position", "salary", "hire_date"]
    written = 0
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
            written += 1
    return written


def _validate_row(row: Dict[str, Any], line_no: int) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    clean: Dict[str, Any] = {}

    for k in ("emp_code", "name", "email", "department", "position", "hire_date"):
        clean[k] = (row.get(k) or "").strip()

    raw_salary = row.get("salary")
    salary_parsed = None
    if raw_salary is None or str(raw_salary).strip() == "":
        errors.append("Line {}: salary is required.".format(line_no))
    else:
        try:
            raw_str = str(raw_salary).strip().replace("$", "").replace(",", "")
            salary_parsed = float(raw_str)
            if salary_parsed < 0:
                errors.append("Line {}: salary must be non-negative.".format(line_no))
            clean["salary"] = salary_parsed
        except (TypeError, ValueError):
            errors.append("Line {}: salary '{}' is not a valid number.".format(line_no, raw_salary))

    if not clean["emp_code"]:
        errors.append("Line {}: emp_code is required.".format(line_no))
    elif len(clean["emp_code"]) < 2:
        errors.append("Line {}: emp_code must be at least 2 characters.".format(line_no))

    if not clean["name"]:
        errors.append("Line {}: name is required.".format(line_no))

    if not clean["email"]:
        errors.append("Line {}: email is required.".format(line_no))
    elif not EMAIL_RE.match(clean["email"]):
        errors.append("Line {}: email '{}' is not a valid address.".format(line_no, clean["email"]))

    if not clean["department"]:
        errors.append("Line {}: department is required.".format(line_no))
    if not clean["position"]:
        errors.append("Line {}: position is required.".format(line_no))

    if not clean["hire_date"]:
        errors.append("Line {}: hire_date is required.".format(line_no))
    elif not DATE_RE.match(clean["hire_date"]):
        errors.append("Line {}: hire_date '{}' must be in YYYY-MM-DD format.".format(line_no, clean["hire_date"]))

    return clean, errors


def import_csv_to_db(path: str, skip_duplicates: bool = True) -> Tuple[int, int, List[str]]:
    if not os.path.isfile(path):
        raise FileNotFoundError("CSV file not found: {}".format(path))

    with open(path, "r", newline="", encoding="utf-8-sig") as f:
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

        dict_reader = csv.DictReader(
            (line for line in _iter_lines_no_header(f)),
            fieldnames=header,
        )

        errors: List[str] = []
        inserted = 0
        skipped = 0
        seen_codes = set()

        for line_no, raw_row in enumerate(dict_reader, start=2):
            row = {_normalize_header(k): v for k, v in raw_row.items()} if raw_row else {}
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

            try:
                database.add_employee(
                    emp_code=clean["emp_code"],
                    name=clean["name"],
                    email=clean["email"],
                    department=clean["department"],
                    position=clean["position"],
                    salary=clean["salary"],
                    hire_date=clean["hire_date"],
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

    return inserted, skipped, errors


def _iter_lines_no_header(f):
    for line in f:
        yield line


def compute_department_aggregates(rows: List[Dict[str, Any]]) -> Tuple[List[str], List[int], List[float]]:
    buckets: Dict[str, Tuple[int, float]] = {}
    for r in rows:
        dept = (r.get("department") or "Uncategorized").strip() or "Uncategorized"
        try:
            salary = float(r.get("salary") or 0.0)
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

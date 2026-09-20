# Employee Management System

A local, fully-offline Windows desktop application for managing employee records. Built with **Python 3.10+ / PyQt5 / matplotlib / SQLite**.

## Features

- Employee records: add, edit, delete, search, paginate
- Department management with cascading renames and safe deletion
- Live analytics dashboard with salary + headcount charts (matplotlib)
- Role-based access (admin / user) with PBKDF2 password hashing
- CSV bulk import / export (with formula-injection protection, flexible date parsing, duplicate skipping)
- Atomic SQLite online backup & restore with pre-restore safety snapshots
- First-run administrator password setup (no hardcoded default passwords)
- Fully offline. No telemetry. No internet connection required.
- High-DPI aware, light & dark themes

## Source Code Layout

```
.
├── run.py                   # Application entry point (careful module ordering!)
├── app_meta.py              # Single source of truth: version, author, copyright
├── app_paths.py             # Path resolution for app assets and user data
├── database.py              # SQLite schema, queries, backup/restore
├── logger.py                # Rotating file logger, sensitive-field filter
├── icon_utils.py            # HiDPI icon loader (PNG → QIcon)
├── csv_utils.py             # CSV import / export / validation
├── main_window.py           # QMainWindow + sidebar + theme styles
├── login.py                 # Login + first-run password dialogs
├── employee_view.py         # Employees list screen
├── employee_form.py         # Add / Edit employee dialog
├── employee_detail.py       # Read-only employee detail card
├── department_view.py       # Departments management screen
├── department_form.py       # Add / Edit department dialog
├── analytics_view.py        # Matplotlib charts dashboard
├── settings_view.py         # Settings: backup, CSV import, user account, danger zone
├── resources/
│   └── icons/               # 30+ high-resolution PNG icons used by the UI
├── sample_data/
│   ├── employees_sample.csv # 1,000-row demo dataset
│   └── README.md
├── docs/                    # User documentation (first-run, guide, backup, troubleshooting)
└── requirements.txt         # Runtime dependencies
```

## Quick Start (Developers)

```powershell
# 1. Install Python 3.10+ from python.org
#    (Check "Add Python to PATH" during install.)

# 2. Create a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install runtime dependencies
pip install -r requirements.txt

# 4. Run the application
python -u run.py
```

On first launch, the application:
  1. Creates a SQLite database at `%LOCALAPPDATA%\EmployeeManagementSystem\data\employee_system.db`
  2. Creates an admin account and immediately prompts you to set a password
  3. Shows the login screen — log in with username `admin` and the password you just chose

## Runtime Paths

The application cleanly separates *application* files from *user* data.

| What | Where (Windows) |
|---|---|
| Application assets & icons | `resources/icons/` |
| SQLite database | `%LOCALAPPDATA%\EmployeeManagementSystem\data\` |
| Rotating logs | `%LOCALAPPDATA%\EmployeeManagementSystem\logs\` |
| Auto snapshots + backups | `%LOCALAPPDATA%\EmployeeManagementSystem\backups\` |
| Sample CSV data | `sample_data/` |
| Documentation | `docs/` |

Override the user-data root at launch time via:

```powershell
$env:EMS_USER_DATA_DIR="D:\PortableData\EmployeeMS"
python run.py
```

## Security Notes

- Password hashing: PBKDF2-HMAC-SHA256 with 100,000 iterations + 16-byte random salt per user. Legacy SHA-256 hashes are transparently upgraded on first successful login.
- No secrets are logged — the logger's `_SensitiveFilter` drops any log line containing `password`, `secret`, `token`, `hash`, etc.
- CSV export neutralises formula triggers (=, +, -, @) for spreadsheet safety.
- Database restore creates a pre-restore safety snapshot BEFORE touching live data. Even a bad restore can be rolled back.

## License

This project is provided under the MIT License — replace if you prefer a different license.

## Contact

- Maintainer: Hamza Hameed — https://github.com/hamza4hameed
- Repo: https://github.com/hamza4hameed/Employee-Management-System
- Email: hamza4hameed@gmail.com

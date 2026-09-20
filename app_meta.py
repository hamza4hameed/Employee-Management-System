"""Central application metadata — single source of truth."""
from datetime import date

APP_NAME          = "Employee Management System"
APP_SHORT_NAME    = "EmployeeMS"
APP_VERSION       = "1.0.0"
APP_VERSION_TUPLE = (1, 0, 0, 0)
APP_DESCRIPTION   = "A local Windows desktop application for managing employee records."
APP_AUTHOR        = "Your Organisation"
APP_AUTHOR_EMAIL  = ""
APP_URL           = ""
APP_COPYRIGHT     = f"Copyright (c) {date.today().year} {APP_AUTHOR}. All rights reserved."
APP_LANGUAGE      = "English (United States)"
APP_BUILD_TYPE    = "Release"
DATA_NOTICE       = (
    "All data is stored locally on this device in an SQLite database file. "
    "No employee information is transmitted externally."
)

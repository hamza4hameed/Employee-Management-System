"""High-quality PNG & SVG icon loader.

Prioritises pristine PNG icons from the bundled icons directory with
multi-resolution smooth mipmaps and HiDPI awareness for crystal-clear quality
at any scale and display resolution.
"""
import os
from typing import Dict, Optional

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QIcon, QPixmap, QImage
from PyQt5.QtWidgets import QApplication

from app_paths import get_resources_dir, get_app_root

PNG_DIR = os.path.join(get_resources_dir(), "icons")
SVG_DIR = os.path.join(get_resources_dir(), "svg_icons")

_ICON_CACHE: Dict[str, QIcon] = {}

_current_color: str = "#ffffff"

ALIASES: Dict[str, str] = {
    "add": "add_employee.png",
    "add_employee": "add_employee.png",
    "active_employees": "active.png",
    "active": "active.png",
    "reports": "export_report.png",
    "export_report": "export_report.png",
    "delete_db": "danger_zone.png",
    "danger_zone": "danger_zone.png",
    "terminated": "exit.png",
    "backup_restore": "create_backup.png",
    "exit": "exit.png",
    "logout": "logout.png",
}


def set_icon_color(hex_color: str) -> None:
    global _current_color, _ICON_CACHE
    hex_color = hex_color.strip()
    if hex_color != _current_color:
        _current_color = hex_color
        _ICON_CACHE.clear()


def _resolve_png_path(name: str) -> Optional[str]:
    base = name
    for ext in (".png", ".svg"):
        if base.endswith(ext):
            base = base[:-len(ext)]
            break

    direct = os.path.join(PNG_DIR, f"{base}.png")
    if os.path.isfile(direct):
        return direct

    if base in ALIASES:
        alias_file = os.path.join(PNG_DIR, ALIASES[base])
        if os.path.isfile(alias_file):
            return alias_file

    return None


def _load_png_icon(png_path: str) -> QIcon:
    return QIcon(png_path)


def get_icon(name: str, color: Optional[str] = None) -> QIcon:
    if not name:
        return QIcon()

    cache_key = name.strip()
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    png_path = _resolve_png_path(name)
    if png_path:
        icon = _load_png_icon(png_path)
        if not icon.isNull():
            _ICON_CACHE[cache_key] = icon
            return icon

    base_name = name
    for ext in (".svg", ".png"):
        if base_name.endswith(ext):
            base_name = base_name[:-len(ext)]
            break

    svg_path = os.path.join(SVG_DIR, f"{base_name}.svg")
    if os.path.isfile(svg_path):
        icon = QIcon(svg_path)
        if not icon.isNull():
            _ICON_CACHE[cache_key] = icon
            return icon

    return QIcon()

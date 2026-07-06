"""Resolve app paths for development vs PyInstaller frozen builds."""

from __future__ import annotations

import os
import shutil
import sys

APP_NAME = "Integral"
APP_SLUG = "Integral"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> str:
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def bundle_root():
    from pathlib import Path

    return Path(bundle_dir())


def app_resource(*parts: str):
    return bundle_root().joinpath(*parts)


def user_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, APP_SLUG)
    return os.path.join(os.path.expanduser("~"), f".{APP_SLUG.lower()}")


def data_file() -> str:
    if is_frozen():
        return os.path.join(user_data_dir(), "data.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "data.json")


def programs_dir() -> str:
    return os.path.join(bundle_dir(), "programs")


def icon_path() -> str | None:
    path = os.path.join(bundle_dir(), "assets", "icon.ico")
    return path if os.path.exists(path) else None


def ensure_data_file() -> str:
    path = data_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        return path

    if is_frozen():
        portable_next_to_exe = os.path.join(os.path.dirname(sys.executable), "data", "data.json")
        if os.path.exists(portable_next_to_exe):
            shutil.copy2(portable_next_to_exe, path)

    return path

"""Resolve app paths for development vs PyInstaller frozen builds."""

from __future__ import annotations

import os
import shutil
import sys

APP_NAME = "Integral"
APP_SLUG = "Integral"
APP_VERSION = "0.3.11.5.6"

INTEGRAL_DATA_DIR_ENV = "INTEGRAL_DATA_DIR"
INTEGRAL_TEST_BUILD_ENV = "INTEGRAL_TEST_BUILD"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def ci_test_build_bundled() -> bool:
    """True when this frozen exe was built with the CI test-data marker bundled."""
    if not is_frozen():
        return False
    return os.path.isfile(os.path.join(bundle_dir(), "build", "ci_test_build.marker"))


def uses_test_data_store() -> bool:
    """Alternate data root (CI/pr builds or explicit override) — not production %APPDATA%\\Integral."""
    if os.environ.get(INTEGRAL_DATA_DIR_ENV, "").strip():
        return True
    if _env_flag(INTEGRAL_TEST_BUILD_ENV):
        return True
    return ci_test_build_bundled()


def show_test_build_window_marker() -> bool:
    """Window title should show TEST BUILD when a non-production data folder is active."""
    return uses_test_data_store()


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
    explicit = os.environ.get(INTEGRAL_DATA_DIR_ENV, "").strip()
    if explicit:
        return os.path.normpath(os.path.expanduser(explicit))

    slug = f"{APP_SLUG}-test" if uses_test_data_store() else APP_SLUG
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, slug)
    return os.path.join(os.path.expanduser("~"), f".{slug.lower()}")


def data_file() -> str:
    """Primary journal path — always under the canonical user data folder (#89)."""
    return os.path.join(user_data_dir(), "data.json")


def programs_dir() -> str:
    return os.path.join(bundle_dir(), "programs")


def icon_path() -> str | None:
    path = os.path.join(bundle_dir(), "assets", "icon.ico")
    return path if os.path.exists(path) else None


def creative_projects_dir() -> str:
    """On-disk folder for inspiration/manuscript text files (not in data.json)."""
    path = os.path.join(user_data_dir(), "creative")
    os.makedirs(path, exist_ok=True)
    return path


def log_dir() -> str:
    """Directory for integral.log (AppData when frozen, ./data/logs in dev)."""
    if is_frozen():
        path = os.path.join(user_data_dir(), "logs")
    else:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "logs")
    os.makedirs(path, exist_ok=True)
    return path


def app_log_file() -> str:
    return os.path.join(log_dir(), "integral.log")


def ensure_data_file() -> str:
    import user_data_migration

    user_data_migration.run_at_startup()
    path = data_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        return path

    if is_frozen():
        portable_next_to_exe = os.path.join(os.path.dirname(sys.executable), "data", "data.json")
        if os.path.exists(portable_next_to_exe):
            # Atomic copy for one-time bootstrap
            from integral_io import atomic_copy_file
            atomic_copy_file(portable_next_to_exe, path)

    return path

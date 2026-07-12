"""Windows Start-with-Windows helpers (HKCU Run) — stdlib only."""

from __future__ import annotations

import sys
from pathlib import Path

from paths import APP_NAME, is_frozen

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = APP_NAME


def launch_command() -> str:
    """Command line used to start Integral for the current build mode."""
    if is_frozen():
        return f'"{sys.executable}"'
    script = Path(__file__).resolve().parent / "personal_dev_tracker.py"
    python = sys.executable
    return f'"{python}" "{script}"'


def is_supported() -> bool:
    return sys.platform == "win32"


def is_enabled() -> bool:
    if not is_supported():
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(str(value).strip())
    except OSError:
        return False


def enable() -> None:
    if not is_supported():
        raise RuntimeError("Start with Windows is only available on Windows.")
    import winreg

    command = launch_command()
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)


def disable() -> None:
    if not is_supported():
        return
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        return
    except OSError:
        # Value already absent
        return


def set_enabled(enabled: bool) -> None:
    if enabled:
        enable()
    else:
        disable()

"""Windows URL protocol registration for integral:// — stdlib only."""

from __future__ import annotations

import sys

from paths import APP_NAME, is_frozen

PROTOCOL = "integral"
CLASSES_ROOT = rf"Software\Classes\{PROTOCOL}"


def launch_command_template() -> str:
    """Command that receives the clicked URL as %1."""
    from pathlib import Path

    if is_frozen():
        return f'"{sys.executable}" "%1"'
    script_path = Path(__file__).resolve().parent / "personal_dev_tracker.py"
    return f'"{sys.executable}" "{script_path}" "%1"'


def is_supported() -> bool:
    return sys.platform == "win32"


def is_registered() -> bool:
    if not is_supported():
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CLASSES_ROOT) as key:
            value, _ = winreg.QueryValueEx(key, None)
            return str(value).lower().startswith(f"url:{PROTOCOL}")
    except OSError:
        return False


def register() -> None:
    if not is_supported():
        raise RuntimeError("integral:// protocol registration is only available on Windows.")
    import winreg

    command = launch_command_template()
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, CLASSES_ROOT) as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, f"URL:{PROTOCOL} Protocol")
        winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, rf"{CLASSES_ROOT}\DefaultIcon") as key:
        icon = sys.executable if is_frozen() else sys.executable
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, f"{icon},0")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, rf"{CLASSES_ROOT}\shell\open\command") as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, command)


def unregister() -> None:
    if not is_supported():
        return
    import winreg

    def _delete_tree(root, path: str) -> None:
        try:
            with winreg.OpenKey(root, path, 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
                while True:
                    try:
                        sub = winreg.EnumKey(key, 0)
                    except OSError:
                        break
                    _delete_tree(root, f"{path}\\{sub}")
            winreg.DeleteKey(root, path)
        except OSError:
            return

    _delete_tree(winreg.HKEY_CURRENT_USER, CLASSES_ROOT)


def set_registered(enabled: bool) -> None:
    if enabled:
        register()
    else:
        unregister()

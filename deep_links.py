"""Pending deep-link handoff when a second Integral instance is launched via integral://."""

from __future__ import annotations

import os
from pathlib import Path

from paths import user_data_dir


PENDING_NAME = "pending_deep_link.txt"
LOCK_NAME = "integral_instance.lock"


def _pending_path() -> Path:
    root = Path(user_data_dir())
    root.mkdir(parents=True, exist_ok=True)
    return root / PENDING_NAME


def _lock_path() -> Path:
    root = Path(user_data_dir())
    root.mkdir(parents=True, exist_ok=True)
    return root / LOCK_NAME


def write_pending_link(url: str) -> None:
    path = _pending_path()
    path.write_text((url or "").strip() + "\n", encoding="utf-8")


def read_and_clear_pending_link() -> str | None:
    path = _pending_path()
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return text or None


def acquire_instance_lock() -> bool:
    """
    Return True if this process owns the single-instance lock.
    If another live Integral holds the lock, return False.
    """
    path = _lock_path()
    if path.is_file():
        try:
            old_pid = int(path.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            old_pid = 0
        if old_pid and _pid_alive(old_pid):
            return False
    path.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_instance_lock() -> None:
    path = _lock_path()
    try:
        if not path.is_file():
            return
        pid = int(path.read_text(encoding="utf-8").strip() or "0")
        if pid == os.getpid():
            path.unlink(missing_ok=True)
    except (OSError, ValueError):
        return


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:  # noqa: BLE001
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def extract_protocol_arg(argv: list[str] | None = None) -> str | None:
    import sys

    args = argv if argv is not None else sys.argv[1:]
    for arg in args:
        cleaned = (arg or "").strip().strip('"')
        if cleaned.lower().startswith("integral://"):
            return cleaned
    return None

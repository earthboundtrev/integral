"""Windows focus shield — enumerate / minimize windows (SPEC-315)."""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    process_name: str


def is_supported() -> bool:
    return sys.platform == "win32"


def list_top_level_windows(*, exclude_pids: set[int] | None = None) -> list[WindowInfo]:
    """Visible top-level windows with a title (best-effort)."""
    if not is_supported():
        return []
    exclude_pids = exclude_pids or set()
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return []

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    results: list[WindowInfo] = []

    def _callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if not title:
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) in exclude_pids:
            return True
        process_name = _process_name(int(pid.value), kernel32)
        # Skip Integral itself by process name when possible
        if process_name.lower() in {"python.exe", "pythonw.exe", "integral.exe"}:
            # Still include other python apps; Integral hwnd filtered via exclude_pids
            pass
        results.append(
            WindowInfo(
                hwnd=int(hwnd),
                title=title[:120],
                pid=int(pid.value),
                process_name=process_name,
            )
        )
        return True

    user32.EnumWindows(EnumWindowsProc(_callback), 0)
    # Dedupe by pid+title
    seen: set[tuple[int, str]] = set()
    unique: list[WindowInfo] = []
    for info in results:
        key = (info.pid, info.title)
        if key in seen:
            continue
        seen.add(key)
        unique.append(info)
    unique.sort(key=lambda w: (w.process_name.lower(), w.title.lower()))
    return unique


def _process_name(pid: int, kernel32) -> str:
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return f"pid:{pid}"
    try:
        size = wintypes.DWORD(260)
        buf = ctypes.create_unicode_buffer(260)
        # QueryFullProcessImageNameW
        QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
        QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        QueryFullProcessImageNameW.restype = wintypes.BOOL
        if QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            path = buf.value.replace("/", "\\")
            return path.rsplit("\\", 1)[-1] or f"pid:{pid}"
    finally:
        kernel32.CloseHandle(handle)
    return f"pid:{pid}"


def minimize_hwnd(hwnd: int) -> bool:
    if not is_supported():
        return False
    try:
        import ctypes

        SW_MINIMIZE = 6
        return bool(ctypes.windll.user32.ShowWindow(int(hwnd), SW_MINIMIZE))
    except Exception:
        return False


def get_foreground_hwnd() -> int | None:
    if not is_supported():
        return None
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetForegroundWindow()
        return int(hwnd) if hwnd else None
    except Exception:
        return None


def window_pid(hwnd: int) -> int | None:
    if not is_supported() or not hwnd:
        return None
    try:
        import ctypes
        from ctypes import wintypes

        pid = wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(int(hwnd), ctypes.byref(pid))
        return int(pid.value)
    except Exception:
        return None


def enforce_allowlist(
    *,
    allowed_pids: set[int],
    integral_pids: set[int],
) -> bool:
    """If foreground is outside allowlist+integral, minimize it. Returns True if acted."""
    hwnd = get_foreground_hwnd()
    if not hwnd:
        return False
    pid = window_pid(hwnd)
    if pid is None:
        return False
    if pid in integral_pids or pid in allowed_pids:
        return False
    return minimize_hwnd(hwnd)


class FocusShieldSession:
    """Tracks which HWNDs were minimized and which PIDs may stay foreground."""

    def __init__(self) -> None:
        self.active = False
        self.allowed_pids: set[int] = set()
        self.integral_pids: set[int] = set()
        self.minimized_hwnds: list[int] = []

    def start(
        self,
        *,
        minimize_windows: list[WindowInfo],
        integral_pids: set[int],
        allowed_pids: set[int] | None = None,
    ) -> None:
        self.integral_pids = set(integral_pids)
        self.allowed_pids = set(allowed_pids or ())
        self.allowed_pids |= self.integral_pids
        self.minimized_hwnds = []
        for info in minimize_windows:
            if info.pid in self.integral_pids:
                continue
            if minimize_hwnd(info.hwnd):
                self.minimized_hwnds.append(info.hwnd)
        self.active = True

    def tick(self) -> None:
        if not self.active:
            return
        enforce_allowlist(
            allowed_pids=self.allowed_pids,
            integral_pids=self.integral_pids,
        )

    def stop(self) -> None:
        self.active = False
        self.allowed_pids.clear()
        self.minimized_hwnds.clear()

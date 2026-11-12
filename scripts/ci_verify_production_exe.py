"""CI check: production onefile exe must not bundle the CI test-data marker."""

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
import time
from ctypes import wintypes

from PyInstaller.archive.readers import CArchiveReader


def _toc_has_ci_marker(toc: dict) -> list[str]:
    hits: list[str] = []
    needle = "ci_test_build.marker"
    for name in toc:
        if needle in name.replace("\\", "/"):
            hits.append(name)
    return hits


def _find_integral_window_title(pid: int, timeout_sec: float) -> str | None:
    if sys.platform != "win32":
        return None

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    found: list[str] = []
    pid_dword = wintypes.DWORD(pid)

    def _enum_cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        proc_id = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
        if proc_id.value != pid_dword.value:
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        if title.startswith("Integral"):
            found.append(title)
        return True

    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)(_enum_cb)
    deadline = time.monotonic() + timeout_sec
    handle = kernel32.OpenProcess(0x1000, False, pid)
    try:
        while time.monotonic() < deadline:
            exit_code = wintypes.DWORD()
            if handle and kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                if exit_code.value != 259:  # STILL_ACTIVE
                    break
            found.clear()
            user32.EnumWindows(enum_proc, 0)
            if found:
                return found[0]
            time.sleep(0.5)
        return None
    finally:
        if handle:
            kernel32.CloseHandle(handle)


def _windows_production_runtime_checks(exe: str, wait_sec: int) -> tuple[list[str], list[str]]:
    """Launch exe with production-like env; return (logs, errors)."""
    if sys.platform != "win32":
        return ["runtime checks skipped (not Windows)"], []

    logs: list[str] = []
    errors: list[str] = []

    appdata_root = os.path.join(os.environ.get("TEMP", "."), f"integral-prod-verify-{os.getpid()}")
    os.makedirs(appdata_root, exist_ok=True)

    env = os.environ.copy()
    env.pop("INTEGRAL_DATA_DIR", None)
    env.pop("INTEGRAL_TEST_BUILD", None)
    env["APPDATA"] = appdata_root

    workdir = os.path.dirname(os.path.abspath(exe))
    proc = subprocess.Popen([exe], env=env, cwd=workdir)
    try:
        title = _find_integral_window_title(proc.pid, timeout_sec=min(90.0, wait_sec + 60.0))
        if title is None:
            errors.append("could not read Integral main window title (production probe)")
        elif "TEST BUILD" in title:
            errors.append(f"main window title includes TEST BUILD: {title!r}")
        else:
            logs.append(f"main window title (production defaults): {title!r}")

        time.sleep(max(0, wait_sec - 5))
        test_dir = os.path.join(appdata_root, "Integral-test")
        prod_dir = os.path.join(appdata_root, "Integral")
        if os.path.isdir(test_dir):
            errors.append(f"isolated APPDATA contains Integral-test (expected production slug Integral): {test_dir}")
        else:
            logs.append("isolated APPDATA has no Integral-test folder (not defaulting to test data dir)")
        if os.path.isdir(prod_dir):
            logs.append(f"Integral data folder present under isolated APPDATA: {prod_dir}")
        else:
            logs.append(
                "Integral folder not created yet under isolated APPDATA (OK before first save; "
                "production default would be %APPDATA%\\Integral)"
            )
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)

    return logs, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", help="Path to dist/Integral.exe")
    parser.add_argument(
        "--runtime-seconds",
        type=int,
        default=15,
        help="Seconds to keep production probe running after window appears",
    )
    args = parser.parse_args()

    reader = CArchiveReader(args.exe)
    marker_hits = _toc_has_ci_marker(reader.toc)

    print("Production exe verification:")
    marker_ok = not marker_hits
    print("  ci_test_build.marker in bundle:", "NO" if marker_ok else "YES")
    if marker_hits:
        print("FAIL: bundled CI test marker entries:", ", ".join(marker_hits), file=sys.stderr)

    runtime_logs, runtime_errors = _windows_production_runtime_checks(args.exe, args.runtime_seconds)
    for line in runtime_logs:
        print(f"  {line}")
    for line in runtime_errors:
        print(f"FAIL: {line}", file=sys.stderr)

    if marker_hits or runtime_errors:
        return 1

    print("Production bundle check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

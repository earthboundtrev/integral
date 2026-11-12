"""Pytest hooks and autouse fixtures for Integral tests."""

from __future__ import annotations

import os
import sys

from tests.tcl_tk_env import ensure_windows_ci_tcl_tk_env, install_tk_constructor_guard

ensure_windows_ci_tcl_tk_env()

import tkinter as tk

install_tk_constructor_guard()
from collections.abc import Iterator
from unittest.mock import patch

import pytest


def create_tk_root(*, withdraw: bool = True) -> tk.Tk:
    """Create a Tk root with Windows CI Tcl/Tk paths applied."""
    last_err: tk.TclError | None = None
    trials = 5 if (sys.platform == "win32" and os.environ.get("INTEGRAL_WINDOWS_EXE_CI") == "1") else 1
    for _ in range(trials):
        ensure_windows_ci_tcl_tk_env()
        try:
            root = tk.Tk()
            if withdraw:
                root.withdraw()
            return root
        except tk.TclError as exc:
            last_err = exc
            import time

            time.sleep(0.25)
    assert last_err is not None
    raise last_err


def pump_tk(root: tk.Misc, steps: int = 25) -> None:
    """Process pending Tk events (chunked dashboard builds use after_idle)."""
    for _ in range(steps):
        try:
            root.update_idletasks()
            root.update()
        except tk.TclError:
            break


def pump_tk_until(
    root: tk.Misc,
    predicate,
    *,
    timeout_s: float = 1.0,
    step_s: float = 0.01,
) -> bool:
    """Pump Tk until ``predicate()`` is true or ``timeout_s`` elapses.

    Uses short sleeps so ``after(ms)`` callbacks (e.g. focus restore) can run.
    """
    import time

    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        try:
            root.update_idletasks()
            root.update()
        except tk.TclError:
            break
        if predicate():
            return True
        time.sleep(step_s)
    try:
        root.update_idletasks()
        root.update()
    except tk.TclError:
        pass
    return bool(predicate())


@pytest.fixture(autouse=True)
def _windows_ci_tcl_tk_env_each_test() -> Iterator[None]:
    """Re-apply Tcl/Tk paths before every test (ttk import runs in-test)."""
    ensure_windows_ci_tcl_tk_env()
    yield
    ensure_windows_ci_tcl_tk_env()


@pytest.fixture(autouse=True)
def _isolated_user_data_home(tmp_path, monkeypatch):
    """Never touch the developer's real home directory during pytest (#89)."""
    home = tmp_path / "pytest-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    if sys.platform == "win32":
        appdata = tmp_path / "AppData" / "Roaming"
        appdata.mkdir(parents=True)
        monkeypatch.setenv("APPDATA", str(appdata))


@pytest.fixture(autouse=True)
def _stub_tk_messageboxes(request: pytest.FixtureRequest) -> Iterator[None]:
    """Prevent blocking messagebox modals from hanging headless pytest runs."""
    if request.node.get_closest_marker("allow_tk_messagebox"):
        yield
        return

    calls: list[tuple[str, tuple, dict]] = []

    def _record(name: str, *args, **kwargs):
        calls.append((name, args, kwargs))
        return None

    with (
        patch(
            "tkinter.messagebox.showerror",
            side_effect=lambda *a, **k: _record("showerror", *a, **k),
        ),
        patch(
            "tkinter.messagebox.showwarning",
            side_effect=lambda *a, **k: _record("showwarning", *a, **k),
        ),
        patch(
            "tkinter.messagebox.showinfo",
            side_effect=lambda *a, **k: _record("showinfo", *a, **k),
        ),
        patch(
            "tkinter.messagebox.askyesno",
            side_effect=lambda *a, **k: _record("askyesno", *a, **k) or False,
        ),
        patch(
            "tkinter.messagebox.askokcancel",
            side_effect=lambda *a, **k: _record("askokcancel", *a, **k) or False,
        ),
        patch(
            "tkinter.messagebox.askquestion",
            side_effect=lambda *a, **k: _record("askquestion", *a, **k) or "no",
        ),
    ):
        request.node._integral_messagebox_calls = calls  # type: ignore[attr-defined]
        yield


def pytest_configure(config: pytest.Config) -> None:
    ensure_windows_ci_tcl_tk_env()
    install_tk_constructor_guard()
    config.addinivalue_line(
        "markers",
        "allow_tk_messagebox: do not stub tkinter.messagebox for this test",
    )


def pytest_sessionstart(session: pytest.Session) -> None:
    ensure_windows_ci_tcl_tk_env()
    install_tk_constructor_guard()


# GitHub Actions windows-latest: Tk focus / clamp geometry differs from dev machines.
# NEEDS-WINDOWS (real machine, INTEGRAL_WINDOWS_EXE_CI unset): docs/WINDOWS_PR_BUILD_CHECKLIST.md
_GHA_WINDOWS_EXE_SKIP_NODEIDS = frozenset(
    {
        "tests/test_app_shell_128.py::test_theme_toggle_preserves_inline_todo_draft_and_focus",
        "tests/test_journal_ui_131.py::test_journal_escape_from_focused_child_cancels_and_closes",
        "tests/test_journal_ui_99.py::TestJournalWindowLayout::test_header_wraplength_fits_minimum_window_width",
        "tests/test_more_menu_130.py::test_esc_closes_and_returns_focus_to_anchor",
        "tests/test_more_menu_130.py::test_popup_x_clamped_to_root_window",
        "tests/test_more_menu_130.py::test_home_end_move_focus",
    }
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("INTEGRAL_WINDOWS_EXE_CI") != "1" or sys.platform != "win32":
        return
    reason = (
        "Tk focus/layout differs on GitHub Actions windows-latest "
        "(NEEDS-WINDOWS: docs/WINDOWS_PR_BUILD_CHECKLIST.md)"
    )
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if item.nodeid in _GHA_WINDOWS_EXE_SKIP_NODEIDS:
            item.add_marker(skip)

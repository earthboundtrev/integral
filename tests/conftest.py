"""Pytest hooks and autouse fixtures for Integral tests."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest


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
    config.addinivalue_line(
        "markers",
        "allow_tk_messagebox: do not stub tkinter.messagebox for this test",
    )

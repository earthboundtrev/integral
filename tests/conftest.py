"""Pytest fixtures shared across Integral tests (issue #173)."""

from __future__ import annotations

import tkinter.messagebox as messagebox

import pytest


@pytest.fixture(autouse=True)
def _stub_tk_messagebox(request):
    """Fail tests that open unexpected Tk modal dialogs."""
    if request.node.get_closest_marker("allow_messagebox"):
        yield
        return

    calls: list[tuple] = []

    mp = pytest.MonkeyPatch()
    for name in (
        "showinfo",
        "showwarning",
        "showerror",
        "askokcancel",
        "askyesno",
        "askquestion",
        "askretrycancel",
    ):
        if not hasattr(messagebox, name):

            continue

        def _make_recorder(kind: str):
            def _recorder(*args, **kwargs):
                calls.append((kind, args, kwargs))
                return None

            return _recorder

        mp.setattr(messagebox, name, _make_recorder(name))

    yield
    mp.undo()
    if calls:
        pytest.fail(
            "Unexpected tkinter.messagebox call(s): "
            + ", ".join(f"{c[0]}{c[1][:1]!r}" for c in calls)
            + " — use @pytest.mark.allow_messagebox if intentional."
        )

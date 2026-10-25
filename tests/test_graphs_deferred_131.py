"""Deferred Graphs open — spinner before matplotlib import (#131)."""

from __future__ import annotations

import tkinter as tk
from unittest.mock import patch

import mpl_tk
import personal_dev_tracker

from tests.conftest import pump_tk_until
from tests.mock_tracker import mock_tracker_init


def test_graphs_spinner_visible_before_matplotlib_import():
    root = tk.Tk()
    root.withdraw()
    with patch.object(
        personal_dev_tracker.PersonalDevelopmentTracker,
        "__init__",
        mock_tracker_init,
    ):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
        tracker._ensure_shell()

    mpl_tk.Figure = None
    mpl_tk.FigureCanvasTkAgg = None
    mpl_tk.mdates = None

    visible_at_import: list[bool] = []
    real_import = mpl_tk.ensure_matplotlib

    def spy_import() -> None:
        host = tracker._open_windows.get("graphs")
        if host is not None:
            indicator = getattr(host, "_deferred_busy_indicator", None)
            visible_at_import.append(bool(indicator and indicator.is_visible))
        real_import()

    with patch.object(mpl_tk, "ensure_matplotlib", spy_import):
        tracker.show_graphs()
        assert pump_tk_until(
            root,
            lambda: tracker._open_windows.get("graphs") is not None,
            timeout_s=3.0,
        )
        assert pump_tk_until(root, lambda: len(visible_at_import) > 0, timeout_s=5.0)

    assert visible_at_import, "matplotlib import should have run"
    assert visible_at_import[0] is True

    host = tracker._open_windows.get("graphs")
    if host is not None:
        try:
            host.destroy()
        except tk.TclError:
            pass
    root.destroy()

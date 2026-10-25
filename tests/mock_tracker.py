"""Shared PersonalDevelopmentTracker test init (#174)."""

from __future__ import annotations

import tkinter as tk

from theme import get_theme


def mock_tracker_init(self, root: tk.Tk, *, dark_mode: bool = False) -> None:
    """Mock __init__ that skips I/O but mirrors production shell state."""
    self.root = root
    self._init_shell_state()
    self.categories = self.get_default_categories()
    if dark_mode:
        self.settings = {"dark_mode": True}
        self.theme = get_theme(True)


def shell_state_attribute_names() -> frozenset[str]:
    """Attribute names set by PersonalDevelopmentTracker._init_shell_state (plus root)."""
    import personal_dev_tracker

    probe = personal_dev_tracker.PersonalDevelopmentTracker.__new__(
        personal_dev_tracker.PersonalDevelopmentTracker
    )
    probe._init_shell_state()
    return frozenset(vars(probe).keys())

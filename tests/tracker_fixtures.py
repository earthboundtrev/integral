"""Shared PersonalDevelopmentTracker test init (issues #174 / #173)."""

from __future__ import annotations

import personal_dev_tracker


def mock_tracker_init(self, root, *, dark_mode: bool = False) -> None:
    """Minimal tracker init: real state attrs, no data load or dashboard."""
    self.root = root
    personal_dev_tracker.PersonalDevelopmentTracker._init_tracker_state(
        self,
        dark_mode=dark_mode,
    )
    self.categories = self.get_default_categories()


def tracker_state_attribute_names() -> set[str]:
    """Names set by _init_tracker_state (for drift guard tests)."""
    import tkinter as tk
    from unittest.mock import patch

    root = tk.Tk()
    root.withdraw()
    tracker = personal_dev_tracker.PersonalDevelopmentTracker.__new__(
        personal_dev_tracker.PersonalDevelopmentTracker
    )
    tracker.root = root
    tracker._init_tracker_state()
    names = {k for k in vars(tracker) if not k.startswith("__")}
    root.destroy()
    return names

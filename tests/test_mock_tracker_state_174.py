"""Guard: test mock tracker init stays aligned with _init_shell_state (#174)."""

import tkinter as tk

from tests.mock_tracker import mock_tracker_init, shell_state_attribute_names


def test_mock_tracker_init_includes_all_shell_state_attributes():
    root = tk.Tk()
    root.withdraw()
    try:
        import personal_dev_tracker

        tracker = personal_dev_tracker.PersonalDevelopmentTracker.__new__(
            personal_dev_tracker.PersonalDevelopmentTracker
        )
        mock_tracker_init(tracker, root)
        mock_keys = set(vars(tracker).keys())
        required = shell_state_attribute_names() | {"root", "categories"}
        missing = required - mock_keys
        assert not missing, f"mock_tracker_init missing attributes: {sorted(missing)}"
    finally:
        root.destroy()

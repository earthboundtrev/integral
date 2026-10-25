"""Guard against drift between real tracker state and test mocks (#174)."""

from tests.tracker_fixtures import mock_tracker_init, tracker_state_attribute_names


def test_mock_tracker_init_covers_init_state_attributes():
    import tkinter as tk
    from unittest.mock import patch

    import personal_dev_tracker

    root = tk.Tk()
    root.withdraw()
    with patch.object(
        personal_dev_tracker.PersonalDevelopmentTracker,
        "__init__",
        mock_tracker_init,
    ):
        tracker = personal_dev_tracker.PersonalDevelopmentTracker(root)
    mock_names = set(vars(tracker))
    expected = tracker_state_attribute_names()
    missing = expected - mock_names
    root.destroy()
    assert not missing, f"mock_tracker_init missing attrs: {sorted(missing)}"

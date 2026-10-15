"""Tests for the delayed busy indicator component (issue #120)."""

from __future__ import annotations

import tkinter as tk
import unittest
import time

from busy_indicator import BusyIndicator


class TestBusyIndicator(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def test_fast_task_never_shows_indicator(self):
        """AC: Nothing is shown when the work finishes within the threshold (50 ms task)."""
        parent = tk.Frame(self.root)
        parent.pack()

        indicator = BusyIndicator(parent, label="Loading…", delay_ms=180)
        indicator.start()

        # Simulate fast work (50 ms).
        self.root.update()
        time.sleep(0.06)
        self.root.update()

        # Stop before the timer fires.
        indicator.stop()
        self.root.update()

        # Assert the indicator never became visible.
        # The indicator uses pack(), so check if there are any children packed.
        # When not visible, the frame is either None or destroyed.
        self.assertIsNone(indicator._frame)
        self.assertFalse(indicator._visible)

    def test_slow_task_shows_indicator_then_hides(self):
        """AC: For a 500 ms task, the indicator appears at 150-200 ms and disappears when done."""
        parent = tk.Frame(self.root)
        parent.pack()

        indicator = BusyIndicator(parent, label="Loading…", delay_ms=180)
        indicator.start()

        # Wait for the timer to fire (180 ms + margin).
        self.root.update()
        time.sleep(0.20)
        self.root.update()

        # Assert the indicator is now visible.
        self.assertTrue(indicator._visible)
        self.assertIsNotNone(indicator._frame)
        self.assertIsNotNone(indicator._spinner)

        # Simulate more work (total ~500 ms).
        time.sleep(0.30)
        self.root.update()

        # Stop.
        indicator.stop()
        self.root.update()

        # Assert the indicator is hidden.
        self.assertFalse(indicator._visible)
        self.assertIsNone(indicator._frame)

    def test_stop_cancels_timer_before_visible(self):
        """Stopping before the delay elapses cancels the timer with no flicker."""
        parent = tk.Frame(self.root)
        parent.pack()

        indicator = BusyIndicator(parent, label="Loading…", delay_ms=180)
        indicator.start()

        # Stop immediately (before timer fires).
        indicator.stop()
        self.root.update()

        # Wait past the delay to confirm nothing appears.
        time.sleep(0.20)
        self.root.update()

        self.assertFalse(indicator._visible)
        self.assertIsNone(indicator._frame)

    def test_step_updates_label_when_visible(self):
        """step(text) updates the label during a long operation."""
        parent = tk.Frame(self.root)
        parent.pack()

        indicator = BusyIndicator(parent, label="Loading…", delay_ms=100)
        indicator.start()

        # Wait for it to become visible.
        self.root.update()
        time.sleep(0.12)
        self.root.update()

        self.assertTrue(indicator._visible)

        # Update the label.
        indicator.step("Building charts…")
        self.root.update()

        self.assertEqual(indicator._label_var.get(), "Building charts…")

        indicator.stop()

    def test_step_before_visible_stores_label(self):
        """step(text) before visible stores the label for when it shows."""
        parent = tk.Frame(self.root)
        parent.pack()

        indicator = BusyIndicator(parent, label="Loading…", delay_ms=180)
        indicator.start()

        # Call step before the timer fires.
        indicator.step("Preparing data…")
        self.assertEqual(indicator._label_text, "Preparing data…")

        # Wait for it to become visible.
        self.root.update()
        time.sleep(0.20)
        self.root.update()

        # Assert the updated label is shown.
        self.assertTrue(indicator._visible)
        self.assertEqual(indicator._label_var.get(), "Preparing data…")

        indicator.stop()

    def test_on_cancel_hook_called_on_escape(self):
        """Esc during loading calls the cancel hook."""
        parent = tk.Frame(self.root)
        parent.pack()

        cancel_called = {"value": False}

        def on_cancel():
            cancel_called["value"] = True

        indicator = BusyIndicator(parent, label="Loading…", delay_ms=100, on_cancel=on_cancel)
        indicator.start()

        # Wait for it to become visible.
        self.root.update()
        time.sleep(0.12)
        self.root.update()

        self.assertTrue(indicator._visible)

        # Simulate Esc key.
        indicator._frame.event_generate("<Escape>")
        self.root.update()

        self.assertTrue(cancel_called["value"])

        indicator.stop()

    def test_light_and_dark_themes(self):
        """Light and dark themes are applied without crashing."""
        parent = tk.Frame(self.root)
        parent.pack()

        light_theme = {
            "bg": "#F4F5F7",
            "fg": "#1A1D21",
            "muted": "#5C6370",
        }
        dark_theme = {
            "bg": "#12151A",
            "fg": "#E8ECF1",
            "muted": "#9AA5B1",
        }

        # Test light theme.
        indicator_light = BusyIndicator(parent, label="Loading…", theme=light_theme, delay_ms=100)
        indicator_light.start()
        self.root.update()
        time.sleep(0.12)
        self.root.update()
        self.assertTrue(indicator_light._visible)
        indicator_light.stop()

        # Test dark theme.
        indicator_dark = BusyIndicator(parent, label="Loading…", theme=dark_theme, delay_ms=100)
        indicator_dark.start()
        self.root.update()
        time.sleep(0.12)
        self.root.update()
        self.assertTrue(indicator_dark._visible)
        indicator_dark.stop()

    def test_restart_cancels_previous_timer(self):
        """Calling start() again while the timer is armed cancels the first timer."""
        parent = tk.Frame(self.root)
        parent.pack()

        indicator = BusyIndicator(parent, label="Loading…", delay_ms=180)
        indicator.start()

        # Wait a bit but not enough to show.
        self.root.update()
        time.sleep(0.10)
        self.root.update()

        # Restart with new label.
        indicator.start(label="Restarting…")

        # Wait for the new timer to fire.
        time.sleep(0.20)
        self.root.update()

        self.assertTrue(indicator._visible)
        self.assertEqual(indicator._label_var.get(), "Restarting…")

        indicator.stop()

    def test_no_layout_jump_after_hide(self):
        """AC: No layout jump when content replaces the indicator.

        This is implicit: the indicator fills its parent and is then destroyed,
        allowing the actual content to take its place. Manual verification needed
        for real layouts, but we can check that hide() cleans up properly.
        """
        parent = tk.Frame(self.root)
        parent.pack()

        indicator = BusyIndicator(parent, label="Loading…", delay_ms=100)
        indicator.start()

        self.root.update()
        time.sleep(0.12)
        self.root.update()

        self.assertTrue(indicator._visible)

        # Hide and ensure clean state.
        indicator.stop()
        self.root.update()

        self.assertFalse(indicator._visible)
        self.assertIsNone(indicator._frame)
        self.assertIsNone(indicator._spinner)


if __name__ == "__main__":
    unittest.main()

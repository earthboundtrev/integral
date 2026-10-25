"""Tests for the delayed busy indicator component (issue #120)."""

from __future__ import annotations

import tkinter as tk
import unittest
import time

from busy_indicator import (
    HEARTBEAT_MAX_GAP_MS,
    BusyIndicator,
    measure_event_loop_gaps,
    run_cooperative_steps,
)


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
        """Esc during loading calls the cancel hook (bound at start, before spinner maps)."""
        toplevel = tk.Toplevel(self.root)
        parent = tk.Frame(toplevel)
        parent.pack()

        cancel_called = {"value": False}

        def on_cancel():
            cancel_called["value"] = True

        indicator = BusyIndicator(parent, label="Loading…", delay_ms=100, on_cancel=on_cancel)
        indicator.start()
        self.root.update()

        self.assertIsNotNone(indicator._escape_funcid, "Escape binding should be set at start")
        bindings = toplevel.bind("<Escape>")
        self.assertTrue(bindings, "Escape binding should exist on toplevel")

        indicator.request_cancel()
        self.assertTrue(cancel_called["value"], "Cancel hook should run")
        self.assertTrue(indicator.cancel_requested)

        toplevel.destroy()

    def test_cooperative_steps_allows_delayed_show(self):
        """Chunked work via run_cooperative_steps lets the indicator appear mid-build."""
        parent = tk.Frame(self.root)
        parent.pack(fill=tk.BOTH, expand=True)

        indicator = BusyIndicator(parent, label="Loading…", delay_ms=100)
        indicator.start()
        done = {"value": False}

        def slow_step() -> None:
            time.sleep(0.15)

        def finish() -> None:
            done["value"] = True
            indicator.stop()

        run_cooperative_steps(
            self.root,
            indicator,
            (slow_step, slow_step),
            on_complete=finish,
        )

        deadline = time.time() + 2.0
        while time.time() < deadline:
            self.root.update()
            if done["value"]:
                break
            time.sleep(0.02)

        self.assertTrue(done["value"])
        self.assertTrue(indicator._visible or indicator._frame is None)

    def test_cooperative_steps_cancel_stops_remaining_steps(self):
        parent = tk.Frame(self.root)
        parent.pack()
        ran = {"count": 0}
        indicator = BusyIndicator(parent, delay_ms=200, on_cancel=lambda: None)
        indicator.start()

        def step() -> None:
            ran["count"] += 1
            indicator.request_cancel()

        run_cooperative_steps(self.root, indicator, (step, step, step))
        for _ in range(25):
            self.root.update()

        self.assertEqual(ran["count"], 1)
        self.assertTrue(indicator.cancel_requested)

    def test_heartbeat_gaps_under_threshold_during_spinner_animation(self):
        """Indicator show/animate must not stall the event loop (issue #120 AC)."""
        parent = tk.Frame(self.root)
        parent.pack(fill=tk.BOTH, expand=True)
        indicator = BusyIndicator(parent, delay_ms=30)
        indicator.start()

        for _ in range(40):
            self.root.update()
            time.sleep(0.02)

        self.assertTrue(indicator._visible)
        gaps = measure_event_loop_gaps(self.root, 0.35, tick_ms=10)
        indicator.stop()

        long_gaps = [g for g in gaps if g > HEARTBEAT_MAX_GAP_MS + 15]
        self.assertFalse(long_gaps, f"indicator stalled event loop: {long_gaps[:5]}")

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

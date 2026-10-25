"""Delayed busy indicator that appears only after a threshold (issue #120)."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from collections.abc import Callable, Sequence
from typing import Any

# Trevor's decision (Oct 14 2026, issue #120 comment): 180 ms threshold.
DEFAULT_DELAY_MS = 180

# Heartbeat harness: indicator work must not stall the event loop longer than this.
HEARTBEAT_MAX_GAP_MS = 50
# Batched UI work should yield to the event loop often enough for the delay timer.
DEFAULT_COOPERATIVE_BATCH_SIZE = 15
# Time-slice cooperative UI work (~one frame at 60 Hz).
DEFAULT_TIME_BOX_MS = 16


class BusyIndicator:
    """Reusable busy indicator that shows only if work takes longer than threshold.

    Usage:
        indicator = BusyIndicator(parent, label="Loading…", theme=theme)
        indicator.start()
        # ... do work (possibly in chunks via after_idle) ...
        indicator.stop()  # Cancels timer or hides the widget.

    Optional:
        indicator.step("Building charts…")  # Update label during long operations.
        indicator = BusyIndicator(..., on_cancel=lambda: stop_work())  # Esc support.
        run_cooperative_steps(win, indicator, [step1, step2], on_complete=done)

    Design:
        - start() arms a timer; the spinner appears only after delay_ms elapses.
        - stop() hides it, or cancels the timer if it never appeared.
        - Never blocks the UI thread itself (works with after_idle/background threads).
        - Light and dark theme support via theme dict (from theme.py).
    """

    def __init__(
        self,
        parent: tk.Misc,
        label: str = "Loading…",
        *,
        theme: dict | None = None,
        delay_ms: int = DEFAULT_DELAY_MS,
        on_cancel: Callable[[], None] | None = None,
    ):
        """Create a BusyIndicator.

        Args:
            parent: Tk widget that will host the indicator.
            label: Initial label text.
            theme: Theme dict from theme.py (bg, fg, muted, etc.).
            delay_ms: Milliseconds before the indicator becomes visible (default 180 ms).
            on_cancel: Optional callback when user presses Esc or closes during loading.
        """
        self._parent = parent
        self._label_text = label
        self._theme = theme or _default_theme()
        self._delay_ms = delay_ms
        self._on_cancel = on_cancel

        self._timer_id: str | None = None
        self._visible = False
        self._frame: tk.Frame | None = None
        self._spinner: ttk.Progressbar | None = None
        self._label_var: tk.StringVar | None = None
        self._escape_funcid: str | None = None
        self._cancel_requested = False

    @property
    def cancel_requested(self) -> bool:
        """True after Esc/cancel hook fired; cooperative steps should stop."""
        return self._cancel_requested

    def start(self, label: str | None = None) -> None:
        """Arm the timer. If work completes before delay_ms, nothing is shown.

        Args:
            label: Optional label to use instead of the initial one.
        """
        if label is not None:
            self._label_text = label

        self._cancel_requested = False

        # Cancel any existing timer.
        if self._timer_id:
            try:
                self._parent.after_cancel(self._timer_id)
            except tk.TclError:
                pass
            self._timer_id = None

        # Hide if already visible (restarting).
        if self._visible:
            self._hide()

        # Esc is armed immediately so cancel works before the spinner maps.
        self._bind_escape()

        # Validate delay_ms.
        if self._delay_ms < 0:
            self._delay_ms = 0

        # Arm the timer.
        self._timer_id = self._parent.after(self._delay_ms, self._show)

    def stop(self) -> None:
        """Hide the indicator or cancel the timer if it never appeared."""
        if self._timer_id:
            try:
                self._parent.after_cancel(self._timer_id)
            except tk.TclError:
                pass
            self._timer_id = None

        self._unbind_escape()

        if self._visible:
            self._hide()

    @property
    def is_visible(self) -> bool:
        """True when the delayed spinner is on screen."""
        return self._visible

    def step(self, text: str) -> None:
        """Update the label during a long operation (optional).

        Args:
            text: New label text (e.g. "Building charts…").
        """
        self._label_text = text
        if self._label_var:
            self._label_var.set(text)

    def request_cancel(self) -> None:
        """Programmatic cancel (same path as Esc)."""
        if self._cancel_requested:
            return
        self._cancel_requested = True
        self.stop()
        if self._on_cancel:
            self._on_cancel()

    def _bind_escape(self) -> None:
        if not self._on_cancel:
            return
        if self._escape_funcid is not None:
            return
        try:
            toplevel = self._parent.winfo_toplevel()
        except tk.TclError:
            return

        def on_escape(_e: Any) -> None:
            self.request_cancel()

        self._escape_funcid = toplevel.bind("<Escape>", on_escape, add="+")

    def _unbind_escape(self) -> None:
        if not self._escape_funcid:
            return
        try:
            toplevel = self._parent.winfo_toplevel()
            toplevel.unbind("<Escape>", self._escape_funcid)
        except (tk.TclError, TypeError):
            pass
        self._escape_funcid = None

    def _show(self) -> None:
        """Internal: create and show the indicator widgets."""
        if self._visible or self._cancel_requested:
            return

        # Check parent is still alive.
        try:
            if not self._parent.winfo_exists():
                return
        except tk.TclError:
            return

        self._timer_id = None

        # Build the UI: centered frame with spinner + label.
        self._frame = tk.Frame(self._parent, bg=self._theme["bg"], cursor="watch")
        self._frame.pack(fill=tk.BOTH, expand=True)

        # Set _visible only after frame is created successfully.
        self._visible = True

        inner = tk.Frame(self._frame, bg=self._theme["bg"])
        inner.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Indeterminate progress bar as spinner.
        self._spinner = ttk.Progressbar(
            inner,
            mode="indeterminate",
            length=200,
        )
        self._spinner.pack(pady=(0, 8))
        self._spinner.start(interval=50)  # 50 ms interval for smooth animation.

        # Label below the spinner using explicit colors for theme support.
        self._label_var = tk.StringVar(master=self._parent, value=self._label_text)
        label = tk.Label(
            inner,
            textvariable=self._label_var,
            bg=self._theme["bg"],
            fg=self._theme.get("muted", self._theme["fg"]),
        )
        label.pack()

    def _hide(self) -> None:
        """Internal: destroy the indicator widgets."""
        if not self._visible:
            return

        self._visible = False

        if self._spinner:
            try:
                self._spinner.stop()
            except tk.TclError:
                pass
            self._spinner = None

        if self._frame:
            try:
                self._frame.destroy()
            except tk.TclError:
                pass
            self._frame = None

        self._label_var = None


def pump_event_loop(widget: tk.Misc) -> None:
    """Yield to Tk so delayed BusyIndicator timers and animations can run."""
    try:
        widget.update_idletasks()
        widget.update()
    except tk.TclError:
        pass


def cooperative_batch_steps(
    total: int,
    batch_size: int,
    run_batch: Callable[[int, int], None],
) -> list[Callable[[], None]]:
    """Build step callables that process ``total`` items in ``batch_size`` chunks."""
    if total <= 0:
        return []
    steps: list[Callable[[], None]] = []
    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)

        def step(s: int = start, e: int = end) -> None:
            run_batch(s, e)

        steps.append(step)
    return steps


def run_cooperative_steps(
    scheduler: tk.Misc,
    indicator: BusyIndicator,
    steps: list[Callable[[], None]] | Sequence[Callable[[], None]],
    *,
    on_complete: Callable[[], None] | None = None,
    on_step_error: Callable[[BaseException], None] | None = None,
) -> None:
    """Run UI build steps with after_idle between each so the indicator can show.

    Long synchronous work inside a single ``after`` callback blocks the delayed
    spinner and Esc handling. Split work into steps and schedule them here
    (same pattern as Today chunked build, issue #135).
    """
    step_list: list[Callable[[], None]] = (
        steps if isinstance(steps, list) else list(steps)
    )
    index = 0

    def _widget_alive() -> bool:
        try:
            return scheduler.winfo_exists()
        except tk.TclError:
            return False

    def run_next() -> None:
        nonlocal index
        if indicator.cancel_requested or not _widget_alive():
            indicator.stop()
            return

        if index >= len(step_list):
            if on_complete:
                on_complete()
            return

        step = step_list[index]
        index += 1
        try:
            step()
        except tk.TclError:
            indicator.stop()
            return
        except BaseException as exc:
            indicator.stop()
            if on_step_error:
                on_step_error(exc)
            else:
                raise
            return

        if indicator.cancel_requested or not _widget_alive():
            indicator.stop()
            return

        try:
            scheduler.update_idletasks()
            scheduler.update()
        except tk.TclError:
            indicator.stop()
            return

        scheduler.after_idle(run_next)

    scheduler.after_idle(run_next)


def run_timeboxed_index_work(
    scheduler: tk.Misc,
    indicator: BusyIndicator,
    *,
    indices: Sequence[int],
    consume: Callable[[int], None],
    budget_ms: float = DEFAULT_TIME_BOX_MS,
    on_complete: Callable[[], None] | None = None,
    on_cancel: Callable[[], None] | None = None,
) -> None:
    """Process ``indices`` in order, yielding to Tk every ``budget_ms`` (issue #131)."""
    position = 0

    def _alive() -> bool:
        try:
            return scheduler.winfo_exists()
        except tk.TclError:
            return False

    def _abort() -> None:
        indicator.stop()
        if on_cancel is not None:
            on_cancel()

    def tick() -> None:
        nonlocal position
        if indicator.cancel_requested or not _alive():
            _abort()
            return
        deadline = time.perf_counter() + (budget_ms / 1000.0)
        while position < len(indices) and time.perf_counter() < deadline:
            if indicator.cancel_requested or not _alive():
                _abort()
                return
            consume(indices[position])
            position += 1
        if position >= len(indices):
            if on_complete is not None:
                on_complete()
            return
        try:
            scheduler.update_idletasks()
            scheduler.update()
        except tk.TclError:
            _abort()
            return
        scheduler.after_idle(tick)

    scheduler.after_idle(tick)


def measure_event_loop_gaps(
    root: tk.Misc,
    duration_s: float,
    *,
    tick_ms: int = 10,
) -> list[float]:
    """Return gaps (ms) between heartbeat ticks while the event loop runs."""
    gaps: list[float] = []
    last = time.perf_counter()
    end = last + duration_s

    def tick() -> None:
        nonlocal last
        now = time.perf_counter()
        if now >= end:
            return
        gap_ms = (now - last) * 1000.0
        gaps.append(gap_ms)
        last = now
        root.after(tick_ms, tick)

    root.after(tick_ms, tick)
    while time.perf_counter() < end:
        try:
            root.update()
        except tk.TclError:
            break
    return gaps


def _default_theme() -> dict:
    """Fallback theme when none provided (light mode)."""
    return {
        "bg": "#F4F5F7",
        "fg": "#1A1D21",
        "muted": "#5C6370",
    }

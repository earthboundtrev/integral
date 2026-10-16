"""Delayed busy indicator that appears only after a threshold (issue #120)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

# Trevor's decision (Oct 14 2026, issue #120 comment): 180 ms threshold.
DEFAULT_DELAY_MS = 180


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

    def start(self, label: str | None = None) -> None:
        """Arm the timer. If work completes before delay_ms, nothing is shown.

        Args:
            label: Optional label to use instead of the initial one.
        """
        if label is not None:
            self._label_text = label

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

        if self._visible:
            self._hide()

    def step(self, text: str) -> None:
        """Update the label during a long operation (optional).

        Args:
            text: New label text (e.g. "Building charts…").
        """
        self._label_text = text
        if self._label_var:
            self._label_var.set(text)

    def _show(self) -> None:
        """Internal: create and show the indicator widgets."""
        if self._visible:
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

        # Wire Esc to cancel hook on the toplevel (not just _frame).
        if self._on_cancel:
            toplevel = self._frame.winfo_toplevel()
            
            def on_escape(_e):
                self.stop()
                if self._on_cancel:
                    self._on_cancel()
            
            # Store the funcid returned by bind(), not the callable.
            self._escape_funcid = toplevel.bind("<Escape>", on_escape, add="+")
        else:
            self._escape_funcid = None

    def _hide(self) -> None:
        """Internal: destroy the indicator widgets."""
        if not self._visible:
            return

        # Unbind escape from toplevel before setting _visible False.
        if self._escape_funcid and self._frame:
            try:
                toplevel = self._frame.winfo_toplevel()
                toplevel.unbind("<Escape>", self._escape_funcid)
            except (tk.TclError, TypeError):
                pass
            self._escape_funcid = None

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


def _default_theme() -> dict:
    """Fallback theme when none provided (light mode)."""
    return {
        "bg": "#F4F5F7",
        "fg": "#1A1D21",
        "muted": "#5C6370",
    }

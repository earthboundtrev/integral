"""Deferred Toplevel builds with delayed BusyIndicator (#120, #131)."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from busy_indicator import BusyIndicator, pump_event_loop


def run_deferred_toplevel_build(
    win: tk.Toplevel,
    *,
    theme: dict,
    busy_label: str,
    build: Callable[[], None],
    on_build_error: Callable[[Exception], None] | None = None,
) -> BusyIndicator:
    """Show a busy indicator on ``win``, then run ``build`` after the next event-loop tick.

    The host window should already exist (title/geometry set). ``build`` populates it and
    must not create another Toplevel for the same surface. Long ``build`` implementations
    should call ``pump_event_loop(win)`` periodically so the 180 ms spinner can appear.
    """
    busy_host = tk.Frame(win, bg=theme["bg"])
    busy_host.pack(fill=tk.BOTH, expand=True)

    indicator_holder: list[BusyIndicator] = []

    def on_close() -> None:
        if indicator_holder:
            indicator_holder[0].stop()
        try:
            win.destroy()
        except tk.TclError:
            pass

    indicator = BusyIndicator(
        busy_host,
        label=busy_label,
        theme=theme,
        on_cancel=on_close,
    )
    indicator_holder.append(indicator)
    win.protocol("WM_DELETE_WINDOW", on_close)
    win._deferred_busy_indicator = indicator

    indicator.start()

    def finish_after_build() -> None:
        try:
            if not win.winfo_exists():
                return
        except tk.TclError:
            return
        indicator.stop()
        try:
            busy_host.destroy()
        except tk.TclError:
            pass

    win._deferred_finish_build = finish_after_build

    def do_build() -> None:
        try:
            if not win.winfo_exists():
                return
        except tk.TclError:
            return
        pump_event_loop(win)
        try:
            build()
        except tk.TclError:
            indicator.stop()
            return
        except Exception as exc:
            indicator.stop()
            if on_build_error is not None:
                on_build_error(exc)
            else:
                raise
            return
        if not getattr(win, "_deferred_build_async", False):
            finish_after_build()

    win.after(1, do_build)
    return indicator

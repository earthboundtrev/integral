"""Deferred Toplevel builds with delayed BusyIndicator (#120, #131)."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from busy_indicator import BusyIndicator


def run_deferred_toplevel_build(
    win: tk.Toplevel,
    *,
    theme: dict,
    busy_label: str,
    build: Callable[[], None],
    on_build_error: Callable[[Exception], None] | None = None,
) -> None:
    """Show a busy indicator on ``win``, then run ``build`` after the next event-loop tick.

    The host window should already exist (title/geometry set). ``build`` populates it and
    must not create another Toplevel for the same surface.
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

    indicator.start()

    def do_build() -> None:
        try:
            if not win.winfo_exists():
                return
        except tk.TclError:
            return
        try:
            build()
        except Exception as exc:
            indicator.stop()
            if on_build_error is not None:
                on_build_error(exc)
            else:
                raise
            return
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

    win.after(1, do_build)

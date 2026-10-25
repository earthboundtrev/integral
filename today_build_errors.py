"""Today tab chunked build errors — inline panel + banner, no modal (issue #173)."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import TYPE_CHECKING, Callable

from busy_indicator import BusyIndicator
from integral_logging import log_exception

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker

INLINE_PANEL_TEXT = "Couldn't show part of today's log. Your data is safe."
BANNER_FIRST = "Today didn't fully load"
BANNER_REPEAT = "Still couldn't load"


class TodayBuildErrorState:
    def __init__(self) -> None:
        self.repeat_failure = False
        self.log_path: str | None = None
        self.traceback_text: str | None = None
        self._retry_busy: BusyIndicator | None = None

    def record(self, error: BaseException, *, chunk: str) -> None:
        self.log_path, self.traceback_text = log_exception(error, context=f"today_build:{chunk}")

    def clear(self) -> None:
        self.repeat_failure = False
        self.log_path = None
        self.traceback_text = None
        if self._retry_busy is not None:
            self._retry_busy.stop()
            self._retry_busy = None


def show_inline_error_panel(parent: tk.Misc, theme: dict) -> ttk.Frame:
    """Non-modal error panel where a failed chunk would have rendered."""
    frame = ttk.Frame(parent, style="Surface.TFrame")
    frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
    ttk.Label(
        frame,
        text=f"✕  {INLINE_PANEL_TEXT}",
        style="OnSurfaceError.TLabel",
    ).pack(anchor=tk.W, pady=(0, 8))
    return frame


def _stop_retry_spinner(state: TodayBuildErrorState) -> None:
    if state._retry_busy is not None:
        state._retry_busy.stop()
        state._retry_busy = None


def show_today_build_banner(
    tracker: PersonalDevelopmentTracker,
    state: TodayBuildErrorState,
    *,
    on_retry: Callable[[], None],
    on_details: Callable[[], None],
    retrying: bool = False,
) -> None:
    _stop_retry_spinner(state)
    message = BANNER_REPEAT if state.repeat_failure else BANNER_FIRST
    banner = tracker.ensure_status_banner()
    if retrying:
        banner.show_error(
            message,
            extra_actions=[("Retrying…", lambda: None)],
            focusable_actions=False,
            actions_disabled=True,
        )
        return
    banner.show_error(
        message,
        extra_actions=[("Retry", on_retry), ("Details", on_details)],
        focusable_actions=True,
    )


def open_details_dialog(root: tk.Misc, theme: dict, log_path: str | None, tb_text: str | None) -> None:
    win = tk.Toplevel(root)
    win.title("Today load details")
    win.transient(root)
    win.geometry("640x400")
    body = scrolledtext.ScrolledText(win, wrap=tk.WORD, font=("Helvetica", 10))
    body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
    lines = []
    if log_path:
        lines.append(f"Log file: {log_path}\n\n")
    if tb_text:
        lines.append(tb_text)
    else:
        lines.append("No traceback was recorded.")
    body.insert("1.0", "".join(lines))
    body.configure(state=tk.DISABLED)
    ttk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 12))


def dismiss_today_load_banner(tracker: PersonalDevelopmentTracker) -> None:
    banner = getattr(tracker, "_status_banner", None)
    if banner is None or banner._frame is None:
        return
    msg = banner._message_var.get()
    if BANNER_FIRST in msg or BANNER_REPEAT in msg:
        banner.dismiss()


def begin_retry_spinner(tracker: PersonalDevelopmentTracker, state: TodayBuildErrorState) -> None:
    if state._retry_busy is not None:
        state._retry_busy.stop()
    host = tracker._banner_host
    if host is None or not host.winfo_exists():
        host = tracker.root
    state._retry_busy = BusyIndicator(
        host,
        label="Retrying…",
        theme=tracker.theme,
        delay_ms=180,
    )
    state._retry_busy.start()

"""Embedded status banners (success / error / info) — issue #112."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

SUCCESS_HIDE_MS = 4000
SUCCESS_UNDO_HIDE_MS = 6000

_KIND_SUCCESS = "success"
_KIND_ERROR = "error"
_KIND_INFO = "info"

_ICONS = {
    _KIND_SUCCESS: "✓",
    _KIND_ERROR: "✕",
    _KIND_INFO: "ℹ",
}


def _banner_colors(kind: str, theme: dict) -> tuple[str, str, str]:
    if kind == _KIND_ERROR:
        return theme.get("error_bg", "#FEE2E2"), theme.get("error", "#B91C1C"), theme.get("error", "#B91C1C")
    if kind == _KIND_SUCCESS:
        return theme.get("success_bg", "#ECFDF5"), theme.get("success", "#047857"), theme.get("success", "#047857")
    return theme.get("warning_bg", "#FEF3C7"), theme.get("fg", "#1A1D21"), theme.get("fg", "#1A1D21")


class StatusBanner:
    """Single banner slot at the top of a window's content area."""

    def __init__(self, parent: tk.Misc, theme: dict) -> None:
        self._host = ttk.Frame(parent)
        self._host.pack(side=tk.TOP, fill=tk.X, pady=(0, 8))
        self._theme = theme
        self._kind: str | None = None
        self._frame: tk.Frame | None = None
        self._message_var = tk.StringVar(value="")
        self._hide_after_id: str | None = None
        self._auto_hide_ms = 0
        self._pause_depth = 0
        self._undo_callback: Callable[[], None] | None = None
        self._deferred_success: tuple[str, str | None, Callable[[], None] | None] | None = None
        self._sr_label = tk.Label(self._host, text="", takefocus=0)
        self._sr_label.place(x=-10000, y=-10000, width=1, height=1)

    def set_theme(self, theme: dict) -> None:
        self._theme = theme
        if self._frame is not None and self._kind is not None:
            bg, fg, _ = _banner_colors(self._kind, theme)
            self._frame.configure(bg=bg)

            def _recolor_widget(widget: tk.Misc) -> None:
                try:
                    if isinstance(widget, tk.Frame):
                        widget.configure(bg=bg)
                    elif isinstance(widget, tk.Label):
                        widget.configure(bg=bg, fg=fg)
                except tk.TclError:
                    pass
                for child in widget.winfo_children():
                    _recolor_widget(child)

            _recolor_widget(self._frame)

    def _cancel_hide(self) -> None:
        if self._hide_after_id is not None:
            try:
                self._host.after_cancel(self._hide_after_id)
            except tk.TclError:
                pass
            self._hide_after_id = None

    def _clear_frame(self) -> None:
        self._cancel_hide()
        self._pause_depth = 0
        if self._frame is not None:
            try:
                self._frame.destroy()
            except tk.TclError:
                pass
        self._frame = None
        self._undo_callback = None

    def dismiss(self) -> None:
        deferred = self._deferred_success if self._kind == _KIND_ERROR else None
        self._deferred_success = None
        self._clear_frame()
        self._kind = None
        self._sr_label.config(text="")
        if deferred is not None:
            message, undo_label, undo_callback = deferred
            self.show_success(message, undo_label=undo_label, undo_callback=undo_callback)

    def _schedule_hide(self, ms: int) -> None:
        self._cancel_hide()
        self._auto_hide_ms = ms
        if ms <= 0:
            return
        self._hide_after_id = self._host.after(ms, self._on_hide_timer)

    def _on_hide_timer(self) -> None:
        self._hide_after_id = None
        if self._pause_depth > 0:
            self._schedule_hide(self._auto_hide_ms)
            return
        if self._kind == _KIND_SUCCESS:
            self.dismiss()

    def _bind_pause(self, widget: tk.Misc) -> None:
        def enter(_e=None) -> None:
            self._pause_depth += 1
            self._cancel_hide()

        def leave(_e=None) -> None:
            self._pause_depth = max(0, self._pause_depth - 1)
            if self._pause_depth == 0 and self._kind == _KIND_SUCCESS and self._auto_hide_ms > 0:
                self._schedule_hide(self._auto_hide_ms)

        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", leave, add="+")
        widget.bind("<FocusIn>", enter, add="+")
        widget.bind("<FocusOut>", leave, add="+")

    def _show(
        self,
        kind: str,
        message: str,
        *,
        auto_hide_ms: int = 0,
        undo_label: str | None = None,
        undo_callback: Callable[[], None] | None = None,
        extra_actions: list[tuple[str, Callable[[], None]]] | None = None,
        closable: bool = False,
        focusable_actions: bool = False,
        actions_disabled: bool = False,
    ) -> None:
        if kind == _KIND_SUCCESS and self._kind == _KIND_ERROR and self._frame is not None:
            self._deferred_success = (message, undo_label, undo_callback)
            return
        self._clear_frame()
        if kind != _KIND_SUCCESS:
            self._deferred_success = None
        self._kind = kind
        bg, fg, accent = _banner_colors(kind, self._theme)
        icon = _ICONS.get(kind, "")

        frame = tk.Frame(self._host, bg=bg, highlightbackground=self._theme.get("card_border", "#D8DCE3"), highlightthickness=1)
        frame.pack(fill=tk.X)
        self._frame = frame

        inner = tk.Frame(frame, bg=bg)
        inner.pack(fill=tk.X, padx=10, pady=8)

        msg = f"{icon}  {message}" if icon else message
        self._message_var.set(msg)
        text = tk.Label(
            inner,
            textvariable=self._message_var,
            bg=bg,
            fg=fg,
            font=("Helvetica", 10),
            anchor="w",
            justify=tk.LEFT,
            wraplength=720,
            takefocus=0,
        )
        text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._sr_label.config(text=message)

        actions = tk.Frame(inner, bg=bg)
        actions.pack(side=tk.RIGHT)

        if undo_label and undo_callback:
            self._undo_callback = undo_callback

            def do_undo() -> None:
                cb = self._undo_callback
                self.dismiss()
                if cb:
                    cb()

            btn = ttk.Button(actions, text=undo_label, command=do_undo, takefocus=0)
            btn.pack(side=tk.LEFT, padx=(8, 0))
            self._bind_pause(btn)

        if extra_actions:
            for label, cmd in extra_actions:
                btn = ttk.Button(
                    actions,
                    text=label,
                    command=cmd,
                    takefocus=1 if focusable_actions and not actions_disabled else 0,
                )
                if actions_disabled:
                    btn.state(["disabled"])
                btn.pack(side=tk.LEFT, padx=(8, 0))

        if closable or kind == _KIND_ERROR:

            def close() -> None:
                self.dismiss()

            close_btn = ttk.Button(actions, text="✕", width=3, command=close, takefocus=0)
            close_btn.pack(side=tk.LEFT, padx=(8, 0))
            self._bind_pause(close_btn)

        self._bind_pause(frame)
        self._bind_pause(text)
        if auto_hide_ms > 0 and kind == _KIND_SUCCESS:
            self._schedule_hide(auto_hide_ms)

    def show_success(
        self,
        message: str,
        *,
        undo_label: str | None = None,
        undo_callback: Callable[[], None] | None = None,
    ) -> None:
        ms = SUCCESS_UNDO_HIDE_MS if undo_callback else SUCCESS_HIDE_MS
        self._show(
            _KIND_SUCCESS,
            message,
            auto_hide_ms=ms,
            undo_label=undo_label,
            undo_callback=undo_callback,
        )

    def show_error(
        self,
        message: str,
        *,
        file_name: str | None = None,
        extra_actions: list[tuple[str, Callable[[], None]]] | None = None,
        focusable_actions: bool = False,
        actions_disabled: bool = False,
    ) -> None:
        text = message
        if file_name:
            text = f"{message} ({file_name})"
        self._show(
            _KIND_ERROR,
            text,
            closable=True,
            extra_actions=extra_actions,
            focusable_actions=focusable_actions,
            actions_disabled=actions_disabled,
        )

    def show_info(
        self,
        message: str,
        *,
        extra_actions: list[tuple[str, Callable[[], None]]] | None = None,
        dismissible: bool = True,
    ) -> None:
        self._show(
            _KIND_INFO,
            message,
            extra_actions=extra_actions,
            closable=dismissible,
            auto_hide_ms=0,
        )


_banners: dict[int, StatusBanner] = {}


def _widget_exists(widget: tk.Misc | None) -> bool:
    if widget is None:
        return False
    try:
        return int(widget.winfo_exists()) == 1
    except tk.TclError:
        return False


def get_status_banner(window: tk.Misc, theme: dict) -> StatusBanner:
    """Return a StatusBanner for this Toplevel or root, creating a host at the top."""
    top = window.winfo_toplevel()
    key = id(top)
    existing = _banners.get(key)
    if existing is not None:
        if _widget_exists(existing._host):
            existing.set_theme(theme)
            return existing
    host_attr = "_integral_status_banner_host"
    host = getattr(top, host_attr, None)
    if host is not None and not _widget_exists(host):
        host = None
    if host is None:
        host = ttk.Frame(top)
        host.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(8, 0))
        setattr(top, host_attr, host)
    banner = StatusBanner(host, theme)
    _banners[key] = banner
    return banner


def attach_banner_to_main(
    main_window: tk.Misc,
    theme: dict,
    *,
    tracker=None,
) -> StatusBanner:
    """Prefer the tracker's shell banner host; fall back to the window top."""
    if tracker is not None and hasattr(tracker, "ensure_status_banner"):
        return tracker.ensure_status_banner()
    return get_status_banner(main_window, theme)

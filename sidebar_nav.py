"""Left sidebar navigation chrome — active state and keyboard (#131)."""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING, Callable

import nav_items
from theme import FONTS

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker

SIDEBAR_WIDTH_PX = 240
NAV_ITEM_HEIGHT_PX = 36
ACCENT_BAR_WIDTH_PX = 3
ACCENT_BAR_HEIGHT_PX = 16


def visible_sidebar_nav_ids(tracker: PersonalDevelopmentTracker) -> list[str]:
    """Nav item ids whose row is currently packed (respects deep-work hiding)."""
    ids: list[str] = []
    frames = getattr(tracker, "_sidebar_nav_frames", {})
    for spec in nav_items.sidebar_nav_items():
        frame = frames.get(spec.id)
        if frame is None:
            continue
        try:
            if frame.winfo_exists() and frame.winfo_manager() == "pack":
                ids.append(spec.id)
        except tk.TclError:
            continue
    return ids


def set_sidebar_active(tracker: PersonalDevelopmentTracker, nav_id: str | None) -> None:
    """Apply active-item styling (surface, bold, 3×16 accent bar)."""
    tracker._sidebar_active_id = nav_id
    theme = tracker.theme
    sidebar_bg = theme.get("sidebar", theme["bg"])
    surface = theme["surface"]
    accent = theme["accent"]
    buttons: dict[str, tk.Button] = getattr(tracker, "_sidebar_nav_buttons_by_id", {})
    frames: dict[str, tk.Frame] = getattr(tracker, "_sidebar_nav_frames", {})
    accent_bars: dict[str, tk.Frame] = getattr(tracker, "_sidebar_nav_accent_bars", {})

    for spec in nav_items.sidebar_nav_items():
        active = spec.id == nav_id
        btn = buttons.get(spec.id)
        frame = frames.get(spec.id)
        bar = accent_bars.get(spec.id)
        if btn is None or frame is None or bar is None:
            continue
        try:
            if not btn.winfo_exists():
                continue
        except tk.TclError:
            continue
        row_bg = surface if active else sidebar_bg
        btn_bg = surface if active else sidebar_bg
        font = FONTS["body_bold"] if active else FONTS["caption"]
        bar_bg = accent if active else sidebar_bg
        try:
            frame.configure(bg=row_bg)
            bar.configure(bg=bar_bg, width=ACCENT_BAR_WIDTH_PX, height=ACCENT_BAR_HEIGHT_PX)
            btn.configure(bg=btn_bg, font=font, activebackground=surface)
        except tk.TclError:
            pass


def _focus_nav_button(tracker: PersonalDevelopmentTracker, nav_id: str) -> None:
    buttons: dict[str, tk.Button] = getattr(tracker, "_sidebar_nav_buttons_by_id", {})
    btn = buttons.get(nav_id)
    if btn is None:
        return
    try:
        if btn.winfo_exists():
            btn.focus_set()
    except tk.TclError:
        pass


def handle_sidebar_nav_key(
    tracker: PersonalDevelopmentTracker,
    nav_id: str,
    keysym: str,
) -> bool:
    """Move focus among visible nav rows. Returns True when handled."""
    if keysym not in ("Up", "Down"):
        return False
    order = visible_sidebar_nav_ids(tracker)
    if nav_id not in order:
        return True
    idx = order.index(nav_id)
    if keysym == "Down" and idx < len(order) - 1:
        _focus_nav_button(tracker, order[idx + 1])
    elif keysym == "Up" and idx > 0:
        _focus_nav_button(tracker, order[idx - 1])
    return True


def bind_sidebar_nav_keyboard(
    tracker: PersonalDevelopmentTracker,
    buttons_by_id: dict[str, tk.Button],
) -> None:
    """Up/Down moves focus among visible nav rows; Return activates."""
    accent = tracker.theme.get("accent", "#2F7A7B")

    def on_nav_key(event: tk.Event, nav_id: str) -> str | None:
        if handle_sidebar_nav_key(tracker, nav_id, event.keysym):
            return "break"
        return None

    for nav_id, btn in buttons_by_id.items():
        try:
            btn.configure(highlightthickness=0)
        except tk.TclError:
            pass

        def on_focus_in(_event: tk.Event, nid: str = nav_id, b: tk.Button = btn) -> None:
            if getattr(tracker, "_sidebar_active_id", None) == nid:
                return
            try:
                b.configure(
                    highlightthickness=1,
                    highlightbackground=accent,
                    highlightcolor=accent,
                )
            except tk.TclError:
                pass

        def on_focus_out(_event: tk.Event, b: tk.Button = btn) -> None:
            try:
                b.configure(highlightthickness=0)
            except tk.TclError:
                pass

        btn.bind("<Key-Up>", lambda e, nid=nav_id: on_nav_key(e, nid), add="+")
        btn.bind("<Key-Down>", lambda e, nid=nav_id: on_nav_key(e, nid), add="+")
        btn.bind("<Return>", lambda e, b=btn: (b.invoke(), "break")[1], add="+")
        btn.bind("<KP_Enter>", lambda e, b=btn: (b.invoke(), "break")[1], add="+")
        btn.bind("<FocusIn>", on_focus_in, add="+")
        btn.bind("<FocusOut>", on_focus_out, add="+")


def attach_sidebar_hover(
    btn: tk.Button,
    *,
    nav_id: str,
    tracker: PersonalDevelopmentTracker,
    sidebar_bg: str,
    surface: str,
) -> None:
    def on_enter(_event: tk.Event) -> None:
        if getattr(tracker, "_sidebar_active_id", None) == nav_id:
            return
        if btn["state"] == "disabled":
            return
        try:
            btn.configure(bg=surface)
        except tk.TclError:
            pass

    def on_leave(_event: tk.Event) -> None:
        if getattr(tracker, "_sidebar_active_id", None) == nav_id:
            return
        try:
            btn.configure(bg=sidebar_bg)
        except tk.TclError:
            pass

    btn.bind("<Enter>", on_enter, add="+")
    btn.bind("<Leave>", on_leave, add="+")


def wrap_sidebar_action(
    tracker: PersonalDevelopmentTracker,
    nav_id: str,
    action: Callable[[], None],
) -> Callable[[], None]:
    """Set active nav id then run the destination action."""

    def run() -> None:
        set_sidebar_active(tracker, nav_id)
        action()

    return run

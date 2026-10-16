"""Single primary accent button policy (#134) — helpers and dialog keys."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """WCAG contrast ratio between two sRGB hex colors."""
    l1 = _relative_luminance(_hex_to_rgb(fg_hex))
    l2 = _relative_luminance(_hex_to_rgb(bg_hex))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def secondary_button_border_contrast(theme: dict[str, str]) -> float:
    """TButton bordercolor on card/surface background (≥ 3:1 required).

    Uses theme tokens (same values passed to ``style.configure("TButton", …)``).
    Actual ttk button edges can vary by platform/theme engine; verify with
    ``ttk_secondary_button_border_contrast`` when a ``ttk.Style`` is available.
    """
    border = theme.get("button_border", theme["card_border"])
    return contrast_ratio(border, theme["surface"])


def ttk_secondary_button_border_contrast(style: ttk.Style, theme: dict[str, str]) -> float:
    """Contrast from the configured TButton bordercolor lookup (when supported)."""
    border = style.lookup("TButton", "bordercolor")
    if not border:
        border = theme.get("button_border", theme["card_border"])
    return contrast_ratio(border, theme["surface"])


def iter_widgets(root: tk.Misc):
    yield root
    for child in root.winfo_children():
        yield from iter_widgets(child)


def is_accent_button(widget: tk.Misc) -> bool:
    if not isinstance(widget, ttk.Button):
        return False
    try:
        return widget.cget("style") == "Accent.TButton"
    except tk.TclError:
        return False


def count_accent_buttons(root: tk.Misc) -> int:
    return sum(1 for w in iter_widgets(root) if is_accent_button(w))


def _return_should_invoke(widget: tk.Misc) -> bool:
    if widget is None:
        return True
    cls = widget.winfo_class()
    if cls in ("Text", "ScrolledText", "Scrolledtext"):
        return False
    return True


def wire_escape_cancel(
    window: tk.Misc,
    *,
    cancel_btn: ttk.Button | None = None,
    cancel_command=None,
) -> None:
    """Esc closes via Cancel/back (for large windows without a single accent primary)."""

    def on_escape(_event: tk.Event) -> str:
        if cancel_btn is not None:
            try:
                cancel_btn.invoke()
            except tk.TclError:
                pass
        elif cancel_command is not None:
            cancel_command()
        else:
            try:
                window.destroy()
            except tk.TclError:
                pass
        return "break"

    window.bind("<Escape>", on_escape, add="+")


def wire_dialog_accent_keys(
    window: tk.Misc,
    accent_btn: ttk.Button,
    *,
    cancel_btn: ttk.Button | None = None,
    cancel_command=None,
) -> None:
    """Enter activates the primary accent; Esc closes via Cancel/back."""

    def on_return(event: tk.Event) -> str | None:
        if not _return_should_invoke(event.widget):
            return None
        try:
            accent_btn.invoke()
        except tk.TclError:
            pass
        return "break"

    window.bind("<Return>", on_return, add="+")
    wire_escape_cancel(window, cancel_btn=cancel_btn, cancel_command=cancel_command)

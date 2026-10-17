"""Inline field validation helpers — issue #112 / #107."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


def validate_rating_1_10(value: str | int) -> str | None:
    if isinstance(value, int):
        if 1 <= value <= 10:
            return None
        return "Rating must be between 1 and 10."
    text = str(value).strip()
    if not text:
        return "Rating is required (1–10)."
    if not text.isdigit():
        return "Rating must be a whole number from 1 to 10."
    num = int(text)
    if num < 1 or num > 10:
        return "Rating must be between 1 and 10."
    return None


def rating_spinbox_validate(proposed: str) -> bool:
    if proposed == "":
        return True
    if not proposed.isdigit():
        return False
    if len(proposed) > 2:
        return False
    return 1 <= int(proposed) <= 10


def _inline_label_bg(parent: tk.Misc, theme: dict) -> str:
    surface = theme.get("surface")
    if surface:
        return str(surface)
    try:
        return parent.cget("background")
    except tk.TclError:
        return "#FFFFFF"


def make_inline_error_label(parent: tk.Misc, theme: dict) -> tk.Label:
    return tk.Label(
        parent,
        text="",
        fg=theme.get("error", "#DC2626"),
        bg=_inline_label_bg(parent, theme),
        wraplength=520,
        justify=tk.LEFT,
        anchor="w",
    )


def set_field_error(error_label: tk.Label | None, message: str | None) -> None:
    if error_label is None:
        return
    if message:
        error_label.config(text=message)
        if not error_label.winfo_ismapped():
            error_label.pack(anchor="w", pady=(2, 0))
            error_label._dynamic_error_pack = True  # type: ignore[attr-defined]
    else:
        error_label.config(text="")
        if getattr(error_label, "_dynamic_error_pack", False):
            error_label.pack_forget()
            error_label._dynamic_error_pack = False  # type: ignore[attr-defined]


def wire_focusout_validation(
    widget: tk.Misc,
    validator: Callable[[], str | None],
    error_label: tk.Label,
) -> None:
    def on_focus_out(_event=None) -> None:
        set_field_error(error_label, validator())

    widget.bind("<FocusOut>", on_focus_out, add="+")


def focus_first_invalid(pairs: list[tuple[tk.Misc, tk.Label | None, str | None]]) -> bool:
    """Apply inline errors; focus first widget with an error message. Returns True if any error."""
    first_widget: tk.Misc | None = None
    found = False
    labels_with_errors: set[int] = set()
    for widget, label, message in pairs:
        if message:
            set_field_error(label, message)
            if label is not None:
                labels_with_errors.add(id(label))
        elif label is None or id(label) not in labels_with_errors:
            set_field_error(label, message)
        if message:
            found = True
            if first_widget is None:
                first_widget = widget
    if first_widget is not None:
        try:
            first_widget.focus_set()
        except tk.TclError:
            pass
    return found


def register_rating_spinbox(spinbox: ttk.Spinbox, root: tk.Misc) -> None:
    vcmd = (root.register(rating_spinbox_validate), "%P")
    spinbox.configure(validate="key", validatecommand=vcmd)

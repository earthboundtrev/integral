"""Light and dark themes for the tracker UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

LIGHT = {
    "name": "light",
    "bg": "#F4F6F8",
    "fg": "#1F2933",
    "muted": "#7F8C8D",
    "accent": "#E67E22",
    "success": "#27AE60",
    "card_border": "#D0D7DE",
    "text_bg": "#FFFFFF",
    "text_fg": "#1F2933",
    "select_bg": "#D6E4FF",
}

DARK = {
    "name": "dark",
    "bg": "#1A1D23",
    "fg": "#E8ECF1",
    "muted": "#9AA5B1",
    "accent": "#F5A623",
    "success": "#3DDB87",
    "card_border": "#3E4C59",
    "text_bg": "#252A33",
    "text_fg": "#E8ECF1",
    "select_bg": "#3D5AFE",
}


def get_theme(dark_mode: bool) -> dict:
    return DARK if dark_mode else LIGHT


def apply_theme(root: tk.Misc, theme: dict) -> None:
    root.configure(bg=theme["bg"])
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(".", background=theme["bg"], foreground=theme["fg"])
    style.configure("TFrame", background=theme["bg"])
    style.configure("TLabel", background=theme["bg"], foreground=theme["fg"])
    style.configure("TLabelframe", background=theme["bg"], foreground=theme["fg"])
    style.configure("TLabelframe.Label", background=theme["bg"], foreground=theme["fg"])
    style.configure("TButton", padding=6)
    style.configure("TCheckbutton", background=theme["bg"], foreground=theme["fg"])
    style.configure("TRadiobutton", background=theme["bg"], foreground=theme["fg"])
    style.configure("TNotebook", background=theme["bg"])
    style.configure("TNotebook.Tab", background=theme["bg"], foreground=theme["fg"], padding=[10, 4])
    style.map("TNotebook.Tab", background=[("selected", theme["text_bg"])])
    style.configure("Treeview", background=theme["text_bg"], foreground=theme["text_fg"], fieldbackground=theme["text_bg"])
    style.configure("Treeview.Heading", background=theme["bg"], foreground=theme["fg"])
    style.configure("Accent.TLabel", foreground=theme["accent"], background=theme["bg"])
    style.configure("Success.TLabel", foreground=theme["success"], background=theme["bg"])
    style.configure("Muted.TLabel", foreground=theme["muted"], background=theme["bg"])


def style_text_widget(widget: tk.Text, theme: dict) -> None:
    widget.configure(
        bg=theme["text_bg"],
        fg=theme["text_fg"],
        insertbackground=theme["fg"],
        selectbackground=theme["select_bg"],
        relief=tk.FLAT,
    )


def style_listbox(widget: tk.Listbox, theme: dict) -> None:
    widget.configure(
        bg=theme["text_bg"],
        fg=theme["text_fg"],
        selectbackground=theme["select_bg"],
        selectforeground=theme["fg"],
        highlightthickness=0,
        borderwidth=1,
    )


def style_canvas(widget: tk.Canvas, theme: dict) -> None:
    widget.configure(bg=theme["bg"], highlightthickness=0)

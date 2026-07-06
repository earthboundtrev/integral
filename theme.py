"""Light and dark themes for Integral."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

_FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"

LIGHT = {
    "name": "light",
    "bg": "#F4F5F7",
    "fg": "#1A1D21",
    "muted": "#5C6370",
    "accent": "#2F7A7B",
    "accent_dark": "#256264",
    "streak": "#D97706",
    "success": "#059669",
    "success_bg": "#ECFDF5",
    "link": "#2563EB",
    "surface": "#FFFFFF",
    "surface_alt": "#EEF0F3",
    "card_border": "#D8DCE3",
    "text_bg": "#FFFFFF",
    "text_fg": "#1A1D21",
    "select_bg": "#D1E7E7",
    "warning_bg": "#FEF3C7",
}

DARK = {
    "name": "dark",
    "bg": "#12151A",
    "fg": "#E8ECF1",
    "muted": "#9AA5B1",
    "accent": "#3D9A9B",
    "accent_dark": "#2F7A7B",
    "streak": "#F5A623",
    "success": "#3DDB87",
    "success_bg": "#0F2A22",
    "link": "#60A5FA",
    "surface": "#1C2128",
    "surface_alt": "#252B33",
    "card_border": "#3E4C59",
    "text_bg": "#1C2128",
    "text_fg": "#E8ECF1",
    "select_bg": "#2A4A4B",
    "warning_bg": "#3D3420",
}

FONTS = {
    "title": (_FONT, 22, "bold"),
    "heading": (_FONT, 14, "bold"),
    "subheading": (_FONT, 12, "bold"),
    "body": (_FONT, 10),
    "body_bold": (_FONT, 10, "bold"),
    "small": (_FONT, 9),
    "stat": (_FONT, 13, "bold"),
    "button": (_FONT, 10),
}

CATEGORY_ACCENTS = {
    "Money/Freedom": "#3B82F6",
    "Career & Vocation": "#6366F1",
    "Body & Presence": "#EF4444",
    "Burnout Prevention & Energy Management": "#8B5CF6",
    "Creative/Mental Work": "#F59E0B",
    "Learning & Intellectual Growth": "#0EA5E9",
    "Family/Logistics": "#14B8A6",
    "Relationships & Social Connection": "#EC4899",
    "Home & Environment": "#22C55E",
    "Search Practice": "#64748B",
    "Spiritual Development": "#A855F7",
    "Emotional Wellbeing": "#F97316",
    "Community & Service": "#10B981",
    "Cultural Life & Heritage": "#E11D48",
    "What You Have Eaten": "#84CC16",
    "Art You Have Consumed": "#F43F5E",
    "General Reading": "#78716C",
    "Content You Have Consumed": "#06B6D4",
}


def get_theme(dark_mode: bool) -> dict:
    return DARK if dark_mode else LIGHT


def category_accent(category_name: str) -> str:
    return CATEGORY_ACCENTS.get(category_name, LIGHT["accent"])


def apply_theme(root: tk.Misc, theme: dict) -> None:
    root.configure(bg=theme["bg"])
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    bg = theme["bg"]
    fg = theme["fg"]
    surface = theme["surface"]
    muted = theme["muted"]

    style.configure(".", background=bg, foreground=fg, font=FONTS["body"])
    style.configure("TFrame", background=bg)
    style.configure("Surface.TFrame", background=surface)
    style.configure("TLabel", background=bg, foreground=fg)
    style.configure("Title.TLabel", background=bg, foreground=fg, font=FONTS["title"])
    style.configure("Heading.TLabel", background=bg, foreground=fg, font=FONTS["heading"])
    style.configure("Subheading.TLabel", background=bg, foreground=fg, font=FONTS["subheading"])
    style.configure("Muted.TLabel", background=bg, foreground=muted, font=FONTS["body"])
    style.configure("Accent.TLabel", foreground=theme["accent"], background=bg, font=FONTS["body_bold"])
    style.configure("Success.TLabel", foreground=theme["success"], background=bg, font=FONTS["body_bold"])
    style.configure("Stat.TLabel", foreground=theme["streak"], background=bg, font=FONTS["stat"])

    style.configure("OnSurface.TLabel", background=surface, foreground=fg, font=FONTS["body"])
    style.configure("OnSurfaceMuted.TLabel", background=surface, foreground=muted, font=FONTS["body"])
    style.configure("OnSurfaceSubheading.TLabel", background=surface, foreground=fg, font=FONTS["subheading"])

    style.configure("TLabelframe", background=bg, bordercolor=theme["card_border"], relief="flat")
    style.configure("TLabelframe.Label", background=bg, foreground=fg, font=FONTS["subheading"])
    style.configure(
        "Card.TLabelframe",
        background=surface,
        bordercolor=theme["card_border"],
        relief="solid",
        borderwidth=1,
    )
    style.configure("Card.TLabelframe.Label", background=surface, foreground=fg, font=FONTS["subheading"])

    style.configure(
        "TButton",
        padding=(12, 6),
        font=FONTS["button"],
        background=surface,
        bordercolor=theme["card_border"],
    )
    style.map("TButton", background=[("active", theme["surface_alt"]), ("pressed", theme["card_border"])])
    style.configure(
        "Accent.TButton",
        padding=(12, 6),
        font=FONTS["button"],
        background=theme["accent"],
        foreground="#FFFFFF",
        bordercolor=theme["accent_dark"],
    )
    style.map(
        "Accent.TButton",
        background=[("active", theme["accent_dark"]), ("pressed", theme["accent_dark"])],
    )
    style.configure(
        "Logged.TButton",
        padding=(10, 5),
        font=FONTS["button"],
        background=theme["success_bg"],
        foreground=theme["success"],
        bordercolor=theme["success"],
    )

    style.configure("TCheckbutton", background=bg, foreground=fg)
    style.configure("TRadiobutton", background=bg, foreground=fg)
    style.configure("TNotebook", background=bg, borderwidth=0)
    style.configure("TNotebook.Tab", background=bg, foreground=fg, padding=(14, 8), font=FONTS["body"])
    style.map("TNotebook.Tab", background=[("selected", surface)])

    style.configure(
        "TEntry",
        fieldbackground=surface,
        foreground=fg,
        bordercolor=theme["card_border"],
        padding=4,
    )
    style.configure(
        "TCombobox",
        fieldbackground=surface,
        background=surface,
        padding=4,
    )
    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=theme["surface_alt"],
        background=theme["accent"],
        bordercolor=theme["card_border"],
        lightcolor=theme["accent"],
        darkcolor=theme["accent"],
        thickness=8,
    )
    style.configure(
        "Treeview",
        background=surface,
        fieldbackground=surface,
        foreground=fg,
        rowheight=26,
        bordercolor=theme["card_border"],
    )
    style.configure(
        "Treeview.Heading",
        background=theme["surface_alt"],
        foreground=fg,
        font=FONTS["body_bold"],
        relief="flat",
    )
    style.map("Treeview", background=[("selected", theme["select_bg"])], foreground=[("selected", fg)])
    style.configure("TSeparator", background=theme["card_border"])


def configure_fitness_tree_tags(tree: ttk.Treeview, theme: dict) -> None:
    tree.tag_configure("book", font=FONTS["heading"])
    tree.tag_configure("program", font=FONTS["body_bold"])
    tree.tag_configure("current", background=theme["warning_bg"])
    tree.tag_configure("mastered", foreground=theme["success"])
    tree.tag_configure("available", foreground=theme["link"])
    tree.tag_configure("in_progress", foreground=theme["streak"])
    tree.tag_configure("locked", foreground=theme["muted"])


def make_card(parent: tk.Misc, theme: dict, accent: str | None = None, padding: int = 12) -> tuple[tk.Frame, tk.Frame]:
    outer = tk.Frame(parent, bg=theme["card_border"], padx=1, pady=1)
    inner_wrap = tk.Frame(outer, bg=theme["surface"])
    inner_wrap.pack(fill=tk.BOTH, expand=True)
    if accent:
        stripe = tk.Frame(inner_wrap, bg=accent, width=4)
        stripe.pack(side=tk.LEFT, fill=tk.Y)
        stripe.pack_propagate(False)
    inner = tk.Frame(inner_wrap, bg=theme["surface"], padx=padding, pady=padding)
    inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    return outer, inner


def streak_badge(parent: tk.Misc, theme: dict, text: str) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme["bg"])
    pill = tk.Label(
        frame,
        text=text,
        font=FONTS["stat"],
        fg="#FFFFFF",
        bg=theme["streak"],
        padx=12,
        pady=4,
    )
    pill.pack()
    return frame


def style_text_widget(widget: tk.Text, theme: dict) -> None:
    widget.configure(
        bg=theme["text_bg"],
        fg=theme["text_fg"],
        insertbackground=theme["fg"],
        selectbackground=theme["select_bg"],
        relief=tk.FLAT,
        highlightthickness=1,
        highlightbackground=theme["card_border"],
        highlightcolor=theme["accent"],
        font=FONTS["body"],
        padx=8,
        pady=8,
    )


def style_listbox(widget: tk.Listbox, theme: dict) -> None:
    widget.configure(
        bg=theme["text_bg"],
        fg=theme["text_fg"],
        selectbackground=theme["select_bg"],
        selectforeground=theme["fg"],
        highlightthickness=0,
        borderwidth=1,
        font=FONTS["body"],
    )


def style_canvas(widget: tk.Canvas, theme: dict) -> None:
    widget.configure(bg=theme["bg"], highlightthickness=0)

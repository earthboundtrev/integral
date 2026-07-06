"""Shared visual theme for the Personal Development Tracker (Tkinter/ttk)."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

# Calm, journal-like palette — readable, low visual noise, one accent color.
COLORS = {
    "bg": "#F4F5F7",
    "surface": "#FFFFFF",
    "surface_alt": "#EEF0F3",
    "border": "#D8DCE3",
    "text": "#1A1D21",
    "text_muted": "#5C6370",
    "accent": "#2F7A7B",
    "accent_dark": "#256264",
    "streak": "#D97706",
    "success": "#059669",
    "success_bg": "#ECFDF5",
    "warning_bg": "#FEF3C7",
    "warning_text": "#92400E",
    "danger": "#DC2626",
    "link": "#2563EB",
}

CATEGORY_ACCENTS = {
    "Money/Freedom": "#3B82F6",
    "Body & Presence": "#EF4444",
    "Burnout Prevention & Energy Management": "#8B5CF6",
    "Creative/Mental Work": "#F59E0B",
    "Family/Logistics": "#14B8A6",
    "Search Practice": "#64748B",
    "Spiritual Development": "#A855F7",
    "Emotional Wellbeing": "#F97316",
}

_FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Helvetica"
FONTS = {
    "title": (_FONT_FAMILY, 22, "bold"),
    "heading": (_FONT_FAMILY, 14, "bold"),
    "subheading": (_FONT_FAMILY, 12, "bold"),
    "body": (_FONT_FAMILY, 10),
    "body_bold": (_FONT_FAMILY, 10, "bold"),
    "small": (_FONT_FAMILY, 9),
    "stat": (_FONT_FAMILY, 13, "bold"),
    "button": (_FONT_FAMILY, 10),
}

FITNESS_TREE_TAGS = {
    "current": {"background": COLORS["warning_bg"]},
    "mastered": {"foreground": COLORS["success"]},
    "available": {"foreground": COLORS["link"]},
    "in_progress": {"foreground": COLORS["streak"]},
    "locked": {"foreground": COLORS["text_muted"]},
    "program": {"font": FONTS["body_bold"]},
}

_theme_applied = False


def color(name: str) -> str:
    return COLORS[name]


def font(name: str) -> tuple:
    return FONTS[name]


def category_accent(category_name: str) -> str:
    return CATEGORY_ACCENTS.get(category_name, COLORS["accent"])


def configure_window(root: tk.Misc) -> None:
    """Set background on a Tk or Toplevel window."""
    try:
        root.configure(bg=COLORS["bg"])
    except tk.TclError:
        pass


def apply_theme(root: tk.Misc | None = None) -> ttk.Style:
    """Configure ttk styles once; optionally set window background."""
    global _theme_applied

    if root is not None:
        configure_window(root)

    style = ttk.Style(root)
    if _theme_applied:
        return style

    if "clam" in style.theme_names():
        style.theme_use("clam")

    base = {
        "background": COLORS["bg"],
        "foreground": COLORS["text"],
        "font": FONTS["body"],
    }
    style.configure(".", **base)
    style.configure("TFrame", background=COLORS["bg"])
    style.configure("Surface.TFrame", background=COLORS["surface"])
    style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("Muted.TLabel", background=COLORS["bg"], foreground=COLORS["text_muted"])
    style.configure("Title.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["title"])
    style.configure("Heading.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["heading"])
    style.configure("Subheading.TLabel", background=COLORS["bg"], foreground=COLORS["text"], font=FONTS["subheading"])
    style.configure("Stat.TLabel", background=COLORS["bg"], foreground=COLORS["streak"], font=FONTS["stat"])
    style.configure(
        "Success.TLabel",
        background=COLORS["bg"],
        foreground=COLORS["success"],
        font=FONTS["body_bold"],
    )
    style.configure(
        "OnSurface.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        font=FONTS["body"],
    )
    style.configure(
        "OnSurfaceMuted.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["text_muted"],
        font=FONTS["body"],
    )
    style.configure(
        "OnSurfaceSubheading.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        font=FONTS["subheading"],
    )
    style.configure(
        "OnSurfaceSuccess.TLabel",
        background=COLORS["surface"],
        foreground=COLORS["success"],
        font=FONTS["body_bold"],
    )

    style.configure(
        "TLabelframe",
        background=COLORS["bg"],
        bordercolor=COLORS["border"],
        relief="flat",
    )
    style.configure(
        "TLabelframe.Label",
        background=COLORS["bg"],
        foreground=COLORS["text"],
        font=FONTS["subheading"],
    )
    style.configure(
        "Card.TLabelframe",
        background=COLORS["surface"],
        bordercolor=COLORS["border"],
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "Card.TLabelframe.Label",
        background=COLORS["surface"],
        foreground=COLORS["text"],
        font=FONTS["subheading"],
    )

    style.configure(
        "TButton",
        font=FONTS["button"],
        padding=(12, 6),
        background=COLORS["surface"],
        bordercolor=COLORS["border"],
        focusthickness=0,
    )
    style.map(
        "TButton",
        background=[("active", COLORS["surface_alt"]), ("pressed", COLORS["border"])],
    )
    style.configure(
        "Accent.TButton",
        font=FONTS["button"],
        padding=(12, 6),
        background=COLORS["accent"],
        foreground="#FFFFFF",
        bordercolor=COLORS["accent_dark"],
    )
    style.map(
        "Accent.TButton",
        background=[("active", COLORS["accent_dark"]), ("pressed", COLORS["accent_dark"])],
        foreground=[("disabled", "#FFFFFF")],
    )
    style.configure(
        "Logged.TButton",
        font=FONTS["button"],
        padding=(10, 5),
        background=COLORS["success_bg"],
        foreground=COLORS["success"],
        bordercolor=COLORS["success"],
    )
    style.map(
        "Logged.TButton",
        background=[("active", "#D1FAE5"), ("pressed", "#A7F3D0")],
    )

    style.configure(
        "TEntry",
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        padding=4,
    )
    style.configure(
        "TCombobox",
        fieldbackground=COLORS["surface"],
        background=COLORS["surface"],
        arrowcolor=COLORS["text_muted"],
        padding=4,
    )
    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=COLORS["surface_alt"],
        background=COLORS["accent"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["accent"],
        darkcolor=COLORS["accent"],
        thickness=8,
    )
    style.configure(
        "Treeview",
        background=COLORS["surface"],
        fieldbackground=COLORS["surface"],
        foreground=COLORS["text"],
        rowheight=26,
        bordercolor=COLORS["border"],
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["surface_alt"],
        foreground=COLORS["text"],
        font=FONTS["body_bold"],
        relief="flat",
    )
    style.map("Treeview", background=[("selected", "#D1E7E7")], foreground=[("selected", COLORS["text"])])
    style.configure("TSeparator", background=COLORS["border"])
    style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
    style.configure("TNotebook.Tab", padding=(12, 6), font=FONTS["body"])

    _theme_applied = True
    return style


def make_card(parent: tk.Misc, accent: str | None = None, padding: int = 12) -> tuple[tk.Frame, tk.Frame]:
    """Card with optional left accent stripe. Returns (outer, inner) frames."""
    outer = tk.Frame(parent, bg=COLORS["border"], padx=1, pady=1)
    inner_wrap = tk.Frame(outer, bg=COLORS["surface"])
    inner_wrap.pack(fill=tk.BOTH, expand=True)

    if accent:
        stripe = tk.Frame(inner_wrap, bg=accent, width=4)
        stripe.pack(side=tk.LEFT, fill=tk.Y)
        stripe.pack_propagate(False)

    inner = tk.Frame(inner_wrap, bg=COLORS["surface"], padx=padding, pady=padding)
    inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    return outer, inner


def streak_badge(parent: tk.Misc, text: str) -> tk.Label:
    """Pill-shaped streak indicator."""
    frame = tk.Frame(parent, bg=COLORS["bg"])
    pill = tk.Label(
        frame,
        text=text,
        font=FONTS["stat"],
        fg="#FFFFFF",
        bg=COLORS["streak"],
        padx=12,
        pady=4,
    )
    pill.pack()
    return frame


def style_text_widget(widget: tk.Text) -> None:
    widget.configure(
        bg=COLORS["surface"],
        fg=COLORS["text"],
        insertbackground=COLORS["text"],
        relief="flat",
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["accent"],
        font=FONTS["body"],
        padx=8,
        pady=8,
    )


def configure_fitness_tree_tags(tree: ttk.Treeview) -> None:
    for tag, opts in FITNESS_TREE_TAGS.items():
        tree.tag_configure(tag, **opts)

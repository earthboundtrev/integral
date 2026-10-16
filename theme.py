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
    "muted": "#666666",  # Darkened from #5C6370 for 4.5:1 contrast on #EBEBEB
    "accent": "#2F7A7B",
    "accent_dark": "#256264",
    "accent_soft": "#D1E7E7",  # v2: soft accent background
    "on_accent": "#FFFFFF",  # v2: text on accent buttons
    "streak": "#D97706",
    "success": "#059669",
    "success_bg": "#ECFDF5",
    "link": "#2563EB",
    "surface": "#FFFFFF",
    "surface_alt": "#EEF0F3",
    "sidebar": "#FAFBFC",  # v2: sidebar background
    "card_border": "#D8DCE3",
    "text_bg": "#FFFFFF",
    "text_fg": "#1A1D21",
    "field_bg": "#FFFFFF",  # v2: input field background
    "select_bg": "#D1E7E7",
    "warning_bg": "#FEF3C7",
    "error": "#DC2626",  # v2: error text
    "error_bg": "#FEE2E2",  # v2: error background
    "disabled": "#9CA3AF",  # v2: disabled text
}

DARK = {
    "name": "dark",
    "bg": "#12151A",
    "fg": "#E8ECF1",
    "muted": "#9AA5B1",
    "accent": "#2F7A7B",  # Darkened from #3D9A9B for better contrast with white text
    "accent_dark": "#256264",
    "accent_soft": "#1E4A4B",  # v2: soft accent background
    "on_accent": "#FFFFFF",  # v2: text on accent buttons  
    "streak": "#F5A623",
    "success": "#3DDB87",
    "success_bg": "#0F2A22",
    "link": "#60A5FA",
    "surface": "#1C2128",
    "surface_alt": "#252B33",
    "sidebar": "#0D0F12",  # v2: sidebar background
    "card_border": "#3E4C59",
    "text_bg": "#1C2128",
    "text_fg": "#E8ECF1",
    "field_bg": "#1C2128",  # v2: input field background
    "select_bg": "#2A4A4B",
    "warning_bg": "#3D3420",
    "error": "#F87171",  # v2: error text
    "error_bg": "#3F1F1F",  # v2: error background
    "disabled": "#6B7280",  # v2: disabled text
}

FONTS = {
    # Existing keys (keep for compatibility)
    "title": (_FONT, 22, "bold"),
    "heading": (_FONT, 14, "bold"),
    "subheading": (_FONT, 12, "bold"),
    "body": (_FONT, 10),
    "body_bold": (_FONT, 10, "bold"),
    "small": (_FONT, 9),
    "stat": (_FONT, 13, "bold"),
    "button": (_FONT, 10),
    # v2 additions (§2.2)
    "h1": (_FONT, 24, "bold"),
    "h3": (_FONT, 16, "bold"),
    "brand": (_FONT, 20, "bold"),
    "caption": (_FONT, 11),
    "hint": (_FONT, 9),
    "menu_header": (_FONT, 10, "bold"),
}

# v2: Spacing tokens on 8px grid (§2.1)
SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
}

# System / Tk default backgrounds that must not appear on chrome widgets (#133).
FORBIDDEN_CHROME_BACKGROUNDS = frozenset(
    {
        "#d9d9d9",
        "#D9D9D9",
        "white",
        "#ffffff",
        "#FFFFFF",
        "SystemButtonFace",
        "SystemWindow",
        "#f0f0f0",
        "#F0F0F0",
    }
)

_CHROME_THEME_KEYS = ("bg", "surface", "sidebar", "surface_alt", "text_bg", "field_bg")

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


def is_forbidden_chrome_background(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip()
    if normalized in FORBIDDEN_CHROME_BACKGROUNDS:
        return True
    if normalized.lower() in {c.lower() for c in FORBIDDEN_CHROME_BACKGROUNDS if c.startswith("#")}:
        return True
    return False


def _remap_chrome_background(old_bg: str, theme: dict) -> str:
    """Map a prior theme chrome colour to the equivalent token in the active theme."""
    old_lower = old_bg.lower()
    for token in _CHROME_THEME_KEYS:
        for palette in (LIGHT, DARK):
            candidate = palette.get(token)
            if candidate is None:
                continue
            if candidate == old_bg or candidate.lower() == old_lower:
                return theme[token]
    if is_forbidden_chrome_background(old_bg):
        return theme["bg"]
    return old_bg


def apply_tk_option_defaults(root: tk.Misc, theme: dict) -> None:
    """Tcl option database defaults for plain tk widgets (§6.1)."""
    priority = 20
    options = {
        "*Background": theme["bg"],
        "*Foreground": theme["fg"],
        "*selectBackground": theme["select_bg"],
        "*selectForeground": theme["fg"],
        "*insertBackground": theme["fg"],
        "*highlightBackground": theme["card_border"],
        "*highlightColor": theme["accent"],
        "*Menu.background": theme["surface"],
        "*Menu.foreground": theme["fg"],
        "*Menu.activeBackground": theme["select_bg"],
        "*Menu.activeForeground": theme["fg"],
        "*Menu.disabledForeground": theme["disabled"],
        "*Listbox.background": theme["text_bg"],
        "*Listbox.foreground": theme["text_fg"],
        "*Listbox.selectBackground": theme["select_bg"],
        "*Listbox.selectForeground": theme["fg"],
        "*Text.background": theme["text_bg"],
        "*Text.foreground": theme["text_fg"],
        "*Text.selectBackground": theme["select_bg"],
        "*Text.insertBackground": theme["fg"],
        "*Entry.background": theme["field_bg"],
        "*Entry.foreground": theme["fg"],
        "*Entry.insertBackground": theme["fg"],
        "*Canvas.background": theme["bg"],
    }
    for pattern, value in options.items():
        root.option_add(pattern, value, priority)


def category_accent(category_name: str) -> str:
    return CATEGORY_ACCENTS.get(category_name, LIGHT["accent"])


def apply_theme(root: tk.Misc, theme: dict) -> None:
    root.configure(bg=theme["bg"])
    apply_tk_option_defaults(root, theme)
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
        foreground=fg,
        arrowcolor=fg,
        bordercolor=theme["card_border"],
        padding=4,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", surface), ("disabled", theme["surface_alt"])],
        selectbackground=[("readonly", theme["select_bg"])],
        selectforeground=[("readonly", fg)],
    )
    for orient, name in (("vertical", "Vertical"), ("horizontal", "Horizontal")):
        style.configure(
            f"{name}.TScrollbar",
            background=theme["surface_alt"],
            troughcolor=bg,
            bordercolor=theme["card_border"],
            arrowcolor=fg,
            relief="flat",
        )
        style.map(
            f"{name}.TScrollbar",
            background=[("active", theme["card_border"]), ("pressed", theme["card_border"])],
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
    reapply_theme_subtree(root, theme)


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


def streak_badge(
    parent: tk.Misc,
    theme: dict,
    text: str,
    *,
    command=None,
    clickable_hint: str = " · details",
) -> tk.Frame:
    """Header streak pill. When command is set, show a details affordance and hand cursor."""
    frame = tk.Frame(parent, bg=theme["bg"])
    label_text = f"{text}{clickable_hint}" if command else text
    pill = tk.Label(
        frame,
        text=label_text,
        font=FONTS["stat"],
        fg="#FFFFFF",
        bg=theme["streak"],
        padx=12,
        pady=4,
        cursor="hand2" if command else "",
        relief=tk.FLAT,
        borderwidth=0,
    )
    pill.pack()
    if command:
        pill.bind("<Button-1>", lambda _e: command())
        frame.bind("<Button-1>", lambda _e: command())

        def on_enter(_e=None) -> None:
            pill.configure(relief=tk.GROOVE, borderwidth=1)

        def on_leave(_e=None) -> None:
            pill.configure(relief=tk.FLAT, borderwidth=0)

        pill.bind("<Enter>", on_enter)
        pill.bind("<Leave>", on_leave)
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


def style_canvas(widget: tk.Canvas, theme: dict, *, bg: str | None = None) -> None:
    widget.configure(bg=bg or theme["bg"], highlightthickness=0)


def style_menu(menu: tk.Menu, theme: dict) -> None:
    menu.configure(
        bg=theme["surface"],
        fg=theme["fg"],
        activebackground=theme["select_bg"],
        activeforeground=theme["fg"],
        disabledforeground=theme["disabled"],
        borderwidth=0,
        relief=tk.FLAT,
    )


def apply_scroll_chrome(
    outer: tk.Misc,
    inner: tk.Misc,
    canvas: tk.Canvas,
    theme: dict,
    *,
    bg: str | None = None,
) -> None:
    """Style plain tk scroll hosts (Frames + Canvas) to match the active theme."""
    fill = bg or theme["bg"]
    for widget in (outer, inner):
        try:
            widget.configure(bg=fill, highlightthickness=0)
        except tk.TclError:
            pass
    style_canvas(canvas, theme, bg=fill)


def _reapply_tk_widget(widget: tk.Misc, theme: dict) -> None:
    cls = widget.winfo_class()
    try:
        if cls == "Canvas":
            current = widget.cget("bg")
            bg = _remap_chrome_background(current, theme)
            style_canvas(widget, theme, bg=bg)
        elif cls == "Text":
            style_text_widget(widget, theme)
        elif cls == "Listbox":
            style_listbox(widget, theme)
        elif cls == "Menu":
            style_menu(widget, theme)
        elif cls == "Entry":
            widget.configure(
                bg=theme["field_bg"],
                fg=theme["fg"],
                insertbackground=theme["fg"],
                selectbackground=theme["select_bg"],
                selectforeground=theme["fg"],
                highlightbackground=theme["card_border"],
                highlightcolor=theme["accent"],
            )
        elif cls in ("Frame", "Label"):
            current = widget.cget("bg")
            if is_forbidden_chrome_background(current) or current in {
                LIGHT[k] for k in _CHROME_THEME_KEYS
            } | {DARK[k] for k in _CHROME_THEME_KEYS}:
                widget.configure(bg=_remap_chrome_background(current, theme), highlightthickness=0)
            if cls == "Label":
                fg = widget.cget("fg")
                if fg in (LIGHT["fg"], DARK["fg"]):
                    widget.configure(fg=theme["fg"])
                elif fg in (LIGHT["muted"], DARK["muted"]):
                    widget.configure(fg=theme["muted"])
    except tk.TclError:
        return


def reapply_theme_subtree(root: tk.Misc, theme: dict) -> None:
    """Live re-theme for plain tk widgets under root (§6.3)."""
    _reapply_tk_widget(root, theme)
    for child in root.winfo_children():
        reapply_theme_subtree(child, theme)


def collect_forbidden_backgrounds(root: tk.Misc) -> list[tuple[str, str, str]]:
    """Return (widget_path, class, bg) for widgets using forbidden chrome backgrounds."""
    hits: list[tuple[str, str, str]] = []

    def walk(widget: tk.Misc) -> None:
        cls = widget.winfo_class()
        if cls in ("Frame", "Canvas", "Label", "Listbox", "Text", "Entry"):
            try:
                bg = widget.cget("bg")
            except tk.TclError:
                bg = ""
            if is_forbidden_chrome_background(bg):
                hits.append((str(widget), cls, bg))
        for child in widget.winfo_children():
            walk(child)

    walk(root)
    return hits

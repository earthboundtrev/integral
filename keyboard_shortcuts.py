"""Global keyboard shortcuts for the app shell (#111)."""

from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Any, Callable

import nav_items
from theme import FONTS, LIGHT, style_text_widget

# Tk event.state bits (platform quirks: treat Meta/Mod1 as Alt for AltGr rejection).
_SHIFT_MASK = 0x0001
_CONTROL_MASK = 0x0004
_ALT_MASKS = (0x0008, 0x20000, 0x80000)

SHORTCUT_ROWS: tuple[tuple[str, str], ...] = (
    ("Quick Capture / Today todo", "Ctrl+Shift+T"),
    ("Log workout", "Ctrl+Shift+W"),
    ("Daily reflection (Reflect)", "Ctrl+Shift+R"),
    ("Journal", "Ctrl+Shift+J"),
    ("Weekly Summary", "Ctrl+Shift+I"),
    ("Graphs & Progress", "Ctrl+Shift+G"),
    ("Go to…", "Ctrl+K"),
    ("This shortcuts list", "Ctrl+Shift+/ or F1"),
)

SIDEBAR_SHORTCUTS: dict[str, str] = {
    "reflect": "Ctrl+Shift+R",
    "journal": "Ctrl+Shift+J",
    "graphs": "Ctrl+Shift+G",
    "weekly_summary": "Ctrl+Shift+I",
}

MORE_ITEM_SHORTCUT_HINTS: dict[str, str] = {
    "quick_capture": "Ctrl+Shift+T",
    "log_exercise": "Ctrl+Shift+W",
    "keyboard_shortcuts": "F1",
    "goto_palette": "Ctrl+K",
}

INLINE_BUTTON_SHORTCUTS: dict[str, str] = {
    "Log workout": "Ctrl+Shift+W",
    "Reflect": "Ctrl+Shift+R",
    "Journal": "Ctrl+Shift+J",
    "Quick Capture": "Ctrl+Shift+T",
}

# Microsoft IME may swallow Ctrl+Shift chords during composition — acceptable (documented in dialog).
_IME_NOTE = (
    "Note: Some IMEs (Japanese, Chinese, Korean) may capture Ctrl+Shift keys while composing text. "
    "Windows layout hotkeys (Ctrl+Shift or Alt+Shift) may still switch language when you release the "
    "chord alone; the shortcut action runs when the full chord is pressed."
)


def alt_in_event_state(state: int) -> bool:
    """True when Alt/AltGr (Ctrl+Alt) is held — reject global shortcuts."""
    return any(state & mask for mask in _ALT_MASKS)


def effective_control_shift(event: tk.Event) -> bool:
    """True when the Shift modifier is held (Caps Lock alone does not count)."""
    return bool(event.state & _SHIFT_MASK)


def shortcut_may_run(tracker: Any, event: tk.Event | None = None) -> bool:
    if event is not None and alt_in_event_state(int(event.state)):
        return False
    try:
        if tracker.root.grab_current() is not None:
            return False
    except tk.TclError:
        pass
    return True


def _wrap_shift_chord(tracker: Any, action: Callable[[], None]) -> Callable[[tk.Event], str | None]:
    def handler(event: tk.Event) -> str | None:
        if not shortcut_may_run(tracker, event):
            return None
        if not effective_control_shift(event):
            return None
        action()
        return "break"

    return handler


def _wrap_plain(tracker: Any, action: Callable[[], None]) -> Callable[[tk.Event], str | None]:
    def handler(event: tk.Event) -> str | None:
        if not shortcut_may_run(tracker, event):
            return None
        action()
        return "break"

    return handler


def _wrap_goto(tracker: Any) -> Callable[[tk.Event], str | None]:
    def handler(event: tk.Event) -> str | None:
        if alt_in_event_state(int(event.state)):
            return None
        if event.state & _SHIFT_MASK:
            return None
        if not shortcut_may_run(tracker, event):
            return None
        tracker.show_goto()
        return "break"

    return handler


def shortcut_focus_today_todo(tracker: Any) -> None:
    tracker._raise_or_open("today")
    entry = getattr(tracker, "_inline_todo_entry", None)
    if entry is not None:
        try:
            if entry.winfo_exists():
                entry.focus_set()
                return
        except tk.TclError:
            pass
    tracker._qc_should_focus = True
    tracker.set_quick_capture_enabled(True)


def shortcut_log_workout(tracker: Any) -> None:
    tracker.show_log_exercise()


def show_keyboard_shortcuts(tracker: Any) -> None:
    existing = getattr(tracker, "_shortcuts_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                return
        except tk.TclError:
            pass
        tracker._shortcuts_window = None

    theme = tracker.theme
    window = tk.Toplevel(tracker.root)
    tracker._shortcuts_window = window
    window.title("Keyboard shortcuts")
    window.geometry("520x480")
    window.minsize(400, 320)
    window.transient(tracker.root)
    window.configure(bg=theme["bg"])

    def on_close() -> None:
        if getattr(tracker, "_shortcuts_window", None) is window:
            tracker._shortcuts_window = None
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", on_close)

    header = ttk.Frame(window, padding=(16, 12))
    header.pack(fill=tk.X)
    ttk.Label(header, text="Keyboard shortcuts", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        header,
        text="Global shortcuts work from the main window and open tool windows.",
        style="Muted.TLabel",
        wraplength=480,
    ).pack(anchor="w", pady=(4, 0))

    body = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=FONTS["body"], height=16)
    style_text_widget(body, theme)
    body.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))
    body.configure(state=tk.NORMAL)
    for label, keys in SHORTCUT_ROWS:
        body.insert(tk.END, f"{keys:<22}  {label}\n")
    body.insert(tk.END, f"\n{_IME_NOTE}\n")
    body.configure(state=tk.DISABLED)

    footer = ttk.Frame(window, padding=(16, 10))
    footer.pack(fill=tk.X)
    ttk.Button(footer, text="Close", command=on_close).pack(side=tk.RIGHT)


def attach_shortcut_tooltip(
    widget: tk.Misc,
    base_text: str,
    shortcut: str,
    theme: dict | None = None,
) -> None:
    """Hover tooltip showing base label and shortcut chord."""
    colors = theme or LIGHT
    tip_bg = colors.get("surface_alt", colors["bg"])
    tip_fg = colors["fg"]
    tip_state: dict[str, tk.Toplevel | None] = {"win": None}

    def show(_event: tk.Event) -> None:
        if tip_state["win"] is not None:
            return
        tip = tk.Toplevel(widget)
        tip.wm_overrideredirect(True)
        tip.attributes("-topmost", True)
        text = f"{base_text} ({shortcut})" if base_text else shortcut
        tk.Label(
            tip,
            text=text,
            bg=tip_bg,
            fg=tip_fg,
            relief=tk.SOLID,
            borderwidth=1,
            padx=6,
            pady=3,
            font=FONTS["hint"],
        ).pack()
        tip.update_idletasks()
        x = widget.winfo_rootx() + 8
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        tip.geometry(f"+{x}+{y}")
        tip_state["win"] = tip

    def hide(_event: tk.Event) -> None:
        tip = tip_state["win"]
        if tip is not None:
            tip.destroy()
            tip_state["win"] = None

    widget.bind("<Enter>", show, add="+")
    widget.bind("<Leave>", hide, add="+")


def _bind_shift_letter(
    root: tk.Misc,
    letter: str,
    tracker: Any,
    action: Callable[[], None],
) -> None:
    upper = letter.upper()
    lower = letter.lower()
    handler = _wrap_shift_chord(tracker, action)
    for seq in (f"<Control-Shift-{upper}>", f"<Control-Shift-{lower}>"):
        root.bind_all(seq, handler, add="+")


def install_global_shortcuts(tracker: Any) -> None:
    """Bind global shortcuts once per tracker instance."""
    if getattr(tracker, "_keyboard_shortcuts_bound", False):
        return
    root = tracker.root
    goto_handler = _wrap_goto(tracker)

    for seq in ("<Control-k>", "<Control-K>"):
        root.bind_all(seq, goto_handler, add="+")

    for class_name in ("Text", "Entry", "TEntry"):
        for seq in ("<Control-k>", "<Control-K>"):
            root.bind_class(class_name, seq, goto_handler)

    _bind_shift_letter(root, "T", tracker, lambda: shortcut_focus_today_todo(tracker))
    _bind_shift_letter(root, "W", tracker, lambda: shortcut_log_workout(tracker))
    _bind_shift_letter(
        root,
        "R",
        tracker,
        lambda: tracker._run_nav_shortcut("reflect", tracker.show_reflect),
    )
    _bind_shift_letter(
        root,
        "J",
        tracker,
        lambda: tracker._run_nav_shortcut(
            "journal", lambda: tracker._raise_or_open("journal")
        ),
    )
    _bind_shift_letter(
        root,
        "I",
        tracker,
        lambda: tracker._run_nav_shortcut("weekly_summary", tracker.show_weekly_summary),
    )
    _bind_shift_letter(
        root,
        "G",
        tracker,
        lambda: tracker._run_nav_shortcut("graphs", lambda: tracker._raise_or_open("graphs")),
    )

    show_list = _wrap_shift_chord(tracker, lambda: show_keyboard_shortcuts(tracker))
    for seq in (
        "<Control-Shift-slash>",
        "<Control-Shift-question>",
    ):
        try:
            root.bind_all(seq, show_list, add="+")
        except tk.TclError:
            pass

    root.bind_all("<F1>", _wrap_plain(tracker, lambda: show_keyboard_shortcuts(tracker)), add="+")

    tracker._keyboard_shortcuts_bound = True


def apply_sidebar_shortcut_tooltips(tracker: Any) -> None:
    """Attach shortcut tooltips to sidebar nav buttons (call after sidebar build)."""
    id_by_label = {item.id: item.label for item in nav_items.sidebar_nav_items()}
    frames = getattr(tracker, "_sidebar_nav_frames", {})
    for nav_id, shortcut in SIDEBAR_SHORTCUTS.items():
        frame = frames.get(nav_id)
        if frame is None:
            continue
        label = id_by_label.get(nav_id, nav_id)
        for child in frame.winfo_children():
            attach_shortcut_tooltip(child, label, shortcut, tracker.theme)

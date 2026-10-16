"""Go to… command palette — jump to screens and Log domain shortcuts."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

import nav_items
from theme import style_listbox
from todays_log import CATEGORY_SHORT_LABELS


def _action_for_nav_item(tracker: Any, item: nav_items.NavItem) -> Callable[[], None]:
    actions: dict[str, Callable[[], None]] = {
        "today": lambda: tracker._raise_or_open("today"),
        "reflect": tracker.show_reflect,
        "overview_categories": tracker.show_streak_details,
        "refresh": lambda: tracker.refresh_dashboard(full=False, recompute=False),
        "guidance": tracker.show_guidance,
        "weekly_summary": tracker.show_weekly_summary,
        "ai_insight": lambda: tracker._show_ai_insight(default_days=7),
        "history": tracker.show_history,
        "search": tracker.show_search,
        "graphs": tracker.show_graphs,
        "journal": tracker.show_journal,
        "writing_projects": tracker.show_writing_projects,
        "deep_work": tracker.show_deep_work,
        "quick_capture": tracker.toggle_quick_capture,
        "plan_tomorrow": tracker.show_plan_tomorrow,
        "log_exercise": tracker.show_log_exercise,
        "fitness_hub": tracker.show_fitness_hub,
        "milestones": tracker.show_milestones,
        "export": tracker.show_export,
        "backup": tracker.show_backup,
        "settings": tracker.show_settings,
        "security": tracker.show_security,
        "toggle_theme": tracker.toggle_dark_mode,
    }
    return actions[item.id]


def build_goto_destinations(tracker: Any) -> list[dict[str, Any]]:
    """
    Build searchable destinations for the Go to… palette.

    Each item: {"label": str, "group": str, "keywords": str, "action": callable}
    """
    destinations: list[dict[str, Any]] = []
    for item in nav_items.goto_nav_items():
        if nav_items.is_hidden_during_deep_work(item_id=item.id, tracker=tracker):
            continue
        destinations.append(
            {
                "label": item.label,
                "group": item.goto_group,
                "keywords": item.goto_keywords,
                "action": _action_for_nav_item(tracker, item),
                "nav_id": item.id,
            }
        )

    for name in tracker.categories.keys():
        short = CATEGORY_SHORT_LABELS.get(name, name)
        destinations.append(
            {
                "label": f"Log {short}",
                "group": "Log",
                "keywords": f"{name} {short} domain category log",
                "action": lambda n=name: tracker.open_log_dialog(n),
                "nav_id": None,
            }
        )
    return destinations


def filter_goto_destinations(
    destinations: list[dict[str, Any]], query: str
) -> list[dict[str, Any]]:
    needle = query.strip().lower()
    if not needle:
        return list(destinations)
    hits: list[dict[str, Any]] = []
    for item in destinations:
        blob = f"{item.get('label', '')} {item.get('group', '')} {item.get('keywords', '')}".lower()
        if needle in blob:
            hits.append(item)
    return hits


def open_goto_palette(tracker: Any) -> None:
    """Modal Go to… palette with live filter (single instance)."""
    existing = getattr(tracker, "_goto_window", None)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                return
        except tk.TclError:
            pass

    theme = tracker.theme
    window = tk.Toplevel(tracker.root)
    tracker._goto_window = window
    window.title("Go to…")
    window.geometry("520x420")
    window.minsize(400, 320)
    window.transient(tracker.root)
    window.grab_set()
    window.configure(bg=theme.get("bg", "#f5f5f5"))

    def close_palette() -> None:
        try:
            if getattr(tracker, "_goto_window", None) is window:
                tracker._goto_window = None
        except Exception:
            pass
        window.destroy()

    footer = ttk.Frame(window, padding=(12, 10))
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Label(
        footer,
        text="Type to filter · Enter or double-click to open · Esc closes",
        style="Muted.TLabel",
    ).pack(side=tk.LEFT)
    ttk.Button(footer, text="Close", command=close_palette).pack(side=tk.RIGHT)

    top = ttk.Frame(window, padding=(12, 10))
    top.pack(side=tk.TOP, fill=tk.X)
    ttk.Label(top, text="Go to:").pack(side=tk.LEFT)
    query_var = tk.StringVar()
    entry = ttk.Entry(top, textvariable=query_var)
    entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(8, 0))

    list_frame = ttk.Frame(window, padding=(12, 0))
    list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    listbox = tk.Listbox(list_frame, activestyle="dotbox", exportselection=False)
    style_listbox(listbox, theme)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    listbox.configure(yscrollcommand=scroll.set)

    all_destinations = build_goto_destinations(tracker)
    visible: list[dict[str, Any]] = []

    def refresh(*_args: object) -> None:
        nonlocal visible
        visible = filter_goto_destinations(all_destinations, query_var.get())
        listbox.delete(0, tk.END)
        for item in visible:
            listbox.insert(tk.END, f"{item['group']}  ·  {item['label']}")
        if visible:
            listbox.selection_set(0)
            listbox.activate(0)

    def run_selected(_event=None) -> None:
        selection = listbox.curselection()
        if not selection:
            return
        index = int(selection[0])
        if index < 0 or index >= len(visible):
            return
        dest = visible[index]
        nav_id = dest.get("nav_id")
        if nav_id and nav_items.deep_work_blocks_action(tracker, item_id=str(nav_id)):
            return
        action: Callable[[], None] = dest["action"]
        close_palette()
        action()

    query_var.trace_add("write", refresh)
    listbox.bind("<Double-1>", run_selected)
    listbox.bind("<Return>", run_selected)
    entry.bind("<Return>", run_selected)
    entry.bind("<Down>", lambda _e: (listbox.focus_set(), listbox.selection_set(0)))
    window.bind("<Escape>", lambda _e: close_palette())
    window.protocol("WM_DELETE_WINDOW", close_palette)
    refresh()
    entry.focus_set()

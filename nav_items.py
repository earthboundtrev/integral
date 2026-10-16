"""Canonical navigation registry — surfaces, labels, and Deep Work visibility (#132)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

Surface = Literal["sidebar", "more", "goto", "today_more"]

# Muted hint shown in sidebar / More when items are hidden (Q3: hide, not grey out).
DEEP_WORK_HIDDEN_HINT = "Deep Work: some items hidden"


@dataclass(frozen=True)
class NavItem:
    """One navigable destination shared across shell surfaces."""

    id: str
    label: str
    hide_in_deep_work: bool
    surfaces: frozenset[Surface]
    goto_keywords: str = ""
    goto_group: str = "Nav"


def _surfaces(*names: Surface) -> frozenset[Surface]:
    return frozenset(names)


# Single source of truth for shell navigation and Deep Work chrome policy.
NAV_ITEMS: tuple[NavItem, ...] = (
    NavItem("today", "Today", False, _surfaces("sidebar", "goto"), "today todays log rating domains"),
    NavItem(
        "fitness_hub",
        "Fitness Hub",
        True,
        _surfaces("sidebar", "today_more", "goto"),
        "fitness hub progression",
        "Fitness",
    ),
    NavItem(
        "reflect",
        "Reflect",
        True,
        _surfaces("sidebar", "goto"),
        "reflect log unlogged domain",
    ),
    NavItem(
        "journal",
        "Journal",
        False,
        _surfaces("sidebar", "goto"),
        "journal write",
    ),
    NavItem(
        "graphs",
        "Graphs & Progress",
        True,
        _surfaces("sidebar", "goto"),
        "graphs charts progress",
    ),
    NavItem(
        "weekly_summary",
        "Weekly Summary",
        True,
        _surfaces("sidebar", "goto"),
        "week summary report",
    ),
    NavItem("goto_palette", "Go to…", True, _surfaces("sidebar", "today_more"), ""),
    NavItem(
        "refresh",
        "Refresh",
        False,
        _surfaces("more", "goto"),
        "refresh reload overview",
    ),
    NavItem("guidance", "Guidance", True, _surfaces("more", "goto"), "insights tips"),
    NavItem(
        "history",
        "Full History",
        True,
        _surfaces("more", "goto"),
        "history past days",
    ),
    NavItem(
        "search",
        "Search Notes",
        True,
        _surfaces("more", "goto"),
        "search notes find text",
    ),
    NavItem(
        "milestones",
        "Milestones",
        True,
        _surfaces("more", "goto"),
        "goals milestones",
    ),
    NavItem(
        "ai_insight",
        "AI Insight",
        False,
        _surfaces("more", "today_more", "goto"),
        "ollama ai insight",
    ),
    NavItem(
        "quick_capture",
        "Quick Capture",
        False,
        _surfaces("more", "today_more", "goto"),
        "todos quick capture",
    ),
    NavItem(
        "writing_projects",
        "Writing Projects",
        False,
        _surfaces("more", "today_more", "goto"),
        "writing novel manuscript creative",
    ),
    NavItem(
        "deep_work",
        "Deep Work",
        False,
        _surfaces("more", "today_more", "goto"),
        "focus timer deep work",
    ),
    NavItem("export", "Export", True, _surfaces("more", "goto"), "export csv", "Data"),
    NavItem("backup", "Backup", True, _surfaces("more", "goto"), "backup restore zip", "Data"),
    NavItem(
        "settings",
        "Edit Categories",
        True,
        _surfaces("more", "goto"),
        "categories domains settings edit",
        "Settings",
    ),
    NavItem(
        "security",
        "Data & Security",
        True,
        _surfaces("more", "goto"),
        "security vault encryption",
        "Settings",
    ),
    NavItem(
        "toggle_theme",
        "Toggle Dark / Light Mode",
        True,
        _surfaces("more", "goto"),
        "theme dark light mode",
        "Settings",
    ),
    NavItem(
        "plan_tomorrow",
        "Plan Tomorrow",
        False,
        _surfaces("today_more", "goto"),
        "plan tomorrow day plan",
    ),
    NavItem(
        "log_exercise",
        "Log Exercise",
        False,
        _surfaces("today_more", "goto"),
        "workout exercise session log",
        "Fitness",
    ),
    NavItem(
        "overview_categories",
        "Overview & Categories",
        False,
        _surfaces("goto"),
        "streak details overview categories activity grid guidance",
    ),
)

_NAV_BY_ID: dict[str, NavItem] = {item.id: item for item in NAV_ITEMS}
_NAV_BY_LABEL: dict[str, NavItem] = {item.label: item for item in NAV_ITEMS}

# Sidebar display overrides (emoji prefix, etc.).
SIDEBAR_DISPLAY_LABELS: dict[str, str] = {
    "goto_palette": "🔍 Go to…",
}

# More menu rows use item ids from MORE_GROUPS; map to nav policy.
MORE_MENU_ITEM_IDS: frozenset[str] = frozenset(
    item.id
    for item in NAV_ITEMS
    if "more" in item.surfaces and item.id != "goto_palette"
)

THEME_MENU_LABELS: frozenset[str] = frozenset({"Dark Mode", "Light Mode"})


def nav_item_for_id(item_id: str) -> NavItem | None:
    return _NAV_BY_ID.get(item_id)


def nav_item_for_label(label: str) -> NavItem | None:
    if label in _NAV_BY_LABEL:
        return _NAV_BY_LABEL[label]
    if label in THEME_MENU_LABELS:
        return _NAV_BY_ID.get("toggle_theme")
    return None


def sidebar_nav_items() -> tuple[NavItem, ...]:
    return tuple(item for item in NAV_ITEMS if "sidebar" in item.surfaces and item.id != "goto_palette")


def goto_nav_items() -> tuple[NavItem, ...]:
    return tuple(item for item in NAV_ITEMS if "goto" in item.surfaces)


def deep_work_active(tracker: Any) -> bool:
    session = getattr(tracker, "_deep_work_session", None)
    return bool(session and session.running)


def is_hidden_during_deep_work(
    *,
    item_id: str | None = None,
    label: str | None = None,
    tracker: Any | None = None,
) -> bool:
    """Return True when Deep Work is running and this destination should not appear."""
    if tracker is not None and not deep_work_active(tracker):
        return False
    item: NavItem | None = None
    if item_id:
        item = nav_item_for_id(item_id)
    elif label:
        item = nav_item_for_label(label)
    if item is None:
        return False
    return item.hide_in_deep_work


def labels_hidden_during_deep_work() -> frozenset[str]:
    """Labels hidden in shell chrome while Deep Work runs (legacy constant sync)."""
    hidden: set[str] = set()
    for item in NAV_ITEMS:
        if item.hide_in_deep_work:
            hidden.add(item.label)
            if item.id == "toggle_theme":
                hidden.update(THEME_MENU_LABELS)
            if item.id == "goto_palette":
                hidden.add("Go to…")
    return frozenset(hidden)


def labels_kept_during_deep_work() -> frozenset[str]:
    kept: set[str] = set()
    for item in NAV_ITEMS:
        if not item.hide_in_deep_work:
            kept.add(item.label)
    return frozenset(kept)


def any_shell_items_hidden_during_deep_work() -> bool:
    return any(item.hide_in_deep_work for item in NAV_ITEMS)


def deep_work_blocks_action(tracker: Any, *, item_id: str | None = None, label: str | None = None) -> bool:
    """
    If Deep Work hides this destination, show a brief notice and return True (blocked).
    """
    if not deep_work_active(tracker):
        return False
    if not is_hidden_during_deep_work(item_id=item_id, label=label, tracker=tracker):
        return False
    from tkinter import messagebox

    messagebox.showinfo(
        "Deep Work",
        "Hidden during Deep Work.",
        parent=getattr(tracker, "root", None),
    )
    return True

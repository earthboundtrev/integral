"""Deep Work Mode — pure timer state (SPEC-305)."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PRESETS = (25, 50, 90)
DEFAULT_MINUTES = 50
EXTEND_MINUTES = 10


@dataclass
class DeepWorkSession:
    duration_seconds: int
    remaining_seconds: int
    running: bool = False
    completed: bool = False

    def tick(self, seconds: int = 1) -> bool:
        """Advance the clock. Returns True when the session just completed."""
        if not self.running or self.completed:
            return False
        self.remaining_seconds = max(0, self.remaining_seconds - max(0, seconds))
        if self.remaining_seconds <= 0:
            self.running = False
            self.completed = True
            return True
        return False

    def extend(self, minutes: int = EXTEND_MINUTES) -> None:
        if self.completed:
            self.completed = False
        self.remaining_seconds += max(0, int(minutes)) * 60
        self.duration_seconds += max(0, int(minutes)) * 60
        self.running = True

    def cancel(self) -> None:
        self.running = False
        self.completed = False
        self.remaining_seconds = 0

    def format_mmss(self) -> str:
        total = max(0, int(self.remaining_seconds))
        minutes, seconds = divmod(total, 60)
        return f"{minutes:02d}:{seconds:02d}"


def start_session(minutes: int) -> DeepWorkSession:
    minutes = max(1, int(minutes))
    seconds = minutes * 60
    return DeepWorkSession(
        duration_seconds=seconds,
        remaining_seconds=seconds,
        running=True,
        completed=False,
    )


def normalize_deep_work_settings(settings: dict | None) -> dict:
    base = {"last_minutes": DEFAULT_MINUTES, "reduce_chrome": True}
    if not isinstance(settings, dict):
        return base
    raw = settings.get("deep_work")
    if not isinstance(raw, dict):
        return base
    try:
        last = int(raw.get("last_minutes", DEFAULT_MINUTES))
    except (TypeError, ValueError):
        last = DEFAULT_MINUTES
    last = max(1, min(last, 24 * 60))
    return {
        "last_minutes": last,
        "reduce_chrome": bool(raw.get("reduce_chrome", True)),
    }


def apply_deep_work_settings(settings: dict, deep_work: dict) -> dict:
    settings = dict(settings or {})
    settings["deep_work"] = normalize_deep_work_settings({"deep_work": deep_work})
    return settings


# Chrome policy is defined on ``nav_items.NAV_ITEMS`` (#132); re-export for tests/callers.
from nav_items import (
    NAV_ITEMS,
    THEME_MENU_LABELS,
    labels_hidden_during_deep_work,
    labels_kept_during_deep_work,
)

DEEP_WORK_HIDDEN_NAV_LABELS = labels_hidden_during_deep_work()

DEEP_WORK_KEEP_NAV_LABELS = frozenset(
    labels_kept_during_deep_work()
    & {
        "Refresh",
        "Journal",
        "Writing Projects",
        "Deep Work",
        "Quick Capture",
    }
)

_hidden_more: set[str] = {
    item.label
    for item in NAV_ITEMS
    if "more" in item.surfaces and item.hide_in_deep_work and item.id != "toggle_theme"
}
if any(item.id == "toggle_theme" and item.hide_in_deep_work for item in NAV_ITEMS):
    _hidden_more.update(THEME_MENU_LABELS)
DEEP_WORK_HIDDEN_MORE_LABELS = frozenset(_hidden_more)

DEEP_WORK_KEEP_MORE_LABELS = frozenset(
    item.label for item in NAV_ITEMS if "more" in item.surfaces and not item.hide_in_deep_work
)

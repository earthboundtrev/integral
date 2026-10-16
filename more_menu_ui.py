"""Grouped More menu popup for the app shell footer (#130)."""

from __future__ import annotations

import sys
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable

import deep_work
from theme import FONTS

# Canonical menu structure (labels tested for reachability).
MORE_GROUPS: tuple[dict[str, Any], ...] = (
    {
        "title": "VIEW",
        "items": (
            {"id": "refresh", "label": "Refresh"},
            {"id": "guidance", "label": "Guidance"},
            {"id": "history", "label": "Full History"},
            {"id": "search", "label": "Search Notes"},
            {"id": "milestones", "label": "Milestones"},
            {"id": "ai_insight", "label": "AI Insight"},
        ),
    },
    {
        "title": "WORK MODES",
        "items": (
            {"id": "quick_capture", "label": "Quick Capture"},
            {"id": "writing_projects", "label": "Writing Projects"},
            {"id": "deep_work", "label": "Deep Work"},
        ),
    },
    {
        "title": "DATA & SETTINGS",
        "items": (
            {"id": "export", "label": "Export"},
            {"id": "backup", "label": "Backup"},
            {"id": "settings", "label": "Edit Categories"},
            {"id": "security", "label": "Data & Security"},
            {"id": "toggle_theme", "label": "toggle_theme"},
        ),
    },
)

LEGACY_FOOTER_LABELS: tuple[str, ...] = (
    "Refresh",
    "Go to…",
    "Guidance",
    "Weekly Summary",
    "Full History",
    "Search Notes",
    "Graphs & Progress",
    "Journal",
    "Writing Projects",
    "Deep Work",
    "Quick Capture",
    "Milestones",
    "Export",
    "Backup",
    "Edit Categories",
    "Data & Security",
    "Dark Mode",
)

TODAY_MORE_MENU_LABELS: tuple[str, ...] = (
    "Go to…",
    "Writing Projects",
    "Deep Work",
    "AI Insight",
    "Plan Tomorrow",
    "Log Exercise",
    "Fitness Hub",
)

SIDEBAR_NAV_LABELS: tuple[str, ...] = (
    "Today",
    "Fitness Hub",
    "Reflect",
    "Journal",
    "Graphs & Progress",
    "Weekly Summary",
)

GOTO_ONLY_LABELS: frozenset[str] = frozenset({"Plan Tomorrow", "Log Exercise"})

THEME_LABEL_ALIASES: frozenset[str] = frozenset({"Dark Mode", "Light Mode"})


@dataclass(frozen=True)
class MoreMenuRow:
    """One selectable row in the popup (group headers are not rows)."""

    group: str
    label: str
    action: Callable[[], None]
    item_id: str


def theme_menu_label(tracker: Any) -> str:
    return "Light Mode" if tracker.settings.get("dark_mode") else "Dark Mode"


def _action_for_id(tracker: Any, item_id: str) -> Callable[[], None]:
    actions: dict[str, Callable[[], None]] = {
        "refresh": lambda: tracker.refresh_dashboard(full=False, recompute=False),
        "guidance": tracker.show_guidance,
        "history": tracker.show_history,
        "search": tracker.show_search,
        "milestones": tracker.show_milestones,
        "ai_insight": lambda: tracker._show_ai_insight(default_days=7),
        "quick_capture": tracker.toggle_quick_capture,
        "writing_projects": tracker.show_writing_projects,
        "deep_work": tracker.show_deep_work,
        "export": tracker.show_export,
        "backup": tracker.show_backup,
        "settings": tracker.show_settings,
        "security": tracker.show_security,
        "toggle_theme": tracker.toggle_dark_mode,
    }
    return actions[item_id]


def _display_label(tracker: Any, item: dict[str, Any]) -> str:
    if item["id"] == "toggle_theme":
        return theme_menu_label(tracker)
    return str(item["label"])


def is_hidden_during_deep_work(label: str) -> bool:
    if label in deep_work.DEEP_WORK_KEEP_MORE_LABELS:
        return False
    if label in deep_work.DEEP_WORK_HIDDEN_MORE_LABELS:
        return True
    if label in THEME_LABEL_ALIASES:
        return "Light Mode" in deep_work.DEEP_WORK_HIDDEN_MORE_LABELS
    return False


def build_more_menu_rows(tracker: Any) -> list[MoreMenuRow]:
    """Flat selectable rows respecting Deep Work chrome (#132)."""
    active = bool(
        getattr(tracker, "_deep_work_session", None)
        and tracker._deep_work_session.running
    )
    rows: list[MoreMenuRow] = []
    for group in MORE_GROUPS:
        title = str(group["title"])
        for item in group["items"]:
            label = _display_label(tracker, item)
            if active and is_hidden_during_deep_work(label):
                continue
            rows.append(
                MoreMenuRow(
                    group=title,
                    label=label,
                    action=_action_for_id(tracker, item["id"]),
                    item_id=str(item["id"]),
                )
            )
    return rows


_REACHABILITY: dict[str, frozenset[str]] = {
    "Refresh": frozenset({"more", "goto"}),
    "Go to…": frozenset({"sidebar", "today_more", "goto"}),
    "Guidance": frozenset({"more", "goto"}),
    "Weekly Summary": frozenset({"sidebar", "goto"}),
    "Full History": frozenset({"more", "goto"}),
    "Search Notes": frozenset({"more", "goto"}),
    "Graphs & Progress": frozenset({"sidebar", "goto"}),
    "Journal": frozenset({"sidebar", "goto"}),
    "Writing Projects": frozenset({"more", "today_more", "goto"}),
    "Deep Work": frozenset({"more", "today_more", "goto"}),
    "Quick Capture": frozenset({"more", "today_more", "goto"}),
    "Milestones": frozenset({"more", "goto"}),
    "Export": frozenset({"more", "goto"}),
    "Backup": frozenset({"more", "goto"}),
    "Edit Categories": frozenset({"more", "goto"}),
    "Data & Security": frozenset({"more", "goto"}),
    "Dark Mode": frozenset({"more", "goto"}),
    "Light Mode": frozenset({"more", "goto"}),
    "AI Insight": frozenset({"more", "today_more", "goto"}),
    "Plan Tomorrow": frozenset({"today_more", "goto"}),
    "Log Exercise": frozenset({"today_more", "goto"}),
    "Fitness Hub": frozenset({"sidebar", "today_more", "goto"}),
}


def reachable_surfaces_for_label(label: str) -> set[str]:
    """Where a legacy footer / Today More label can be reached after #130."""
    hit = _REACHABILITY.get(label)
    if hit:
        return set(hit)
    if label in SIDEBAR_NAV_LABELS:
        return {"sidebar"}
    return set()


def _more_menu_labels_flat(*, include_theme: bool = False) -> frozenset[str]:
    labels: set[str] = set()
    for group in MORE_GROUPS:
        for item in group["items"]:
            if item["id"] == "toggle_theme":
                if include_theme:
                    labels.update(THEME_LABEL_ALIASES)
            else:
                labels.add(str(item["label"]))
    return frozenset(labels)


def assert_legacy_features_reachable() -> None:
    """Raise AssertionError if any pre-#130 footer / Today More label lost a path."""
    for label in LEGACY_FOOTER_LABELS:
        surfaces = reachable_surfaces_for_label(label)
        if not surfaces:
            raise AssertionError(f"No reachability path for {label!r}")
    for label in TODAY_MORE_MENU_LABELS:
        surfaces = reachable_surfaces_for_label(label)
        if not surfaces:
            raise AssertionError(f"No reachability path for Today More item {label!r}")


def typeahead_advance(
    rows: list[MoreMenuRow], current_index: int, prefix: str
) -> int | None:
    """Return index of next row whose label starts with prefix (case-insensitive)."""
    if not prefix:
        return None
    needle = prefix.lower()
    start = current_index + 1 if current_index >= 0 else 0
    for idx in range(start, len(rows)):
        if rows[idx].label.lower().startswith(needle):
            return idx
    for idx in range(0, start):
        if rows[idx].label.lower().startswith(needle):
            return idx
    return None


class MoreMenuPopup:
    """Single-instance grouped menu anchored to a footer/sidebar More control."""

    _ROW_HEIGHT = 32
    _HEADER_HEIGHT = 28
    _PAD = 8
    _WIDTH = 300

    def __init__(self, tracker: Any, anchor: tk.Widget) -> None:
        self.tracker = tracker
        self.anchor = anchor
        self.root = tracker.root
        self.theme = tracker.theme
        self.rows = build_more_menu_rows(tracker)
        self._focus_index = 0 if self.rows else -1
        self._typeahead = ""
        self._typeahead_after: str | None = None
        self._outside_bind = None

        self.window = tk.Toplevel(self.root)
        tracker._more_menu_popup = self
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.transient(self.root)
        if sys.platform == "win32":
            try:
                self.window.attributes("-toolwindow", True)
            except tk.TclError:
                pass
        self.window.configure(bg=self.theme["surface"])

        self._body = tk.Frame(self.window, bg=self.theme["surface"], highlightthickness=1)
        self._body.pack(fill=tk.BOTH, expand=True)
        try:
            self._body.configure(
                highlightbackground=self.theme.get("card_border", self.theme["muted"]),
                highlightcolor=self.theme.get("card_border", self.theme["muted"]),
            )
        except tk.TclError:
            pass

        self._row_widgets: list[tk.Frame] = []
        self._label_widgets: list[tk.Label] = []
        self._build_rows()
        self._place_near_anchor()
        self.window.deiconify()
        self._bind_events()
        self._highlight_focus()
        self.window.focus_set()
        self.window.bind("<FocusOut>", self._on_focus_out, add="+")

    def _build_rows(self) -> None:
        last_group: str | None = None
        for row in self.rows:
            if row.group != last_group:
                last_group = row.group
                hdr = tk.Label(
                    self._body,
                    text=row.group,
                    anchor="w",
                    bg=self.theme["surface_alt"],
                    fg=self.theme["muted"],
                    font=FONTS["hint"],
                    padx=self._PAD,
                    pady=4,
                )
                hdr.pack(fill=tk.X)
            idx = len(self._row_widgets)
            frame = tk.Frame(self._body, bg=self.theme["surface"], height=self._ROW_HEIGHT)
            frame.pack(fill=tk.X)
            frame.pack_propagate(False)
            lbl = tk.Label(
                frame,
                text=row.label,
                anchor="w",
                bg=self.theme["surface"],
                fg=self.theme["fg"],
                font=FONTS["caption"],
                padx=self._PAD,
            )
            lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            for widget in (frame, lbl):
                widget.bind(
                    "<Button-1>",
                    lambda _e, i=idx: self._activate(i),
                )
                widget.bind("<Enter>", lambda _e, i=idx: self._set_focus(i))
            self._row_widgets.append(frame)
            self._label_widgets.append(lbl)

    def _place_near_anchor(self) -> None:
        self.anchor.update_idletasks()
        self.window.update_idletasks()
        ax = self.anchor.winfo_rootx()
        ay = self.anchor.winfo_rooty()
        ah = self.anchor.winfo_height()
        aw = self.anchor.winfo_width()
        wh = self.window.winfo_reqheight()
        ww = self._WIDTH
        x = max(0, ax + aw - ww)
        y = ay + ah + 4
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        if x + ww > sw:
            x = max(0, sw - ww - 4)
        if y + wh > sh:
            y = max(0, ay - wh - 4)
        self.window.geometry(f"{ww}x{wh}+{x}+{y}")

    def _bind_events(self) -> None:
        self.window.bind("<Escape>", self._on_escape)
        self.window.bind("<Return>", self._on_return)
        self.window.bind("<Up>", self._on_up)
        self.window.bind("<Down>", self._on_down)
        self.window.bind("<Home>", self._on_home)
        self.window.bind("<End>", self._on_end)
        self.window.bind("<Key>", self._on_key)
        self.root.bind("<Unmap>", self._on_root_unmap, add="+")
        self.root.bind("<Configure>", self._on_root_configure, add="+")
        self.root.after_idle(
            lambda: self.root.bind_all("<Button-1>", self._on_global_click, add="+")
        )

    def _on_root_unmap(self, _event: tk.Event) -> None:
        self.close()

    def _on_focus_out(self, _event: tk.Event) -> None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return
        self.root.after_idle(self._close_if_focus_left_popup)

    def _close_if_focus_left_popup(self) -> None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return
        focus = None
        try:
            focus = self.root.focus_get()
        except (KeyError, tk.TclError):
            focus = None
        if focus is None:
            self.close()
            return
        widget: tk.Misc | None = focus
        while widget is not None:
            if widget is self.window:
                return
            try:
                widget = widget.master
            except AttributeError:
                break
        self.close()

    def _on_root_configure(self, _event: tk.Event) -> None:
        if not self.window.winfo_exists():
            return
        try:
            if self.root.state() == "iconic":
                self.close()
                return
        except tk.TclError:
            pass
        self._place_near_anchor()

    def _on_global_click(self, event: tk.Event) -> None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return
        widget = event.widget
        w: tk.Misc | None = widget
        while w is not None:
            if w is self.window or w is self.anchor:
                return
            try:
                w = w.master
            except AttributeError:
                break
        self.close()

    def _on_escape(self, _event: tk.Event) -> None:
        self.close(focus_anchor=True)

    def _on_return(self, _event: tk.Event) -> None:
        if 0 <= self._focus_index < len(self.rows):
            self._activate(self._focus_index)

    def _on_up(self, _event: tk.Event) -> None:
        if not self.rows:
            return
        self._set_focus((self._focus_index - 1) % len(self.rows))

    def _on_down(self, _event: tk.Event) -> None:
        if not self.rows:
            return
        start = self._focus_index if self._focus_index >= 0 else -1
        self._set_focus((start + 1) % len(self.rows))

    def _on_home(self, _event: tk.Event) -> None:
        if self.rows:
            self._set_focus(0)

    def _on_end(self, _event: tk.Event) -> None:
        if self.rows:
            self._set_focus(len(self.rows) - 1)

    def _on_key(self, event: tk.Event) -> None:
        if event.keysym in {"Escape", "Return", "Up", "Down", "Home", "End"}:
            return
        if event.state & 0x20000:  # Alt
            return
        char = event.char
        if not char or not char.isprintable():
            return
        self._typeahead += char
        if self._typeahead_after:
            self.root.after_cancel(self._typeahead_after)
        self._typeahead_after = self.root.after(800, self._clear_typeahead)
        match = typeahead_advance(self.rows, self._focus_index, self._typeahead)
        if match is not None:
            self._set_focus(match)

    def _clear_typeahead(self) -> None:
        self._typeahead = ""
        self._typeahead_after = None

    def _set_focus(self, index: int) -> None:
        if not self.rows:
            return
        self._focus_index = max(0, min(index, len(self.rows) - 1))
        self._highlight_focus()

    def _highlight_focus(self) -> None:
        select_bg = self.theme.get("select_bg", self.theme["accent_soft"])
        for idx, (frame, lbl) in enumerate(zip(self._row_widgets, self._label_widgets)):
            if idx == self._focus_index:
                frame.configure(bg=select_bg)
                lbl.configure(bg=select_bg)
            else:
                frame.configure(bg=self.theme["surface"])
                lbl.configure(bg=self.theme["surface"])

    def _activate(self, index: int) -> None:
        if index < 0 or index >= len(self.rows):
            return
        action = self.rows[index].action
        self.close()
        action()

    def close(self, *, focus_anchor: bool = False) -> None:
        popup = getattr(self.tracker, "_more_menu_popup", None)
        if popup is self:
            self.tracker._more_menu_popup = None
        if self._typeahead_after:
            try:
                self.root.after_cancel(self._typeahead_after)
            except tk.TclError:
                pass
        try:
            self.root.unbind_all("<Button-1>")
        except tk.TclError:
            pass
        self._outside_bind = None
        try:
            self.root.unbind("<Unmap>")
            self.root.unbind("<Configure>")
        except tk.TclError:
            pass
        try:
            if self.window.winfo_exists():
                self.window.destroy()
        except tk.TclError:
            pass
        if focus_anchor:
            try:
                self.anchor.focus_set()
            except tk.TclError:
                pass


def toggle_more_menu(tracker: Any, anchor: tk.Widget) -> None:
    """Open or close the grouped More menu (single instance)."""
    existing = getattr(tracker, "_more_menu_popup", None)
    if existing is not None:
        try:
            if existing.window.winfo_exists():
                existing.close(focus_anchor=True)
                return
        except tk.TclError:
            tracker._more_menu_popup = None
    if not build_more_menu_rows(tracker):
        return
    MoreMenuPopup(tracker, anchor)


def close_more_menu(tracker: Any) -> None:
    existing = getattr(tracker, "_more_menu_popup", None)
    if existing is None:
        return
    try:
        existing.close()
    except tk.TclError:
        tracker._more_menu_popup = None

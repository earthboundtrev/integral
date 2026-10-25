"""Grouped More menu popup for the app shell footer (#130)."""

from __future__ import annotations

import sys
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable

import nav_items
from keyboard_shortcuts import MORE_ITEM_SHORTCUT_HINTS, show_keyboard_shortcuts
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
            {"id": "keyboard_shortcuts", "label": "Keyboard shortcuts"},
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

# Menu groups separated by a divider (order matches TODAY_MORE_MENU_LABELS).
TODAY_MORE_MENU_GROUPS: tuple[tuple[str, ...], ...] = (
    ("goto_palette",),
    ("writing_projects", "deep_work", "ai_insight", "plan_tomorrow"),
    ("log_exercise", "fitness_hub"),
)

SIDEBAR_NAV_LABELS: tuple[str, ...] = tuple(
    item.label for item in nav_items.sidebar_nav_items()
)

THEME_LABEL_ALIASES: frozenset[str] = frozenset({"Dark Mode", "Light Mode"})

GOTO_THEME_LABEL = "Toggle Dark / Light Mode"


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
        "goto_palette": tracker.show_goto,
        "plan_tomorrow": tracker.show_plan_tomorrow,
        "log_exercise": tracker.show_log_exercise,
        "fitness_hub": tracker.show_fitness_hub,
        "keyboard_shortcuts": lambda: show_keyboard_shortcuts(tracker),
    }
    return actions[item_id]


def _today_more_item_visible(item_id: str, tracker: Any) -> bool:
    if nav_items.deep_work_active(tracker) and nav_items.is_hidden_during_deep_work(
        item_id=item_id, tracker=tracker
    ):
        return False
    return nav_items.nav_item_for_id(item_id) is not None


def today_more_menu_labels(tracker: Any) -> tuple[str, ...]:
    """Labels for the Today tab More… menu, respecting Deep Work chrome (#132)."""
    labels: list[str] = []
    for group in TODAY_MORE_MENU_GROUPS:
        for item_id in group:
            if not _today_more_item_visible(item_id, tracker):
                continue
            item = nav_items.nav_item_for_id(item_id)
            if item is not None:
                labels.append(item.label)
    return tuple(labels)


def populate_today_more_menu(menu: tk.Menu, tracker: Any, theme: dict) -> None:
    """Rebuild Today More… menu entries from NAV_ITEMS / Deep Work policy."""
    from theme import style_menu

    try:
        menu.delete(0, "end")
    except tk.TclError:
        return
    added_any = False
    for group_index, group in enumerate(TODAY_MORE_MENU_GROUPS):
        visible_ids = [i for i in group if _today_more_item_visible(i, tracker)]
        if not visible_ids:
            continue
        if added_any:
            menu.add_separator()
        for item_id in visible_ids:
            item = nav_items.nav_item_for_id(item_id)
            if item is None:
                continue
            accel = MORE_ITEM_SHORTCUT_HINTS.get(item_id, "").strip()
            if accel:
                menu.add_command(
                    label=item.label,
                    command=_action_for_id(tracker, item_id),
                    accelerator=accel,
                )
            else:
                menu.add_command(label=item.label, command=_action_for_id(tracker, item_id))
        added_any = True
    style_menu(menu, theme)


def _display_label(tracker: Any, item: dict[str, Any]) -> str:
    if item["id"] == "toggle_theme":
        return theme_menu_label(tracker)
    return str(item["label"])


def is_hidden_during_deep_work(item_id: str, tracker: Any | None = None) -> bool:
    return nav_items.is_hidden_during_deep_work(item_id=item_id, tracker=tracker)


def build_more_menu_rows(tracker: Any) -> list[MoreMenuRow]:
    """Flat selectable rows respecting Deep Work chrome (#132)."""
    active = nav_items.deep_work_active(tracker)
    rows: list[MoreMenuRow] = []
    for group in MORE_GROUPS:
        title = str(group["title"])
        for item in group["items"]:
            item_id = str(item["id"])
            if active and is_hidden_during_deep_work(item_id, tracker):
                continue
            label = _display_label(tracker, item)
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
    "Keyboard shortcuts": frozenset({"more"}),
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


def more_menu_static_labels() -> set[str]:
    """All labels that can appear in the grouped More popup (both theme wordings)."""
    labels: set[str] = set()
    for group in MORE_GROUPS:
        for item in group["items"]:
            if item["id"] == "toggle_theme":
                labels.update(THEME_LABEL_ALIASES)
            else:
                labels.add(str(item["label"]))
    return labels


def labels_for_surface(surface: str, tracker: Any | None = None) -> set[str]:
    """Labels exposed on a reachability surface (More, sidebar, Today More, Go to…)."""
    if surface == "more":
        if tracker is not None:
            return {row.label for row in build_more_menu_rows(tracker)}
        return more_menu_static_labels()
    if surface == "sidebar":
        return set(SIDEBAR_NAV_LABELS) | {"Go to…"}
    if surface == "today_more":
        if tracker is not None:
            return set(today_more_menu_labels(tracker))
        return set(TODAY_MORE_MENU_LABELS)
    if surface == "goto":
        if tracker is None:
            return set()
        from goto_ui import build_goto_destinations

        return {d["label"] for d in build_goto_destinations(tracker)}
    return set()


def _label_present_on_surface(label: str, surface: str, tracker: Any | None) -> bool:
    if surface == "goto" and label == "Go to…":
        return True
    if label in THEME_LABEL_ALIASES:
        if surface == "more":
            avail = labels_for_surface("more", tracker)
            return bool(avail & THEME_LABEL_ALIASES)
        if surface == "goto":
            return GOTO_THEME_LABEL in labels_for_surface("goto", tracker)
    avail = labels_for_surface(surface, tracker)
    return label in avail


def assert_legacy_features_reachable(tracker: Any | None = None) -> None:
    """Raise AssertionError if any pre-#130 footer / Today More label lost a path."""
    for label in LEGACY_FOOTER_LABELS:
        surfaces = reachable_surfaces_for_label(label)
        if not surfaces:
            raise AssertionError(f"No reachability path for {label!r}")
        if not any(_label_present_on_surface(label, s, tracker) for s in surfaces):
            raise AssertionError(
                f"{label!r} not present on declared surfaces {sorted(surfaces)!r}"
            )
    for label in TODAY_MORE_MENU_LABELS:
        surfaces = reachable_surfaces_for_label(label)
        if not surfaces:
            raise AssertionError(f"No reachability path for Today More item {label!r}")
        if not any(_label_present_on_surface(label, s, tracker) for s in surfaces):
            raise AssertionError(
                f"Today More {label!r} not present on declared surfaces {sorted(surfaces)!r}"
            )


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
        self._outside_click_after_id: str | None = None
        self._focus_after_id: str | None = None
        self._binding_funcids: list[tuple[tk.Misc, str, str]] = []
        self._binding_all_funcids: list[tuple[str, str]] = []
        self._had_grab = False

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
        self._hint_widgets: list[tk.Label | None] = []
        try:
            self._build_rows()
            self._place_near_anchor()
            self.window.deiconify()
            try:
                self.window.grab_set()
                self._had_grab = True
            except tk.TclError:
                self._had_grab = False
            self._bind_events()
            self._highlight_focus()
            try:
                self.window.focus_force()
            except tk.TclError:
                pass
            self._bind_func(self.window, "<FocusOut>", self._on_focus_out)
        except tk.TclError:
            tracker._more_menu_popup = None
            try:
                if self.window.winfo_exists():
                    self.window.destroy()
            except tk.TclError:
                pass
            raise

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
            hint_text = MORE_ITEM_SHORTCUT_HINTS.get(row.item_id, "").strip()
            hint_lbl: tk.Label | None = None
            if hint_text:
                hint_lbl = tk.Label(
                    frame,
                    text=hint_text,
                    anchor="e",
                    bg=self.theme["surface"],
                    fg=self.theme["muted"],
                    font=FONTS["hint"],
                    padx=self._PAD,
                )
                hint_lbl.pack(side=tk.RIGHT)
            self._hint_widgets.append(hint_lbl)
            row_widgets_click = [frame, lbl]
            if hint_lbl is not None:
                row_widgets_click.append(hint_lbl)
            for widget in row_widgets_click:
                widget.bind(
                    "<Button-1>",
                    lambda _e, i=idx: self._activate(i),
                )
                widget.bind("<Enter>", lambda _e, i=idx: self._set_focus(i))
            self._row_widgets.append(frame)
            self._label_widgets.append(lbl)

        if nav_items.deep_work_active(self.tracker) and nav_items.any_shell_items_hidden_during_deep_work():
            dw_hint = tk.Label(
                self._body,
                text=nav_items.DEEP_WORK_HIDDEN_HINT,
                anchor="w",
                bg=self.theme["surface"],
                fg=self.theme["muted"],
                font=FONTS["hint"],
                padx=self._PAD,
            )
            dw_hint.pack(fill=tk.X, pady=(4, 0))
        nav_hint = tk.Label(
            self._body,
            text="↑↓ · Enter · Esc",
            anchor="e",
            bg=self.theme["surface"],
            fg=self.theme["muted"],
            font=FONTS["hint"],
            padx=self._PAD,
            pady=4,
        )
        nav_hint.pack(fill=tk.X, padx=0, pady=(4, self._PAD))

    def _bind_func(self, widget: tk.Misc, sequence: str, handler: Any) -> None:
        funcid = widget.bind(sequence, handler, add="+")
        self._binding_funcids.append((widget, sequence, funcid))

    def _bind_all_func(self, sequence: str, handler: Any) -> None:
        funcid = self.root.bind_all(sequence, handler, add="+")
        self._binding_all_funcids.append((sequence, funcid))

    def _place_near_anchor(self) -> None:
        self.anchor.update_idletasks()
        self.window.update_idletasks()
        ax = self.anchor.winfo_rootx()
        ay = self.anchor.winfo_rooty()
        ah = self.anchor.winfo_height()
        aw = self.anchor.winfo_width()
        wh = self.window.winfo_reqheight()
        ww = self._WIDTH
        x = ax + aw - ww
        y = ay + ah + 4
        try:
            root_x = self.root.winfo_rootx()
            root_y = self.root.winfo_rooty()
            root_w = self.root.winfo_width()
            root_h = self.root.winfo_height()
            if x < root_x:
                x = root_x
            if x + ww > root_x + root_w:
                x = root_x + root_w - ww
            if y + wh > root_y + root_h:
                y = ay - wh - 4
        except tk.TclError:
            pass
        self.window.geometry(f"{ww}x{wh}+{x}+{y}")

    def _bind_events(self) -> None:
        key_sequences = (
            "<Escape>",
            "<Return>",
            "<Up>",
            "<Down>",
            "<Home>",
            "<End>",
            "<Key>",
        )
        for sequence in key_sequences:
            handler = {
                "<Escape>": self._on_escape,
                "<Return>": self._on_return,
                "<Up>": self._on_up,
                "<Down>": self._on_down,
                "<Home>": self._on_home,
                "<End>": self._on_end,
                "<Key>": self._on_key,
            }[sequence]
            self._bind_func(self.window, sequence, handler)
            self._bind_func(self.root, sequence, handler)
        self._bind_func(self.root, "<Unmap>", self._on_root_unmap)
        self._bind_func(self.root, "<Configure>", self._on_root_configure)
        if self._outside_click_after_id:
            try:
                self.root.after_cancel(self._outside_click_after_id)
            except tk.TclError:
                pass
        self._outside_click_after_id = self.root.after_idle(self._install_outside_click_bind)

    def _install_outside_click_bind(self) -> None:
        self._outside_click_after_id = None
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return
        try:
            if not self.window.winfo_exists():
                return
        except tk.TclError:
            return
        self._bind_all_func("<Button-1>", self._on_global_click)

    def _on_root_unmap(self, _event: tk.Event) -> None:
        self.close()

    def _on_focus_out(self, _event: tk.Event) -> None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return
        if self._focus_after_id:
            try:
                self.root.after_cancel(self._focus_after_id)
            except tk.TclError:
                pass
        self._focus_after_id = self.root.after_idle(self._close_if_focus_left_popup)

    def _close_if_focus_left_popup(self) -> None:
        self._focus_after_id = None
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return
        try:
            if not self.window.winfo_exists():
                return
        except tk.TclError:
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

    def _point_in_widget(self, x_root: int, y_root: int, widget: tk.Misc) -> bool:
        try:
            wx = widget.winfo_rootx()
            wy = widget.winfo_rooty()
            ww = widget.winfo_width()
            wh = widget.winfo_height()
        except tk.TclError:
            return False
        return wx <= x_root < wx + ww and wy <= y_root < wy + wh

    def _on_global_click(self, event: tk.Event) -> None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return
        x_root = int(getattr(event, "x_root", 0))
        y_root = int(getattr(event, "y_root", 0))
        if self._point_in_widget(x_root, y_root, self.anchor):
            self.close()
            return
        if self._point_in_widget(x_root, y_root, self.window):
            return
        self.close()

    def _on_escape(self, _event: tk.Event) -> str | None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return None
        self.close(focus_anchor=True)
        return "break"

    def _on_return(self, _event: tk.Event) -> str | None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return None
        if 0 <= self._focus_index < len(self.rows):
            self._activate(self._focus_index)
        return "break"

    def _on_up(self, _event: tk.Event) -> str | None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return None
        if not self.rows:
            return "break"
        self._set_focus((self._focus_index - 1) % len(self.rows))
        return "break"

    def _on_down(self, _event: tk.Event) -> str | None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return None
        if not self.rows:
            return "break"
        start = self._focus_index if self._focus_index >= 0 else -1
        self._set_focus((start + 1) % len(self.rows))
        return "break"

    def _on_home(self, _event: tk.Event) -> str | None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return None
        if self.rows:
            self._set_focus(0)
        return "break"

    def _on_end(self, _event: tk.Event) -> str | None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return None
        if self.rows:
            self._set_focus(len(self.rows) - 1)
        return "break"

    def _on_key(self, event: tk.Event) -> str | None:
        if getattr(self.tracker, "_more_menu_popup", None) is not self:
            return None
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
        return "break"

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
            hint = self._hint_widgets[idx] if idx < len(self._hint_widgets) else None
            if idx == self._focus_index:
                frame.configure(bg=select_bg)
                lbl.configure(bg=select_bg)
                if hint is not None:
                    hint.configure(bg=select_bg)
            else:
                frame.configure(bg=self.theme["surface"])
                lbl.configure(bg=self.theme["surface"])
                if hint is not None:
                    hint.configure(bg=self.theme["surface"])

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
        for after_id in (self._typeahead_after, self._outside_click_after_id, self._focus_after_id):
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
        self._typeahead_after = None
        self._outside_click_after_id = None
        self._focus_after_id = None
        for widget, sequence, funcid in self._binding_funcids:
            try:
                widget.unbind(sequence, funcid)
            except tk.TclError:
                pass
        self._binding_funcids.clear()
        for sequence, funcid in self._binding_all_funcids:
            try:
                self.root.tk.call("unbind", "all", sequence, funcid)
            except tk.TclError:
                pass
        self._binding_all_funcids.clear()
        if self._had_grab:
            try:
                if self.window.winfo_exists():
                    self.window.grab_release()
            except tk.TclError:
                pass
            self._had_grab = False
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

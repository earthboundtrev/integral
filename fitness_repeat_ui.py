"""Log-form Repeat controls — split button, recent overlay (#259)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

import ui_scroll
from fitness_programs import format_family_label
from progression.db import FitnessRepository
from progression.session_repeat import (
    RepeatableSessionRow,
    format_date_display,
    format_repeatable_row_text,
    list_repeatable_session_rows,
)
from progression.sessions import find_latest_session_for_repeat


def repeatable_rows(repo: FitnessRepository, exclude_date: str) -> list[RepeatableSessionRow]:
    return list_repeatable_session_rows(repo, exclude_date=exclude_date, limit=10)


def default_last_overall_session_id(repo: FitnessRepository, exclude_date: str) -> str | None:
    session = find_latest_session_for_repeat(repo, exclude_date=exclude_date)
    return session.id if session else None


def last_of_type_menu_entries(
    repo: FitnessRepository,
    *,
    exclude_date: str,
) -> list[tuple[str, str, str]]:
    """Return (family_key, menu_label, session_id) sorted by family label."""
    families = getattr(repo, "list_families_with_repeatable_sessions", lambda **_k: [])(exclude_date=exclude_date)
    entries: list[tuple[str, str, str]] = []
    for family in families:
        session = find_latest_session_for_repeat(repo, exclude_date=exclude_date, family=family)
        if session is None:
            continue
        label = format_family_label(family)
        date_part = format_date_display(session.date)
        entries.append((family, f"Last {label} ({date_part})", session.id))
    entries.sort(key=lambda item: item[1].lower())
    return entries


class RecentSessionsOverlay:
    """On-demand list anchored to the Repeat caret."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: dict,
        *,
        on_pick: Callable[[str], None],
        on_close: Callable[[], None],
        default_session_id: str | None,
        max_visible: int = 10,
    ):
        self._parent = parent
        self._theme = theme
        self._on_pick = on_pick
        self._on_close = on_close
        self._default_session_id = default_session_id
        self._max_visible = max_visible
        self._rows: list[RepeatableSessionRow] = []
        self._selection = 0
        self._popup: tk.Toplevel | None = None
        self._listbox: tk.Listbox | None = None
        self._escape_funcids: list[tuple[tk.Misc, str]] = []

    def is_open(self) -> bool:
        return self._popup is not None and self._popup.winfo_exists()

    def close(self) -> None:
        if self._popup is not None:
            try:
                if self._popup.winfo_exists():
                    self._popup.destroy()
            except tk.TclError:
                pass
        self._popup = None
        self._listbox = None
        for widget, funcid in self._escape_funcids:
            try:
                widget.unbind("<Escape>", funcid)
            except tk.TclError:
                pass
        self._escape_funcids.clear()
        self._on_close()

    def show(self, anchor_widget: tk.Misc, rows: list[RepeatableSessionRow]) -> None:
        self.close()
        self._rows = rows
        self._selection = 0
        if self._default_session_id:
            for idx, row in enumerate(rows):
                if row.session_id == self._default_session_id:
                    self._selection = idx
                    break

        height = min(len(rows), 4 if _is_compact(self._parent) else 10)
        if height < 1:
            return

        popup = tk.Toplevel(anchor_widget)
        popup.withdraw()
        popup.overrideredirect(True)
        popup.configure(bg=self._theme.get("border", "#CBD5E1"))
        try:
            popup.transient(self._parent.winfo_toplevel())
        except tk.TclError:
            pass

        frame = tk.Frame(popup, bg=self._theme.get("surface", "#FFFFFF"), padx=1, pady=1)
        frame.pack(fill=tk.BOTH, expand=True)

        listbox = tk.Listbox(
            frame,
            height=height,
            exportselection=False,
            font=("Helvetica", 10),
            bg=self._theme.get("surface", "#FFFFFF"),
            fg=self._theme.get("fg", "#111827"),
            selectbackground=self._theme.get("accent", "#2F7A7B"),
            selectforeground=self._theme.get("surface", "#FFFFFF"),
            highlightthickness=0,
            relief=tk.FLAT,
            borderwidth=0,
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=listbox.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=scroll.set)
        ui_scroll.bind_mousewheel(listbox, listbox.yview)

        for row in rows:
            listbox.insert(tk.END, format_repeatable_row_text(row))
        listbox.selection_set(self._selection)
        listbox.see(self._selection)

        anchor_widget.update_idletasks()
        ax = anchor_widget.winfo_rootx()
        ay = anchor_widget.winfo_rooty() + anchor_widget.winfo_height()
        popup.geometry(f"+{ax}+{ay}")
        popup.deiconify()
        popup.lift()
        listbox.focus_set()

        def pick_selected(_event=None):
            sel = listbox.curselection()
            idx = int(sel[0]) if sel else self._selection
            if 0 <= idx < len(self._rows):
                self._on_pick(self._rows[idx].session_id)
            self.close()
            return "break"

        def on_up(_event=None):
            if not self._rows:
                return "break"
            self._selection = max(0, self._selection - 1)
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(self._selection)
            listbox.see(self._selection)
            return "break"

        def on_down(_event=None):
            if not self._rows:
                return "break"
            self._selection = min(len(self._rows) - 1, self._selection + 1)
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(self._selection)
            listbox.see(self._selection)
            return "break"

        def on_esc(_event=None):
            self.close()
            return "break"

        listbox.bind("<Return>", pick_selected)
        listbox.bind("<Double-Button-1>", pick_selected)
        listbox.bind("<Up>", on_up)
        listbox.bind("<Down>", on_down)
        popup.bind("<FocusOut>", lambda _e: popup.after(80, self._maybe_close_focus, popup))

        self._popup = popup
        self._listbox = listbox
        self._escape_funcids = [
            (listbox, listbox.bind("<Escape>", on_esc)),
            (popup, popup.bind("<Escape>", on_esc)),
        ]

    def _maybe_close_focus(self, popup: tk.Toplevel) -> None:
        if self._popup is not popup or not popup.winfo_exists():
            return
        try:
            focus = popup.focus_displayof()
        except tk.TclError:
            focus = None
        if focus is None:
            self.close()
            return
        widget = focus
        while widget is not None:
            if str(widget) == str(popup):
                return
            try:
                widget = widget.master
            except (AttributeError, tk.TclError):
                break
        self.close()


def _is_compact(widget: tk.Misc) -> bool:
    try:
        widget.update_idletasks()
        h = widget.winfo_height()
        return h > 0 and h < 600
    except tk.TclError:
        return False


def build_repeat_type_menu(
    parent: tk.Misc,
    entries: list[tuple[str, str, str]],
    *,
    on_pick_session: Callable[[str], None],
    on_pick_history: Callable[[], None],
) -> tk.Menu:
    menu = tk.Menu(parent, tearoff=0)
    for _family, label, session_id in entries:
        menu.add_command(
            label=label,
            command=lambda sid=session_id: on_pick_session(sid),
        )
    if entries:
        menu.add_separator()
    menu.add_command(label="Pick from history…", command=on_pick_history)
    return menu
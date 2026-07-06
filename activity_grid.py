"""GitHub-style contribution activity grid for Tkinter."""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime, timedelta
from tkinter import ttk
from typing import Callable


LEVEL_COLORS_LIGHT = ["#EBEDF0", "#40C463", "#30A14E", "#216E39", "#196127"]
LEVEL_COLORS_DARK = ["#161B22", "#26A641", "#006D32", "#30A14E", "#39D353"]


def activity_level(count: int, max_categories: int = 18) -> int:
    """Map daily contribution count to a color level (GitHub-style: any log = green)."""
    if count <= 0:
        return 0
    if count == 1:
        return 1
    if count <= max(2, max_categories // 3):
        return 2
    if count <= max(4, (2 * max_categories) // 3):
        return 3
    return 4


def day_activity_count(
    entries: dict,
    day: date,
    *,
    category: str | None = None,
    sessions: list[dict] | None = None,
    journal: dict | None = None,
) -> int:
    date_str = day.strftime("%Y-%m-%d")
    if category == "__journal__":
        if not journal:
            return 0
        from journal import count_entries_for_day

        return count_entries_for_day(journal, day)

    day_entries = entries.get(date_str, {})
    if category:
        return 1 if category in day_entries else 0

    count = len(day_entries)
    if sessions:
        for session in sessions:
            if session.get("date") == date_str:
                count += 1
                break
    if journal:
        from journal import count_entries_for_day

        count += count_entries_for_day(journal, day)
    return count


def build_week_columns(end: date | None = None, num_weeks: int = 53) -> list[list[date | None]]:
    """Return week columns (oldest → newest), each with 7 cells Sun–Sat."""
    end = end or date.today()
    span = num_weeks * 7
    grid_start = end - timedelta(days=span - 1)
    while grid_start.weekday() != 6:
        grid_start -= timedelta(days=1)

    weeks: list[list[date | None]] = []
    current_week: list[date | None] = []
    day = grid_start
    while day <= end:
        current_week.append(day)
        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []
        day += timedelta(days=1)
    if current_week:
        while len(current_week) < 7:
            current_week.append(None)
        weeks.append(current_week)
    return weeks[-num_weeks:]


def month_labels(weeks: list[list[date | None]]) -> list[tuple[int, str]]:
    labels: list[tuple[int, str]] = []
    last_month: int | None = None
    for index, week in enumerate(weeks):
        for day in week:
            if day is None:
                continue
            if day.month != last_month:
                labels.append((index, day.strftime("%b")))
                last_month = day.month
            break
    return labels


class ContributionGrid(ttk.Frame):
    """Small-square activity heatmap like GitHub contributions."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        entries: dict,
        categories: dict,
        theme: dict,
        sessions: list[dict] | None = None,
        journal: dict | None = None,
        session_counts: dict[str, int] | None = None,
        on_day_click: Callable[[str], None] | None = None,
        num_weeks: int = 53,
    ) -> None:
        super().__init__(parent)
        self.entries = entries
        self.categories = categories
        self.theme = theme
        self.sessions = sessions or []
        self._session_counts_override = session_counts
        self.journal = journal or {"entries": []}
        self.on_day_click = on_day_click
        self.num_weeks = num_weeks
        self.category_filter = tk.StringVar(value="All areas")
        self.colors = LEVEL_COLORS_DARK if theme.get("name") == "dark" else LEVEL_COLORS_LIGHT

        self.cell_size = 13
        self.gap = 3
        self.left_pad = 28
        self.top_pad = 22

        self._tooltip: tk.Toplevel | None = None
        self._journal_counts: dict[str, int] = {}
        self._session_counts: dict[str, int] = {}
        self._rebuild_source_indexes()
        self._build_controls()
        self._canvas = tk.Canvas(self, highlightthickness=0, height=130, bg=theme["bg"])
        self._canvas.pack(fill=tk.X, pady=(8, 0))
        self._canvas.bind("<Configure>", lambda _event: self._draw())
        self.category_filter.trace_add("write", lambda *_args: self._draw())

        from ui_scroll import bind_mousewheel

        bind_mousewheel(self._canvas, self._canvas.xview, horizontal=True)

        legend_row = ttk.Frame(self)
        legend_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(legend_row, text="Less").pack(side=tk.LEFT, padx=(self.left_pad, 4))
        legend_frame = tk.Frame(legend_row, bg=theme["bg"])
        legend_frame.pack(side=tk.LEFT)
        for level_color in self.colors:
            box = tk.Frame(legend_frame, bg=level_color, width=self.cell_size, height=self.cell_size)
            box.pack(side=tk.LEFT, padx=1)
            box.pack_propagate(False)
        ttk.Label(legend_row, text="More").pack(side=tk.LEFT, padx=4)
        self._total_label = ttk.Label(legend_row, text="", foreground=theme["muted"])
        self._total_label.pack(side=tk.RIGHT, padx=8)

    def _rebuild_source_indexes(self) -> None:
        self._journal_counts = {}
        for entry in self.journal.get("entries", []):
            date_str = entry.get("entry_date")
            if date_str:
                self._journal_counts[date_str] = self._journal_counts.get(date_str, 0) + 1

        self._session_counts = {}
        if self._session_counts_override is not None:
            self._session_counts = dict(self._session_counts_override)
        else:
            for session in self.sessions:
                date_str = session.get("date")
                if date_str:
                    self._session_counts[date_str] = self._session_counts.get(date_str, 0) + 1

    def refresh_data(
        self,
        entries: dict,
        journal: dict | None = None,
        sessions: list[dict] | None = None,
        session_counts: dict[str, int] | None = None,
    ) -> None:
        self.entries = entries
        self.journal = journal or {"entries": []}
        self.sessions = sessions or []
        self._session_counts_override = session_counts
        self._rebuild_source_indexes()
        self._draw()

    def _scroll_to_current_week(self) -> None:
        """Keep the latest week (including today) in view — like GitHub's graph."""
        canvas = self._canvas
        canvas.update_idletasks()
        region = canvas.cget("scrollregion")
        if not region:
            return
        parts = region.split()
        if len(parts) != 4:
            return
        total_width = float(parts[2])
        view_width = canvas.winfo_width()
        if total_width > view_width:
            canvas.xview_moveto(1.0)

    def _build_controls(self) -> None:
        row = ttk.Frame(self)
        row.pack(fill=tk.X)

        ttk.Label(row, text="Activity", font=("Helvetica", 13, "bold")).pack(side=tk.LEFT)
        ttk.Label(row, text="  —  click a day to explore", foreground=self.theme["muted"]).pack(side=tk.LEFT)

        filter_values = ["All areas", "Journal", *list(self.categories.keys()), "Fitness sessions"]
        ttk.Label(row, text="Show:").pack(side=tk.RIGHT, padx=(8, 4))
        ttk.Combobox(
            row,
            textvariable=self.category_filter,
            values=filter_values,
            state="readonly",
            width=28,
        ).pack(side=tk.RIGHT)

    def _selected_category(self) -> str | None:
        value = self.category_filter.get()
        if value == "All areas":
            return None
        if value == "Fitness sessions":
            return "__fitness__"
        if value == "Journal":
            return "__journal__"
        return value

    def _count_for_day(self, day: date) -> int:
        selected = self._selected_category()
        date_str = day.strftime("%Y-%m-%d")
        if selected == "__fitness__":
            return self._session_counts.get(date_str, 0)
        if selected == "__journal__":
            return self._journal_counts.get(date_str, 0)
        if selected:
            return 1 if selected in self.entries.get(date_str, {}) else 0

        count = len(self.entries.get(date_str, {}))
        if self._session_counts.get(date_str):
            count += 1
        count += self._journal_counts.get(date_str, 0)
        return count

    def _draw(self) -> None:
        canvas = self._canvas
        canvas.delete("all")
        canvas.configure(bg=self.theme["bg"])

        weeks = build_week_columns(num_weeks=self.num_weeks)
        if not weeks:
            return

        total_width = self.left_pad + len(weeks) * (self.cell_size + self.gap) + 8
        canvas.configure(scrollregion=(0, 0, max(total_width, canvas.winfo_width()), 130))

        for column, label in month_labels(weeks):
            x = self.left_pad + column * (self.cell_size + self.gap)
            canvas.create_text(x, 8, text=label, anchor="nw", fill=self.theme["muted"], font=("Helvetica", 8))

        day_labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        for row_index, label in enumerate(day_labels):
            if row_index % 2 == 0:
                y = self.top_pad + row_index * (self.cell_size + self.gap) + self.cell_size / 2
                canvas.create_text(2, y, text=label, anchor="w", fill=self.theme["muted"], font=("Helvetica", 8))

        max_categories = max(len(self.categories), 1)
        total = 0

        for week_index, week in enumerate(weeks):
            for row_index, day in enumerate(week):
                x0 = self.left_pad + week_index * (self.cell_size + self.gap)
                y0 = self.top_pad + row_index * (self.cell_size + self.gap)
                x1 = x0 + self.cell_size
                y1 = y0 + self.cell_size

                if day is None:
                    color = self.theme["bg"]
                    canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=color)
                    continue

                count = self._count_for_day(day)
                total += count
                level = activity_level(count, max_categories=max_categories)
                color = self.colors[level]
                date_str = day.strftime("%Y-%m-%d")
                canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=color, tags=("cell", date_str))

                if day == date.today():
                    outline = self.colors[min(level, 4)] if count > 0 else self.theme.get("accent", "#58A6FF")
                    canvas.create_rectangle(
                        x0 - 1,
                        y0 - 1,
                        x1 + 1,
                        y1 + 1,
                        outline=outline,
                        width=1,
                    )

        canvas.tag_bind("cell", "<Enter>", self._on_enter)
        canvas.tag_bind("cell", "<Leave>", self._on_leave)
        canvas.tag_bind("cell", "<Button-1>", self._on_click)

        self._total_label.config(text=f"{total} contributions in the last year")
        self._scroll_to_current_week()

    def _on_enter(self, event: tk.Event) -> None:
        canvas = self._canvas
        item = canvas.find_withtag("current")
        if not item:
            return
        tags = canvas.gettags(item[0])
        date_str = next((tag for tag in tags if tag != "cell"), None)
        if not date_str:
            return
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return
        count = self._count_for_day(day)
        self._hide_tooltip()
        self._tooltip = tk.Toplevel(self)
        self._tooltip.wm_overrideredirect(True)
        self._tooltip.configure(bg=self.theme["text_bg"])
        tip = day.strftime("%a, %b %d, %Y — no logs")
        if count:
            tip = f"{count} contribution{'s' if count != 1 else ''} on {day.strftime('%a, %b %d, %Y')}"
        tk.Label(
            self._tooltip,
            text=tip,
            bg=self.theme["text_bg"],
            fg=self.theme["text_fg"],
            padx=8,
            pady=4,
            font=("Helvetica", 9),
        ).pack()
        self._tooltip.geometry(f"+{event.x_root + 12}+{event.y_root + 12}")

    def _on_leave(self, _event: tk.Event) -> None:
        self._hide_tooltip()

    def _hide_tooltip(self) -> None:
        if self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None

    def _on_click(self, _event: tk.Event) -> None:
        canvas = self._canvas
        item = canvas.find_withtag("current")
        if not item or not self.on_day_click:
            return
        tags = canvas.gettags(item[0])
        date_str = next((tag for tag in tags if tag != "cell"), None)
        if date_str:
            self.on_day_click(date_str)

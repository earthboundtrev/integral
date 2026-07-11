"""Matplotlib charts embedded in Tkinter windows."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Callable

import mpl_tk
import tkinter as tk
from tkinter import messagebox, ttk

DEFAULT_DASHBOARD_COUNT = 8
MAX_DASHBOARD_COUNT = 12
MIN_DASHBOARD_COUNT = 4


def normalize_graph_settings(settings: dict | None) -> dict:
    base = dict(settings or {})
    graphs = base.get("graphs") or {}
    pinned = graphs.get("dashboard_categories")
    if pinned is not None and not isinstance(pinned, list):
        pinned = None
    elif pinned is not None:
        pinned = [str(name) for name in pinned]
    return {"dashboard_categories": pinned}


def short_category_label(name: str) -> str:
    return name.split("/")[0].split("&")[0].strip()


def category_rating_stats(entries: dict, categories: dict) -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for category in categories:
        ratings: list[float] = []
        for cats in entries.values():
            entry = cats.get(category)
            if entry is None or entry.get("rating") is None:
                continue
            try:
                ratings.append(float(entry["rating"]))
            except (TypeError, ValueError):
                continue
        stats[category] = {
            "count": len(ratings),
            "average": sum(ratings) / len(ratings) if ratings else None,
        }
    return stats


def resolve_dashboard_categories(
    entries: dict,
    categories: dict,
    pinned: list[str] | None,
    *,
    default_count: int = DEFAULT_DASHBOARD_COUNT,
) -> tuple[list[str], list[str]]:
    """Return (visible panels, hidden categories) for the dashboard grid."""
    all_names = list(categories.keys())
    if not all_names:
        return [], []

    if pinned:
        visible = [name for name in pinned if name in categories]
    else:
        stats = category_rating_stats(entries, categories)
        ranked = sorted(
            all_names,
            key=lambda name: (-stats[name]["count"], all_names.index(name)),
        )
        visible = ranked[: min(default_count, len(ranked))]

    visible_set = set(visible)
    hidden = [name for name in all_names if name not in visible_set]
    return visible, hidden


def _save_graph_settings(
    current: dict,
    pinned: list[str] | None,
    on_changed: Callable[[dict], None] | None,
) -> dict:
    updated = {**current, "dashboard_categories": pinned}
    if on_changed is not None:
        on_changed({"graphs": updated})
    return updated


def _parse_dates(entries: dict) -> list[datetime.date]:
    dates: list[datetime.date] = []
    for date_str in entries:
        try:
            dates.append(datetime.strptime(date_str, "%Y-%m-%d").date())
        except ValueError:
            continue
    return sorted(dates)


def _rating_series(entries: dict, category: str) -> tuple[list[datetime.date], list[float]]:
    dates: list[datetime.date] = []
    values: list[float] = []
    for date_str in sorted(entries.keys()):
        entry = entries[date_str].get(category)
        if not entry or entry.get("rating") is None:
            continue
        try:
            dates.append(datetime.strptime(date_str, "%Y-%m-%d").date())
            values.append(float(entry["rating"]))
        except (ValueError, TypeError):
            continue
    return dates, values


def _metric_series(entries: dict, category: str, metric_name: str) -> tuple[list[datetime.date], list[float]]:
    dates: list[datetime.date] = []
    values: list[float] = []
    for date_str in sorted(entries.keys()):
        entry = entries[date_str].get(category)
        if not entry:
            continue
        metric_val = entry.get("metrics", {}).get(metric_name)
        if metric_val is None:
            continue
        try:
            dates.append(datetime.strptime(date_str, "%Y-%m-%d").date())
            values.append(float(metric_val))
        except (ValueError, TypeError):
            continue
    return dates, values


def _activity_by_date(entries: dict, category: str | None = None) -> dict[datetime.date, int]:
    counts: dict[datetime.date, int] = defaultdict(int)
    for date_str, cats in entries.items():
        try:
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if category is None:
            counts[day] = len(cats)
        elif category in cats:
            counts[day] = 1
    return counts


class GraphWindow:
    def __init__(
        self,
        parent: tk.Misc,
        entries: dict,
        categories: dict,
        theme: dict,
        *,
        journal_data: dict | None = None,
        fitness_settings: dict | None = None,
        app_settings: dict | None = None,
        on_graph_settings_changed: Callable[[dict], None] | None = None,
        initial_tab: str | None = None,
    ) -> None:
        mpl_tk.ensure_matplotlib()
        self.entries = entries
        self.categories = categories
        self.theme = theme
        self.journal_data = journal_data
        self.fitness_settings = fitness_settings
        self._graph_settings = normalize_graph_settings(app_settings)
        self._on_graph_settings_changed = on_graph_settings_changed
        self._ratings_category_var: tk.StringVar | None = None
        self._tab_index: dict[str, int] = {}
        self._dashboard_refresh: Callable[[], None] | None = None

        self.window = tk.Toplevel(parent)
        self.window.title("Graphing & Progress")
        self.window.geometry("1180x820")
        self.window.configure(bg=theme["bg"])

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._notebook = notebook

        if entries:
            self._add_dashboard_tab(notebook)
            self._add_ratings_tab(notebook)
            self._add_metrics_tab(notebook)
            self._add_heatmap_tab(notebook)
            self._add_radar_tab(notebook)
        else:
            empty = ttk.Frame(notebook, padding=20)
            notebook.add(empty, text="Charts")
            self._tab_index["empty"] = notebook.index(empty)
            ttk.Label(
                empty,
                text="Log a few days of data to see charts.",
                font=("Helvetica", 12),
            ).pack(anchor="w")

        self._add_ai_insight_tab(notebook)

        if initial_tab == "ai_insight":
            notebook.select(self._tab_index["ai_insight"])
        elif initial_tab == "ratings" and "ratings" in self._tab_index:
            notebook.select(self._tab_index["ratings"])
        elif "dashboard" in self._tab_index:
            notebook.select(self._tab_index["dashboard"])

    def _register_tab(self, notebook: ttk.Notebook, frame: ttk.Frame, key: str) -> None:
        self._tab_index[key] = notebook.index(frame)

    def _focus_ratings_tab(self, category: str) -> None:
        if self._ratings_category_var is not None:
            self._ratings_category_var.set(category)
        if "ratings" in self._tab_index:
            self._notebook.select(self._tab_index["ratings"])

    def _build_rating_figure(
        self,
        category: str,
        *,
        figsize: tuple[float, float] = (10, 5),
        title: str | None = None,
    ) -> tuple[object, object, bool]:
        mpl_tk.ensure_matplotlib()
        figure = mpl_tk.Figure(figsize=figsize, dpi=100)
        figure.patch.set_facecolor(self.theme["bg"])
        canvas = mpl_tk.FigureCanvasTkAgg(figure, master=self.window)
        ax = figure.add_subplot(111)
        self._style_axes(ax)
        dates, values = _rating_series(self.entries, category)
        has_data = bool(dates)
        if has_data:
            ax.plot(dates, values, marker="o", linewidth=2, color="#5B8DEF", markersize=4)
            ax.set_ylim(0, 10.5)
            ax.set_ylabel("Rating")
            ax.set_title(title or f"{category} — daily rating")
            ax.xaxis.set_major_formatter(mpl_tk.mdates.DateFormatter("%b %d"))
            figure.autofmt_xdate(rotation=30)
        else:
            ax.text(
                0.5,
                0.5,
                "No ratings yet",
                ha="center",
                va="center",
                color=self.theme["muted"],
            )
            ax.set_title(title or short_category_label(category))
        figure.tight_layout()
        return figure, canvas, has_data

    def _add_dashboard_tab(self, notebook: ttk.Notebook) -> None:
        import ui_scroll

        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Dashboard")
        self._register_tab(notebook, frame, "dashboard")

        header = ttk.Frame(frame, padding=(8, 8, 8, 0))
        header.pack(fill=tk.X)
        ttk.Label(
            header,
            text="Multi-area progress — customize which life domains appear as panels below.",
            style="Muted.TLabel",
            wraplength=980,
        ).pack(anchor="w")

        controls = ttk.Frame(frame, padding=(8, 8))
        controls.pack(fill=tk.X)
        status_var = tk.StringVar(value="")

        def refresh_status() -> None:
            visible, hidden = resolve_dashboard_categories(
                self.entries,
                self.categories,
                self._graph_settings.get("dashboard_categories"),
            )
            pinned = self._graph_settings.get("dashboard_categories")
            mode = "custom" if pinned else "auto"
            status_var.set(
                f"Showing {len(visible)} panel{'s' if len(visible) != 1 else ''}"
                + (f" · {len(hidden)} more available below" if hidden else "")
                + ("" if mode == "custom" else " · auto-picked from your most-logged areas")
            )

        ttk.Label(controls, textvariable=status_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(controls, text="Customize panels…", command=self._open_dashboard_customizer).pack(
            side=tk.RIGHT, padx=(8, 0)
        )
        ttk.Button(controls, text="Reset to auto", command=self._reset_dashboard_panels).pack(side=tk.RIGHT)

        outer, inner, _canvas = ui_scroll.make_scrollable_frame(frame)
        outer.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        grid_host = ttk.Frame(inner)
        grid_host.pack(fill=tk.BOTH, expand=True)
        grid_host.columnconfigure(0, weight=1)
        grid_host.columnconfigure(1, weight=1)

        more_host = ttk.LabelFrame(inner, text="More life areas — click to view", padding=10)
        more_host.pack(fill=tk.X, pady=(12, 8))
        chip_wrap, chip_row, _chip_canvas = ui_scroll.make_horizontal_scroll_row(
            more_host,
            overflow_hint="Scroll for more areas →",
        )
        chip_wrap.pack(fill=tk.X)

        stats = category_rating_stats(self.entries, self.categories)

        def render_dashboard() -> None:
            refresh_status()
            for child in grid_host.winfo_children():
                child.destroy()
            for child in chip_row.winfo_children():
                child.destroy()

            visible, hidden = resolve_dashboard_categories(
                self.entries,
                self.categories,
                self._graph_settings.get("dashboard_categories"),
            )

            for index, category in enumerate(visible):
                row = index // 2
                col = index % 2
                panel = ttk.LabelFrame(
                    grid_host,
                    text=short_category_label(category),
                    padding=8,
                )
                panel.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

                meta = stats.get(category, {})
                avg = meta.get("average")
                count = meta.get("count", 0)
                avg_text = f"avg {avg:.1f}/10" if avg is not None else "no ratings yet"
                ttk.Label(
                    panel,
                    text=f"{count} log{'s' if count != 1 else ''} · {avg_text}",
                    style="Muted.TLabel",
                ).pack(anchor="w")

                plot_host = ttk.Frame(panel)
                plot_host.pack(fill=tk.BOTH, expand=True)
                _figure, canvas, _has_data = self._build_rating_figure(
                    category,
                    figsize=(4.8, 2.6),
                    title="",
                )
                canvas.figure = _figure
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                canvas.draw()

                actions = ttk.Frame(panel)
                actions.pack(fill=tk.X, pady=(6, 0))
                ttk.Button(
                    actions,
                    text="Expand",
                    command=lambda c=category: self._focus_ratings_tab(c),
                ).pack(side=tk.LEFT, padx=(0, 6))
                ttk.Button(
                    actions,
                    text="Quick view",
                    command=lambda c=category: self._open_category_quick_view(c),
                ).pack(side=tk.LEFT)

            if not visible:
                ttk.Label(
                    grid_host,
                    text="No categories configured. Use Customize panels to pick life areas.",
                    wraplength=720,
                ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=8)

            if hidden:
                for category in hidden:
                    count = stats.get(category, {}).get("count", 0)
                    label = short_category_label(category)
                    if count:
                        label = f"{label} ({count})"
                    ttk.Button(
                        chip_row,
                        text=label,
                        command=lambda c=category: self._open_category_quick_view(c),
                    ).pack(side=tk.LEFT, padx=4, pady=2)
            else:
                ttk.Label(chip_row, text="All areas are on the dashboard.", style="Muted.TLabel").pack(
                    side=tk.LEFT, padx=4
                )

        self._dashboard_refresh = render_dashboard
        render_dashboard()

    def _reset_dashboard_panels(self) -> None:
        self._graph_settings = _save_graph_settings(
            self._graph_settings,
            None,
            self._on_graph_settings_changed,
        )
        if self._dashboard_refresh is not None:
            self._dashboard_refresh()

    def _open_dashboard_customizer(self) -> None:
        import ui_scroll

        visible, _hidden = resolve_dashboard_categories(
            self.entries,
            self.categories,
            self._graph_settings.get("dashboard_categories"),
        )
        pinned_mode = self._graph_settings.get("dashboard_categories") is not None
        selected = set(visible if pinned_mode else visible)

        dialog, inner, footer, _canvas, _refresh = ui_scroll.create_dialog_shell(
            self.window,
            title="Customize dashboard panels",
            geometry="520x620",
            minsize=(440, 420),
            grab=True,
        )
        ttk.Label(
            inner,
            text=(
                f"Pick {MIN_DASHBOARD_COUNT}–{MAX_DASHBOARD_COUNT} life areas to show as chart panels. "
                "Others stay one click away in “More life areas”."
            ),
            wraplength=460,
        ).pack(anchor="w", padx=16, pady=(16, 10))

        vars_by_name: dict[str, tk.BooleanVar] = {}
        checks = ttk.Frame(inner, padding=(16, 0))
        checks.pack(fill=tk.BOTH, expand=True)
        for category in self.categories:
            var = tk.BooleanVar(value=category in selected)
            vars_by_name[category] = var
            ttk.Checkbutton(checks, text=category, variable=var, wraplength=420).pack(anchor="w", pady=2)

        def apply_selection(*, use_auto: bool = False) -> None:
            if use_auto:
                self._graph_settings = _save_graph_settings(
                    self._graph_settings,
                    None,
                    self._on_graph_settings_changed,
                )
                dialog.destroy()
                if self._dashboard_refresh is not None:
                    self._dashboard_refresh()
                return

            chosen = [name for name in self.categories if vars_by_name[name].get()]
            if len(chosen) < MIN_DASHBOARD_COUNT:
                messagebox.showwarning(
                    "Too few panels",
                    f"Choose at least {MIN_DASHBOARD_COUNT} life areas.",
                    parent=dialog,
                )
                return
            if len(chosen) > MAX_DASHBOARD_COUNT:
                messagebox.showwarning(
                    "Too many panels",
                    f"Choose at most {MAX_DASHBOARD_COUNT} life areas for the dashboard grid.",
                    parent=dialog,
                )
                return
            self._graph_settings = _save_graph_settings(
                self._graph_settings,
                chosen,
                self._on_graph_settings_changed,
            )
            dialog.destroy()
            if self._dashboard_refresh is not None:
                self._dashboard_refresh()

        ttk.Button(footer, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(
            footer,
            text="Use auto layout",
            command=lambda: apply_selection(use_auto=True),
        ).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(
            footer,
            text="Save panels",
            style="Accent.TButton",
            command=lambda: apply_selection(use_auto=False),
        ).pack(side=tk.RIGHT)

    def _open_category_quick_view(self, category: str) -> None:
        dialog = tk.Toplevel(self.window)
        dialog.title(short_category_label(category))
        dialog.geometry("760x460")
        dialog.minsize(560, 360)
        dialog.transient(self.window)
        dialog.configure(bg=self.theme["bg"])

        footer = ttk.Frame(dialog, padding=10)
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(
            footer,
            text="Open full trend tab",
            command=lambda: (dialog.destroy(), self._focus_ratings_tab(category)),
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            footer,
            text="Add to dashboard",
            command=lambda: self._pin_category_to_dashboard(category, dialog),
        ).pack(side=tk.LEFT)
        ttk.Button(footer, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

        plot_host = ttk.Frame(dialog, padding=10)
        plot_host.pack(fill=tk.BOTH, expand=True)
        _figure, canvas, _has_data = self._build_rating_figure(category)
        canvas.figure = _figure
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()

    def _pin_category_to_dashboard(self, category: str, dialog: tk.Misc) -> None:
        pinned = list(self._graph_settings.get("dashboard_categories") or [])
        visible, _hidden = resolve_dashboard_categories(
            self.entries,
            self.categories,
            pinned or None,
        )
        if not pinned:
            pinned = list(visible)
        if category in pinned:
            messagebox.showinfo("Dashboard", f"{short_category_label(category)} is already pinned.", parent=dialog)
            return
        if len(pinned) >= MAX_DASHBOARD_COUNT:
            pinned = pinned[1:]
        pinned.append(category)
        self._graph_settings = _save_graph_settings(
            self._graph_settings,
            pinned,
            self._on_graph_settings_changed,
        )
        dialog.destroy()
        if self._dashboard_refresh is not None:
            self._dashboard_refresh()

    def _figure(self, rows: int = 1, cols: int = 1) -> tuple[object, object]:
        mpl_tk.ensure_matplotlib()
        figure = mpl_tk.Figure(figsize=(10, 5 if rows == 1 else 7), dpi=100)
        figure.patch.set_facecolor(self.theme["bg"])
        canvas = mpl_tk.FigureCanvasTkAgg(figure, master=self.window)
        return figure, canvas

    def _style_axes(self, ax) -> None:
        ax.set_facecolor(self.theme["text_bg"])
        ax.tick_params(colors=self.theme["fg"])
        ax.title.set_color(self.theme["fg"])
        ax.xaxis.label.set_color(self.theme["fg"])
        ax.yaxis.label.set_color(self.theme["fg"])
        for spine in ax.spines.values():
            spine.set_color(self.theme["card_border"])

    def _add_ratings_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Rating Trends")
        self._register_tab(notebook, frame, "ratings")

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(controls, text="Category:").pack(side=tk.LEFT)
        category_var = tk.StringVar(value=next(iter(self.categories.keys())))
        self._ratings_category_var = category_var
        combo = ttk.Combobox(
            controls,
            textvariable=category_var,
            values=list(self.categories.keys()),
            state="readonly",
            width=40,
        )
        combo.pack(side=tk.LEFT, padx=8)

        plot_frame = ttk.Frame(frame)
        plot_frame.pack(fill=tk.BOTH, expand=True)

        def render(*_args: object) -> None:
            for child in plot_frame.winfo_children():
                child.destroy()
            category = category_var.get()
            dates, values = _rating_series(self.entries, category)
            figure, canvas = self._figure()
            ax = figure.add_subplot(111)
            self._style_axes(ax)
            if dates:
                ax.plot(dates, values, marker="o", linewidth=2, color="#5B8DEF")
                ax.set_ylim(0, 10.5)
                ax.set_ylabel("Rating")
                ax.set_title(f"{category} — daily rating")
                ax.xaxis.set_major_formatter(mpl_tk.mdates.DateFormatter("%b %d"))
                figure.autofmt_xdate()
            else:
                ax.text(0.5, 0.5, "No ratings yet for this category", ha="center", va="center", color=self.theme["muted"])
            canvas.figure = figure
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            canvas.draw()

        ttk.Button(controls, text="Refresh", command=render).pack(side=tk.LEFT)
        category_var.trace_add("write", render)
        render()

    def _add_metrics_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Metric Trends")

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, padx=8, pady=8)
        category_var = tk.StringVar(value=next(iter(self.categories.keys())))
        metric_var = tk.StringVar()

        ttk.Label(controls, text="Category:").pack(side=tk.LEFT)
        cat_combo = ttk.Combobox(
            controls,
            textvariable=category_var,
            values=list(self.categories.keys()),
            state="readonly",
            width=28,
        )
        cat_combo.pack(side=tk.LEFT, padx=6)

        ttk.Label(controls, text="Metric:").pack(side=tk.LEFT, padx=(12, 0))
        metric_combo = ttk.Combobox(controls, textvariable=metric_var, state="readonly", width=32)
        metric_combo.pack(side=tk.LEFT, padx=6)

        plot_frame = ttk.Frame(frame)
        plot_frame.pack(fill=tk.BOTH, expand=True)

        def refresh_metrics(*_args: object) -> None:
            metrics = self.categories.get(category_var.get(), {}).get("metrics", [])
            names = [metric["name"] for metric in metrics]
            metric_combo["values"] = names
            if names and metric_var.get() not in names:
                metric_var.set(names[0])

        def render(*_args: object) -> None:
            refresh_metrics()
            for child in plot_frame.winfo_children():
                child.destroy()
            category = category_var.get()
            metric_name = metric_var.get()
            if not metric_name:
                return
            dates, values = _metric_series(self.entries, category, metric_name)
            figure, canvas = self._figure()
            ax = figure.add_subplot(111)
            self._style_axes(ax)
            if dates:
                ax.plot(dates, values, marker="o", linewidth=2, color="#3DDB87")
                ax.set_title(f"{category} — {metric_name}")
                ax.set_ylabel(metric_name)
                ax.xaxis.set_major_formatter(mpl_tk.mdates.DateFormatter("%b %d"))
                figure.autofmt_xdate()
            else:
                ax.text(0.5, 0.5, "No metric data yet", ha="center", va="center", color=self.theme["muted"])
            canvas.figure = figure
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            canvas.draw()

        ttk.Button(controls, text="Refresh", command=render).pack(side=tk.LEFT, padx=8)
        category_var.trace_add("write", render)
        metric_var.trace_add("write", render)
        render()

    def _add_heatmap_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Activity Heatmap")

        figure, canvas = self._figure()
        ax = figure.add_subplot(111)
        self._style_axes(ax)

        end = datetime.now().date()
        start = end - timedelta(days=83)
        day = start
        weeks: list[list[int]] = []
        current_week: list[int] = []
        week_labels: list[str] = []

        while day <= end:
            if day.weekday() == 0 and current_week:
                weeks.append(current_week)
                week_labels.append(day.strftime("%b %d"))
                current_week = []
            count = len(self.entries.get(day.strftime("%Y-%m-%d"), {}))
            current_week.append(count)
            day += timedelta(days=1)
        if current_week:
            weeks.append(current_week)

        if weeks:
            data = [week + [0] * (7 - len(week)) for week in weeks]
            im = ax.imshow(data, aspect="auto", cmap="YlOrRd")
            ax.set_title("Daily logging activity (categories logged per day)")
            ax.set_xlabel("Day of week (Mon-Sun)")
            ax.set_ylabel("Week")
            ax.set_xticks(range(7))
            ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
            figure.colorbar(im, ax=ax, label="Categories logged")
        else:
            ax.text(0.5, 0.5, "No activity data yet", ha="center", va="center", color=self.theme["muted"])

        canvas.figure = figure
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        canvas.draw()

    def _add_radar_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Life Balance")

        figure, canvas = self._figure()
        ax = figure.add_subplot(111, polar=True)
        ax.set_facecolor(self.theme["text_bg"])
        ax.tick_params(colors=self.theme["fg"])

        labels: list[str] = []
        values: list[float] = []
        for category in self.categories:
            ratings: list[float] = []
            for date_str, cats in self.entries.items():
                entry = cats.get(category)
                if entry and entry.get("rating") is not None:
                    try:
                        ratings.append(float(entry["rating"]))
                    except (TypeError, ValueError):
                        pass
            if ratings:
                short = category.split("/")[0].split("&")[0].strip()
                labels.append(short[:18])
                values.append(sum(ratings) / len(ratings))

        if len(values) >= 3:
            values.append(values[0])
            angles = [n / float(len(labels)) * 2 * 3.14159265 for n in range(len(labels))]
            angles.append(angles[0])
            ax.plot(angles, values, "o-", linewidth=2, color="#9B59B6")
            ax.fill(angles, values, alpha=0.2, color="#9B59B6")
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels, color=self.theme["fg"], size=8)
            ax.set_ylim(0, 10)
            ax.set_title("Average ratings by life area", color=self.theme["fg"], pad=20)
        else:
            ax.text(0.5, 0.5, "Need ratings in 3+ categories", transform=ax.transAxes, ha="center", color=self.theme["muted"])

        canvas.figure = figure
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        canvas.draw()

    def _add_ai_insight_tab(self, notebook: ttk.Notebook) -> None:
        import ai_insights

        tab = ttk.Frame(notebook)
        notebook.add(tab, text="AI Insight")
        self._register_tab(notebook, tab, "ai_insight")
        ai_insights.mount_insight_panel(
            tab,
            self.theme,
            entries=self.entries,
            categories=self.categories,
            journal_data=self.journal_data,
            fitness_settings=self.fitness_settings,
            default_days=7,
        )


def open_graphs(
    parent: tk.Misc,
    entries: dict,
    categories: dict,
    theme: dict,
    *,
    journal_data: dict | None = None,
    fitness_settings: dict | None = None,
    app_settings: dict | None = None,
    on_graph_settings_changed: Callable[[dict], None] | None = None,
    initial_tab: str | None = None,
) -> None:
    try:
        GraphWindow(
            parent,
            entries,
            categories,
            theme,
            journal_data=journal_data,
            fitness_settings=fitness_settings,
            app_settings=app_settings,
            on_graph_settings_changed=on_graph_settings_changed,
            initial_tab=initial_tab,
        )
    except ImportError:
        messagebox.showerror(
            "Matplotlib required",
            "Install charting support with:\n\npip install matplotlib",
        )

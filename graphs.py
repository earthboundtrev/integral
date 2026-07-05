"""Matplotlib charts embedded in Tkinter windows."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import tkinter as tk
from tkinter import messagebox, ttk


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
    ) -> None:
        self.entries = entries
        self.categories = categories
        self.theme = theme

        self.window = tk.Toplevel(parent)
        self.window.title("Graphing & Progress")
        self.window.geometry("1100x760")
        self.window.configure(bg=theme["bg"])

        if not entries:
            ttk.Label(
                self.window,
                text="Log a few days of data to see charts.",
                font=("Helvetica", 12),
            ).pack(expand=True)
            return

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._add_ratings_tab(notebook)
        self._add_metrics_tab(notebook)
        self._add_heatmap_tab(notebook)
        self._add_radar_tab(notebook)

    def _figure(self, rows: int = 1, cols: int = 1) -> tuple[Figure, FigureCanvasTkAgg]:
        figure = Figure(figsize=(10, 5 if rows == 1 else 7), dpi=100)
        figure.patch.set_facecolor(self.theme["bg"])
        canvas = FigureCanvasTkAgg(figure, master=self.window)
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

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(controls, text="Category:").pack(side=tk.LEFT)
        category_var = tk.StringVar(value=next(iter(self.categories.keys())))
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
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
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
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
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


def open_graphs(parent: tk.Misc, entries: dict, categories: dict, theme: dict) -> None:
    try:
        GraphWindow(parent, entries, categories, theme)
    except ImportError:
        messagebox.showerror(
            "Matplotlib required",
            "Install charting support with:\n\npip install matplotlib",
        )

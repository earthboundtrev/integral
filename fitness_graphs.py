"""Matplotlib charts for multi-program fitness tracking."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

import matplotlib

matplotlib.use("TkAgg")

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import tkinter as tk
from tkinter import ttk


def _parse_date(date_str: str) -> datetime.date | None:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def _style_axes(ax, theme: dict) -> None:
    ax.set_facecolor(theme["text_bg"])
    ax.tick_params(colors=theme["fg"])
    ax.title.set_color(theme["fg"])
    ax.xaxis.label.set_color(theme["fg"])
    ax.yaxis.label.set_color(theme["fg"])
    for spine in ax.spines.values():
        spine.set_color(theme["card_border"])


class FitnessGraphWindow:
    def __init__(
        self,
        parent: tk.Misc,
        sessions: list[dict],
        programs: dict[str, dict],
        theme: dict,
    ) -> None:
        self.sessions = sessions
        self.programs = programs
        self.theme = theme

        self.window = tk.Toplevel(parent)
        self.window.title("Fitness Charts & Progress")
        self.window.geometry("1100x760")
        self.window.configure(bg=theme["bg"])

        if not sessions:
            ttk.Label(
                self.window,
                text="Log fitness sessions to see step ladders, rep ramps, and volume trends.",
                font=("Helvetica", 12),
            ).pack(expand=True)
            return

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._add_step_ladder_tab(notebook)
        self._add_tibetan_tab(notebook)
        self._add_volume_tab(notebook)

    def _figure(self) -> tuple[Figure, FigureCanvasTkAgg]:
        figure = Figure(figsize=(10, 5), dpi=100)
        figure.patch.set_facecolor(self.theme["bg"])
        canvas = FigureCanvasTkAgg(figure, master=self.window)
        return figure, canvas

    def _add_step_ladder_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Step Ladders")

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(controls, text="Program:").pack(side=tk.LEFT)
        program_ids = [pid for pid, prog in self.programs.items() if prog["progression_model"] in ("step_ladder", "parc_step")]
        program_var = tk.StringVar(value=program_ids[0] if program_ids else "")
        ttk.Combobox(controls, textvariable=program_var, values=program_ids, state="readonly", width=28).pack(
            side=tk.LEFT, padx=8
        )

        plot_frame = ttk.Frame(frame)
        plot_frame.pack(fill=tk.BOTH, expand=True)

        def render(*_args: object) -> None:
            for child in plot_frame.winfo_children():
                child.destroy()
            program = self.programs.get(program_var.get())
            if not program:
                return
            figure, canvas = self._figure()
            ax = figure.add_subplot(111)
            _style_axes(ax, self.theme)

            keys: list[str] = []
            if program["progression_model"] == "parc_step":
                keys = [chain["id"] for chain in program.get("chains", [])]
                label_map = {chain["id"]: chain["name"] for chain in program.get("chains", [])}
            else:
                keys = [movement["id"] for movement in program.get("movements", [])]
                label_map = {movement["id"]: movement["name"] for movement in program.get("movements", [])}

            colors = ["#5B8DEF", "#E85D75", "#50C878", "#F4A442", "#9B59B6", "#1ABC9C"]
            plotted = False
            for index, key in enumerate(keys):
                dates: list[datetime.date] = []
                steps: list[int] = []
                for session in sorted(self.sessions, key=lambda item: item["date"]):
                    if session.get("program_id") != program["id"]:
                        continue
                    for log in session.get("movement_logs", []):
                        log_key = log.get("chain_key") or log.get("movement_key")
                        if log_key != key:
                            continue
                        day = _parse_date(session["date"])
                        if day is None:
                            continue
                        dates.append(day)
                        steps.append(int(log.get("step", 1)))
                if dates:
                    plotted = True
                    ax.plot(dates, steps, marker="o", linewidth=2, label=label_map[key], color=colors[index % len(colors)])

            ax.set_ylim(0.5, 10.5)
            ax.set_ylabel("Step")
            ax.set_title(f"{program['name']} — step progression over time")
            if plotted:
                ax.legend(loc="upper left", fontsize=8)
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
                figure.autofmt_xdate()
            else:
                ax.text(0.5, 0.5, "No step data yet", ha="center", va="center", color=self.theme["muted"])
            canvas.figure = figure
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            canvas.draw()

        ttk.Button(controls, text="Refresh", command=render).pack(side=tk.LEFT)
        program_var.trace_add("write", render)
        render()

    def _add_tibetan_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Tibetan Rep Ramp")

        plot_frame = ttk.Frame(frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        program = self.programs.get("tibetan-rites")
        if not program:
            ttk.Label(plot_frame, text="Tibetan Rites program not loaded.").pack()
            return

        figure, canvas = self._figure()
        ax = figure.add_subplot(111)
        _style_axes(ax, self.theme)

        official_weeks = [entry["week"] for entry in program["weekly_schedule"]]
        official_reps = [entry["reps_per_rite"] for entry in program["weekly_schedule"]]
        ax.plot(official_weeks, official_reps, linestyle="--", color="#888888", label="Official Kelder/Bradford ramp")

        logged_weeks: list[int] = []
        logged_targets: list[int] = []
        for session in sorted(self.sessions, key=lambda item: item["date"]):
            if session.get("program_id") != "tibetan-rites":
                continue
            for log in session.get("movement_logs", []):
                target = log.get("target_reps")
                if target is None:
                    continue
                week = 1
                for entry in program["weekly_schedule"]:
                    if entry["reps_per_rite"] == int(target):
                        week = entry["week"]
                        break
                logged_weeks.append(week)
                logged_targets.append(int(target))

        if logged_weeks:
            ax.scatter(logged_weeks, logged_targets, color="#5B8DEF", s=60, zorder=5, label="Your logged targets")

        ax.set_xlabel("Week")
        ax.set_ylabel("Reps per rite")
        ax.set_title("Five Tibetan Rites — official weekly rep schedule")
        ax.legend()
        canvas.figure = figure
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()

    def _add_volume_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Session Volume")

        plot_frame = ttk.Frame(frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        counts: dict[datetime.date, int] = defaultdict(int)
        for session in self.sessions:
            day = _parse_date(session.get("date", ""))
            if day:
                counts[day] += 1

        figure, canvas = self._figure()
        ax = figure.add_subplot(111)
        _style_axes(ax, self.theme)

        if counts:
            dates = sorted(counts.keys())
            values = [counts[day] for day in dates]
            ax.bar(dates, values, color="#5B8DEF")
            ax.set_ylabel("Sessions")
            ax.set_title("Fitness sessions per day (all programs)")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
            figure.autofmt_xdate()
        else:
            ax.text(0.5, 0.5, "No sessions yet", ha="center", va="center", color=self.theme["muted"])

        canvas.figure = figure
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()


def open_fitness_graphs(
    parent: tk.Misc,
    sessions: list[dict],
    programs: dict[str, dict],
    theme: dict,
) -> None:
    FitnessGraphWindow(parent, sessions, programs, theme)

"""Matplotlib charts for multi-program fitness tracking."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

import mpl_tk
import tkinter as tk
from tkinter import ttk

from fitness.engine import compute_program_state
from fitness.intelligence import compute_development_scores, find_personal_records, metric_total


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
        settings: dict | None = None,
    ) -> None:
        mpl_tk.ensure_matplotlib()
        self.sessions = sessions
        self.programs = programs
        self.theme = theme
        self.settings = settings or {}
        self.program_state = compute_program_state(programs, sessions, self.settings)

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
        self._add_tibetan_rites_tab(notebook)
        self._add_height_tab(notebook)
        self._add_volume_tab(notebook)
        self._add_volume_by_program_tab(notebook)
        self._add_heatmap_tab(notebook)
        self._add_radar_tab(notebook)

    def _figure(self, parent: tk.Misc | None = None) -> tuple[object, object]:
        mpl_tk.ensure_matplotlib()
        figure = mpl_tk.Figure(figsize=(10, 5), dpi=100)
        figure.patch.set_facecolor(self.theme["bg"])
        master = parent or self.window
        canvas = mpl_tk.FigureCanvasTkAgg(figure, master=master)
        return figure, canvas

    def _add_step_ladder_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Step Ladders")

        controls = ttk.Frame(frame)
        controls.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(controls, text="Program:").pack(side=tk.LEFT)
        program_ids = [
            pid for pid, prog in self.programs.items() if prog["progression_model"] in ("step_ladder", "parc_step")
        ]
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
            figure, canvas = self._figure(plot_frame)
            ax = figure.add_subplot(111)
            _style_axes(ax, self.theme)

            keys: list[str] = []
            if program["progression_model"] == "parc_step":
                keys = [chain["id"] for chain in program.get("chains", [])]
                label_map = {chain["id"]: chain["name"] for chain in program.get("chains", [])}
            else:
                keys = [movement["id"] for movement in program.get("movements", [])]
                label_map = {movement["id"]: movement["name"] for movement in program.get("movements", [])}

            pr_dates: dict[str, datetime.date] = {}
            for record in find_personal_records(self.sessions, program["id"]):
                day = _parse_date(record["date"])
                if day:
                    pr_dates[record["label"]] = day

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
                    ax.plot(
                        dates,
                        steps,
                        marker="o",
                        linewidth=2,
                        label=label_map[key],
                        color=colors[index % len(colors)],
                    )
                    if dates:
                        ax.scatter([dates[-1]], [steps[-1]], color=colors[index % len(colors)], s=80, zorder=6)

            ax.set_ylim(0.5, 10.5)
            ax.set_ylabel("Step")
            ax.set_title(f"{program['name']} — step progression (dots = latest)")
            if plotted:
                ax.legend(loc="upper left", fontsize=8)
                ax.xaxis.set_major_formatter(mpl_tk.mdates.DateFormatter("%b %d"))
                figure.autofmt_xdate()
            else:
                ax.text(0.5, 0.5, "No step data yet", ha="center", va="center", color=self.theme["muted"])
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

        figure, canvas = self._figure(plot_frame)
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
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()

    def _add_tibetan_rites_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Tibetan — 5 Rites")

        plot_frame = ttk.Frame(frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        program = self.programs.get("tibetan-rites")
        if not program:
            ttk.Label(plot_frame, text="Tibetan Rites program not loaded.").pack()
            return

        figure, canvas = self._figure(plot_frame)
        ax = figure.add_subplot(111)
        _style_axes(ax, self.theme)

        colors = ["#5B8DEF", "#E85D75", "#50C878", "#F4A442", "#9B59B6"]
        plotted = False
        for index, rite in enumerate(program["movements"]):
            dates: list[datetime.date] = []
            reps: list[int] = []
            for session in sorted(self.sessions, key=lambda item: item["date"]):
                if session.get("program_id") != "tibetan-rites":
                    continue
                day = _parse_date(session["date"])
                if day is None:
                    continue
                for log in session.get("movement_logs", []):
                    rite_reps = log.get("reps_per_rite", {})
                    if rite["id"] in rite_reps:
                        dates.append(day)
                        reps.append(int(rite_reps[rite["id"]]))
            if dates:
                plotted = True
                ax.plot(dates, reps, marker="o", label=rite["name"], color=colors[index % len(colors)])

        ax.set_ylabel("Reps")
        ax.set_title("Reps per rite over time")
        if plotted:
            ax.legend(fontsize=8)
            ax.xaxis.set_major_formatter(mpl_tk.mdates.DateFormatter("%b %d"))
            figure.autofmt_xdate()
        else:
            ax.text(0.5, 0.5, "No Tibetan data yet", ha="center", va="center", color=self.theme["muted"])
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()

    def _add_height_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="EC Height")

        plot_frame = ttk.Frame(frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        program = self.programs.get("explosive-calisthenics")
        if not program:
            ttk.Label(plot_frame, text="Explosive Calisthenics program not loaded.").pack()
            return

        figure, canvas = self._figure(plot_frame)
        ax = figure.add_subplot(111)
        _style_axes(ax, self.theme)

        by_chain: dict[str, list[tuple[datetime.date, float]]] = defaultdict(list)
        for session in sorted(self.sessions, key=lambda item: item["date"]):
            if session.get("program_id") != program["id"]:
                continue
            day = _parse_date(session["date"])
            if day is None:
                continue
            for log in session.get("movement_logs", []):
                height = log.get("height_cm")
                if height is None:
                    continue
                label = log.get("chain_name") or log.get("chain_key", "chain")
                by_chain[label].append((day, float(height)))

        colors = ["#5B8DEF", "#E85D75", "#50C878", "#F4A442"]
        for index, (label, points) in enumerate(by_chain.items()):
            dates, heights = zip(*points)
            ax.plot(dates, heights, marker="o", label=label, color=colors[index % len(colors)])

        ax.set_ylabel("Height (cm)")
        ax.set_title("Explosive Calisthenics — vertical leap height")
        if by_chain:
            ax.legend(fontsize=8)
            ax.xaxis.set_major_formatter(mpl_tk.mdates.DateFormatter("%b %d"))
            figure.autofmt_xdate()
        else:
            ax.text(0.5, 0.5, "Log height_cm on EC sessions", ha="center", va="center", color=self.theme["muted"])
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

        figure, canvas = self._figure(plot_frame)
        ax = figure.add_subplot(111)
        _style_axes(ax, self.theme)

        if counts:
            dates = sorted(counts.keys())
            values = [counts[day] for day in dates]
            ax.bar(dates, values, color="#5B8DEF")
            ax.set_ylabel("Sessions")
            ax.set_title("Fitness sessions per day (all programs)")
            ax.xaxis.set_major_formatter(mpl_tk.mdates.DateFormatter("%b %d"))
            figure.autofmt_xdate()
        else:
            ax.text(0.5, 0.5, "No sessions yet", ha="center", va="center", color=self.theme["muted"])

        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()

    def _add_volume_by_program_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Volume by Program")

        plot_frame = ttk.Frame(frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        totals: dict[str, float] = defaultdict(float)
        for session in self.sessions:
            program = self.programs.get(session.get("program_id", ""), {})
            name = program.get("name", session.get("program_id", "unknown"))
            for log in session.get("movement_logs", []):
                totals[name] += metric_total(log)

        figure, canvas = self._figure(plot_frame)
        ax = figure.add_subplot(111)
        _style_axes(ax, self.theme)

        if totals:
            labels = list(totals.keys())
            values = [totals[label] for label in labels]
            ax.barh(labels, values, color="#5B8DEF")
            ax.set_xlabel("Total volume (reps / hold / height proxy)")
            ax.set_title("Cumulative training volume by program")
        else:
            ax.text(0.5, 0.5, "No volume data yet", ha="center", va="center", color=self.theme["muted"])

        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()

    def _add_heatmap_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Activity Heatmap")

        plot_frame = ttk.Frame(frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        import numpy as np

        end = datetime.now().date()
        start = end - timedelta(days=83)
        day_count = (end - start).days + 1
        grid = np.zeros((7, max(1, (day_count + 6) // 7)))

        for session in self.sessions:
            day = _parse_date(session.get("date", ""))
            if day is None or day < start or day > end:
                continue
            offset = (day - start).days
            row = day.weekday()
            col = offset // 7
            if col < grid.shape[1]:
                grid[row, col] += 1

        figure, canvas = self._figure(plot_frame)
        ax = figure.add_subplot(111)
        _style_axes(ax, self.theme)
        im = ax.imshow(grid, aspect="auto", cmap="Blues", vmin=0)
        ax.set_yticks(range(7))
        ax.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        ax.set_title("Fitness sessions — last ~12 weeks (darker = more sessions)")
        figure.colorbar(im, ax=ax, label="Sessions")
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()

    def _add_radar_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook)
        notebook.add(frame, text="Development Radar")

        plot_frame = ttk.Frame(frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        scores = compute_development_scores(self.programs, self.sessions, self.program_state)
        if not scores:
            ttk.Label(plot_frame, text="No programs loaded.").pack()
            return

        import numpy as np

        labels = [self.programs[pid].get("name", pid) for pid in scores]
        values = list(scores.values())
        angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
        values_cycle = values + values[:1]
        angles_cycle = angles + angles[:1]

        figure, canvas = self._figure(plot_frame)
        ax = figure.add_subplot(111, polar=True)
        ax.set_facecolor(self.theme["text_bg"])
        ax.plot(angles_cycle, values_cycle, color="#5B8DEF", linewidth=2)
        ax.fill(angles_cycle, values_cycle, color="#5B8DEF", alpha=0.25)
        ax.set_xticks(angles)
        ax.set_xticklabels(labels, color=self.theme["fg"])
        ax.set_ylim(0, 100)
        ax.set_title("Cross-program development score (0–100)", color=self.theme["fg"], pad=20)
        ax.tick_params(colors=self.theme["fg"])
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()


def open_fitness_graphs(
    parent: tk.Misc,
    sessions: list[dict],
    programs: dict[str, dict],
    theme: dict,
    settings: dict | None = None,
) -> None:
    FitnessGraphWindow(parent, sessions, programs, theme, settings=settings)


"""Personal Development Tracker — daily notes, checklists, metrics, charts, and settings."""

from __future__ import annotations

import json
import os
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, scrolledtext, simpledialog, ttk

from activity_grid import ContributionGrid
from graphs import open_graphs
from fitness.engine import compute_program_state, load_program_definitions, migrate_data
from fitness.intelligence import weekly_fitness_summary
from fitness.ui import open_fitness_hub
from insights.engine import analyze_all, category_insight, format_guidance_report, format_insight_line, top_insights
from integral_dialogs import (
    prompt_vault_unlock,
    show_backup_dialog,
    show_export_dialog,
    show_milestones_dialog,
    show_onboarding,
    show_security_dialog,
)
from milestones import merge_milestones, milestone_summary
from paths import APP_NAME, data_file, ensure_data_file, icon_path
from theme import apply_theme, get_theme, style_canvas, style_listbox, style_text_widget
from vault import is_encrypted_file, load_data_file, save_data_file


DATA_FILE = data_file()


class PersonalDevelopmentTracker:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)
        self._apply_window_icon()

        self.categories: dict = {}
        self.entries: dict = {}
        self.settings: dict = {"dark_mode": False}
        self.sessions: list = []
        self.milestones: list = []
        self.program_state: dict = {}
        self.programs: dict = load_program_definitions()
        self.data_path = DATA_FILE
        self.vault_passphrase: str | None = None
        self.theme = get_theme(False)
        self._mousewheel_binding: str | None = None

        if is_encrypted_file(DATA_FILE) and not prompt_vault_unlock(self):
            messagebox.showerror("Locked", "Cannot open encrypted journal without passphrase.")
            root.destroy()
            return

        self.load_data()
        self.apply_current_theme()
        self.create_dashboard()
        if not self.settings.get("onboarding_complete"):
            show_onboarding(self)

    def _apply_window_icon(self) -> None:
        path = icon_path()
        if not path:
            return
        try:
            self.root.iconbitmap(path)
        except tk.TclError:
            pass

    def get_default_categories(self) -> dict:
        return {
            "Money/Freedom": {
                "checklist": [
                    "Tracked daily finances",
                    "Took action toward financial freedom",
                    "Reviewed long-term money goals",
                ],
                "metrics": [
                    {"name": "Savings/Income logged", "type": "number", "unit": "$", "default": 0},
                    {"name": "Freedom mindset rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Body & Presence": {
                "checklist": [
                    "Completed movement/exercise",
                    "Practiced mindfulness or presence",
                    "Ate nourishing food",
                ],
                "metrics": [
                    {"name": "Sleep hours last night", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Energy level", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Presence rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Burnout Prevention & Energy Management": {
                "checklist": [
                    "Took intentional breaks",
                    "Respected personal boundaries",
                    "Did a self-care activity",
                ],
                "metrics": [
                    {"name": "Morning energy", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Stress level (lower = better)", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Creative/Mental Work": {
                "checklist": [
                    "Had a focused/deep work session",
                    "Captured ideas or insights",
                    "Made progress on creative project",
                ],
                "metrics": [
                    {"name": "Deep work hours", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Focus / Creativity rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Family/Logistics": {
                "checklist": [
                    "Spent quality time with family",
                    "Handled key logistics/tasks",
                    "Communicated openly",
                ],
                "metrics": [
                    {"name": "Family time", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Logistics completion", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Search Practice": {
                "checklist": [
                    "Engaged in search/inquiry practice",
                    "Journaled or reflected on search",
                    "Took a concrete search-related action",
                ],
                "metrics": [
                    {"name": "Search effort rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Insights or actions taken", "type": "number", "unit": "", "default": 0},
                ],
            },
            "Spiritual Development": {
                "checklist": [
                    "Daily spiritual practice (meditation, prayer, contemplation, etc.)",
                    "Read or reflected on spiritual teachings / wisdom",
                    "Practiced gratitude, surrender, or presence",
                    "Connected with community, nature, or higher purpose",
                ],
                "metrics": [
                    {"name": "Spiritual practice time", "type": "number", "unit": "min", "default": 0},
                    {
                        "name": "Spiritual connection / peace rating",
                        "type": "rating",
                        "min": 1,
                        "max": 10,
                        "default": 5,
                    },
                    {"name": "Insights or realizations", "type": "number", "unit": "", "default": 0},
                ],
            },
            "Emotional Wellbeing": {
                "checklist": [
                    "Checked in with my current emotions",
                    "Journaled or processed feelings",
                    "Practiced self-compassion or emotional regulation",
                    "Expressed emotions in a healthy, constructive way",
                ],
                "metrics": [
                    {"name": "Emotional awareness rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {
                        "name": "Overall mood / emotional stability",
                        "type": "rating",
                        "min": 1,
                        "max": 10,
                        "default": 5,
                    },
                    {
                        "name": "Emotional check-ins or processing sessions",
                        "type": "number",
                        "unit": "",
                        "default": 0,
                    },
                ],
            },
        }

    def apply_current_theme(self) -> None:
        self.theme = get_theme(bool(self.settings.get("dark_mode", False)))
        apply_theme(self.root, self.theme)

    def toggle_dark_mode(self) -> None:
        self.settings["dark_mode"] = not self.settings.get("dark_mode", False)
        self.save_data()
        self.create_dashboard()

    def merge_categories_with_defaults(self, stored: dict | None) -> dict:
        defaults = self.get_default_categories()
        if not stored:
            return defaults

        merged = dict(stored)
        changed = False
        for name, definition in defaults.items():
            if name not in merged:
                merged[name] = definition
                changed = True
        if changed:
            self.save_data(categories=merged)
        return merged

    def load_data(self) -> None:
        ensure_data_file()
        if os.path.exists(DATA_FILE):
            try:
                data = load_data_file(DATA_FILE, self.vault_passphrase)
            except PermissionError:
                if not prompt_vault_unlock(self):
                    raise
                data = load_data_file(DATA_FILE, self.vault_passphrase)
            migrated = migrate_data(data, self.programs)
            self.categories = self.merge_categories_with_defaults(migrated.get("categories"))
            self.entries = migrated.get("entries", {})
            self.settings = {**{"dark_mode": False}, **migrated.get("settings", {})}
            self.sessions = migrated.get("sessions", [])
            self.milestones = merge_milestones(migrated.get("milestones"))
            self.program_state = migrated.get("program_state", {})
        else:
            self.categories = self.get_default_categories()
            self.entries = {}
            self.settings = {"dark_mode": False, "onboarding_complete": False}
            self.sessions = []
            self.milestones = merge_milestones(None)
            self.program_state = compute_program_state(self.programs, self.sessions, self.settings)
            self.save_data()

    def _payload(self) -> dict:
        self.program_state = compute_program_state(self.programs, self.sessions, self.settings)
        return {
            "schema_version": 2,
            "categories": self.categories,
            "entries": self.entries,
            "settings": self.settings,
            "sessions": self.sessions,
            "milestones": self.milestones,
            "program_state": self.program_state,
            "user_levels": {},
        }

    def save_data(self, categories: dict | None = None) -> None:
        if categories is not None:
            self.categories = categories
        payload = self._payload()
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        save_data_file(
            DATA_FILE,
            payload,
            encrypted=bool(self.settings.get("encryption_enabled")),
            passphrase=self.vault_passphrase,
        )

    def save_fitness_data(self) -> None:
        self.save_data()

    def get_streak(self, category: str | None = None) -> int:
        if not self.entries:
            return 0

        relevant_dates: list[datetime.date] = []
        for date_str, cats in self.entries.items():
            if category is None or category in cats:
                try:
                    relevant_dates.append(datetime.strptime(date_str, "%Y-%m-%d").date())
                except ValueError:
                    continue

        if not relevant_dates:
            return 0

        streak = 0
        expected = datetime.now().date()
        for day in sorted(relevant_dates, reverse=True):
            if day == expected:
                streak += 1
                expected -= timedelta(days=1)
            elif day < expected:
                break
        return streak

    def create_dashboard(self) -> None:
        if self._mousewheel_binding:
            self.root.unbind_all(self._mousewheel_binding)
            self._mousewheel_binding = None

        for widget in self.root.winfo_children():
            widget.destroy()

        self.apply_current_theme()

        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=15, pady=15)
        ttk.Label(
            header,
            text=APP_NAME,
            font=("Helvetica", 22, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Label(
            header,
            text=f"Today: {datetime.now().strftime('%B %d, %Y')}",
            font=("Helvetica", 12),
        ).pack(side=tk.RIGHT, padx=20)
        ttk.Label(
            header,
            text=f"Overall streak: {self.get_streak()} days",
            style="Accent.TLabel",
            font=("Helvetica", 14, "bold"),
        ).pack(side=tk.RIGHT)

        self.insights = analyze_all(
            self.entries,
            self.categories,
            sessions=self.sessions,
            program_state=self.program_state,
        )

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        overview = ttk.Frame(notebook)
        categories_tab = ttk.Frame(notebook)
        notebook.add(overview, text="Overview")
        notebook.add(categories_tab, text="Categories")

        self._build_overview_tab(overview)
        self._build_categories_tab(categories_tab)

        footer = ttk.Frame(self.root)
        footer.pack(fill=tk.X, padx=15, pady=10)
        ttk.Button(footer, text="Refresh", command=self.create_dashboard).pack(side=tk.LEFT)
        ttk.Button(footer, text="Guidance", command=self.show_guidance).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Weekly Summary", command=self.show_weekly_summary).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Full History", command=self.show_history).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Search Notes", command=self.show_search).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Graphs & Progress", command=self.show_graphs).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Fitness Hub", command=self.show_fitness_hub).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Milestones", command=self.show_milestones).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Export", command=self.show_export).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Backup", command=self.show_backup).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Edit Categories", command=self.show_settings).pack(side=tk.LEFT, padx=8)
        ttk.Button(footer, text="Data & Security", command=self.show_security).pack(side=tk.LEFT, padx=8)
        mode_label = "Light Mode" if self.settings.get("dark_mode") else "Dark Mode"
        ttk.Button(footer, text=mode_label, command=self.toggle_dark_mode).pack(side=tk.RIGHT)

    def _build_overview_tab(self, parent: ttk.Frame) -> None:
        canvas = tk.Canvas(parent, highlightthickness=0)
        style_canvas(canvas, self.theme)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        main = ttk.Frame(canvas)
        main.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=main, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mousewheel)
        self._mousewheel_binding = "<MouseWheel>"

        main.columnconfigure(0, weight=1)

        grid_panel = ttk.Frame(main, borderwidth=2, relief="groove", padding=12)
        grid_panel.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        ContributionGrid(
            grid_panel,
            entries=self.entries,
            categories=self.categories,
            theme=self.theme,
            sessions=self.sessions,
            on_day_click=self.show_day_explorer,
        ).pack(fill=tk.X)

        today_str = datetime.now().strftime("%Y-%m-%d")
        logged_today = len(self.entries.get(today_str, {}))
        fitness_today = sum(1 for session in self.sessions if session.get("date") == today_str)
        stats = ttk.Frame(main, padding=8)
        stats.grid(row=1, column=0, sticky="ew", padx=4)
        ttk.Label(
            stats,
            text=f"Today: {logged_today}/{len(self.categories)} life areas logged"
            + (f"  |  {fitness_today} fitness session(s)" if fitness_today else "")
            + f"  |  {milestone_summary(self.milestones)}",
            font=("Helvetica", 11),
        ).pack(anchor="w")
        ttk.Button(stats, text="Explore today", command=lambda: self.show_day_explorer(today_str)).pack(
            anchor="w", pady=(6, 0)
        )

        self._render_guidance_panel(main, row=2)

    def _build_categories_tab(self, parent: ttk.Frame) -> None:
        canvas = tk.Canvas(parent, highlightthickness=0)
        style_canvas(canvas, self.theme)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        main = ttk.Frame(canvas)
        main.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=main, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)

        ttk.Label(
            main,
            text="Log and explore each life area — rating + Save is enough on low-energy days.",
            wraplength=900,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 4))

        row = col = 1
        for cat_name, cat_data in self.categories.items():
            card = self.create_category_card(main, cat_name, cat_data)
            card.grid(row=row, column=col, padx=12, pady=12, sticky="nsew")
            col += 1
            if col > 1:
                col = 0
                row += 1

    def _render_guidance_panel(self, parent: ttk.Frame, row: int = 0) -> None:
        panel = ttk.Frame(parent, borderwidth=2, relief="groove", padding=12)
        panel.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 8))

        ttk.Label(panel, text="Today's Guidance", font=("Helvetica", 13, "bold")).pack(anchor="w")
        highlights = top_insights(self.insights, limit=3)
        if not highlights:
            ttk.Label(
                panel,
                text="Log ratings across a few days — the app will spot trends, gaps, and suggest next steps.",
                wraplength=900,
            ).pack(anchor="w", pady=(4, 0))
        else:
            for insight in highlights:
                style = "Accent.TLabel" if insight.severity == "action" else "Muted.TLabel"
                ttk.Label(
                    panel,
                    text=format_insight_line(insight),
                    wraplength=900,
                    style=style,
                ).pack(anchor="w", pady=2)
                if insight.suggested_actions:
                    ttk.Label(
                        panel,
                        text=f"  → {insight.suggested_actions[0]}",
                        wraplength=880,
                    ).pack(anchor="w", padx=12)

        ttk.Button(panel, text="Full Guidance Report", command=self.show_guidance).pack(anchor="w", pady=(8, 0))

    def create_category_card(self, parent: ttk.Frame, cat_name: str, cat_data: dict) -> ttk.Frame:
        frame = ttk.Frame(parent, borderwidth=2, relief="groove", padding=12)
        ttk.Label(frame, text=cat_name, font=("Helvetica", 14, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Current streak: {self.get_streak(cat_name)} days").pack(anchor="w", pady=4)

        today_str = datetime.now().strftime("%Y-%m-%d")
        today_entry = self.entries.get(today_str, {}).get(cat_name, {})
        if today_entry:
            rating = today_entry.get("rating", "?")
            status = f"Today's rating: {rating}/10"
            style = "Success.TLabel"
        else:
            status = "Not logged today"
            style = "Muted.TLabel"
        ttk.Label(frame, text=status, style=style).pack(anchor="w", pady=4)

        hint = category_insight(self.insights, cat_name)
        if hint:
            hint_style = "Accent.TLabel" if hint.severity == "action" else "Muted.TLabel"
            ttk.Label(frame, text=hint.title, style=hint_style, wraplength=320).pack(anchor="w")

        ttk.Button(
            frame,
            text="Log / Update Today",
            command=lambda name=cat_name: self.open_log_dialog(name),
        ).pack(fill=tk.X, pady=8)

        notes = today_entry.get("notes", "")
        if notes:
            preview = notes[:70] + "..." if len(notes) > 70 else notes
            ttk.Label(frame, text=f"Last note: {preview}", wraplength=320).pack(anchor="w")

        return frame

    def show_day_explorer(self, date_str: str) -> None:
        window = tk.Toplevel(self.root)
        try:
            day_label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %d, %Y")
        except ValueError:
            day_label = date_str
        window.title(f"Day: {day_label}")
        window.geometry("720x640")
        window.configure(bg=self.theme["bg"])
        window.transient(self.root)

        header = ttk.Frame(window)
        header.pack(fill=tk.X, padx=15, pady=12)
        ttk.Label(header, text=day_label, font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)

        day_entries = self.entries.get(date_str, {})
        day_fitness = [session for session in self.sessions if session.get("date") == date_str]
        ttk.Label(
            header,
            text=f"{len(day_entries)} areas  |  {len(day_fitness)} fitness",
            foreground=self.theme["muted"],
        ).pack(side=tk.RIGHT)

        body = ttk.Frame(window)
        body.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        body.columnconfigure(0, weight=1)

        canvas = tk.Canvas(body, highlightthickness=0)
        style_canvas(canvas, self.theme)
        scrollbar = ttk.Scrollbar(body, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        row = 0
        if day_entries:
            for cat_name, entry in sorted(day_entries.items()):
                card = ttk.Frame(scroll_frame, borderwidth=1, relief="groove", padding=10)
                card.grid(row=row, column=0, sticky="ew", pady=6)
                scroll_frame.columnconfigure(0, weight=1)

                ttk.Label(card, text=cat_name, font=("Helvetica", 12, "bold")).pack(anchor="w")
                ttk.Label(card, text=f"Rating: {entry.get('rating', '?')}/10").pack(anchor="w", pady=2)
                done = [label for label, checked in entry.get("checklist", {}).items() if checked]
                if done:
                    ttk.Label(card, text=f"Checklist: {', '.join(done[:4])}{'...' if len(done) > 4 else ''}").pack(
                        anchor="w"
                    )
                if entry.get("metrics"):
                    metrics_preview = ", ".join(f"{name}: {value}" for name, value in list(entry["metrics"].items())[:3])
                    ttk.Label(card, text=f"Metrics: {metrics_preview}", wraplength=620).pack(anchor="w")
                if entry.get("notes"):
                    note = entry["notes"]
                    preview = note[:200] + "..." if len(note) > 200 else note
                    ttk.Label(card, text=preview, wraplength=620).pack(anchor="w", pady=(4, 0))
                ttk.Button(
                    card,
                    text="Edit log",
                    command=lambda name=cat_name, d=date_str: self._open_log_and_close(window, name, d),
                ).pack(anchor="w", pady=(8, 0))
                row += 1
        else:
            ttk.Label(scroll_frame, text="No life-area logs on this day.").grid(row=row, column=0, sticky="w", pady=8)
            row += 1

        if day_fitness:
            ttk.Label(scroll_frame, text="Fitness sessions", font=("Helvetica", 12, "bold")).grid(
                row=row, column=0, sticky="w", pady=(12, 4)
            )
            row += 1
            for session in day_fitness:
                program = self.programs.get(session.get("program_id", ""), {})
                ttk.Label(
                    scroll_frame,
                    text=f"• {program.get('name', session.get('program_id', 'Fitness'))}"
                    + (f" — {session.get('notes', '')[:80]}" if session.get("notes") else ""),
                    wraplength=620,
                ).grid(row=row, column=0, sticky="w")
                row += 1

        missing = [name for name in self.categories if name not in day_entries]
        if missing:
            ttk.Label(scroll_frame, text="Not logged this day", font=("Helvetica", 11, "bold")).grid(
                row=row, column=0, sticky="w", pady=(16, 6)
            )
            row += 1
            chips = ttk.Frame(scroll_frame)
            chips.grid(row=row, column=0, sticky="w")
            for cat_name in missing:
                ttk.Button(
                    chips,
                    text=f"+ {cat_name}",
                    command=lambda name=cat_name, d=date_str: self._open_log_and_close(window, name, d),
                ).pack(side=tk.LEFT, padx=4, pady=4)
            row += 1

        footer = ttk.Frame(window)
        footer.pack(fill=tk.X, padx=15, pady=(0, 12))
        ttk.Button(footer, text="Close", command=window.destroy).pack(side=tk.RIGHT)

    def _open_log_and_close(self, parent_window: tk.Toplevel, cat_name: str, date_str: str) -> None:
        parent_window.destroy()
        self.open_log_dialog(cat_name, date_str=date_str)

    def open_log_dialog(self, cat_name: str, date_str: str | None = None) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Log: {cat_name}")
        dialog.geometry("560x760")
        dialog.configure(bg=self.theme["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        cat_data = self.categories[cat_name]
        today_str = date_str or datetime.now().strftime("%Y-%m-%d")
        existing = self.entries.get(today_str, {}).get(cat_name, {})

        ttk.Label(dialog, text=f"Date: {today_str}", font=("Helvetica", 11)).pack(pady=8)

        ttk.Label(dialog, text="Overall Progress Rating (1-10)", font=("Helvetica", 11, "bold")).pack(
            anchor="w", padx=15
        )
        rating_var = tk.IntVar(value=existing.get("rating", 5))
        spin_frame = ttk.Frame(dialog)
        spin_frame.pack(padx=15, pady=5, fill=tk.X)
        ttk.Spinbox(
            spin_frame,
            from_=1,
            to=10,
            textvariable=rating_var,
            width=6,
            font=("Helvetica", 14),
        ).pack(side=tk.LEFT)

        ttk.Label(
            dialog,
            text="Checklist — tick what you completed",
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=15, pady=(12, 4))
        check_vars: dict[str, tk.BooleanVar] = {}
        for item in cat_data["checklist"]:
            var = tk.BooleanVar(value=existing.get("checklist", {}).get(item, False))
            check_vars[item] = var
            ttk.Checkbutton(dialog, text=item, variable=var).pack(anchor="w", padx=25, pady=2)

        ttk.Label(dialog, text="Specific Measures", font=("Helvetica", 11, "bold")).pack(
            anchor="w", padx=15, pady=(12, 4)
        )
        metric_vars: dict[str, tk.Variable] = {}
        for metric in cat_data["metrics"]:
            metric_name = metric["name"]
            metric_type = metric.get("type", "number")
            metric_unit = metric.get("unit", "")
            existing_val = existing.get("metrics", {}).get(metric_name, metric.get("default", 0))

            row = ttk.Frame(dialog)
            row.pack(fill=tk.X, padx=15, pady=3)
            ttk.Label(row, text=f"{metric_name}:").pack(side=tk.LEFT)

            if metric_type == "number":
                var: tk.Variable = tk.DoubleVar(value=float(existing_val))
                ttk.Entry(row, textvariable=var, width=12).pack(side=tk.LEFT, padx=6)
                if metric_unit:
                    ttk.Label(row, text=metric_unit).pack(side=tk.LEFT)
            else:
                var = tk.IntVar(value=int(existing_val))
                ttk.Spinbox(
                    row,
                    from_=metric.get("min", 1),
                    to=metric.get("max", 10),
                    textvariable=var,
                    width=6,
                ).pack(side=tk.LEFT, padx=6)
            metric_vars[metric_name] = var

        ttk.Label(
            dialog,
            text="General notes / journal entry (write as much as you want)",
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=15, pady=(12, 4))
        notes_text = scrolledtext.ScrolledText(dialog, height=12, width=62, wrap=tk.WORD, font=("Helvetica", 11))
        style_text_widget(notes_text, self.theme)
        notes_text.pack(padx=15, pady=5, fill=tk.BOTH, expand=True)
        if existing.get("notes"):
            notes_text.insert("1.0", existing["notes"])

        btns = ttk.Frame(dialog)
        btns.pack(pady=15)
        ttk.Button(
            btns,
            text="Save Log",
            command=lambda: self.save_log(
                dialog, cat_name, today_str, rating_var, check_vars, metric_vars, notes_text
            ),
        ).pack(side=tk.LEFT, padx=10)
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)

    def save_log(
        self,
        dialog: tk.Toplevel,
        cat_name: str,
        date_str: str,
        rating_var: tk.IntVar,
        check_vars: dict[str, tk.BooleanVar],
        metric_vars: dict[str, tk.Variable],
        notes_text: scrolledtext.ScrolledText,
    ) -> None:
        if date_str not in self.entries:
            self.entries[date_str] = {}

        checklist_data = {item: var.get() for item, var in check_vars.items()}
        metrics_data: dict[str, float | int] = {}
        for name, var in metric_vars.items():
            try:
                metrics_data[name] = var.get()
            except (tk.TclError, ValueError):
                metrics_data[name] = 0

        self.entries[date_str][cat_name] = {
            "rating": rating_var.get(),
            "checklist": checklist_data,
            "metrics": metrics_data,
            "notes": notes_text.get("1.0", tk.END).strip(),
        }
        self.save_data()
        dialog.destroy()
        messagebox.showinfo("Saved", f"Progress and notes logged for {cat_name}.")
        hint = category_insight(
            analyze_all(
                self.entries,
                self.categories,
                sessions=self.sessions,
                program_state=self.program_state,
            ),
            cat_name,
        )
        if hint and hint.suggested_actions:
            messagebox.showinfo("Guidance", f"{hint.message}\n\nTry: {hint.suggested_actions[0]}")
        self.create_dashboard()

    def show_guidance(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Guidance & Maintenance")
        window.geometry("920x720")
        window.configure(bg=self.theme["bg"])

        ttk.Label(
            window,
            text="Intelligent guidance from your logs — trends, gaps, and next steps",
            font=("Helvetica", 13, "bold"),
        ).pack(anchor="w", padx=12, pady=12)

        text = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Helvetica", 11))
        style_text_widget(text, self.theme)
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        text.insert(tk.END, format_guidance_report(self.insights))

    def show_history(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Full History")
        window.geometry("860x640")
        window.configure(bg=self.theme["bg"])
        text = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Consolas", 10))
        style_text_widget(text, self.theme)
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        if not self.entries:
            text.insert(tk.END, "No entries yet.")
            return

        for date in sorted(self.entries.keys(), reverse=True):
            text.insert(tk.END, f"\n{'=' * 60}\n{date}\n{'=' * 60}\n")
            for cat, entry in self.entries[date].items():
                text.insert(tk.END, f"\n> {cat}\n")
                text.insert(tk.END, f"   Rating: {entry.get('rating')}/10\n")
                done = [label for label, checked in entry.get("checklist", {}).items() if checked]
                if done:
                    text.insert(tk.END, f"   Checklist done: {', '.join(done)}\n")
                if entry.get("metrics"):
                    text.insert(tk.END, f"   Metrics: {entry['metrics']}\n")
                if entry.get("notes"):
                    text.insert(tk.END, f"   Notes:\n{entry['notes']}\n")

    def show_weekly_summary(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Weekly Summary")
        window.geometry("900x680")
        window.configure(bg=self.theme["bg"])

        end = datetime.now().date()
        start = end - timedelta(days=6)
        ttk.Label(
            window,
            text=f"Week of {start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}",
            font=("Helvetica", 14, "bold"),
        ).pack(anchor="w", padx=12, pady=12)

        text = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Helvetica", 11))
        style_text_widget(text, self.theme)
        text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        week_dates = [(start + timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(7)]
        days_logged = sum(1 for date in week_dates if date in self.entries)
        text.insert(tk.END, f"Days with any logs: {days_logged}/7\n")
        text.insert(tk.END, f"Overall streak: {self.get_streak()} days\n\n")

        week_insights = analyze_all(
            self.entries,
            self.categories,
            sessions=self.sessions,
            program_state=self.program_state,
        )
        text.insert(tk.END, format_guidance_report(top_insights(week_insights, limit=8)))
        text.insert(tk.END, "\n" + "=" * 50 + "\nCATEGORY DETAIL\n" + "=" * 50 + "\n\n")

        for cat_name, cat_def in self.categories.items():
            ratings: list[float] = []
            checklist_done = 0
            checklist_total = 0
            note_snippets: list[str] = []

            for date in week_dates:
                entry = self.entries.get(date, {}).get(cat_name)
                if not entry:
                    continue
                if entry.get("rating") is not None:
                    try:
                        ratings.append(float(entry["rating"]))
                    except (TypeError, ValueError):
                        pass
                for item in cat_def.get("checklist", []):
                    checklist_total += 1
                    if entry.get("checklist", {}).get(item):
                        checklist_done += 1
                notes = entry.get("notes", "").strip()
                if notes:
                    note_snippets.append(f"  {date}: {notes[:120]}{'...' if len(notes) > 120 else ''}")

            text.insert(tk.END, f"{'-' * 50}\n{cat_name}\n")
            text.insert(tk.END, f"  Days logged: {sum(1 for d in week_dates if cat_name in self.entries.get(d, {}))}/7\n")
            if ratings:
                text.insert(tk.END, f"  Avg rating: {sum(ratings) / len(ratings):.1f}/10\n")
            if checklist_total:
                pct = int((checklist_done / checklist_total) * 100)
                text.insert(tk.END, f"  Checklist completion: {pct}% ({checklist_done}/{checklist_total})\n")
            if note_snippets:
                text.insert(tk.END, "  Recent notes:\n")
                for snippet in note_snippets[:3]:
                    text.insert(tk.END, f"{snippet}\n")
            text.insert(tk.END, "\n")

        text.insert(tk.END, weekly_fitness_summary(self.sessions, self.programs, week_dates))

    def show_milestones(self) -> None:
        show_milestones_dialog(self)

    def show_export(self) -> None:
        show_export_dialog(self)

    def show_backup(self) -> None:
        show_backup_dialog(self)

    def show_security(self) -> None:
        show_security_dialog(self)

    def show_search(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Search Notes")
        window.geometry("860x640")
        window.configure(bg=self.theme["bg"])

        search_frame = ttk.Frame(window)
        search_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        query_var = tk.StringVar()
        entry = ttk.Entry(search_frame, textvariable=query_var, width=50)
        entry.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        results = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Consolas", 10))
        style_text_widget(results, self.theme)
        results.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        def run_search(*_args: object) -> None:
            query = query_var.get().strip().lower()
            results.delete("1.0", tk.END)
            if not query:
                results.insert(tk.END, "Type to search life notes, checklists, and fitness session notes.")
                return

            hits = 0
            if self.entries:
                for date in sorted(self.entries.keys(), reverse=True):
                    for cat, data in self.entries[date].items():
                        haystacks = [
                            cat.lower(),
                            str(data.get("notes", "")).lower(),
                            " ".join(
                                label.lower()
                                for label, checked in data.get("checklist", {}).items()
                                if checked
                            ),
                        ]
                        if any(query in chunk for chunk in haystacks):
                            hits += 1
                            results.insert(tk.END, f"\n{date} — {cat}\n")
                            results.insert(tk.END, f"Rating: {data.get('rating')}/10\n")
                            if data.get("notes"):
                                results.insert(tk.END, f"{data['notes']}\n")
                            results.insert(tk.END, "-" * 40 + "\n")

            for session in sorted(self.sessions, key=lambda item: item.get("date", ""), reverse=True):
                program = self.programs.get(session.get("program_id", ""), {})
                program_name = program.get("name", session.get("program_id", ""))
                haystacks = [
                    program_name.lower(),
                    str(session.get("notes", "")).lower(),
                ]
                for log in session.get("movement_logs", []):
                    haystacks.append(str(log.get("notes", "")).lower())
                if any(query in chunk for chunk in haystacks):
                    hits += 1
                    results.insert(tk.END, f"\n{session.get('date')} — Fitness: {program_name}\n")
                    if session.get("notes"):
                        results.insert(tk.END, f"{session['notes']}\n")
                    results.insert(tk.END, "-" * 40 + "\n")

            if hits == 0:
                results.insert(tk.END, f"No matches for '{query_var.get().strip()}'.")

        ttk.Button(search_frame, text="Search", command=run_search).pack(side=tk.LEFT)
        query_var.trace_add("write", run_search)
        entry.focus_set()
        run_search()

    def show_graphs(self) -> None:
        open_graphs(self.root, self.entries, self.categories, self.theme)

    def show_fitness_hub(self) -> None:
        open_fitness_hub(
            self.root,
            sessions=self.sessions,
            program_state=self.program_state,
            programs=self.programs,
            settings=self.settings,
            theme=self.theme,
            on_save=self.save_fitness_data,
        )

    def show_settings(self) -> None:
        editor = tk.Toplevel(self.root)
        editor.title("Edit Categories")
        editor.geometry("920x640")
        editor.configure(bg=self.theme["bg"])
        editor.transient(self.root)
        editor.grab_set()

        working = json.loads(json.dumps(self.categories))

        body = ttk.Frame(editor)
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        ttk.Label(body, text="Categories").grid(row=0, column=0, sticky="nw")
        category_list = tk.Listbox(body, height=20, width=28, exportselection=False)
        category_list.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        style_listbox(category_list, self.theme)

        editor_panel = ttk.Frame(body)
        editor_panel.grid(row=0, column=1, sticky="nsew")
        editor_panel.columnconfigure(0, weight=1)

        ttk.Label(editor_panel, text="Category name").grid(row=0, column=0, sticky="w")
        name_var = tk.StringVar()
        name_entry = ttk.Entry(editor_panel, textvariable=name_var, width=50)
        name_entry.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(editor_panel, text="Checklist items (one per line)").grid(row=2, column=0, sticky="w")
        checklist_text = scrolledtext.ScrolledText(editor_panel, height=8, wrap=tk.WORD)
        style_text_widget(checklist_text, self.theme)
        checklist_text.grid(row=3, column=0, sticky="nsew", pady=(0, 10))

        ttk.Label(editor_panel, text="Metrics (name | type | unit | default)").grid(row=4, column=0, sticky="w")
        metrics_text = scrolledtext.ScrolledText(editor_panel, height=8, wrap=tk.WORD)
        style_text_widget(metrics_text, self.theme)
        metrics_text.grid(row=5, column=0, sticky="nsew")
        editor_panel.rowconfigure(3, weight=1)
        editor_panel.rowconfigure(5, weight=1)

        def refresh_list(select_name: str | None = None) -> None:
            category_list.delete(0, tk.END)
            for name in working.keys():
                category_list.insert(tk.END, name)
            if select_name and select_name in working:
                idx = list(working.keys()).index(select_name)
                category_list.selection_clear(0, tk.END)
                category_list.selection_set(idx)
                category_list.activate(idx)
                load_selected()

        def metrics_to_text(metrics: list[dict]) -> str:
            lines: list[str] = []
            for metric in metrics:
                unit = metric.get("unit", "")
                default = metric.get("default", 0)
                mtype = metric.get("type", "number")
                if mtype == "rating":
                    lines.append(
                        f"{metric['name']} | rating | {metric.get('min', 1)}-{metric.get('max', 10)} | {default}"
                    )
                else:
                    lines.append(f"{metric['name']} | number | {unit} | {default}")
            return "\n".join(lines)

        def text_to_metrics(raw: str) -> list[dict]:
            metrics: list[dict] = []
            for line in raw.splitlines():
                parts = [part.strip() for part in line.split("|")]
                if len(parts) < 2 or not parts[0]:
                    continue
                name, mtype = parts[0], parts[1].lower()
                if mtype == "rating":
                    bounds = parts[2] if len(parts) > 2 else "1-10"
                    default = float(parts[3]) if len(parts) > 3 and parts[3] else 5
                    low, high = bounds.split("-", 1)
                    metrics.append(
                        {
                            "name": name,
                            "type": "rating",
                            "min": int(low),
                            "max": int(high),
                            "default": int(default),
                        }
                    )
                else:
                    unit = parts[2] if len(parts) > 2 else ""
                    default = float(parts[3]) if len(parts) > 3 and parts[3] else 0
                    metrics.append({"name": name, "type": "number", "unit": unit, "default": default})
            return metrics

        def load_selected(*_args: object) -> None:
            selection = category_list.curselection()
            if not selection:
                return
            name = category_list.get(selection[0])
            data = working[name]
            name_var.set(name)
            checklist_text.delete("1.0", tk.END)
            checklist_text.insert("1.0", "\n".join(data.get("checklist", [])))
            metrics_text.delete("1.0", tk.END)
            metrics_text.insert("1.0", metrics_to_text(data.get("metrics", [])))

        def apply_editor() -> str | None:
            selection = category_list.curselection()
            if not selection:
                messagebox.showwarning("Select category", "Choose a category to save.")
                return None
            old_name = category_list.get(selection[0])
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showwarning("Name required", "Category name cannot be empty.")
                return None
            checklist = [line.strip() for line in checklist_text.get("1.0", tk.END).splitlines() if line.strip()]
            metrics = text_to_metrics(metrics_text.get("1.0", tk.END))
            payload = {"checklist": checklist, "metrics": metrics}
            if new_name != old_name:
                if new_name in working:
                    messagebox.showerror("Duplicate", f"Category '{new_name}' already exists.")
                    return None
                working[new_name] = payload
                del working[old_name]
                for date_entries in self.entries.values():
                    if old_name in date_entries:
                        date_entries[new_name] = date_entries.pop(old_name)
            else:
                working[old_name] = payload
            return new_name

        def save_category() -> None:
            saved_name = apply_editor()
            if saved_name:
                refresh_list(saved_name)

        def add_category() -> None:
            name = simpledialog.askstring("New category", "Category name:", parent=editor)
            if not name:
                return
            name = name.strip()
            if not name:
                return
            if name in working:
                messagebox.showerror("Duplicate", "That category already exists.")
                return
            working[name] = {"checklist": ["New checklist item"], "metrics": []}
            refresh_list(name)

        def delete_category() -> None:
            selection = category_list.curselection()
            if not selection:
                return
            name = category_list.get(selection[0])
            if not messagebox.askyesno("Delete category", f"Delete '{name}' from settings?"):
                return
            del working[name]
            refresh_list()

        def save_all() -> None:
            saved_name = apply_editor()
            if category_list.curselection() and saved_name is None:
                return
            self.categories = working
            self.save_data()
            editor.destroy()
            messagebox.showinfo("Saved", "Categories updated.")
            self.create_dashboard()

        def reset_defaults() -> None:
            if not messagebox.askyesno("Reset", "Restore all default categories? Custom names will be kept only if not conflicting."):
                return
            working.clear()
            working.update(self.get_default_categories())
            refresh_list(next(iter(working.keys())))

        category_list.bind("<<ListboxSelect>>", load_selected)

        buttons = ttk.Frame(editor)
        buttons.pack(fill=tk.X, padx=12, pady=(0, 12))
        ttk.Button(buttons, text="Add Category", command=add_category).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Delete Category", command=delete_category).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Save Category", command=save_category).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Reset Defaults", command=reset_defaults).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Save & Close", command=save_all).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Cancel", command=editor.destroy).pack(side=tk.RIGHT, padx=8)

        refresh_list(next(iter(working.keys())))


def main() -> None:
    root = tk.Tk()
    app = PersonalDevelopmentTracker(root)
    if root.winfo_exists():
        root.mainloop()


if __name__ == "__main__":
    main()

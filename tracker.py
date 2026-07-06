import tkinter as tk
from datetime import datetime
from tkinter import messagebox, scrolledtext, simpledialog, ttk

import charts
import fitness_ui
import history
import profiles
import storage
import streak
import summaries
import ui_theme

CATEGORY_SHORT_LABELS = {
    "Money/Freedom": "Money",
    "Body & Presence": "Body",
    "Burnout Prevention & Energy Management": "Energy",
    "Creative/Mental Work": "Creative",
    "Family/Logistics": "Family",
    "Search Practice": "Search",
    "Spiritual Development": "Spiritual",
    "Emotional Wellbeing": "Emotional",
}


class PersonalDevelopmentTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("Personal Development Tracker")
        self.root.geometry("1200x800")
        ui_theme.apply_theme(self.root)
        self.reload_profile_data()
        self.create_dashboard()

    def reload_profile_data(self):
        profiles.ensure_app_structure()
        self.active_profile = profiles.get_active_profile()
        self.data = storage.load()
        self.categories = self.data["categories"]
        self.entries = self.data["entries"]

    def save_data(self):
        storage.save(self.data)

    def get_streak(self, category=None):
        return streak.get_streak(self.entries, category)

    def today_str(self):
        return datetime.now().strftime("%Y-%m-%d")

    def count_today_logged(self) -> tuple[int, int]:
        logged = len(self.entries.get(self.today_str(), {}))
        return logged, len(self.categories)

    def first_unlogged_category(self) -> str | None:
        today_entries = self.entries.get(self.today_str(), {})
        for cat_name in self.categories:
            if cat_name not in today_entries:
                return cat_name
        return None

    def create_todays_log_bar(self):
        logged_count, total = self.count_today_logged()
        today_entries = self.entries.get(self.today_str(), {})

        log_bar = ttk.LabelFrame(self.root, text="Today's Log", padding=14, style="Card.TLabelframe")
        log_bar.pack(fill=tk.X, padx=16, pady=(0, 10))

        top = ttk.Frame(log_bar, style="Surface.TFrame")
        top.pack(fill=tk.X)
        left = ttk.Frame(top, style="Surface.TFrame")
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(
            left,
            text=f"{logged_count} of {total} life areas logged",
            style="OnSurfaceSubheading.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            left,
            text="Log as you go, or reflect at end of day — pick any area below.",
            style="OnSurfaceMuted.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        progress_row = ttk.Frame(log_bar, style="Surface.TFrame")
        progress_row.pack(fill=tk.X, pady=(8, 0))
        progress = ttk.Progressbar(
            progress_row,
            orient=tk.HORIZONTAL,
            mode="determinate",
            maximum=max(total, 1),
            value=logged_count,
        )
        progress.pack(fill=tk.X)

        actions = ttk.Frame(top, style="Surface.TFrame")
        actions.pack(side=tk.RIGHT)
        next_cat = self.first_unlogged_category()
        if next_cat:
            ttk.Button(
                actions,
                text=f"Continue → {CATEGORY_SHORT_LABELS.get(next_cat, next_cat)}",
                style="Accent.TButton",
                command=lambda: self.open_log_dialog(next_cat),
            ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Log Fitness Workout", command=self.show_fitness).pack(side=tk.LEFT)

        btn_row = ttk.Frame(log_bar, style="Surface.TFrame")
        btn_row.pack(fill=tk.X, pady=(12, 0))
        for index, cat_name in enumerate(self.categories):
            short = CATEGORY_SHORT_LABELS.get(cat_name, cat_name)
            is_logged = cat_name in today_entries
            rating = today_entries.get(cat_name, {}).get("rating", "")
            label = f"✓ {short} ({rating}/10)" if is_logged else f"Log {short}"
            btn_style = "Logged.TButton" if is_logged else "TButton"
            ttk.Button(
                btn_row,
                text=label,
                style=btn_style,
                command=lambda c=cat_name: self.open_log_dialog(c),
            ).grid(row=index // 4, column=index % 4, padx=4, pady=4, sticky="ew")
        for col in range(4):
            btn_row.columnconfigure(col, weight=1)

    def create_dashboard(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=16, pady=(16, 10))

        title_block = ttk.Frame(header)
        title_block.pack(side=tk.LEFT)
        ttk.Label(title_block, text="Personal Development Tracker", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_block,
            text="Daily reflection across eight life areas",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        right_header = ttk.Frame(header)
        right_header.pack(side=tk.RIGHT)

        profile_frame = ttk.Frame(right_header)
        profile_frame.pack(side=tk.TOP, anchor="e", pady=(0, 6))
        self.profile_var = tk.StringVar(value=self.active_profile["name"])
        profile_combo = ttk.Combobox(
            profile_frame,
            textvariable=self.profile_var,
            values=[p["name"] for p in profiles.list_profiles()],
            state="readonly",
            width=18,
        )
        profile_combo.pack(side=tk.LEFT)
        profile_combo.bind("<<ComboboxSelected>>", self.on_profile_selected)
        ttk.Button(profile_frame, text="New Profile", command=self.create_profile).pack(
            side=tk.LEFT, padx=6
        )

        meta_row = ttk.Frame(right_header)
        meta_row.pack(side=tk.TOP, anchor="e")
        ui_theme.streak_badge(meta_row, f"🔥 {self.get_streak()} day streak").pack(side=tk.RIGHT, padx=(12, 0))
        ttk.Label(
            meta_row,
            text=f"Today · {datetime.now().strftime('%B %d, %Y')}",
            style="Muted.TLabel",
        ).pack(side=tk.RIGHT)

        self.create_todays_log_bar()

        import ui_scroll

        scroll_outer, scroll_inner, _canvas = ui_scroll.make_scrollable_frame(self.root)
        scroll_outer.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 4))

        main = ttk.Frame(scroll_inner)
        main.pack(fill=tk.BOTH, expand=True)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(1, weight=1)

        rec_frame = ttk.LabelFrame(main, text="What's Next", padding=12, style="Card.TLabelframe")
        rec_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 10))
        import recommendations
        from progression.db import FitnessRepository

        repo = FitnessRepository()
        repo.initialize()
        recs = recommendations.build_recommendations(self.entries, self.categories, repo)
        for rec in recs[:5]:
            ttk.Label(rec_frame, text=f"• {rec}", wraplength=1050, style="OnSurfaceMuted.TLabel").pack(
                anchor="w", pady=1
            )

        cats_frame = ttk.LabelFrame(
            main, text="Life Areas — Details & Streaks", padding=10, style="Card.TLabelframe"
        )
        cats_frame.grid(row=1, column=0, sticky="nsew")
        cats_frame.columnconfigure((0, 1), weight=1)

        row = 0
        col = 0
        for cat_name in self.categories:
            card = self.create_category_card(cats_frame, cat_name)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            col += 1
            if col > 1:
                col = 0
                row += 1

        activity_frame = ttk.LabelFrame(main, text="Recent Activity", padding=10, style="Card.TLabelframe")
        activity_frame.grid(row=1, column=1, sticky="nsew", padx=(12, 0), pady=8)
        activity_text = scrolledtext.ScrolledText(
            activity_frame,
            wrap=tk.WORD,
            width=34,
            height=24,
            borderwidth=0,
        )
        activity_text.pack(fill=tk.BOTH, expand=True)
        ui_theme.style_text_widget(activity_text)
        activity_text.insert(tk.END, history.format_recent_activity(self.entries))
        activity_text.configure(state=tk.DISABLED)

        footer = ttk.Frame(self.root)
        footer.pack(fill=tk.X, padx=16, pady=(4, 12))
        ttk.Separator(footer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
        nav = ttk.Frame(footer)
        nav.pack(fill=tk.X)
        ttk.Button(nav, text="Refresh", command=self.create_dashboard).pack(side=tk.LEFT)
        ttk.Button(nav, text="View Full History", command=self.show_history).pack(side=tk.LEFT, padx=8)
        ttk.Button(nav, text="Graphs & Summaries", command=self.show_graphs_and_summaries).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(nav, text="Fitness Progress", style="Accent.TButton", command=self.show_fitness).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(nav, text="Settings", command=self.show_settings).pack(side=tk.LEFT)

    def create_category_card(self, parent, cat_name):
        outer, inner = ui_theme.make_card(parent, accent=ui_theme.category_accent(cat_name))
        surface = ui_theme.color("surface")
        tk.Label(
            inner,
            text=cat_name,
            font=ui_theme.font("subheading"),
            bg=surface,
            fg=ui_theme.color("text"),
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            inner,
            text=f"Streak: {self.get_streak(cat_name)} days",
            font=ui_theme.font("body"),
            bg=surface,
            fg=ui_theme.color("text_muted"),
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 0))

        today_str = datetime.now().strftime("%Y-%m-%d")
        today_entry = self.entries.get(today_str, {}).get(cat_name, {})
        if today_entry:
            status = f"Today's rating: {today_entry.get('rating', '?')}/10"
            status_fg = ui_theme.color("success")
        else:
            status = "Not logged today"
            status_fg = ui_theme.color("text_muted")
        tk.Label(
            inner,
            text=status,
            font=ui_theme.font("body_bold"),
            bg=surface,
            fg=status_fg,
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 0))

        ttk.Button(
            inner,
            text="Log / Update Today",
            style="Accent.TButton" if not today_entry else "TButton",
            command=lambda: self.open_log_dialog(cat_name),
        ).pack(fill=tk.X, pady=(10, 0))
        return outer

    def open_log_dialog(self, cat_name):
        import ui_scroll

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Log: {cat_name}")
        dialog.geometry("540x720")
        dialog.transient(self.root)
        dialog.grab_set()
        ui_theme.configure_window(dialog)

        outer, inner, _canvas = ui_scroll.make_scrollable_frame(dialog)
        outer.pack(fill=tk.BOTH, expand=True)

        cat_data = self.categories[cat_name]
        today_str = datetime.now().strftime("%Y-%m-%d")
        existing = self.entries.get(today_str, {}).get(cat_name, {})

        ttk.Label(inner, text=f"Date: {today_str}", style="Subheading.TLabel").pack(pady=8)
        ttk.Label(
            inner,
            text="Capture what you're doing now, or reflect on your day in the notes below.",
            wraplength=480,
            style="Muted.TLabel",
        ).pack(padx=15, pady=(0, 6))

        rating_var = tk.IntVar(value=existing.get("rating", 5))
        ttk.Label(inner, text="Overall Progress Rating (1-10)").pack(anchor="w", padx=15)
        ttk.Spinbox(
            inner, from_=1, to=10, textvariable=rating_var, width=6, font=("Helvetica", 14)
        ).pack(pady=5)

        ttk.Label(inner, text="Checklist").pack(anchor="w", padx=15, pady=(10, 0))
        check_vars = {}
        for item in cat_data["checklist"]:
            var = tk.BooleanVar(value=existing.get("checklist", {}).get(item, False))
            check_vars[item] = var
            ttk.Checkbutton(inner, text=item, variable=var).pack(anchor="w", padx=25)

        ttk.Label(inner, text="Specific Measures").pack(anchor="w", padx=15, pady=(10, 0))
        metric_vars = {}
        for metric in cat_data["metrics"]:
            m_name = metric["name"]
            row = ttk.Frame(inner)
            row.pack(fill=tk.X, padx=15, pady=3)
            ttk.Label(row, text=f"{m_name}:").pack(side=tk.LEFT)
            if metric.get("type") == "number":
                var = tk.DoubleVar(
                    value=existing.get("metrics", {}).get(m_name, metric.get("default", 0))
                )
                ttk.Entry(row, textvariable=var, width=12).pack(side=tk.LEFT, padx=6)
            else:
                var = tk.IntVar(
                    value=existing.get("metrics", {}).get(m_name, metric.get("default", 5))
                )
                ttk.Spinbox(row, from_=1, to=10, textvariable=var, width=6).pack(
                    side=tk.LEFT, padx=6
                )
            metric_vars[m_name] = var

        ttk.Label(inner, text="Notes / Journal (stream of consciousness or end-of-day reflection)").pack(
            anchor="w", padx=15, pady=(10, 0)
        )
        notes_text = scrolledtext.ScrolledText(inner, height=10, borderwidth=0)
        notes_text.pack(padx=15, pady=5, fill=tk.BOTH, expand=True)
        ui_theme.style_text_widget(notes_text)
        if existing.get("notes"):
            notes_text.insert("1.0", existing["notes"])

        btns = ttk.Frame(inner)
        btns.pack(pady=15)
        ttk.Button(
            btns,
            text="Save",
            style="Accent.TButton",
            command=lambda: self.save_log(
                dialog, cat_name, today_str, rating_var, check_vars, metric_vars, notes_text
            ),
        ).pack(side=tk.LEFT, padx=10)
        ttk.Button(btns, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)

    def save_log(
        self, dialog, cat_name, date_str, rating_var, check_vars, metric_vars, notes_text
    ):
        if date_str not in self.entries:
            self.entries[date_str] = {}
        self.entries[date_str][cat_name] = {
            "rating": rating_var.get(),
            "checklist": {item: var.get() for item, var in check_vars.items()},
            "metrics": {name: var.get() for name, var in metric_vars.items()},
            "notes": notes_text.get("1.0", tk.END).strip(),
        }
        self.data["entries"] = self.entries
        self.save_data()
        dialog.destroy()
        messagebox.showinfo("Saved", f"Logged for {cat_name}")
        self.create_dashboard()

    def show_graphs_and_summaries(self):
        win = tk.Toplevel(self.root)
        win.title("Graphs & Summaries")
        win.geometry("1100x750")
        ui_theme.configure_window(win)

        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        summary_tab = ttk.Frame(notebook)
        notebook.add(summary_tab, text="Summaries")
        txt = scrolledtext.ScrolledText(summary_tab, wrap=tk.WORD, borderwidth=0)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ui_theme.style_text_widget(txt)
        txt.insert(tk.END, summaries.build_summary_text(self.entries))

        graphs_tab = ttk.Frame(notebook)
        notebook.add(graphs_tab, text="Graphs")
        charts.embed_figure(graphs_tab, charts.build_daily_avg_figure(self.entries))
        charts.embed_figure(
            graphs_tab, charts.build_category_avg_figure(self.entries, self.categories)
        )

        radar_tab = ttk.Frame(notebook)
        notebook.add(radar_tab, text="Life Balance")
        charts.embed_figure(
            radar_tab, charts.build_life_balance_figure(self.entries, self.categories)
        )

    def show_history(self):
        win = tk.Toplevel(self.root)
        win.title("Full History")
        win.geometry("800x600")
        ui_theme.configure_window(win)
        txt = scrolledtext.ScrolledText(win, wrap=tk.WORD, borderwidth=0)
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        ui_theme.style_text_widget(txt)
        txt.insert(tk.END, history.format_history(self.entries))

    def show_fitness(self):
        fitness_ui.show_fitness_window(self.root)

    def on_profile_selected(self, _event=None):
        selected_name = self.profile_var.get()
        selected = next(
            (p for p in profiles.list_profiles() if p["name"] == selected_name),
            None,
        )
        if selected is None or selected["id"] == self.active_profile["id"]:
            return
        profiles.set_active_profile(selected["id"])
        self.reload_profile_data()
        self.create_dashboard()

    def create_profile(self):
        name = simpledialog.askstring("New Profile", "Profile name:")
        if not name or not name.strip():
            return
        try:
            profile = profiles.create_profile(name.strip())
        except ValueError as exc:
            messagebox.showerror("Profile Error", str(exc))
            return
        profiles.set_active_profile(profile["id"])
        self.reload_profile_data()
        self.create_dashboard()
        messagebox.showinfo("Profile Created", f"Switched to profile: {profile['name']}")

    def show_settings(self):
        import backup

        win = tk.Toplevel(self.root)
        win.title("Settings & Backup")
        win.geometry("520x360")
        win.transient(self.root)
        ui_theme.configure_window(win)

        frame = ttk.Frame(win, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Settings & Backup", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text=f"Active profile: {self.active_profile['name']}\n"
            f"Daily data: {storage.get_data_path()}\n"
            f"Fitness DB: {profiles.get_profile_dir()}/fitness.db",
            wraplength=460,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(8, 12))

        backup_box = ttk.LabelFrame(frame, text="Export / Import", padding=12)
        backup_box.pack(fill=tk.X, pady=(0, 12))
        ttk.Label(
            backup_box,
            text="Backups are zip files with config.json, data.json, and fitness.db per profile.",
            wraplength=420,
        ).pack(anchor="w", pady=(0, 8))

        btn_row = ttk.Frame(backup_box)
        btn_row.pack(fill=tk.X)

        def export_active():
            from tkinter import filedialog

            path = filedialog.asksaveasfilename(
                parent=win,
                title="Export Profile Backup",
                defaultextension=".zip",
                filetypes=[("Backup zip", "*.zip")],
                initialfile=f"{self.active_profile['id']}-backup.zip",
            )
            if not path:
                return
            backup.export_backup(path, profile_id=self.active_profile["id"])
            messagebox.showinfo("Exported", f"Profile backup saved:\n{path}")

        def export_all():
            from tkinter import filedialog

            path = filedialog.asksaveasfilename(
                parent=win,
                title="Export Full Backup",
                defaultextension=".zip",
                filetypes=[("Backup zip", "*.zip")],
                initialfile="personal-dev-tracker-backup.zip",
            )
            if not path:
                return
            backup.export_backup(path)
            messagebox.showinfo("Exported", f"Full backup saved:\n{path}")

        def import_backup_file():
            from tkinter import filedialog

            path = filedialog.askopenfilename(
                parent=win,
                title="Import Backup",
                filetypes=[("Backup zip", "*.zip")],
            )
            if not path:
                return
            try:
                summary = backup.list_backup_contents(path)
                backup.import_backup(path, merge_profiles=True)
            except ValueError as exc:
                messagebox.showerror("Import Failed", str(exc))
                return
            self.reload_profile_data()
            self.create_dashboard()
            profiles_list = ", ".join(summary["manifest"].get("profiles", []))
            messagebox.showinfo("Imported", f"Restored profiles: {profiles_list}")

        ttk.Button(btn_row, text="Export This Profile", command=export_active).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Export All Profiles", command=export_all).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_row, text="Import Backup", command=import_backup_file).pack(side=tk.LEFT)

        ttk.Button(frame, text="Close", command=win.destroy).pack(anchor="e", pady=(8, 0))


def main():
    root = tk.Tk()
    PersonalDevelopmentTracker(root)
    root.mainloop()


if __name__ == "__main__":
    main()

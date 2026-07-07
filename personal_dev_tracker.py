"""Personal Development Tracker — daily notes, checklists, metrics, charts, and settings."""

from __future__ import annotations

import json
import os
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, scrolledtext, simpledialog, ttk

from activity_grid import ContributionGrid
import day_plans
from day_plans_ui import show_plan_comparison_window, show_plan_window
from day_watch import DayWatch
from graphs import open_graphs
from fitness.engine import compute_program_state, load_program_definitions, migrate_data
from fitness.intelligence import get_fitness_settings, weekly_fitness_summary
from insights.engine import analyze_all, category_insight, format_guidance_report, format_insight_line, top_insights
from integral_dialogs import (
    prompt_vault_unlock,
    show_backup_dialog,
    show_export_dialog,
    show_milestones_dialog,
    show_onboarding,
    show_security_dialog,
)
import journal
from journal_ui import show_journal_window
from milestones import merge_milestones, milestone_summary
from notifications import ReminderScheduler, normalize_notification_settings
from paths import APP_NAME, APP_VERSION, data_file, ensure_data_file, icon_path
import streak
from theme import (
    FONTS,
    apply_theme,
    category_accent,
    get_theme,
    make_card,
    streak_badge,
    style_canvas,
    style_listbox,
    style_text_widget,
)
import ui_scroll
from vault import is_encrypted_file, load_data_file, save_data_file

CATEGORY_SHORT_LABELS = {
    "Money/Freedom": "Money",
    "Career & Vocation": "Career",
    "Body & Presence": "Body",
    "Burnout Prevention & Energy Management": "Energy",
    "Creative/Mental Work": "Creative",
    "Learning & Intellectual Growth": "Learning",
    "Family/Logistics": "Family",
    "Relationships & Social Connection": "Relationships",
    "Home & Environment": "Home",
    "Search Practice": "Search",
    "Spiritual Development": "Spiritual",
    "Emotional Wellbeing": "Emotional",
    "Community & Service": "Community",
    "Cultural Life & Heritage": "Culture",
    "What You Have Eaten": "Food",
    "Art You Have Consumed": "Art",
    "General Reading": "Reading",
    "Content You Have Consumed": "Content",
}


DATA_FILE = data_file()


class PersonalDevelopmentTracker:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)
        self._apply_window_icon()

        self.categories: dict = {}
        self.entries: dict = {}
        self.settings: dict = {"dark_mode": False}
        self.sessions: list = []
        self.milestones: list = []
        self.journal: dict = journal.empty_journal()
        self.day_plans: dict = day_plans.empty_day_plans()
        self.program_state: dict = {}
        self.programs: dict = load_program_definitions()
        self.data_path = DATA_FILE
        self.vault_passphrase: str | None = None
        self.theme = get_theme(False)
        self._mousewheel_binding: str | None = None
        self._insights_cache = None
        self._streak_cache: dict[str, int] = {}
        self._save_after_id: str | None = None
        self._pending_save_payload: dict | None = None
        self._fitness_state_dirty = False
        self._dashboard_ready = False
        self._categories_tab_built = False
        self._theme_dark: bool | None = None
        self._log_bar: ttk.LabelFrame | None = None
        self._activity_grid: ContributionGrid | None = None
        self._guidance_panel: ttk.LabelFrame | None = None
        self._streak_pill: tk.Label | None = None
        self._date_label: ttk.Label | None = None
        self._overview_stats_label: ttk.Label | None = None
        self._reminder_scheduler: ReminderScheduler | None = None
        self._day_watch: DayWatch | None = None
        self._categories_tab_frame: ttk.Frame | None = None
        self._notebook: ttk.Notebook | None = None

        if is_encrypted_file(DATA_FILE) and not prompt_vault_unlock(self):
            messagebox.showerror("Locked", "Cannot open encrypted journal without passphrase.")
            root.destroy()
            return

        self.load_data()
        self.apply_current_theme()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.create_dashboard()
        self._start_day_watch()
        self._start_reminder_scheduler()
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
            # --- Financial & vocational ---
            "Money/Freedom": {
                "checklist": [
                    "Tracked spending, income, or accounts",
                    "Took action toward financial freedom",
                    "Reviewed budget, debt, or long-term money goals",
                    "Saved, invested, or moved money intentionally",
                    "Practiced generosity or aligned spending with values",
                ],
                "metrics": [
                    {"name": "Money actions taken", "type": "number", "unit": "", "default": 0},
                    {"name": "Savings/Income logged", "type": "number", "unit": "$", "default": 0},
                    {"name": "Financial clarity rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Freedom mindset rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Career & Vocation": {
                "checklist": [
                    "Meaningful work or professional effort",
                    "Skill-building for career or calling",
                    "Networking, mentoring, or professional relationship",
                    "Aligned work with values — noted honestly if not",
                    "Rested or set boundaries around work",
                ],
                "metrics": [
                    {"name": "Focused work hours", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Career satisfaction", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Progress toward professional goals", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            # --- Physical ---
            "Body & Presence": {
                "checklist": [
                    "Completed movement or exercise",
                    "Mobility, stretching, or joint care",
                    "Practiced mindfulness or embodied presence",
                    "Prioritized sleep or recovery",
                    "Hydration and basic physical self-care",
                    "Addressed pain, injury, or medical need",
                ],
                "metrics": [
                    {"name": "Sleep hours last night", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Movement / exercise time", "type": "number", "unit": "min", "default": 0},
                    {"name": "Energy level", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Physical comfort (pain-free)", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Presence rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Burnout Prevention & Energy Management": {
                "checklist": [
                    "Took intentional breaks",
                    "Respected personal boundaries",
                    "Did a self-care or restoration activity",
                    "Limited doomscrolling or reactive screen time",
                    "Time in nature or away from screens",
                ],
                "metrics": [
                    {"name": "Morning energy", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Stress level (lower = better)", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Recovery / rest quality", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            # --- Mental & creative ---
            "Creative/Mental Work": {
                "checklist": [
                    "Had a focused or deep work session",
                    "Captured ideas, notes, or insights",
                    "Made progress on a creative project",
                    "Shipped, shared, or finished something small",
                    "Solved a problem or made a decision",
                ],
                "metrics": [
                    {"name": "Deep work hours", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Focus rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Creativity / output rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Learning & Intellectual Growth": {
                "checklist": [
                    "Studied or practiced a skill",
                    "Language, instrument, or craft practice",
                    "Course, lecture, or structured lesson",
                    "Applied something new you learned",
                    "Curiosity followed — rabbit hole logged honestly",
                ],
                "metrics": [
                    {"name": "Learning time", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Mental clarity", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Growth / stretch rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            # --- Relational & domestic ---
            "Family/Logistics": {
                "checklist": [
                    "Quality time with family or household",
                    "Handled key logistics, errands, or admin",
                    "Communicated openly with household",
                    "Supported someone who depends on you",
                    "Household systems maintained (meals, bills, schedule)",
                ],
                "metrics": [
                    {"name": "Family / household time", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Connection quality", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Logistics completion", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Relationships & Social Connection": {
                "checklist": [
                    "Reached out to a friend or loved one",
                    "Meaningful conversation (not only logistics)",
                    "Partner / romance / intimacy (if applicable)",
                    "Social time — in person or intentional call",
                    "Set or respected a social boundary",
                ],
                "metrics": [
                    {"name": "Social connection time", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Belonging / connection rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Loneliness (lower = better)", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Home & Environment": {
                "checklist": [
                    "Tidied, organized, or improved living space",
                    "Time outdoors or in nature",
                    "Sustainable or intentional consumption choice",
                    "Made home more comfortable or functional",
                    "Noticed and logged environment's effect on mood",
                ],
                "metrics": [
                    {"name": "Time in nature", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Home / space satisfaction", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Environment supported wellbeing", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            # --- Inner life ---
            "Search Practice": {
                "checklist": [
                    "Engaged in search or inquiry practice",
                    "Journaled or reflected on search",
                    "Took a concrete search-related action",
                    "Sat with a question without forcing an answer",
                    "Noticed resistance, longing, or direction",
                ],
                "metrics": [
                    {"name": "Search effort rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Clarity or direction sense", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Insights or actions taken", "type": "number", "unit": "", "default": 0},
                ],
            },
            "Spiritual Development": {
                "checklist": [
                    "Daily spiritual practice (meditation, prayer, contemplation)",
                    "Read or reflected on spiritual teachings or wisdom",
                    "Gratitude, surrender, or sacred presence",
                    "Community, nature, or higher purpose felt",
                    "Ritual, ceremony, or tradition honored",
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
                    "Checked in with current emotions",
                    "Journaled or processed feelings",
                    "Self-compassion or emotional regulation",
                    "Expressed emotions constructively",
                    "Therapy, support, or nervous-system care",
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
            "Community & Service": {
                "checklist": [
                    "Helped someone without obligation",
                    "Volunteering, civic, or community participation",
                    "Donation, mutual aid, or generosity of time",
                    "Listened well or showed up for community",
                    "Contributed to something bigger than self",
                ],
                "metrics": [
                    {"name": "Service / giving time", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Sense of contribution", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Community belonging", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            # --- Cultural (active + consumed) ---
            "Cultural Life & Heritage": {
                "checklist": [
                    "Language or cultural skill practice",
                    "Festival, ceremony, or tradition participated in",
                    "Museum, heritage site, or cultural event",
                    "Explored cuisine, travel, or culture intentionally",
                    "Connected with ancestry, heritage, or identity",
                ],
                "metrics": [
                    {"name": "Cultural engagement time", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Cultural richness / aliveness", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Identity / roots connection", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "What You Have Eaten": {
                "checklist": [
                    "Logged what I ate (meals or key snacks)",
                    "Ate with awareness (not only on autopilot)",
                    "Choices mostly aligned with how I want to eat",
                    "Home cooking or intentional food prep",
                    "Shared a meal with others",
                ],
                "metrics": [
                    {"name": "Meals / snacks logged", "type": "number", "unit": "", "default": 0},
                    {"name": "Nourishment rating", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Energy after eating", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Art You Have Consumed": {
                "checklist": [
                    "Film, TV, or animation",
                    "Music (album, concert, deep listen)",
                    "Novels or literary fiction",
                    "Visual art, painting, or comics",
                    "Theatre, dance, or live performance",
                    "Video games (played with intention)",
                    "Architecture, design, or craft admired",
                ],
                "metrics": [
                    {"name": "Time with art", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "How much it moved me", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Would recommend to someone I care about", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "General Reading": {
                "checklist": [
                    "Nonfiction book",
                    "Reference, textbook, or manual",
                    "Memoir or biography",
                    "Audiobook (book-length)",
                    "Made meaningful progress — title in notes",
                    "Philosophy, history, or ideas read deeply",
                ],
                "metrics": [
                    {"name": "Reading time", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Pages or progress", "type": "number", "unit": "", "default": 0},
                    {"name": "What I retained or applied", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
            "Content You Have Consumed": {
                "checklist": [
                    "Articles, essays, or newsletters",
                    "Podcasts (episode or clip)",
                    "Learning videos, documentaries, or courses",
                    "Social or news (logged honestly — including doomscrolling)",
                    "Took away something useful or applied one idea",
                ],
                "metrics": [
                    {"name": "Content time", "type": "number", "unit": "hrs", "default": 0},
                    {"name": "Quality of attention", "type": "rating", "min": 1, "max": 10, "default": 5},
                    {"name": "Actual value received", "type": "rating", "min": 1, "max": 10, "default": 5},
                ],
            },
        }

    def apply_current_theme(self, *, force: bool = False) -> None:
        dark = bool(self.settings.get("dark_mode", False))
        if not force and self._theme_dark == dark:
            return
        self._theme_dark = dark
        self.theme = get_theme(dark)
        apply_theme(self.root, self.theme)

    def _invalidate_caches(self) -> None:
        self._insights_cache = None
        self._streak_cache.clear()

    def _get_insights(self):
        if self._insights_cache is None:
            self._insights_cache = analyze_all(
                self.entries,
                self.categories,
                sessions=self.sessions,
                program_state=self.program_state,
            )
        return self._insights_cache

    def _on_close(self) -> None:
        if self._reminder_scheduler is not None:
            self._reminder_scheduler.stop()
        if self._day_watch is not None:
            self._day_watch.stop()
        if self._save_after_id:
            self.root.after_cancel(self._save_after_id)
            self._save_after_id = None
        self._flush_save(sync=True)
        self.root.destroy()

    def _start_day_watch(self) -> None:
        self._day_watch = DayWatch(self.root, on_new_day=self._on_calendar_day_changed)

    def _start_reminder_scheduler(self) -> None:
        self.settings = normalize_notification_settings(self.settings)
        self._reminder_scheduler = ReminderScheduler(
            self.root,
            get_settings=lambda: self.settings,
            set_settings=self._apply_notification_settings,
            has_logged_today=lambda: bool(self.entries.get(self.today_str())),
            persist_settings=lambda: self.save_data(flush=True),
        )

    def _apply_notification_settings(self, settings: dict) -> None:
        self.settings = settings

    def _on_calendar_day_changed(self, previous_day, new_day) -> None:
        del previous_day, new_day
        if self._reminder_scheduler is not None:
            self._reminder_scheduler.reset_for_new_day()
        self.refresh_dashboard(full=True)

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
                continue

            cat = merged[name]
            checklist = list(cat.get("checklist", []))
            for item in definition.get("checklist", []):
                if item not in checklist:
                    checklist.append(item)
                    changed = True
            cat["checklist"] = checklist

            existing_metric_names = {
                metric.get("name")
                for metric in cat.get("metrics", [])
                if isinstance(metric, dict) and metric.get("name")
            }
            for metric in definition.get("metrics", []):
                if isinstance(metric, dict) and metric.get("name") not in existing_metric_names:
                    cat.setdefault("metrics", []).append(metric)
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
            self.settings = normalize_notification_settings(
                {**{"dark_mode": False}, **migrated.get("settings", {})}
            )
            self.settings["fitness"] = get_fitness_settings(self.settings)
            self.sessions = migrated.get("sessions", [])
            self.milestones = merge_milestones(migrated.get("milestones"))
            self.journal = journal.normalize_journal(migrated.get("journal"))
            self.day_plans = day_plans.normalize_day_plans(migrated.get("day_plans"))
            self.program_state = migrated.get("program_state", {})
        else:
            self.categories = self.get_default_categories()
            self.entries = {}
            self.settings = normalize_notification_settings(
                {"dark_mode": False, "onboarding_complete": False}
            )
            self.settings["fitness"] = get_fitness_settings(self.settings)
            self.sessions = []
            self.milestones = merge_milestones(None)
            self.journal = journal.empty_journal()
            self.day_plans = day_plans.empty_day_plans()
            self.program_state = compute_program_state(self.programs, self.sessions, self.settings)
            self.save_data(flush=True)

    def _payload(self, *, recompute_fitness: bool = False) -> dict:
        if recompute_fitness or self._fitness_state_dirty or not self.program_state:
            self.program_state = compute_program_state(self.programs, self.sessions, self.settings)
            self._fitness_state_dirty = False
        return {
            "schema_version": 2,
            "categories": self.categories,
            "entries": self.entries,
            "settings": self.settings,
            "sessions": self.sessions,
            "milestones": self.milestones,
            "journal": self.journal,
            "day_plans": self.day_plans,
            "program_state": self.program_state,
            "user_levels": {},
        }

    def save_data(
        self,
        categories: dict | None = None,
        *,
        recompute_fitness: bool = False,
        flush: bool = False,
    ) -> None:
        if categories is not None:
            self.categories = categories
        payload = self._payload(recompute_fitness=recompute_fitness)
        self._pending_save_payload = payload
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        if flush:
            if self._save_after_id:
                self.root.after_cancel(self._save_after_id)
                self._save_after_id = None
            self._flush_save(sync=True)
            return
        if self._save_after_id:
            self.root.after_cancel(self._save_after_id)
        self._save_after_id = self.root.after(250, lambda: self._flush_save(sync=False))

    def _flush_save(self, sync: bool = False) -> None:
        self._save_after_id = None
        payload = self._pending_save_payload
        if payload is None:
            return

        encrypted = bool(self.settings.get("encryption_enabled"))
        passphrase = self.vault_passphrase
        path = DATA_FILE

        def write() -> None:
            save_data_file(path, payload, encrypted=encrypted, passphrase=passphrase)

        if sync:
            write()
            return
        threading.Thread(target=write, daemon=True).start()

    def save_fitness_data(self) -> None:
        self._fitness_state_dirty = True
        self.save_data(recompute_fitness=True)

    def get_streak(self, category: str | None = None) -> int:
        cache_key = category or "__all__"
        if cache_key not in self._streak_cache:
            self._streak_cache[cache_key] = streak.get_streak(self.entries, category)
        return self._streak_cache[cache_key]

    def today_str(self) -> str:
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

    def create_todays_log_bar(self) -> None:
        logged_count, total = self.count_today_logged()
        today_entries = self.entries.get(self.today_str(), {})

        log_bar = ttk.LabelFrame(self.root, text="Today's Log", padding=14, style="Card.TLabelframe")
        self._log_bar = log_bar
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
        ttk.Button(
            actions, text="Journal", style="Accent.TButton", command=self.show_journal
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            actions, text="Plan Tomorrow", command=self.show_plan_tomorrow
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            actions, text="Fitness Hub", style="Accent.TButton", command=self.show_fitness_hub
        ).pack(side=tk.LEFT)

        today_plan = day_plans.plan_for_date(self.day_plans, self.today_str())
        if today_plan:
            comparison = day_plans.compare_plan_to_actual(
                today_plan,
                self.entries.get(self.today_str(), {}),
                all_categories=list(self.categories.keys()),
            )
            plan_row = ttk.Frame(log_bar, style="Surface.TFrame")
            plan_row.pack(fill=tk.X, pady=(10, 0))
            ttk.Label(
                plan_row,
                text=f"Today's plan: {comparison['summary']}",
                style="OnSurfaceMuted.TLabel",
                wraplength=760,
            ).pack(side=tk.LEFT, fill=tk.X, expand=True)
            ttk.Button(
                plan_row,
                text="Plan vs Actual",
                command=lambda: show_plan_comparison_window(self, self.today_str()),
            ).pack(side=tk.RIGHT)

        progress = ttk.Progressbar(
            log_bar,
            orient=tk.HORIZONTAL,
            mode="determinate",
            maximum=max(total, 1),
            value=logged_count,
        )
        progress.pack(fill=tk.X, pady=(10, 0))

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

    def refresh_dashboard(self, *, full: bool = False) -> None:
        if full or not self._dashboard_ready:
            self.create_dashboard()
            return

        self._invalidate_caches()
        self.insights = self._get_insights()

        if self._streak_pill is not None:
            self._streak_pill.config(text=f"🔥 {self.get_streak()} day streak")

        if self._date_label is not None:
            self._date_label.config(text=f"Today · {datetime.now().strftime('%B %d, %Y')}")

        if self._log_bar is not None:
            self._log_bar.destroy()
        self.create_todays_log_bar()

        if self._activity_grid is not None:
            self._refresh_activity_grid()

        if self._guidance_panel is not None:
            for child in self._guidance_panel.winfo_children():
                child.destroy()
            self._fill_guidance_panel(self._guidance_panel)

        if self._overview_stats_label is not None:
            today_str = self.today_str()
            logged_today = len(self.entries.get(today_str, {}))
            fitness_today = self._session_counts_for_date(today_str)
            stats_text = f"Today: {logged_today}/{len(self.categories)} life areas logged"
            if fitness_today:
                stats_text += f"  ·  {fitness_today} fitness session(s)"
            stats_text += f"  ·  {milestone_summary(self.milestones)}"
            self._overview_stats_label.config(text=stats_text)

        if self._categories_tab_built and self._categories_tab_frame is not None:
            for child in self._categories_tab_frame.winfo_children():
                child.destroy()
            self._categories_tab_built = False
            if self._notebook is not None and self._notebook.index("current") == 1:
                self._build_categories_tab(self._categories_tab_frame)
                self._categories_tab_built = True

    def _session_counts_for_date(self, date_str: str) -> int:
        return self._activity_session_counts().get(date_str, 0)

    def _activity_session_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for session in self.sessions:
            date_str = session.get("date")
            if date_str:
                counts[date_str] = counts.get(date_str, 0) + 1
        try:
            from fitness_ui import get_profile_repo

            for session in get_profile_repo().list_workout_sessions(limit=2000):
                counts[session.date] = counts.get(session.date, 0) + 1
        except Exception:
            pass
        return counts

    def _refresh_activity_grid(self) -> None:
        if self._activity_grid is None:
            return
        self._activity_grid.refresh_data(
            self.entries,
            self.journal,
            self.sessions,
            session_counts=self._activity_session_counts(),
        )

    def _on_notebook_tab_changed(self, event: tk.Event) -> None:
        notebook = event.widget
        if notebook.index("current") != 1 or self._categories_tab_built:
            return
        if self._categories_tab_frame is not None:
            self._build_categories_tab(self._categories_tab_frame)
            self._categories_tab_built = True

    def create_dashboard(self) -> None:
        self._dashboard_ready = False
        if self._mousewheel_binding:
            self.root.unbind_all(self._mousewheel_binding)
            self._mousewheel_binding = None

        for widget in self.root.winfo_children():
            widget.destroy()

        self.apply_current_theme(force=True)

        header = ttk.Frame(self.root)
        header.pack(fill=tk.X, padx=16, pady=(16, 10))

        title_block = ttk.Frame(header)
        title_block.pack(side=tk.LEFT)
        ttk.Label(title_block, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_block,
            text="Holistic life tracking across eighteen domains",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        right_header = ttk.Frame(header)
        right_header.pack(side=tk.RIGHT)
        streak_frame = streak_badge(right_header, self.theme, f"🔥 {self.get_streak()} day streak")
        streak_frame.pack(side=tk.RIGHT, padx=(12, 0))
        for child in streak_frame.winfo_children():
            if isinstance(child, tk.Label):
                self._streak_pill = child
                break
        self._date_label = ttk.Label(
            right_header,
            text=f"Today · {datetime.now().strftime('%B %d, %Y')}",
            style="Muted.TLabel",
        )
        self._date_label.pack(side=tk.RIGHT)

        self.create_todays_log_bar()

        self._invalidate_caches()
        self.insights = self._get_insights()

        notebook = ttk.Notebook(self.root)
        self._notebook = notebook
        notebook.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

        overview = ttk.Frame(notebook)
        categories_tab = ttk.Frame(notebook)
        self._categories_tab_frame = categories_tab
        self._categories_tab_built = False
        notebook.add(overview, text="Overview")
        notebook.add(categories_tab, text="Categories")
        notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)

        self._build_overview_tab(overview)

        footer = ttk.Frame(self.root)
        footer.pack(fill=tk.X, padx=16, pady=(4, 12))
        ttk.Separator(footer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
        nav = ttk.Frame(footer)
        nav.pack(fill=tk.X)
        ttk.Button(nav, text="Refresh", command=self.create_dashboard).pack(side=tk.LEFT)
        ttk.Button(nav, text="Guidance", command=self.show_guidance).pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Weekly Summary", command=self.show_weekly_summary).pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Full History", command=self.show_history).pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Search Notes", command=self.show_search).pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Graphs & Progress", command=self.show_graphs).pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Journal", style="Accent.TButton", command=self.show_journal).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(nav, text="Plan Tomorrow", command=self.show_plan_tomorrow).pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Fitness Hub", style="Accent.TButton", command=self.show_fitness_hub).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(nav, text="Milestones", command=self.show_milestones).pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Export", command=self.show_export).pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Backup", command=self.show_backup).pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Edit Categories", command=self.show_settings).pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Data & Security", command=self.show_security).pack(side=tk.LEFT, padx=6)
        mode_label = "Light Mode" if self.settings.get("dark_mode") else "Dark Mode"
        ttk.Button(nav, text=mode_label, command=self.toggle_dark_mode).pack(side=tk.RIGHT)
        self._dashboard_ready = True

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

        grid_panel = ttk.LabelFrame(main, text="Activity", padding=12, style="Card.TLabelframe")
        grid_panel.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        self._activity_grid = ContributionGrid(
            grid_panel,
            entries=self.entries,
            categories=self.categories,
            theme=self.theme,
            sessions=self.sessions,
            journal=self.journal,
            session_counts=self._activity_session_counts(),
            on_day_click=self.show_day_explorer,
        )
        self._activity_grid.pack(fill=tk.X)

        today_str = self.today_str()
        logged_today = len(self.entries.get(today_str, {}))
        fitness_today = self._session_counts_for_date(today_str)
        stats = ttk.Frame(main, padding=8)
        stats.grid(row=1, column=0, sticky="ew", padx=4)
        stats_text = f"Today: {logged_today}/{len(self.categories)} life areas logged"
        if fitness_today:
            stats_text += f"  ·  {fitness_today} fitness session(s)"
        stats_text += f"  ·  {milestone_summary(self.milestones)}"
        self._overview_stats_label = ttk.Label(
            stats,
            text=stats_text,
            style="Muted.TLabel",
        )
        self._overview_stats_label.pack(anchor="w")
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
        panel = ttk.LabelFrame(parent, text="Today's Guidance", padding=12, style="Card.TLabelframe")
        panel.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 8))
        self._guidance_panel = panel
        self._fill_guidance_panel(panel)

    def _fill_guidance_panel(self, panel: ttk.LabelFrame) -> None:
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

    def create_category_card(self, parent: ttk.Frame, cat_name: str, cat_data: dict) -> tk.Frame:
        outer, inner = make_card(parent, self.theme, accent=category_accent(cat_name))
        surface = self.theme["surface"]
        tk.Label(
            inner,
            text=cat_name,
            font=FONTS["subheading"],
            bg=surface,
            fg=self.theme["fg"],
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            inner,
            text=f"Streak: {self.get_streak(cat_name)} days",
            font=FONTS["body"],
            bg=surface,
            fg=self.theme["muted"],
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 0))

        today_str = datetime.now().strftime("%Y-%m-%d")
        today_entry = self.entries.get(today_str, {}).get(cat_name, {})
        if today_entry:
            rating = today_entry.get("rating", "?")
            status = f"Today's rating: {rating}/10"
            status_fg = self.theme["success"]
        else:
            status = "Not logged today"
            status_fg = self.theme["muted"]
        tk.Label(
            inner,
            text=status,
            font=FONTS["body_bold"],
            bg=surface,
            fg=status_fg,
            anchor="w",
        ).pack(fill=tk.X, pady=(4, 0))

        hint = category_insight(self.insights, cat_name)
        if hint:
            hint_fg = self.theme["accent"] if hint.severity == "action" else self.theme["muted"]
            tk.Label(
                inner,
                text=hint.title,
                font=FONTS["body"],
                bg=surface,
                fg=hint_fg,
                wraplength=320,
                anchor="w",
            ).pack(fill=tk.X, pady=(4, 0))

        ttk.Button(
            inner,
            text="Log / Update Today",
            style="Accent.TButton" if not today_entry else "TButton",
            command=lambda name=cat_name: self.open_log_dialog(name),
        ).pack(fill=tk.X, pady=(10, 0))

        notes = today_entry.get("notes", "")
        if notes:
            preview = notes[:70] + "..." if len(notes) > 70 else notes
            tk.Label(
                inner,
                text=f"Note: {preview}",
                font=FONTS["small"],
                bg=surface,
                fg=self.theme["muted"],
                wraplength=320,
                anchor="w",
            ).pack(fill=tk.X, pady=(6, 0))

        return outer

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
        day_journal = journal.entries_for_day(self.journal, datetime.strptime(date_str, "%Y-%m-%d").date())
        ttk.Label(
            header,
            text=f"{len(day_entries)} areas  ·  {len(day_journal)} journal  ·  {len(day_fitness)} fitness",
            style="Muted.TLabel",
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
        day_plan = day_plans.plan_for_date(self.day_plans, date_str)
        if day_plan:
            comparison = day_plans.compare_plan_to_actual(
                day_plan,
                day_entries,
                all_categories=list(self.categories.keys()),
            )
            plan_card = ttk.LabelFrame(scroll_frame, text="Plan for this day", padding=10)
            plan_card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
            scroll_frame.columnconfigure(0, weight=1)
            ttk.Label(plan_card, text=comparison["summary"], wraplength=620).pack(anchor="w")
            if day_plan.get("day_intention"):
                ttk.Label(
                    plan_card,
                    text=f"Intention: {day_plan['day_intention']}",
                    wraplength=620,
                ).pack(anchor="w", pady=(6, 0))
            if day_plan.get("fitness_note"):
                ttk.Label(
                    plan_card,
                    text=f"Fitness: {day_plan['fitness_note']}",
                    wraplength=620,
                ).pack(anchor="w", pady=(4, 0))
            ttk.Button(
                plan_card,
                text="Plan vs Actual",
                command=lambda: show_plan_comparison_window(self, date_str),
            ).pack(anchor="w", pady=(8, 0))
            row += 1

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

        if day_journal:
            ttk.Label(scroll_frame, text="Journal", style="Subheading.TLabel").grid(
                row=row, column=0, sticky="w", pady=(12, 4)
            )
            row += 1
            for item in day_journal:
                card = ttk.LabelFrame(scroll_frame, text=item.get("title") or item.get("prompt") or "Entry", padding=8)
                card.grid(row=row, column=0, sticky="ew", pady=4)
                scroll_frame.columnconfigure(0, weight=1)
                preview = item.get("body", "")
                if len(preview) > 240:
                    preview = preview[:240] + "..."
                ttk.Label(card, text=preview, wraplength=620).pack(anchor="w")
                if item.get("backdate_reason"):
                    ttk.Label(
                        card,
                        text=f"Backdated: {item['backdate_reason']}",
                        style="Muted.TLabel",
                        wraplength=620,
                    ).pack(anchor="w", pady=(4, 0))
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
            ttk.Label(scroll_frame, text="Not logged this day", style="Subheading.TLabel").grid(
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

        journal_row = ttk.Frame(scroll_frame)
        journal_row.grid(row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Button(journal_row, text="+ Journal entry for this day", command=lambda: show_journal_window(self, date_str)).pack(side=tk.LEFT)

        footer = ttk.Frame(window)
        footer.pack(fill=tk.X, padx=15, pady=(0, 12))
        ttk.Button(footer, text="Close", command=window.destroy).pack(side=tk.RIGHT)

    def _open_log_and_close(self, parent_window: tk.Toplevel, cat_name: str, date_str: str) -> None:
        parent_window.destroy()
        self.open_log_dialog(cat_name, date_str=date_str)

    def open_log_dialog(self, cat_name: str, date_str: str | None = None) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Log: {cat_name}")
        dialog.geometry("600x720")
        dialog.minsize(520, 480)
        dialog.configure(bg=self.theme["bg"])
        dialog.transient(self.root)
        dialog.grab_set()

        cat_data = self.categories[cat_name]
        today = datetime.now().strftime("%Y-%m-%d")
        date_var = tk.StringVar(value=date_str or today)
        backdate_var = tk.StringVar(value="")
        rating_var = tk.IntVar(value=5)
        check_vars: dict[str, tk.BooleanVar] = {}
        metric_vars: dict[str, tk.Variable] = {}

        footer = ttk.Frame(dialog, padding=(15, 12))
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Separator(footer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
        footer_btns = ttk.Frame(footer)
        footer_btns.pack(fill=tk.X)

        outer, inner, _canvas = ui_scroll.make_scrollable_frame(dialog)
        outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        notes_text = scrolledtext.ScrolledText(inner, height=10, width=62, wrap=tk.WORD, font=("Helvetica", 11))
        style_text_widget(notes_text, self.theme)

        existing_holder: dict[str, dict] = {"entry": {}}

        def load_existing(*_args: object) -> None:
            current_date = date_var.get().strip()
            existing_holder["entry"] = self.entries.get(current_date, {}).get(cat_name, {})
            existing = existing_holder["entry"]
            rating_var.set(existing.get("rating", 5))
            for item, var in check_vars.items():
                var.set(existing.get("checklist", {}).get(item, False))
            for name, var in metric_vars.items():
                metric_def = next((m for m in cat_data["metrics"] if m["name"] == name), None)
                default = metric_def.get("default", 0) if metric_def else 0
                try:
                    var.set(existing.get("metrics", {}).get(name, default))
                except tk.TclError:
                    pass
            notes_text.delete("1.0", tk.END)
            if existing.get("notes"):
                notes_text.insert("1.0", existing["notes"])
            backdate_var.set(existing.get("backdate_reason", "") or "")
            refresh_backdate_ui()

        ttk.Label(inner, text="Entry date (YYYY-MM-DD)", style="Subheading.TLabel").pack(anchor="w", padx=15, pady=(8, 0))
        date_row = ttk.Frame(inner)
        date_row.pack(fill=tk.X, padx=15, pady=4)
        ttk.Entry(date_row, textvariable=date_var, width=14).pack(side=tk.LEFT)

        backdate_frame = ttk.Frame(inner)
        backdate_frame.pack(fill=tk.X, padx=15, pady=(0, 6))
        backdate_label = ttk.Label(
            backdate_frame,
            text="Why are you logging for a past date?",
            style="Muted.TLabel",
        )
        backdate_entry = ttk.Entry(backdate_frame, textvariable=backdate_var)
        backdate_hint = ttk.Label(
            backdate_frame,
            text=f"Required for past dates (min {journal.MIN_BACKDATE_REASON_LEN} characters).",
            style="Muted.TLabel",
            wraplength=500,
        )

        def refresh_backdate_ui(*_args: object) -> None:
            parsed = journal.parse_entry_date(date_var.get())
            if parsed and parsed < datetime.now().date():
                backdate_label.pack(anchor="w")
                backdate_entry.pack(fill=tk.X, pady=(4, 2))
                backdate_hint.pack(anchor="w")
            else:
                backdate_label.pack_forget()
                backdate_entry.pack_forget()
                backdate_hint.pack_forget()

        ttk.Label(inner, text="Overall Progress Rating (1-10)", style="Subheading.TLabel").pack(anchor="w", padx=15)
        spin_frame = ttk.Frame(inner)
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
            inner,
            text="Checklist — tick what you completed",
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=15, pady=(12, 4))
        for item in cat_data["checklist"]:
            var = tk.BooleanVar(value=False)
            check_vars[item] = var
            ttk.Checkbutton(inner, text=item, variable=var).pack(anchor="w", padx=25, pady=2)

        ttk.Label(inner, text="Specific Measures", font=("Helvetica", 11, "bold")).pack(anchor="w", padx=15, pady=(12, 4))
        for metric in cat_data["metrics"]:
            metric_name = metric["name"]
            metric_type = metric.get("type", "number")
            metric_unit = metric.get("unit", "")
            existing_val = metric.get("default", 0)

            row = ttk.Frame(inner)
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
            inner,
            text="General notes / journal entry (write as much as you want)",
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=15, pady=(12, 4))
        notes_text.pack(padx=15, pady=(0, 12), fill=tk.X)

        date_var.trace_add("write", load_existing)
        load_existing()

        ttk.Button(
            footer_btns,
            text="Save Log",
            style="Accent.TButton",
            command=lambda: self.save_log(
                dialog,
                cat_name,
                date_var,
                backdate_var,
                rating_var,
                check_vars,
                metric_vars,
                notes_text,
            ),
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(footer_btns, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)
        ttk.Label(
            footer,
            text="Save stores your rating, checklist, metrics, and notes for this life area.",
            style="Muted.TLabel",
            wraplength=560,
        ).pack(anchor="w", pady=(8, 0))

    def save_log(
        self,
        dialog: tk.Toplevel,
        cat_name: str,
        date_var: tk.StringVar,
        backdate_var: tk.StringVar,
        rating_var: tk.IntVar,
        check_vars: dict[str, tk.BooleanVar],
        metric_vars: dict[str, tk.Variable],
        notes_text: scrolledtext.ScrolledText,
    ) -> None:
        date_str = date_var.get().strip()
        reason = backdate_var.get().strip()
        error = journal.validate_backdate(date_str, reason=reason)
        if error:
            messagebox.showwarning("Date", error)
            return

        if date_str not in self.entries:
            self.entries[date_str] = {}

        checklist_data = {item: var.get() for item, var in check_vars.items()}
        metrics_data: dict[str, float | int] = {}
        for name, var in metric_vars.items():
            try:
                metrics_data[name] = var.get()
            except (tk.TclError, ValueError):
                metrics_data[name] = 0

        entry_payload = {
            "rating": rating_var.get(),
            "checklist": checklist_data,
            "metrics": metrics_data,
            "notes": notes_text.get("1.0", tk.END).strip(),
        }
        parsed = journal.parse_entry_date(date_str)
        if parsed and parsed < datetime.now().date():
            entry_payload["backdate_reason"] = reason

        self.entries[date_str][cat_name] = entry_payload
        self._invalidate_caches()
        dialog.destroy()
        if date_str == self.today_str() and self._reminder_scheduler is not None:
            self._reminder_scheduler.notify_logged_today()
        self.refresh_dashboard()
        self.save_data(recompute_fitness=False)
        hint = category_insight(self._get_insights(), cat_name)
        if hint and hint.suggested_actions:
            self.root.after(
                1,
                lambda: messagebox.showinfo("Guidance", f"{hint.message}\n\nTry: {hint.suggested_actions[0]}"),
            )

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

        journal_entries = journal.list_entries(self.journal)
        if journal_entries:
            text.insert(tk.END, f"\n{'=' * 60}\nJOURNAL ENTRIES\n{'=' * 60}\n")
            for item in journal_entries:
                text.insert(tk.END, f"\n{item.get('entry_date')} — {item.get('title') or item.get('prompt')}\n")
                if item.get("backdate_reason"):
                    text.insert(tk.END, f"   Backdated: {item['backdate_reason']}\n")
                text.insert(tk.END, f"{item.get('body', '')}\n")

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

    def show_journal(self) -> None:
        show_journal_window(self)

    def show_plan_tomorrow(self) -> None:
        show_plan_window(self)

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
                results.insert(tk.END, "Type to search life notes, journal entries, checklists, and fitness session notes.")
                return

            hits = 0
            for item in journal.search_entries(self.journal, query):
                hits += 1
                results.insert(tk.END, f"\n{item.get('entry_date')} — Journal: {item.get('title') or item.get('prompt')}\n")
                if item.get("backdate_reason"):
                    results.insert(tk.END, f"Backdated: {item['backdate_reason']}\n")
                results.insert(tk.END, f"{item.get('body', '')}\n")
                results.insert(tk.END, "-" * 40 + "\n")

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
        import fitness_ui

        def on_session_saved(session_date: str) -> None:
            day = self.entries.setdefault(session_date, {})
            body = day.setdefault(
                "Body & Presence",
                {"rating": 7, "checklist": {}, "metrics": {}, "notes": ""},
            )
            body.setdefault("checklist", {})["Completed movement or exercise"] = True
            self._fitness_state_dirty = True
            self._invalidate_caches()
            self.refresh_dashboard()
            self.save_data(recompute_fitness=True)

        def on_fitness_settings_changed(updated: dict) -> None:
            self.settings["fitness"] = updated
            self.save_data(flush=True)

        fitness_ui.show_fitness_window(
            self.root,
            on_session_saved=on_session_saved,
            theme=self.theme,
            fitness_settings=self.settings.get("fitness"),
            on_fitness_settings_changed=on_fitness_settings_changed,
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
            self._invalidate_caches()
            self.save_data()
            editor.destroy()
            messagebox.showinfo("Saved", "Categories updated.")
            self.refresh_dashboard()

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

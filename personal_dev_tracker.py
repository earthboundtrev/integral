"""Personal Development Tracker — daily notes, checklists, metrics, charts, and settings."""

from __future__ import annotations

import json
import logging
from typing import Callable
import os
import sys
import threading
import time
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, scrolledtext, simpledialog, ttk

from activity_grid import ContributionGrid
from busy_indicator import BusyIndicator
import day_plans
from day_plans_ui import show_plan_comparison_window, show_plan_window
from day_watch import DayWatch
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
    show_template_picker,
)
import domain_templates
import journal
from journal_ui import show_journal_window
import creative_projects
from creative_ui import show_writing_projects_window
import deep_work
from deep_work_ui import open_writing_pair, show_deep_work_start_dialog
import nav_items
import quick_capture
from quick_capture_ui import close_quick_capture_panel, open_quick_capture_panel
import focus_shield
import todos
import practices
import youtube_takeout
from milestones import merge_milestones, milestone_summary
from notifications import ReminderScheduler, normalize_notification_settings, show_windows_notification
from paths import APP_NAME, APP_VERSION, data_file, ensure_data_file, icon_path
from progression.sessions import bridge_fitness_to_daily_entries, sync_fitness_sessions_to_entries
import streak
from theme import (
    FONTS,
    apply_theme,
    category_accent,
    get_theme,
    make_card,
    reapply_theme_subtree,
    streak_badge,
    style_canvas,
    style_listbox,
    style_menu,
    style_text_widget,
)
import ui_scroll
from inline_validation import (
    focus_first_invalid,
    make_inline_error_label,
    register_rating_spinbox,
    set_field_error,
    validate_rating_1_10,
    wire_focusout_validation,
)
from status_banner import StatusBanner, attach_banner_to_main
from vault import is_encrypted_file, load_data_file, load_data_file_with_recovery, save_data_file
from entry_payload import (
    build_entry_payload,
    collect_touched_checklist,
    collect_touched_metrics,
    merge_entry_updates,
)
from todays_log import (
    CATEGORY_SHORT_LABELS,
    apply_todays_log_settings,
    filter_todays_log_categories,
    pinned_domains,
    prune_pinned_domains,
    toggle_pinned_domain,
)

DATA_FILE = data_file()

# Environment variables for debugging and performance measurement (issue #135)
try:
    DEBUG_DELAY_MS = int(os.environ.get("INTEGRAL_DEBUG_DELAY_MS", "0"))
except ValueError:
    DEBUG_DELAY_MS = 0
PERF_LOGGING = os.environ.get("INTEGRAL_PERF", "").lower() in ("1", "true", "yes")


def _perf_log(message: str) -> None:
    """Log performance message if INTEGRAL_PERF=1."""
    if PERF_LOGGING:
        print(f"[PERF {time.time():.3f}] {message}", file=sys.stderr, flush=True)


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
        self.creative_projects: dict = creative_projects.empty_creative_projects()
        self.youtube_history: dict = youtube_takeout.empty_youtube_history()
        self.day_plans: dict = day_plans.empty_day_plans()
        self.program_state: dict = {}
        self.programs: dict = load_program_definitions()
        self.data_path = DATA_FILE
        self.vault_passphrase: str | None = None
        self.theme = get_theme(False)
        self._insights_cache = None
        self._streak_cache: dict[str, int] = {}
        self._session_counts_cache: dict[str, int] | None = None
        self._save_after_id: str | None = None
        self._pending_save_payload: dict | None = None
        self._save_after_callbacks: list[Callable[[bool, BaseException | None], None]] = []
        self._save_write_in_progress = False
        self._status_banner: StatusBanner | None = None
        self._fitness_state_dirty = False
        self._dashboard_ready = False
        self._categories_tab_built = False
        self._theme_dark: bool | None = None
        self._log_bar: ttk.LabelFrame | None = None
        self._todays_log_filter = ""
        self._todays_log_status = "all"
        self._activity_grid: ContributionGrid | None = None
        self._guidance_panel: ttk.LabelFrame | None = None
        self._streak_pill: tk.Label | None = None
        self._date_label: ttk.Label | None = None
        self._overview_stats_label: ttk.Label | None = None
        self._reminder_scheduler: ReminderScheduler | None = None
        self._day_watch: DayWatch | None = None
        self._categories_tab_frame: ttk.Frame | None = None
        self._notebook: ttk.Notebook | None = None
        self._streak_details_window: tk.Toplevel | None = None
        self._deep_work_session: deep_work.DeepWorkSession | None = None
        self._deep_work_after_id: str | None = None
        self._deep_work_banner: ttk.Frame | None = None
        self._deep_work_timer_label: ttk.Label | None = None
        self._deep_work_extend_btn: ttk.Button | None = None
        self._deep_work_end_btn: ttk.Button | None = None
        self._sidebar_nav_frames: dict[str, tk.Frame] = {}
        self._sidebar_goto_frame: tk.Frame | None = None
        self._sidebar_deep_work_hint: tk.Label | None = None
        self._quick_capture_win: tk.Toplevel | None = None
        self._focus_shield = focus_shield.FocusShieldSession()
        self._focus_shield_after_id: str | None = None
        self.todos: dict = todos.empty_todos()
        self.practices: dict = practices.empty_practices()
        self._nav_buttons: dict[str, ttk.Widget] = {}
        self._nav_pack_order: list[str] = []
        self._nav_frame: ttk.Frame | None = None
        self._shell_frame: ttk.Frame | None = None
        self._shell_header: ttk.Frame | None = None
        self._content_pane: ttk.Frame | None = None
        self._shell_footer: ttk.Frame | None = None
        self._banner_host: ttk.Frame | None = None
        self._sidebar_slot: ttk.Frame | None = None
        self._theme_reopen_banner: ttk.Frame | None = None
        self._open_windows: dict[str, tk.Toplevel] = {}  # Track windows for raise-if-open
        self._more_menu_popup: Any | None = None
        self._footer_more_btn: ttk.Button | None = None

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
        self.sync_quick_capture_panel()
        if not self.settings.get("onboarding_complete"):
            show_onboarding(self)

        self.root.after(1500, self._poll_pending_deep_link)
        pending_url = getattr(self, "_startup_deep_link", None)
        if pending_url:
            self.root.after(400, lambda: self.handle_deep_link(pending_url))

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
        status_banner = getattr(self, "_status_banner", None)
        if status_banner is not None:
            status_banner.set_theme(self.theme)
        self._retheme_open_windows()

    def _retheme_open_windows(self) -> None:
        """Live re-theme for Q10 popups (Go to… palette) after a theme change (#133)."""
        goto = getattr(self, "_goto_window", None)
        if goto is None:
            return
        try:
            if not goto.winfo_exists():
                return
            goto.configure(bg=self.theme["bg"])
            reapply_theme_subtree(goto, self.theme)
        except tk.TclError:
            return

    def _other_open_toplevels(self) -> list[tk.Toplevel]:
        """Open Toplevels that are not live-rethemed per Q10 (Go to… only)."""
        goto = getattr(self, "_goto_window", None)
        others: list[tk.Toplevel] = []
        for child in self.root.winfo_children():
            if not isinstance(child, tk.Toplevel):
                continue
            try:
                if not child.winfo_exists():
                    continue
            except tk.TclError:
                continue
            if child is goto:
                continue
            others.append(child)
        return others

    def _ensure_theme_reopen_banner(self) -> None:
        host = self._banner_host
        if host is None:
            return
        if self._theme_reopen_banner is not None:
            try:
                if self._theme_reopen_banner.winfo_exists():
                    return
            except tk.TclError:
                self._theme_reopen_banner = None
        banner = ttk.Frame(host)
        ttk.Label(
            banner,
            text="Reopen other windows to apply the theme.",
            style="Muted.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Button(banner, text="Dismiss", command=self._dismiss_theme_reopen_banner).pack(
            side=tk.RIGHT, padx=(8, 0)
        )
        self._theme_reopen_banner = banner

    def _dismiss_theme_reopen_banner(self) -> None:
        banner = getattr(self, "_theme_reopen_banner", None)
        if banner is None:
            return
        try:
            banner.pack_forget()
        except tk.TclError:
            pass

    def _update_theme_reopen_banner(self) -> None:
        if not self._other_open_toplevels():
            self._dismiss_theme_reopen_banner()
            return
        self._ensure_theme_reopen_banner()
        if self._theme_reopen_banner is not None:
            try:
                self._theme_reopen_banner.pack(fill=tk.X, pady=(0, 8))
            except tk.TclError:
                pass

    def _invalidate_caches(self) -> None:
        self._insights_cache = None
        self._streak_cache.clear()

    def _invalidate_session_counts(self) -> None:
        self._session_counts_cache = None

    def _get_insights(self):
        if self._insights_cache is None:
            self._insights_cache = analyze_all(
                self.entries,
                self.categories,
                sessions=self.sessions,
                program_state=self.program_state,
                practices=self.practices,
            )
        return self._insights_cache

    def _on_close(self) -> None:
        notifications = normalize_notification_settings(self.settings)["notifications"]
        if notifications.get("minimize_on_close"):
            self.root.iconify()
            return
        self.quit_app()

    def quit_app(self) -> None:
        if self._reminder_scheduler is not None:
            self._reminder_scheduler.stop()
        if self._day_watch is not None:
            self._day_watch.stop()
        if self._deep_work_after_id:
            self.root.after_cancel(self._deep_work_after_id)
            self._deep_work_after_id = None
        if self._save_after_id:
            self.root.after_cancel(self._save_after_id)
            self._save_after_id = None
        from creative_ui import flush_open_document_windows

        flush_open_document_windows()
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
            has_logged_today=self.has_logged_today,
            persist_settings=lambda: self.save_data(flush=True),
        )

    def _apply_notification_settings(self, settings: dict) -> None:
        self.settings = settings

    def _on_calendar_day_changed(self, previous_day, new_day) -> None:
        del previous_day, new_day
        if self._reminder_scheduler is not None:
            self._reminder_scheduler.reset_for_new_day()
        self.refresh_dashboard(full=False, recompute=True)

    def toggle_dark_mode(self) -> None:
        self.settings["dark_mode"] = not self.settings.get("dark_mode", False)
        self.save_data()
        # Force full shell rebuild for theme changes (chrome colors + mode button label)
        if self._shell_frame is not None:
            try:
                self._shell_frame.destroy()
            except tk.TclError:
                pass
            self._shell_frame = None
        self.create_dashboard()
        self.sync_quick_capture_panel()
        self._retheme_open_windows()
        self._update_theme_reopen_banner()

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
            def on_recovery_prompt(bak_path, bak_timestamp):
                """Prompt user to restore from backup."""
                return messagebox.askyesno(
                    "Data File Damaged",
                    f"Your data file appears to be damaged.\n\n"
                    f"Restore from backup?\n"
                    f"(Last good backup: {bak_timestamp})",
                    icon="warning"
                )
            
            def on_both_corrupt_prompt():
                """Prompt user when both files are corrupt."""
                return messagebox.askyesno(
                    "Data Recovery",
                    "Both your data file and backup appear to be damaged.\n\n"
                    "The damaged files will be preserved with a timestamp.\n"
                    "Start with a fresh, empty journal?",
                    icon="warning"
                )
            
            try:
                data = load_data_file_with_recovery(
                    DATA_FILE, 
                    self.vault_passphrase,
                    on_recovery_prompt=on_recovery_prompt,
                    on_both_corrupt_prompt=on_both_corrupt_prompt
                )
            except PermissionError:
                if not prompt_vault_unlock(self):
                    raise
                data = load_data_file_with_recovery(
                    DATA_FILE, 
                    self.vault_passphrase,
                    on_recovery_prompt=on_recovery_prompt,
                    on_both_corrupt_prompt=on_both_corrupt_prompt
                )
            except ValueError as e:
                # User declined recovery
                messagebox.showerror("Cannot Continue", str(e))
                raise
                
            migrated = migrate_data(data, self.programs)
            self.categories = self.merge_categories_with_defaults(migrated.get("categories"))
            self.entries = migrated.get("entries", {})
            self.settings = normalize_notification_settings(
                {**{"dark_mode": False}, **migrated.get("settings", {})}
            )
            self.settings = quick_capture.apply_quick_capture_settings(
                self.settings,
                quick_capture.normalize_quick_capture_settings(self.settings),
            )
            self.settings = apply_todays_log_settings(self.settings)
            self.settings["fitness"] = get_fitness_settings(self.settings)
            self.sessions = migrated.get("sessions", [])
            self._invalidate_session_counts()
            
            # Migrate legacy program sessions to fitness.db (with backup)
            if self.sessions:
                from legacy_fitness_migration import run_migration
                from progression.db import get_fitness_db_path
                try:
                    # Check if any unmigrated sessions remain
                    needs_migration = any(
                        not sess.get("migrated_to_fitness_db")
                        for sess in self.sessions
                    )
                    if needs_migration:
                        result = run_migration(
                            data_path=DATA_FILE,
                            fitness_db_path=get_fitness_db_path(),
                            mark_migrated=True
                        )
                        if result.get("migrated_count", 0) > 0:
                            print(f"Legacy migration: {result['migrated_count']} sessions migrated")
                        if result.get("errors"):
                            print(f"Legacy migration warnings: {len(result['errors'])} issues")
                except Exception as e:
                    messagebox.showerror(
                        "Migration Failed",
                        f"Legacy fitness session migration failed:\n\n{e}\n\n"
                        "Your data is safe. Backups were created if migration started."
                    )
            
            self.milestones = merge_milestones(migrated.get("milestones"))
            self.journal = journal.normalize_journal(migrated.get("journal"))
            self.creative_projects = creative_projects.normalize_creative_projects(
                migrated.get("creative_projects")
            )
            self.youtube_history = youtube_takeout.normalize_youtube_history(
                migrated.get("youtube_history")
            )
            self.day_plans = day_plans.normalize_day_plans(migrated.get("day_plans"))
            self.todos = todos.normalize_todos(migrated.get("todos"))
            self.practices = practices.normalize_practices(migrated.get("practices"))
            self.program_state = migrated.get("program_state", {})
            dirty = False
            if sync_fitness_sessions_to_entries(self.entries, self.settings.get("fitness")):
                dirty = True
            qc_flags = dict(self.settings.get("quick_capture") or {})
            if not qc_flags.get("todo_done_entries_backfilled"):
                self.entries, _added = quick_capture.backfill_todo_done_entries(
                    self.entries,
                    self.todos,
                    today=self.today_str(),
                )
                qc_flags["todo_done_entries_backfilled"] = True
                self.settings = quick_capture.apply_quick_capture_settings(
                    self.settings, qc_flags
                )
                dirty = True
            if dirty:
                self.save_data(flush=True)
        else:
            self.categories = self.get_default_categories()
            self.entries = {}
            self.settings = normalize_notification_settings(
                {"dark_mode": False, "onboarding_complete": False}
            )
            self.settings = quick_capture.apply_quick_capture_settings(
                self.settings,
                quick_capture.default_quick_capture_settings(),
            )
            self.settings = apply_todays_log_settings(self.settings)
            self.settings["fitness"] = get_fitness_settings(self.settings)
            self.sessions = []
            self._invalidate_session_counts()
            self.milestones = merge_milestones(None)
            self.journal = journal.empty_journal()
            self.creative_projects = creative_projects.empty_creative_projects()
            self.youtube_history = youtube_takeout.empty_youtube_history()
            self.day_plans = day_plans.empty_day_plans()
            self.todos = todos.empty_todos()
            self.practices = practices.empty_practices()
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
            "creative_projects": self.creative_projects,
            "youtube_history": self.youtube_history,
            "day_plans": self.day_plans,
            "todos": self.todos,
            "practices": self.practices,
            "program_state": self.program_state,
            "user_levels": {},
        }

    def save_data(
        self,
        categories: dict | None = None,
        *,
        recompute_fitness: bool = False,
        flush: bool = False,
        on_complete: Callable[[bool, BaseException | None], None] | None = None,
    ) -> None:
        if categories is not None:
            self.categories = categories
        if on_complete is not None:
            self._save_after_callbacks.append(on_complete)
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

    def _invoke_save_callbacks(
        self,
        callbacks: list[Callable[[bool, BaseException | None], None]],
        ok: bool,
        error: BaseException | None,
    ) -> None:
        for cb in callbacks:
            try:
                cb(ok, error)
            except Exception:  # noqa: BLE001
                logging.exception("Save completion callback failed")

    def _notify_save_complete(self, ok: bool, error: BaseException | None) -> None:
        """Backward-compatible hook for tests; prefer per-flush callback lists."""
        callbacks = self._save_after_callbacks
        self._save_after_callbacks = []
        self._invoke_save_callbacks(callbacks, ok, error)

    def _show_save_error_banner(self, error: BaseException | None) -> None:
        logging.error("Save failed: %s", error)
        banner = self.ensure_status_banner()
        file_label = os.path.basename(DATA_FILE) or "data.json"
        detail = str(error) if error else "Could not save your data."
        banner.show_error(f"Save failed: {detail}", file_name=file_label)

    def _finish_save(self, ok: bool, error: BaseException | None) -> None:
        if ok:
            self._notify_save_complete(True, None)
            return
        self._show_save_error_banner(error)
        self._notify_save_complete(False, error)

    def _schedule_chained_flush(self, *, sync: bool) -> None:
        if self._pending_save_payload is None and not self._save_after_callbacks:
            return
        if sync:
            self._flush_save(sync=True)
            return
        if self._save_after_id:
            return
        self._save_after_id = self.root.after(0, lambda: self._flush_save(sync=False))

    def _flush_save(self, sync: bool = False) -> None:
        self._save_after_id = None
        if self._save_write_in_progress:
            return
        payload = self._pending_save_payload
        if payload is None:
            return

        callbacks = self._save_after_callbacks
        self._save_after_callbacks = []

        encrypted = bool(self.settings.get("encryption_enabled"))
        passphrase = self.vault_passphrase
        path = DATA_FILE

        def write() -> None:
            save_data_file(path, payload, encrypted=encrypted, passphrase=passphrase)

        def on_done(ok: bool, error: BaseException | None) -> None:
            self._save_write_in_progress = False
            self._invoke_save_callbacks(callbacks, ok, error)
            if ok:
                if self._pending_save_payload is payload:
                    self._pending_save_payload = None
            else:
                self._show_save_error_banner(error)
                if self._pending_save_payload is payload:
                    self._pending_save_payload = None
            self._schedule_chained_flush(sync=sync)

        def run_async() -> None:
            try:
                write()
            except Exception as exc:  # noqa: BLE001
                self.root.after(0, lambda e=exc: on_done(False, e))
            else:
                self.root.after(0, lambda: on_done(True, None))

        self._save_write_in_progress = True
        if sync:
            try:
                write()
            except Exception as exc:  # noqa: BLE001
                on_done(False, exc)
            else:
                on_done(True, None)
            return
        threading.Thread(target=run_async, daemon=True).start()

    def ensure_status_banner(self) -> StatusBanner:
        if self._status_banner is not None:
            try:
                if int(self._status_banner._host.winfo_exists()) == 1:
                    return self._status_banner
            except tk.TclError:
                pass
        host = self._banner_host
        if host is None or not host.winfo_exists():
            host = self.root
        self._status_banner = StatusBanner(host, self.theme)
        return self._status_banner

    def show_save_success_banner(self, message: str, **kwargs) -> None:
        self.ensure_status_banner().show_success(message, **kwargs)

    def save_fitness_data(self) -> None:
        self._fitness_state_dirty = True
        self._invalidate_session_counts()
        self.save_data(recompute_fitness=True)

    def get_streak(self, category: str | None = None) -> int:
        cache_key = category or "__all__"
        if cache_key not in self._streak_cache:
            if category is None:
                self._streak_cache[cache_key] = streak.get_streak(
                    self.entries,
                    journal=self.journal,
                    sessions=self.sessions,
                )
            else:
                self._streak_cache[cache_key] = streak.get_streak(self.entries, category)
        return self._streak_cache[cache_key]

    def has_logged_today(self) -> bool:
        return streak.day_has_engagement(
            self.entries,
            datetime.now().date(),
            journal=self.journal,
            sessions=self.sessions,
        )

    def today_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def open_gap_repair_journal(self) -> None:
        yesterday = (datetime.now().date() - timedelta(days=1)).strftime("%Y-%m-%d")
        show_journal_window(self, yesterday, prompt=journal.GAP_PROMPT)

    def open_journal_entry(self, entry_id: str, *, parent=None) -> None:
        target = journal.get_entry(self.journal, entry_id)
        if not target:
            messagebox.showwarning(
                "Missing entry",
                "That journal link no longer points to an entry (deleted or unknown id).",
                parent=parent or self.root,
            )
            return
        show_journal_window(self, entry_id=entry_id)

    def open_integral_link(self, link, *, parent=None) -> None:
        """Open journal / domain / fitness / writing-project targets from an IntegralLink."""
        import integral_links
        from creative_ui import show_writing_projects_window

        if not isinstance(link, integral_links.IntegralLink):
            return
        parent = parent or self.root
        if link.kind == "journal":
            self.open_journal_entry(link.target, parent=parent)
        elif link.kind == "domain":
            cat = (link.extra or "").strip()
            if not cat or cat not in self.categories:
                messagebox.showwarning(
                    "Missing domain",
                    f"No life-domain category named “{cat}”.",
                    parent=parent,
                )
                return
            self.open_log_dialog(cat, date_str=link.target)
        elif link.kind == "fitness":
            self.show_day_explorer(link.target)
        elif link.kind == "project":
            project = creative_projects.get_project(self.creative_projects, link.target)
            if not project:
                messagebox.showwarning(
                    "Missing project",
                    "That writing project link no longer exists.",
                    parent=parent,
                )
                return
            show_writing_projects_window(self, select_project_id=link.target)
        else:
            messagebox.showwarning("Unknown link", f"Unsupported link kind: {link.kind}", parent=parent)

    def handle_deep_link(self, url: str | None) -> bool:
        if not url:
            return False
        import integral_links

        link = integral_links.parse_deep_link(url)
        if not link:
            messagebox.showwarning(
                "Unknown link",
                "Integral only opens known integral:// links "
                "(journal, domain, fitness, project).",
                parent=self.root,
            )
            return False
        self.root.after(1, lambda: self.open_integral_link(link))
        return True

    def _poll_pending_deep_link(self) -> None:
        from deep_links import read_and_clear_pending_link

        pending = read_and_clear_pending_link()
        if pending:
            self.handle_deep_link(pending)
        if self.root.winfo_exists():
            self.root.after(1500, self._poll_pending_deep_link)

    def format_today_presence_line(self) -> str:
        """Non-punitive summary: check-ins count, never N/total completeness."""
        logged_count, _total = self.count_today_logged()
        if logged_count == 0:
            return "Nothing logged yet today — one rating is enough whenever you're ready."
        if logged_count == 1:
            return "1 check-in today — that's a complete honest day."
        return f"{logged_count} check-ins today — add more only if you want."

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
        logged_count, _total = self.count_today_logged()
        today_entries = self.entries.get(self.today_str(), {})
        logged_names = set(today_entries.keys())
        pruned = prune_pinned_domains(self.settings, self.categories.keys())
        if pruned.get("todays_log") != self.settings.get("todays_log"):
            self.settings = pruned
            self.save_data(flush=True)

        parent = self._content_pane if self._content_pane is not None else self.root
        log_bar = ttk.LabelFrame(parent, text="Today's Log", padding=14, style="Card.TLabelframe")
        self._log_bar = log_bar
        log_bar.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=16, pady=(0, 10))

        ttk.Label(
            log_bar,
            text=self.format_today_presence_line(),
            style="OnSurfaceSubheading.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            log_bar,
            text="Domains are optional depth — pick any area below, or skip. Rating + Save is enough.",
            style="OnSurfaceMuted.TLabel",
        ).pack(anchor="w", pady=(4, 10))

        # --- Inline todo entry and quick action buttons ---
        quick_actions_frame = ttk.Frame(log_bar, style="Surface.TFrame")
        quick_actions_frame.pack(fill=tk.X, pady=(0, 12))
        
        # Inline todo field
        todo_row = ttk.Frame(quick_actions_frame, style="Surface.TFrame")
        todo_row.pack(fill=tk.X, pady=(0, 8))
        
        todo_var = tk.StringVar()
        todo_entry = ttk.Entry(
            todo_row,
            textvariable=todo_var,
            font=FONTS["body"],
        )
        todo_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self._inline_todo_entry = todo_entry
        self._inline_todo_var = todo_var
        
        # More options link to open Quick Capture
        more_link = ttk.Label(
            todo_row,
            text="More options…",
            foreground=self.theme["link"],
            cursor="hand2",
            style="OnSurfaceMuted.TLabel"
        )
        more_link.pack(side=tk.LEFT, padx=(0, 8))
        
        # Workout history button
        ttk.Button(
            todo_row,
            text="Workout history",
            command=self.show_workout_history,
        ).pack(side=tk.LEFT, padx=(8, 0))
        
        def open_qc_with_text(event=None):
            text = todo_var.get().strip()
            if text != "Add a todo… (Enter to save, Ctrl+Shift+T from anywhere)" and text:
                # Store text for QC to pick up
                self._qc_prefill_text = text
            self._qc_should_focus = True
            self.set_quick_capture_enabled(True)
            return "break"
        
        more_link.bind("<Button-1>", open_qc_with_text)
        
        # Placeholder simulation
        def on_focus_in(event):
            if todo_var.get() == "Add a todo… (Enter to save, Ctrl+Shift+T from anywhere)":
                todo_var.set("")
                todo_entry.config(foreground=self.theme["fg"])
        
        def on_focus_out(event):
            if not todo_var.get():
                todo_var.set("Add a todo… (Enter to save, Ctrl+Shift+T from anywhere)")
                todo_entry.config(foreground=self.theme["muted"])
        
        todo_var.set("Add a todo… (Enter to save, Ctrl+Shift+T from anywhere)")
        todo_entry.config(foreground=self.theme["muted"])
        todo_entry.bind("<FocusIn>", on_focus_in)
        todo_entry.bind("<FocusOut>", on_focus_out)
        
        # Use tk.Label for error messages (ttk ignores foreground color)
        error_label = tk.Label(todo_row, text="", fg="#DC2626", bg=self.theme["surface"])
        self._inline_error_label = error_label
        self._error_timer_id = None
        
        def add_inline_todo(event=None):
            text = todo_var.get().strip()
            if text == "Add a todo… (Enter to save, Ctrl+Shift+T from anywhere)" or not text:
                return "break"
            
            # Note: IME composition handling not available in standard Tk.
            # Users completing IME input should press Enter after composition is committed.
            
            error = self.add_todo_quick(text)
            if error:
                error_label.config(text=error)
                error_label.pack(side=tk.LEFT, padx=(8, 0))
                # Cancel previous timer if any
                if self._error_timer_id:
                    self.root.after_cancel(self._error_timer_id)
                self._error_timer_id = self.root.after(5000, lambda: self._clear_error_label())
                # Keep text in field on error so user can fix it
            else:
                # Cancel error timer if any
                if self._error_timer_id:
                    self.root.after_cancel(self._error_timer_id)
                    self._error_timer_id = None
                error_label.pack_forget()
                todo_var.set("")
                on_focus_out(None)
                self.refresh_dashboard(full=False)
                # Restore focus after refresh
                self.root.after(10, lambda: self._restore_inline_todo_focus())
                self.sync_quick_capture_panel()
            
            return "break"
        
        def clear_todo(event):
            if todo_var.get() and todo_var.get() != "Add a todo… (Enter to save, Ctrl+Shift+T from anywhere)":
                todo_var.set("")
                on_focus_out(None)
                error_label.pack_forget()
                return "break"
            else:
                # Second Escape: move focus to + Todo button
                if hasattr(self, "_add_todo_button"):
                    self._add_todo_button.focus_set()
                return "break"
        
        todo_entry.bind("<Return>", add_inline_todo)
        todo_entry.bind("<Escape>", clear_todo)
        
        # Quick action buttons
        buttons_row = ttk.Frame(quick_actions_frame, style="Surface.TFrame")
        buttons_row.pack(fill=tk.X)
        
        add_todo_btn = ttk.Button(
            buttons_row,
            text="+ Todo",
            command=lambda: todo_entry.focus_set()
        )
        add_todo_btn.pack(side=tk.LEFT, padx=(0, 8), ipady=4)
        self._add_todo_button = add_todo_btn
        
        log_workout_btn = ttk.Button(
            buttons_row,
            text="Log workout",
            command=self.show_log_exercise
        )
        log_workout_btn.pack(side=tk.LEFT, padx=(0, 8), ipady=4)
        from keyboard_shortcuts import INLINE_BUTTON_SHORTCUTS, attach_shortcut_tooltip

        attach_shortcut_tooltip(
            log_workout_btn,
            "Log workout",
            INLINE_BUTTON_SHORTCUTS["Log workout"],
            self.theme,
        )
        
        def reflect_action():
            next_cat = self.first_unlogged_category()
            if next_cat:
                self.open_log_dialog(next_cat)
        
        reflect_btn = ttk.Button(
            buttons_row,
            text="Reflect",
            command=reflect_action
        )
        reflect_btn.pack(side=tk.LEFT, ipady=4)
        attach_shortcut_tooltip(
            reflect_btn, "Reflect", INLINE_BUTTON_SHORTCUTS["Reflect"], self.theme
        )

        actions_host, actions, _actions_canvas = ui_scroll.make_horizontal_scroll_row(
            log_bar,
            height=40,
            overflow_hint="Scroll for more →",
            theme=self.theme,
            chrome_bg=self.theme["surface"],
        )
        actions_host.pack(fill=tk.X, pady=(0, 4))
        next_cat = self.first_unlogged_category()
        if next_cat:
            ttk.Button(
                actions,
                text=f"Log one → {CATEGORY_SHORT_LABELS.get(next_cat, next_cat)}",
                style="Accent.TButton",
                command=lambda: self.open_log_dialog(next_cat),
            ).pack(side=tk.LEFT, padx=(0, 8))
        elif logged_count:
            ttk.Label(
                actions,
                text="All listed domains have a check-in — nothing more required.",
                style="OnSurfaceMuted.TLabel",
            ).pack(side=tk.LEFT)
        journal_btn = ttk.Button(actions, text="Journal", command=self.show_journal)
        journal_btn.pack(side=tk.LEFT, padx=(0, 8))
        attach_shortcut_tooltip(
            journal_btn, "Journal", INLINE_BUTTON_SHORTCUTS["Journal"], self.theme
        )
        qc_btn = ttk.Button(
            actions,
            text="Quick Capture",
            command=self.toggle_quick_capture,
        )
        qc_btn.pack(side=tk.LEFT, padx=(0, 8))
        attach_shortcut_tooltip(
            qc_btn,
            "Quick Capture",
            INLINE_BUTTON_SHORTCUTS["Quick Capture"],
            self.theme,
        )

        from more_menu_ui import populate_today_more_menu

        more = ttk.Menubutton(actions, text="More…")
        more_menu = tk.Menu(more, tearoff=0)
        self._today_more_menu = more_menu
        populate_today_more_menu(more_menu, self, self.theme)
        more["menu"] = more_menu
        more.pack(side=tk.LEFT)

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

        filter_row = ttk.Frame(log_bar, style="Surface.TFrame")
        filter_row.pack(fill=tk.X, pady=(12, 0))
        ttk.Label(filter_row, text="Find:", style="OnSurfaceMuted.TLabel").pack(
            side=tk.LEFT, padx=(0, 6)
        )
        filter_var = tk.StringVar(value=self._todays_log_filter)
        filter_entry = ttk.Entry(filter_row, textvariable=filter_var, width=28)
        filter_entry.pack(side=tk.LEFT, padx=(0, 8))
        status_var = tk.StringVar(value=self._todays_log_status or "all")
        for value, label in (
            ("all", "All"),
            ("unlogged", "Unlogged"),
            ("logged", "Logged"),
        ):
            ttk.Radiobutton(
                filter_row,
                text=label,
                value=value,
                variable=status_var,
            ).pack(side=tk.LEFT, padx=(0, 4))

        def clear_filter() -> None:
            filter_var.set("")
            status_var.set("all")
            filter_entry.focus_set()

        ttk.Button(filter_row, text="Clear", command=clear_filter).pack(side=tk.LEFT, padx=(8, 0))

        # ~3 rows of category buttons visible by default; mousewheel scrolls the rest
        cat_scroll_host = ttk.Frame(log_bar, style="Surface.TFrame")
        cat_scroll_host.pack(fill=tk.X, pady=(8, 0))
        _cat_wrap, btn_row, cat_canvas = ui_scroll.make_bounded_vertical_scroll(
            cat_scroll_host,
            max_height=252,
            overflow_hint="↓ Scroll for more categories",
            theme=self.theme,
            chrome_bg=self.theme["surface"],
        )
        _cat_wrap.pack(fill=tk.X)
        match_hint = ttk.Label(log_bar, text="", style="OnSurfaceMuted.TLabel")
        match_hint.pack(anchor="w", pady=(4, 0))

        def rebuild_domain_grid(*_args) -> None:
            self._todays_log_filter = filter_var.get()
            self._todays_log_status = status_var.get() or "all"
            pins = pinned_domains(self.settings)
            pin_set = set(pins)
            for child in btn_row.winfo_children():
                child.destroy()
            names = filter_todays_log_categories(
                list(self.categories.keys()),
                query=self._todays_log_filter,
                status=self._todays_log_status,
                logged_names=logged_names,
                pinned_names=pins,
            )
            total = len(self.categories)
            if not names:
                ttk.Label(
                    btn_row,
                    text="No domains match — clear the filter or switch to All.",
                    style="OnSurfaceMuted.TLabel",
                ).grid(row=0, column=0, columnspan=4, sticky="w", padx=4, pady=8)
                match_hint.config(text="")
                cat_canvas.yview_moveto(0)
                return

            def pin_menu(event, cat: str) -> None:
                menu = tk.Menu(btn_row, tearoff=0)
                style_menu(menu, self.theme)
                if cat in pin_set:
                    menu.add_command(
                        label="Unpin domain",
                        command=lambda: self._toggle_domain_pin(cat, rebuild_domain_grid),
                    )
                else:
                    menu.add_command(
                        label="Pin domain (up to 5)",
                        command=lambda: self._toggle_domain_pin(cat, rebuild_domain_grid),
                    )
                try:
                    menu.tk_popup(event.x_root, event.y_root)
                finally:
                    menu.grab_release()

            for index, cat_name in enumerate(names):
                short = CATEGORY_SHORT_LABELS.get(cat_name, cat_name)
                is_logged = cat_name in today_entries
                rating = today_entries.get(cat_name, {}).get("rating", "")
                star = "★ " if cat_name in pin_set else ""
                if is_logged:
                    label = f"{star}✓ {short} ({rating}/10)"
                else:
                    label = f"{star}Log {short}"
                btn_style = "Logged.TButton" if is_logged else "TButton"
                btn = ttk.Button(
                    btn_row,
                    text=label,
                    style=btn_style,
                    command=lambda c=cat_name: self.open_log_dialog(c),
                )
                btn.grid(row=index // 4, column=index % 4, padx=4, pady=4, sticky="ew")
                btn.bind("<Button-3>", lambda e, c=cat_name: pin_menu(e, c))
            for col in range(4):
                btn_row.columnconfigure(col, weight=1)
            bits: list[str] = []
            if pins:
                bits.append(f"{len(pins)} pinned")
            if len(names) < total or self._todays_log_filter.strip() or self._todays_log_status != "all":
                bits.append(f"showing {len(names)} of {total}")
            elif not pins:
                bits.append("Unlogged first — right-click to pin favorites")
            match_hint.config(text=" · ".join(bits))
            cat_canvas.yview_moveto(0)

        filter_var.trace_add("write", rebuild_domain_grid)
        status_var.trace_add("write", rebuild_domain_grid)
        rebuild_domain_grid()

    def _toggle_domain_pin(self, cat_name: str, on_done=None) -> None:
        from tkinter import messagebox

        updated, err = toggle_pinned_domain(
            self.settings,
            cat_name,
            valid_names=set(self.categories.keys()),
        )
        if err:
            messagebox.showinfo("Pinned domains", err, parent=self.root)
            return
        self.settings = updated
        self.save_data(flush=True)
        if on_done:
            on_done()

    def refresh_dashboard(self, *, full: bool = False, recompute: bool = True) -> None:
        if full or not self._dashboard_ready:
            self.create_dashboard()
            return
        
        # Update header chrome
        self._refresh_header_chrome()
        
        # Rebuild content pane
        self._build_content(recompute=recompute)

        try:
            if self._activity_grid is not None:
                self._refresh_activity_grid()

            # Guidance + Categories rebuild only when data may have changed (#47 / #50).
            if recompute and self._guidance_panel is not None:
                for child in self._guidance_panel.winfo_children():
                    child.destroy()
                self._fill_guidance_panel(self._guidance_panel)

            if self._overview_stats_label is not None:
                today_str = self.today_str()
                logged_today = len(self.entries.get(today_str, {}))
                fitness_today = self._session_counts_for_date(today_str)
                if logged_today == 0:
                    stats_text = "Today: no life-domain check-ins yet (optional)"
                elif logged_today == 1:
                    stats_text = "Today: 1 life-domain check-in"
                else:
                    stats_text = f"Today: {logged_today} life-domain check-ins"
                if fitness_today:
                    stats_text += f"  ·  {fitness_today} fitness session(s)"
                stats_text += f"  ·  {milestone_summary(self.milestones)}"
                self._overview_stats_label.config(text=stats_text)

            if recompute and self._categories_tab_built and self._categories_tab_frame is not None:
                for child in self._categories_tab_frame.winfo_children():
                    child.destroy()
                self._categories_tab_built = False
                if self._notebook is not None and self._notebook.index("current") == 1:
                    self._build_categories_tab(self._categories_tab_frame)
                    self._categories_tab_built = True
        except tk.TclError:
            self._close_streak_details_window()

    def _session_counts_for_date(self, date_str: str) -> int:
        return self._activity_session_counts().get(date_str, 0)

    def _activity_session_counts(self) -> dict[str, int]:
        if self._session_counts_cache is not None:
            return self._session_counts_cache
        counts: dict[str, int] = {}
        for session in self.sessions:
            date_str = session.get("date")
            if date_str:
                counts[date_str] = counts.get(date_str, 0) + 1
        try:
            from fitness_ui import get_profile_repo

            db_counts = get_profile_repo().count_workout_sessions_by_date(limit=2000)
            for date_str, n in db_counts.items():
                counts[date_str] = counts.get(date_str, 0) + int(n)
        except Exception:
            pass
        self._session_counts_cache = counts
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
        from more_menu_ui import close_more_menu

        close_more_menu(self)
        self._dashboard_ready = False

        # Check if theme changed (for backup restore with different dark_mode)
        theme_changed = self._theme_dark != self.settings.get("dark_mode", False)
        
        # First-time creation or full rebuild
        needs_shell = self._shell_frame is None or not self._shell_frame.winfo_exists() or theme_changed
        
        # Apply theme before shell creation so colors are correct
        self.apply_current_theme(force=True)
        
        if needs_shell:
            # Full teardown and shell creation (preserve open Toplevels — Q10 / #133 AC3)
            for widget in self.root.winfo_children():
                if isinstance(widget, tk.Toplevel):
                    continue
                widget.destroy()
            self._deep_work_banner = None
            self._deep_work_timer_label = None
            self._nav_buttons = {}
            self._nav_pack_order = []
            self._nav_frame = None
            self._ensure_shell()
        else:
            # Shell exists, refresh header chrome (for backup restore, etc.)
            self._refresh_header_chrome()
        
        self._build_content(recompute=True)
        self._dashboard_ready = True
    
    def _restore_content_focus(self) -> None:
        """Set focus to first focusable control in content pane."""
        if self._content_pane is None or not self._content_pane.winfo_exists():
            return
        
        # Deep search for first focusable widget
        def find_focusable(widget):
            """Recursively find first focusable widget."""
            if widget.winfo_class() in ("TEntry", "Entry", "Text"):
                return widget
            for child in widget.winfo_children():
                result = find_focusable(child)
                if result:
                    return result
            return None
        
        focusable = find_focusable(self._content_pane)
        if focusable:
            focusable.focus_set()
    
    def _refresh_header_chrome(self) -> None:
        """Update header widgets (streak, date) without rebuilding shell."""
        if self._streak_pill is not None:
            try:
                if self._streak_pill.winfo_exists():
                    self._streak_pill.config(text=f"🔥 {self.get_streak()} day streak · details")
            except tk.TclError:
                pass
        if self._date_label is not None:
            try:
                if self._date_label.winfo_exists():
                    self._date_label.config(text=f"Today · {datetime.now().strftime('%B %d, %Y')}")
            except tk.TclError:
                pass

    def _ensure_shell(self) -> None:
        """Create the persistent shell frame structure."""
        # Shell container
        self._shell_frame = ttk.Frame(self.root)
        self._shell_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header (persistent)
        self._shell_header = ttk.Frame(self._shell_frame)
        self._shell_header.pack(fill=tk.X, padx=16, pady=(16, 10))
        
        title_block = ttk.Frame(self._shell_header)
        title_block.pack(side=tk.LEFT)
        ttk.Label(title_block, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            title_block,
            text="Holistic life tracking",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 0))
        
        right_header = ttk.Frame(self._shell_header)
        right_header.pack(side=tk.RIGHT)
        streak_frame = streak_badge(
            right_header,
            self.theme,
            f"🔥 {self.get_streak()} day streak",
            command=self.show_streak_details,
        )
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
        
        # Sidebar (#131) - pack before content
        self._sidebar_slot = ttk.Frame(self._shell_frame)
        self._sidebar_slot.pack(side=tk.LEFT, fill=tk.Y)
        self._build_sidebar()
        
        # Banner host (persistent, for Deep Work and future banners)
        self._banner_host = ttk.Frame(self._shell_frame)
        self._banner_host.pack(fill=tk.X, padx=16, pady=(0, 0))
        
        # Footer (persistent) - pack before content to avoid clipping at minsize/high DPI
        self._shell_footer = ttk.Frame(self._shell_frame)
        self._shell_footer.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=(4, 12))
        
        # Content pane (persistent frame, children rebuilt) - pack after footer
        self._content_pane = ttk.Frame(self._shell_frame)
        self._content_pane.pack(fill=tk.BOTH, expand=True)
        ttk.Separator(self._shell_footer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
        footer_actions = ttk.Frame(self._shell_footer)
        footer_actions.pack(fill=tk.X)
        self._footer_more_btn = ttk.Button(
            footer_actions,
            text="More… ▾",
            command=self._toggle_footer_more_menu,
        )
        self._footer_more_btn.pack(side=tk.RIGHT)
        self._nav_frame = footer_actions
        self._nav_buttons = {}
        self._nav_pack_order = []
        self._ensure_deep_work_banner(self._banner_host)
        self._apply_deep_work_chrome()
        from keyboard_shortcuts import apply_sidebar_shortcut_tooltips, install_global_shortcuts

        if not getattr(self, "_keyboard_shortcuts_bound", False):
            install_global_shortcuts(self)
        apply_sidebar_shortcut_tooltips(self)

    def _build_sidebar(self) -> None:
        """Build the left sidebar navigation (#131)."""
        from theme import FONTS
        
        theme = self.theme
        sidebar_bg = theme.get("sidebar", theme["bg"])
        
        container = tk.Frame(self._sidebar_slot, bg=sidebar_bg, width=240)
        container.pack(fill=tk.BOTH, expand=True)
        container.pack_propagate(False)
        
        brand_frame = tk.Frame(container, bg=sidebar_bg)
        brand_frame.pack(fill=tk.X, padx=16, pady=(16, 8))
        brand_label = tk.Label(
            brand_frame,
            text="Integral",
            bg=sidebar_bg,
            fg=theme["fg"],
            font=FONTS["brand"],
        )
        brand_label.pack(anchor="w")
        tagline = tk.Label(
            brand_frame,
            text="Tend every area of your life",
            bg=sidebar_bg,
            fg=theme["muted"],
            font=FONTS["caption"],
        )
        tagline.pack(anchor="w")
        
        nav_container = tk.Frame(container, bg=sidebar_bg)
        nav_container.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        
        self._sidebar_nav_buttons = []
        self._sidebar_nav_frames = {}
        
        sidebar_actions: dict[str, Callable[[], None]] = {
            "today": lambda: self._raise_or_open("today"),
            "fitness_hub": lambda: self._raise_or_open("fitness"),
            "reflect": self.show_reflect,
            "journal": lambda: self._raise_or_open("journal"),
            "graphs": lambda: self._raise_or_open("graphs"),
            "weekly_summary": self.show_weekly_summary,
        }
        
        for spec in nav_items.sidebar_nav_items():
            btn_frame = tk.Frame(nav_container, bg=sidebar_bg, height=36)
            btn_frame.pack(fill=tk.X, padx=8, pady=1)
            btn_frame.pack_propagate(False)
            self._sidebar_nav_frames[spec.id] = btn_frame
            
            btn = tk.Button(
                btn_frame,
                text=spec.label,
                command=sidebar_actions[spec.id],
                bg=sidebar_bg,
                fg=theme["fg"],
                font=FONTS["caption"],
                relief=tk.FLAT,
                cursor="hand2",
                anchor="w",
                padx=8,
            )
            btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._sidebar_nav_buttons.append(btn)
            
            def on_enter(e, b=btn):
                if b["state"] != "disabled":
                    b.configure(bg=theme["surface"])
            
            def on_leave(e, b=btn):
                b.configure(bg=sidebar_bg)
            
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
        
        hint_row = tk.Frame(nav_container, bg=sidebar_bg)
        hint_row.pack(fill=tk.X, padx=16, pady=(4, 0))
        self._sidebar_deep_work_hint = tk.Label(
            hint_row,
            text=nav_items.DEEP_WORK_HIDDEN_HINT,
            bg=sidebar_bg,
            fg=theme["muted"],
            font=FONTS["hint"],
            anchor="w",
        )
        self._sidebar_deep_work_hint.pack(fill=tk.X, anchor="w")
        hint_row.pack_forget()
        self._sidebar_deep_work_hint_row = hint_row
        self._sidebar_nav_container = nav_container
        
        goto_frame = tk.Frame(container, bg=sidebar_bg)
        goto_frame.pack(fill=tk.X, padx=16, pady=(16, 8))
        self._sidebar_goto_frame = goto_frame
        goto_btn = tk.Button(
            goto_frame,
            text=nav_items.SIDEBAR_DISPLAY_LABELS.get("goto_palette", "Go to…"),
            command=self.show_goto,
            bg=theme["field_bg"],
            fg=theme["muted"],
            font=FONTS["caption"],
            relief=tk.FLAT,
            cursor="hand2",
            anchor="w",
            padx=8,
        )
        goto_btn.pack(fill=tk.X)
        
        hint_label = tk.Label(
            goto_frame,
            text="Ctrl+K",
            bg=sidebar_bg,
            fg=theme["muted"],
            font=FONTS["hint"],
        )
        hint_label.pack(anchor="w", pady=(4, 0))
        
        more_frame = tk.Frame(container, bg=sidebar_bg)
        more_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 16))
        self._sidebar_more_btn = tk.Button(
            more_frame,
            text="⋯ More",
            command=self._toggle_sidebar_more_menu,
            bg=sidebar_bg,
            fg=theme["muted"],
            font=FONTS["caption"],
            relief=tk.FLAT,
            cursor="hand2",
            anchor="w",
            padx=8,
        )
        self._sidebar_more_btn.pack(fill=tk.X)

    def _raise_or_open(self, window_key: str) -> None:
        """Open a window or raise it if already open (#131)."""
        existing = self._open_windows.get(window_key)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass
            del self._open_windows[window_key]
        
        if window_key == "today":
            self.root.lift()
            self.root.focus_force()
            if self._content_pane and self._content_pane.winfo_exists():
                self._content_pane.focus_set()
        elif window_key == "fitness":
            if nav_items.deep_work_blocks_action(self, item_id="fitness_hub"):
                return
            self.show_fitness_hub()
        elif window_key == "journal":
            self.show_journal()
        elif window_key == "graphs":
            if nav_items.deep_work_blocks_action(self, item_id="graphs"):
                return
            self.show_graphs()
    
    def _track_window(self, window_key: str, window: tk.Toplevel) -> None:
        """Track a window for raise-if-open behavior. Wraps existing WM_DELETE_WINDOW."""
        self._open_windows[window_key] = window
        existing_handler = window.protocol("WM_DELETE_WINDOW")
        
        def on_close():
            if window_key in self._open_windows:
                del self._open_windows[window_key]
            if existing_handler and callable(existing_handler):
                try:
                    window.call(existing_handler)
                except tk.TclError:
                    window.destroy()
            else:
                window.destroy()
        window.protocol("WM_DELETE_WINDOW", on_close)

    def _run_nav_shortcut(self, nav_id: str, action: Callable[[], None]) -> None:
        if nav_items.deep_work_blocks_action(self, item_id=nav_id):
            return
        action()

    def show_reflect(self) -> None:
        """Open one-screen daily reflection for today (#113)."""
        if nav_items.deep_work_blocks_action(self, item_id="reflect"):
            return
        from reflect_page_ui import open_reflect_page

        open_reflect_page(self)
    
    def _build_content(self, *, recompute: bool = True) -> None:
        """Build or rebuild the content pane (Today's Log and Overview).
        
        Issue #135: Chunked build with BusyIndicator (180ms delay).
        """
        if self._content_pane is None or not self._content_pane.winfo_exists():
            return
        
        focused_widget = self.root.focus_get()
        focused_path = str(focused_widget) if focused_widget else None
        
        for child in self._content_pane.winfo_children():
            child.destroy()
        
        build_start_time = time.time()
        _perf_log("Content build started")
        
        busy = BusyIndicator(
            self._content_pane,
            label="Loading today's log…",
            theme=self.theme,
            delay_ms=180,
        )
        
        if DEBUG_DELAY_MS > 0:
            _perf_log(f"Applying debug delay: {DEBUG_DELAY_MS}ms")
        
        busy.start()
        
        chunk_times = []
        
        def chunk_1_setup():
            chunk_start = time.time()
            if recompute:
                self._invalidate_caches()
                self.insights = self._get_insights()
            chunk_times.append(("setup", time.time() - chunk_start))
            if DEBUG_DELAY_MS > 0:
                self.root.after(DEBUG_DELAY_MS, chunk_2_build_log_bar)
            else:
                self.root.after_idle(chunk_2_build_log_bar)
        
        def chunk_2_build_log_bar():
            chunk_start = time.time()
            try:
                self.create_todays_log_bar()
            except Exception as e:
                busy.stop()
                _show_build_error(e)
                return
            chunk_times.append(("log_bar", time.time() - chunk_start))
            self.root.after_idle(chunk_3_finalize)
        
        def chunk_3_finalize():
            chunk_start = time.time()
            if focused_path and focused_path.startswith(str(self._content_pane)):
                self.root.after(10, lambda: self._restore_content_focus())
            chunk_times.append(("finalize", time.time() - chunk_start))
            busy.stop()
            total_time = time.time() - build_start_time
            _perf_log(f"Content build complete: {total_time*1000:.1f}ms total")
            for name, duration in chunk_times:
                _perf_log(f"  - {name}: {duration*1000:.1f}ms")
        
        def _show_build_error(error):
            error_frame = ttk.Frame(self._content_pane, style="Surface.TFrame")
            error_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
            ttk.Label(
                error_frame,
                text="Couldn't load today's log.",
                style="OnSurfaceError.TLabel",
            ).pack(pady=(0, 8))
            ttk.Label(
                error_frame,
                text=str(error),
                style="OnSurfaceMuted.TLabel",
                wraplength=600,
            ).pack(pady=(0, 16))
            ttk.Button(
                error_frame,
                text="Retry",
                command=lambda: self.refresh_dashboard(full=False, recompute=True),
            ).pack()
            messagebox.showerror("Build Error", f"Couldn't load today's log:\n\n{error}")
        
        self.root.after_idle(chunk_1_setup)

    def _build_overview_tab(self, parent: ttk.Frame) -> None:
        outer, main, canvas = ui_scroll.make_scrollable_frame(parent, theme=self.theme, chrome_bg=self.theme["bg"])
        outer.pack(fill=tk.BOTH, expand=True)

        main.columnconfigure(0, weight=1)

        grid_panel = ttk.Frame(main, padding=8)
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
        if logged_today == 0:
            stats_text = "Today: no life-domain check-ins yet (optional)"
        elif logged_today == 1:
            stats_text = "Today: 1 life-domain check-in"
        else:
            stats_text = f"Today: {logged_today} life-domain check-ins"
        if fitness_today:
            stats_text += f"  ·  {fitness_today} fitness session(s)"
        stats_text += f"  ·  {milestone_summary(self.milestones)}"
        stats_left = ttk.Frame(stats)
        stats_left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._overview_stats_label = ttk.Label(
            stats_left,
            text=stats_text,
            style="Muted.TLabel",
        )
        self._overview_stats_label.pack(anchor="w")
        ttk.Button(stats_left, text="Explore today", command=lambda: self.show_day_explorer(today_str)).pack(
            anchor="w", pady=(6, 0)
        )
        stats_actions = ttk.Frame(stats)
        stats_actions.pack(side=tk.RIGHT)
        ttk.Button(
            stats_actions,
            text="AI Insight",
            command=lambda: self._show_ai_insight(default_days=7),
        ).pack(anchor="e")

        self._render_ai_insight_panel(main, row=2)
        self._render_guidance_panel(main, row=3)

    def _build_categories_tab(self, parent: ttk.Frame) -> None:
        outer, main, canvas = ui_scroll.make_scrollable_frame(parent, theme=self.theme, chrome_bg=self.theme["bg"])
        outer.pack(fill=tk.BOTH, expand=True)

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

    def _render_ai_insight_panel(self, parent: ttk.Frame, row: int = 0) -> None:
        panel = ttk.LabelFrame(
            parent,
            text="Local AI Insight (optional — Ollama on your machine)",
            padding=12,
            style="Card.TLabelframe",
        )
        panel.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 8))
        ttk.Label(
            panel,
            text=(
                "Summarize your last 7–30 days across life domains, journal, and fitness. "
                "Private, local, no cloud — requires Ollama (see README)."
            ),
            wraplength=900,
        ).pack(anchor="w", pady=(4, 0))
        actions = ttk.Frame(panel)
        actions.pack(anchor="w", pady=(10, 0))
        ttk.Button(
            actions,
            text="Get AI Insight",
            command=lambda: self._show_ai_insight(default_days=7),
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            actions,
            text="Open in Graphs & Progress",
            command=self.show_graphs_ai,
        ).pack(side=tk.LEFT)

    def _render_guidance_panel(self, parent: ttk.Frame, row: int = 0) -> None:
        panel = ttk.LabelFrame(parent, text="Today's Guidance", padding=12, style="Card.TLabelframe")
        panel.grid(row=row, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 8))
        self._guidance_panel = panel
        self._fill_guidance_panel(panel)

    def _fill_guidance_panel(self, panel: ttk.LabelFrame) -> None:
        gap_hint = streak.gap_repair_hint(
            entries=self.entries,
            journal=self.journal,
            sessions=self.sessions,
        )
        if gap_hint:
            ttk.Label(
                panel,
                text=gap_hint,
                wraplength=900,
                style="Accent.TLabel",
            ).pack(anchor="w", pady=(4, 0))
            ttk.Button(
                panel,
                text="Journal for yesterday",
                command=self.open_gap_repair_journal,
            ).pack(anchor="w", pady=(6, 8))

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

        btn_row = ttk.Frame(panel)
        btn_row.pack(anchor="w", pady=(8, 0))
        ttk.Button(btn_row, text="Full Guidance Report", command=self.show_guidance).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(
            btn_row,
            text="AI Insight",
            command=lambda: self._show_ai_insight(default_days=7),
        ).pack(side=tk.LEFT)

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

        footer = ttk.Frame(window)
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=(0, 12))
        ttk.Button(
            footer,
            text="Log exercise for this day",
            command=lambda: (window.destroy(), self.show_log_exercise(date_str)),
        ).pack(side=tk.LEFT)
        ttk.Button(footer, text="Close", command=window.destroy).pack(side=tk.RIGHT)

        header = ttk.Frame(window)
        header.pack(side=tk.TOP, fill=tk.X, padx=15, pady=12)
        ttk.Label(header, text=day_label, font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)

        day_entries = self.entries.get(date_str, {})
        day_fitness_summaries = self._fitness_summaries_for_date(date_str)
        day_journal = journal.entries_for_day(self.journal, datetime.strptime(date_str, "%Y-%m-%d").date())
        ttk.Label(
            header,
            text=f"{len(day_entries)} areas  ·  {len(day_journal)} journal  ·  {len(day_fitness_summaries)} fitness",
            style="Muted.TLabel",
        ).pack(side=tk.RIGHT)

        scroll_host = ttk.Frame(window)
        scroll_host.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        outer, scroll_frame, _canvas = ui_scroll.make_scrollable_frame(
            scroll_host, theme=self.theme, chrome_bg=self.theme["bg"]
        )
        outer.pack(fill=tk.BOTH, expand=True)

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
                ttk.Button(
                    card,
                    text="Open entry",
                    command=lambda eid=item.get("id", ""): self.open_journal_entry(eid, parent=window),
                ).pack(anchor="w", pady=(6, 0))
                row += 1

        if day_fitness_summaries:
            ttk.Label(scroll_frame, text="Fitness sessions", font=("Helvetica", 12, "bold")).grid(
                row=row, column=0, sticky="w", pady=(12, 4)
            )
            row += 1
            for summary in day_fitness_summaries:
                ttk.Label(scroll_frame, text=f"• {summary}", wraplength=620).grid(
                    row=row, column=0, sticky="w"
                )
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

    def _open_log_and_close(self, parent_window: tk.Toplevel, cat_name: str, date_str: str) -> None:
        parent_window.destroy()
        self.open_log_dialog(cat_name, date_str=date_str)

    def open_log_dialog(
        self,
        cat_name: str,
        date_str: str | None = None,
        *,
        on_closed: Callable[[bool], None] | None = None,
    ) -> tk.Toplevel:
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
        checklist_touched: set[str] = set()
        metrics_touched: set[str] = set()

        footer = ttk.Frame(dialog, padding=(15, 12))
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Separator(footer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
        footer_btns = ttk.Frame(footer)
        footer_btns.pack(fill=tk.X)

        outer, inner, _canvas = ui_scroll.make_scrollable_frame(
            dialog, theme=self.theme, chrome_bg=self.theme["bg"]
        )
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
        rating_spin = ttk.Spinbox(
            spin_frame,
            from_=1,
            to=10,
            textvariable=rating_var,
            width=6,
            font=("Helvetica", 14),
        )
        rating_spin.pack(side=tk.LEFT)
        register_rating_spinbox(rating_spin, dialog)
        date_error = make_inline_error_label(date_row, self.theme)
        backdate_error = make_inline_error_label(backdate_frame, self.theme)
        rating_error = make_inline_error_label(spin_frame, self.theme)

        def validate_date_field() -> str | None:
            return journal.validate_backdate(date_var.get().strip(), reason=backdate_var.get().strip())

        def validate_rating_field() -> str | None:
            try:
                raw = rating_var.get()
            except tk.TclError:
                return validate_rating_1_10("")
            return validate_rating_1_10(raw)

        wire_focusout_validation(date_row.winfo_children()[0], validate_date_field, date_error)
        wire_focusout_validation(backdate_entry, validate_date_field, backdate_error)
        wire_focusout_validation(rating_spin, validate_rating_field, rating_error)

        ttk.Label(
            inner,
            text="Checklist — tick what you completed",
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=15, pady=(12, 4))
        for item in cat_data["checklist"]:
            var = tk.BooleanVar(value=False)
            check_vars[item] = var

            def mark_checklist(name=item) -> None:
                checklist_touched.add(name)

            ttk.Checkbutton(
                inner,
                text=item,
                variable=var,
                command=mark_checklist,
            ).pack(anchor="w", padx=25, pady=2)

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
                metric_widget = ttk.Entry(row, textvariable=var, width=12)
                metric_widget.pack(side=tk.LEFT, padx=6)
                if metric_unit:
                    ttk.Label(row, text=metric_unit).pack(side=tk.LEFT)
            else:
                var = tk.IntVar(value=int(existing_val))
                metric_widget = ttk.Spinbox(
                    row,
                    from_=metric.get("min", 1),
                    to=metric.get("max", 10),
                    textvariable=var,
                    width=6,
                )
                metric_widget.pack(side=tk.LEFT, padx=6)
            metric_vars[metric_name] = var

            def mark_metric(_event=None, name=metric_name) -> None:
                metrics_touched.add(name)

            metric_widget.bind("<KeyRelease>", mark_metric, add="+")
            if metric_type != "number":
                metric_widget.bind("<<Increment>>", mark_metric, add="+")
                metric_widget.bind("<<Decrement>>", mark_metric, add="+")

        ttk.Label(
            inner,
            text="General notes / journal entry (write as much as you want)",
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=15, pady=(12, 4))
        notes_text.pack(padx=15, pady=(0, 12), fill=tk.X)

        date_var.trace_add("write", load_existing)
        load_existing()

        def request_close_log(*, saved: bool = False) -> None:
            if getattr(dialog, "_integral_log_save_in_progress", False) and not saved:
                return
            if on_closed is not None and not getattr(dialog, "_integral_log_on_closed_fired", False):
                dialog._integral_log_on_closed_fired = True
                on_closed(saved)
            dialog.destroy()

        dialog._integral_request_close_log = request_close_log

        save_log_btn = ttk.Button(
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
                date_entry=date_row.winfo_children()[0],
                backdate_entry=backdate_entry,
                rating_widget=rating_spin,
                date_error=date_error,
                backdate_error=backdate_error,
                rating_error=rating_error,
                validate_date=validate_date_field,
                validate_rating=validate_rating_field,
                save_log_btn=save_log_btn,
                cancel_log_btn=cancel_log_btn,
                checklist_touched=checklist_touched,
                metrics_touched=metrics_touched,
                cat_data=cat_data,
            ),
        )
        save_log_btn.pack(side=tk.LEFT, padx=(0, 8))
        if cat_name == creative_projects.CREATIVE_CATEGORY:
            ttk.Button(
                footer_btns,
                text="Writing Projects",
                command=lambda: (dialog.destroy(), self.show_writing_projects()),
            ).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Button(
                footer_btns,
                text="Log writing session",
                command=lambda: self.log_writing_session_for_day(date_var.get().strip(), parent=dialog),
            ).pack(side=tk.LEFT, padx=(0, 8))
        cancel_log_btn = ttk.Button(footer_btns, text="Cancel", command=lambda: request_close_log(saved=False))
        cancel_log_btn.pack(side=tk.LEFT)
        dialog.protocol("WM_DELETE_WINDOW", lambda: request_close_log(saved=False))
        from ui_accent import wire_dialog_accent_keys

        wire_dialog_accent_keys(dialog, save_log_btn, cancel_btn=cancel_log_btn)
        ttk.Label(
            footer,
            text="Save stores your rating, checklist, metrics, and notes for this life area.",
            style="Muted.TLabel",
            wraplength=560,
        ).pack(anchor="w", pady=(8, 0))

        return dialog

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
        *,
        date_entry: tk.Misc | None = None,
        backdate_entry: tk.Misc | None = None,
        rating_widget: tk.Misc | None = None,
        date_error: tk.Label | None = None,
        backdate_error: tk.Label | None = None,
        rating_error: tk.Label | None = None,
        validate_date: Callable[[], str | None] | None = None,
        validate_rating: Callable[[], str | None] | None = None,
        save_log_btn: tk.Misc | None = None,
        cancel_log_btn: tk.Misc | None = None,
        checklist_touched: set[str] | None = None,
        metrics_touched: set[str] | None = None,
        cat_data: dict | None = None,
    ) -> None:
        if getattr(dialog, "_integral_log_save_in_progress", False):
            return
        date_str = date_var.get().strip()
        reason = backdate_var.get().strip()
        date_msg = validate_date() if validate_date else journal.validate_backdate(date_str, reason=reason)
        rating_msg = validate_rating() if validate_rating else validate_rating_1_10(rating_var.get())
        pairs: list[tuple[tk.Misc, tk.Label | None, str | None]] = []
        if date_msg:
            parsed = journal.parse_entry_date(date_str)
            if (
                parsed
                and parsed < datetime.now().date()
                and backdate_entry is not None
                and "reason" in date_msg.lower()
            ):
                pairs.append((backdate_entry, backdate_error, date_msg))
            elif date_entry is not None:
                pairs.append((date_entry, date_error, date_msg))
        else:
            set_field_error(date_error, None)
            set_field_error(backdate_error, None)
        if rating_widget is not None:
            pairs.append((rating_widget, rating_error, rating_msg))
        if focus_first_invalid(pairs):
            return

        import copy

        prior_day = copy.deepcopy(self.entries.get(date_str))

        if date_str not in self.entries:
            self.entries[date_str] = {}

        try:
            rating_value = rating_var.get()
        except tk.TclError:
            focus_first_invalid([(rating_widget or dialog, rating_error, validate_rating_1_10(""))])
            return

        cat_def = cat_data if cat_data is not None else self.categories.get(cat_name, {})
        cl_touched = checklist_touched or set()
        m_touched = metrics_touched or set()
        checklist_data = collect_touched_checklist(check_vars, touched=cl_touched)
        metrics_data = collect_touched_metrics(metric_vars, cat_def, touched=m_touched)

        entry_payload = build_entry_payload(
            cat_def,
            rating_value,
            checklist=checklist_data,
            metrics=metrics_data,
            notes=notes_text.get("1.0", tk.END).strip(),
        )
        if entry_payload is None:
            focus_first_invalid([(rating_widget or dialog, rating_error, validate_rating_1_10(""))])
            return
        parsed = journal.parse_entry_date(date_str)
        if parsed and parsed < datetime.now().date():
            entry_payload["backdate_reason"] = reason

        existing = self.entries.get(date_str, {}).get(cat_name, {})
        self.entries[date_str][cat_name] = merge_entry_updates(existing, entry_payload)
        self._invalidate_caches()
        hint = category_insight(self._get_insights(), cat_name)
        guidance_text = None
        if hint and hint.suggested_actions and not self.settings.get("hide_post_log_guidance"):
            guidance_text = f"{hint.message}\n\nTry: {hint.suggested_actions[0]}"

        dialog._integral_log_save_in_progress = True
        if save_log_btn is not None:
            save_log_btn.config(state=tk.DISABLED)
        if cancel_log_btn is not None:
            cancel_log_btn.config(state=tk.DISABLED)

        def on_saved(ok: bool, _err: BaseException | None) -> None:
            from status_banner import _widget_exists

            dialog._integral_log_save_in_progress = False
            if not ok:
                if prior_day is None:
                    self.entries.pop(date_str, None)
                else:
                    self.entries[date_str] = prior_day
                self._invalidate_caches()
                if _widget_exists(save_log_btn):
                    save_log_btn.config(state=tk.NORMAL)
                if _widget_exists(cancel_log_btn):
                    cancel_log_btn.config(state=tk.NORMAL)
                return
            if _widget_exists(dialog):
                close_fn = getattr(dialog, "_integral_request_close_log", None)
                if close_fn is not None:
                    close_fn(saved=True)
                else:
                    dialog.destroy()
            if date_str == self.today_str() and self._reminder_scheduler is not None:
                self._reminder_scheduler.notify_logged_today()
            self.refresh_dashboard()
            banner = self.ensure_status_banner()
            if guidance_text:

                def hide_guidance_forever() -> None:
                    self.settings["hide_post_log_guidance"] = True
                    self.save_data(flush=True)
                    banner.dismiss()

                banner.show_info(
                    f"Saved log for {cat_name}. {guidance_text}",
                    extra_actions=[("Don't show again", hide_guidance_forever)],
                )
            else:
                banner.show_success(f"Saved log for {cat_name} ({date_str}).")

        self.save_data(recompute_fitness=False, flush=True, on_complete=on_saved)

    def show_guidance(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Guidance & Maintenance")
        window.geometry("920x720")
        window.minsize(560, 400)
        window.configure(bg=self.theme["bg"])

        footer = ttk.Frame(window, padding=(12, 10))
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        ai_insight_btn = ttk.Button(
            footer,
            text="AI Insight",
            style="Accent.TButton",
            command=lambda: self._show_ai_insight(default_days=7),
        )
        ai_insight_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(footer, text="Close", command=window.destroy).pack(side=tk.RIGHT)

        ttk.Label(
            window,
            text="Intelligent guidance from your logs — trends, gaps, and next steps",
            font=("Helvetica", 13, "bold"),
        ).pack(side=tk.TOP, anchor="w", padx=12, pady=12)

        text = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Helvetica", 11))
        style_text_widget(text, self.theme)
        text.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        text.insert(tk.END, format_guidance_report(self.insights))

    def show_history(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Full History")
        window.geometry("860x640")
        window.minsize(560, 400)
        window.configure(bg=self.theme["bg"])

        footer = ttk.Frame(window, padding=(12, 10))
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        close_btn = ttk.Button(footer, text="Close", command=window.destroy)
        close_btn.pack(side=tk.RIGHT)
        from ui_accent import wire_escape_cancel

        wire_escape_cancel(window, cancel_btn=close_btn)

        text = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Consolas", 10))
        style_text_widget(text, self.theme)
        text.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)

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
        if nav_items.deep_work_blocks_action(self, item_id="weekly_summary"):
            return
        existing = self._open_windows.get("weekly_summary")
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass
            del self._open_windows["weekly_summary"]
        
        window = tk.Toplevel(self.root)
        self._track_window("weekly_summary", window)
        window.title("Weekly Summary")
        window.geometry("900x680")
        window.minsize(560, 400)
        window.configure(bg=self.theme["bg"])

        footer = ttk.Frame(window, padding=(12, 10))
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        insight_btn = ttk.Button(
            footer,
            text="Get AI Insight",
            style="Accent.TButton",
            command=lambda: self._show_ai_insight(default_days=7),
        )
        insight_btn.pack(side=tk.LEFT)
        ttk.Button(footer, text="Close", command=window.destroy).pack(side=tk.RIGHT)

        end = datetime.now().date()
        start = end - timedelta(days=6)
        ttk.Label(
            window,
            text=f"Week of {start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}",
            font=("Helvetica", 14, "bold"),
        ).pack(side=tk.TOP, anchor="w", padx=12, pady=12)
        ttk.Label(
            window,
            text="Use Get AI Insight below for a local Ollama review of this week.",
            style="Muted.TLabel",
            wraplength=860,
        ).pack(side=tk.TOP, anchor="w", padx=12, pady=(0, 8))

        text = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Helvetica", 11))
        style_text_widget(text, self.theme)
        text.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        week_dates = [(start + timedelta(days=offset)).strftime("%Y-%m-%d") for offset in range(7)]
        days_logged = sum(1 for date in week_dates if date in self.entries)
        text.insert(tk.END, f"Days with any logs: {days_logged}/7\n")
        text.insert(tk.END, f"Overall streak: {self.get_streak()} days\n\n")

        week_insights = analyze_all(
            self.entries,
            self.categories,
            sessions=self.sessions,
            program_state=self.program_state,
            practices=self.practices,
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
        existing = self._open_windows.get("journal")
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass
            del self._open_windows["journal"]
        
        before_children = set(self.root.winfo_children())
        show_journal_window(self)
        self.root.update_idletasks()
        after_children = set(self.root.winfo_children())
        new_windows = after_children - before_children
        for child in new_windows:
            if isinstance(child, tk.Toplevel):
                self._track_window("journal", child)
                break

    def set_quick_capture_enabled(self, enabled: bool, *, persist: bool = True) -> None:
        self.settings = quick_capture.apply_quick_capture_settings(
            self.settings,
            {"enabled": bool(enabled)},
        )
        if persist:
            self.save_data(flush=True)
        if not enabled:
            self.stop_focus_shield()
        self.sync_quick_capture_panel()

    def sync_quick_capture_panel(self) -> None:
        if quick_capture.is_quick_capture_enabled(self.settings):
            open_quick_capture_panel(self)
        else:
            close_quick_capture_panel(self)

    def toggle_quick_capture(self) -> None:
        self.set_quick_capture_enabled(not quick_capture.is_quick_capture_enabled(self.settings))

    def add_todo_quick(self, text: str, category: str | None = None) -> str | None:
        """Add a todo for today with optional category. Return error string or None on success."""
        from category_picker import resolve_category_name

        cleaned = text.strip()
        if not cleaned:
            return None
        
        MAX_TODO_LENGTH = 500
        if len(cleaned) > MAX_TODO_LENGTH:
            return f"Todo text is too long (max {MAX_TODO_LENGTH} characters)."
        
        if category is None:
            category = self.settings.get("last_todo_category", "")
        
        # If the stored category is invalid/missing, fall back to blank
        resolved = resolve_category_name(
            category, list(self.categories.keys()), allow_blank=True
        )
        if resolved is None:
            resolved = ""
        
        try:
            self.todos = todos.add_todo(
                self.todos,
                text=cleaned,
                work_date=self.today_str(),
                category=resolved,
            )
            self.settings["last_todo_category"] = resolved
            self.save_data()
            return None
        except ValueError as exc:
            return str(exc)

    def _restore_inline_todo_focus(self) -> None:
        """Restore focus to inline todo entry after dashboard refresh."""
        if hasattr(self, "_inline_todo_entry"):
            try:
                if self._inline_todo_entry.winfo_exists():
                    self._inline_todo_entry.focus_set()
            except tk.TclError:
                pass
    
    def _clear_error_label(self) -> None:
        """Safely clear inline todo error label after timeout."""
        if hasattr(self, "_inline_error_label"):
            try:
                if self._inline_error_label.winfo_exists():
                    self._inline_error_label.pack_forget()
            except tk.TclError:
                pass
        self._error_timer_id = None

    def show_writing_projects(self) -> None:
        show_writing_projects_window(self)

    def show_log_practice(self, parent=None) -> None:
        from practices_ui import show_practice_log_dialog

        show_practice_log_dialog(self, parent)

    def log_writing_session_for_day(self, day: str | None = None, *, parent=None) -> bool:
        day_str = (day or self.today_str()).strip()
        ok, message = creative_projects.mark_writing_session(
            self.entries,
            self.categories,
            day_str,
        )
        if ok:
            self.save_data(flush=True)
            self.refresh_dashboard(full=False)
            messagebox.showinfo("Writing session", message, parent=parent or self.root)
        else:
            messagebox.showinfo("Writing session", message, parent=parent or self.root)
        return ok

    def show_deep_work(self) -> None:
        if self._deep_work_session and self._deep_work_session.running:
            messagebox.showinfo(
                "Deep Work",
                f"Already in session — {self._deep_work_session.format_mmss()} remaining.",
            )
            return
        show_deep_work_start_dialog(self)

    def start_deep_work(
        self,
        minutes: int,
        *,
        writing_project_id: str | None = None,
        focus_minimize_windows: list | None = None,
    ) -> None:
        if self._deep_work_after_id:
            self.root.after_cancel(self._deep_work_after_id)
            self._deep_work_after_id = None
        self._deep_work_session = deep_work.start_session(minutes)
        self._ensure_deep_work_banner()
        self._apply_deep_work_chrome()
        self._update_deep_work_banner()
        self._schedule_deep_work_tick()
        if focus_minimize_windows:
            self.start_focus_shield(focus_minimize_windows)
        if writing_project_id:
            try:
                open_writing_pair(self, writing_project_id)
            except Exception:
                messagebox.showwarning(
                    "Deep Work",
                    "Session started, but the writing project windows could not be opened.",
                )

    def start_focus_shield(self, minimize_windows: list) -> None:
        self.stop_focus_shield()
        if not focus_shield.is_supported():
            return
        integral_pids = {os.getpid()}
        self._focus_shield.start(
            minimize_windows=minimize_windows,
            integral_pids=integral_pids,
            allowed_pids=set(integral_pids),
        )
        self._schedule_focus_shield_tick()

    def stop_focus_shield(self) -> None:
        if self._focus_shield_after_id:
            try:
                self.root.after_cancel(self._focus_shield_after_id)
            except Exception:
                pass
            self._focus_shield_after_id = None
        self._focus_shield.stop()

    def _schedule_focus_shield_tick(self) -> None:
        if self._focus_shield_after_id:
            try:
                self.root.after_cancel(self._focus_shield_after_id)
            except Exception:
                pass
        if not self._focus_shield.active:
            return
        self._focus_shield.tick()
        self._focus_shield_after_id = self.root.after(1500, self._schedule_focus_shield_tick)

    def end_deep_work(self, *, completed: bool = False) -> None:
        if self._deep_work_after_id:
            self.root.after_cancel(self._deep_work_after_id)
            self._deep_work_after_id = None
        self.stop_focus_shield()
        if self._deep_work_session is not None:
            self._deep_work_session.cancel()
        self._deep_work_session = None
        if self._deep_work_banner is not None:
            try:
                self._deep_work_banner.destroy()
            except tk.TclError:
                pass
        self._deep_work_banner = None
        self._deep_work_timer_label = None
        self._deep_work_extend_btn = None
        self._deep_work_end_btn = None
        # Restore packed nav without tearing down the dashboard (#47).
        self._apply_deep_work_chrome()
        self.sync_quick_capture_panel()
        if completed:
            show_windows_notification("Deep Work", "Session complete. Nice focus.")
            messagebox.showinfo("Deep Work", "Session complete. Chrome restored.")

    def extend_deep_work(self, minutes: int = deep_work.EXTEND_MINUTES) -> None:
        if not self._deep_work_session:
            return
        self._deep_work_session.extend(minutes)
        if not self._deep_work_after_id:
            self._schedule_deep_work_tick()
        self._apply_deep_work_chrome()
        self._update_deep_work_banner()

    def _register_nav_buttons(self, nav: ttk.Frame) -> None:
        self._nav_buttons = {}
        self._nav_pack_order = []
        for child in nav.winfo_children():
            try:
                label = str(child.cget("text"))
            except tk.TclError:
                continue
            if label:
                self._nav_buttons[label] = child
                self._nav_pack_order.append(label)

    def _ensure_deep_work_banner(self, banner_host: ttk.Frame | None = None) -> None:
        if self._deep_work_banner is not None:
            try:
                if self._deep_work_banner.winfo_exists():
                    return
            except tk.TclError:
                self._deep_work_banner = None
        host = banner_host if banner_host is not None else self._banner_host
        if host is None:
            host = ttk.Frame(self.root)
            host.pack(side=tk.TOP, fill=tk.X, padx=16, pady=(0, 4))
        banner = ttk.Frame(host)
        self._deep_work_banner = banner
        self._deep_work_timer_label = ttk.Label(banner, text="", style="Subheading.TLabel")
        self._deep_work_timer_label.pack(side=tk.LEFT)
        self._deep_work_extend_btn = ttk.Button(
            banner, text="+10 min", command=lambda: self.extend_deep_work()
        )
        self._deep_work_extend_btn.pack(side=tk.LEFT, padx=(12, 6))
        self._deep_work_end_btn = ttk.Button(
            banner,
            text="End Deep Work",
            style="TButton",
            command=lambda: self.end_deep_work(completed=False),
        )
        self._deep_work_end_btn.pack(side=tk.LEFT)

    def _apply_deep_work_chrome(self) -> None:
        active = nav_items.deep_work_active(self)
        if active:
            from more_menu_ui import close_more_menu

            close_more_menu(self)
        self._apply_sidebar_deep_work_chrome(active)
        today_more = getattr(self, "_today_more_menu", None)
        if today_more is not None:
            from more_menu_ui import populate_today_more_menu

            try:
                populate_today_more_menu(today_more, self, self.theme)
            except tk.TclError:
                pass
        if self._deep_work_extend_btn is not None:
            try:
                self._deep_work_extend_btn.configure(style="TButton")
            except tk.TclError:
                pass
        if self._deep_work_end_btn is not None:
            try:
                self._deep_work_end_btn.configure(style="TButton")
            except tk.TclError:
                pass
        if self._deep_work_banner is not None:
            try:
                if active:
                    self._deep_work_banner.pack(fill=tk.X, pady=(0, 8))
                    self._focus_deep_work_end_if_sidebar_hidden()
                else:
                    self._deep_work_banner.pack_forget()
            except tk.TclError:
                pass

    def _apply_sidebar_deep_work_chrome(self, active: bool) -> None:
        hidden_any = False
        visible: dict[str, bool] = {}
        for spec in nav_items.sidebar_nav_items():
            hide = active and spec.hide_in_deep_work
            if hide:
                hidden_any = True
            visible[spec.id] = not hide

        nav_container = getattr(self, "_sidebar_nav_container", None)
        if nav_container is not None:
            try:
                if nav_container.winfo_exists():
                    for spec in nav_items.sidebar_nav_items():
                        frame = self._sidebar_nav_frames.get(spec.id)
                        if frame is None:
                            continue
                        try:
                            if frame.winfo_exists():
                                frame.pack_forget()
                        except tk.TclError:
                            continue
                    hint_row = getattr(self, "_sidebar_deep_work_hint_row", None)
                    if hint_row is not None:
                        try:
                            if hint_row.winfo_exists():
                                hint_row.pack_forget()
                        except tk.TclError:
                            pass
                    for spec in nav_items.sidebar_nav_items():
                        if not visible.get(spec.id):
                            continue
                        frame = self._sidebar_nav_frames.get(spec.id)
                        if frame is None:
                            continue
                        try:
                            if frame.winfo_exists():
                                frame.pack(fill=tk.X, padx=8, pady=1)
                        except tk.TclError:
                            continue
                    if (
                        hint_row is not None
                        and self._sidebar_deep_work_hint is not None
                        and active
                        and hidden_any
                    ):
                        try:
                            if hint_row.winfo_exists():
                                hint_row.pack(fill=tk.X, padx=16, pady=(4, 0))
                                if self._sidebar_deep_work_hint.winfo_manager() != "pack":
                                    self._sidebar_deep_work_hint.pack(
                                        fill=tk.X, anchor="w"
                                    )
                        except tk.TclError:
                            pass
            except tk.TclError:
                pass

        goto = self._sidebar_goto_frame
        if goto is not None:
            try:
                if goto.winfo_exists():
                    if active and nav_items.is_hidden_during_deep_work(
                        item_id="goto_palette", tracker=self
                    ):
                        hidden_any = True
                        if goto.winfo_manager():
                            goto.pack_forget()
                    elif goto.winfo_manager() != "pack":
                        goto.pack(fill=tk.X, padx=16, pady=(16, 8))
            except tk.TclError:
                pass

    def _widget_inside(self, widget: tk.Misc | None, ancestor: tk.Misc | None) -> bool:
        if widget is None or ancestor is None:
            return False
        current: tk.Misc | None = widget
        while current is not None:
            if current is ancestor:
                return True
            try:
                current = current.master
            except AttributeError:
                break
        return False

    def _focus_deep_work_end_if_sidebar_hidden(self) -> None:
        end_btn = self._deep_work_end_btn
        if end_btn is None:
            return
        try:
            focus = self.root.focus_get()
        except (KeyError, tk.TclError):
            return
        if focus is None:
            return
        for spec in nav_items.sidebar_nav_items():
            if not spec.hide_in_deep_work:
                continue
            frame = self._sidebar_nav_frames.get(spec.id)
            if self._widget_inside(focus, frame):
                try:
                    end_btn.focus_set()
                except tk.TclError:
                    pass
                return
        if self._widget_inside(focus, self._sidebar_goto_frame):
            try:
                end_btn.focus_set()
            except tk.TclError:
                pass

    def _update_deep_work_banner(self) -> None:
        label = self._deep_work_timer_label
        session = self._deep_work_session
        if label is None:
            return
        try:
            if not label.winfo_exists():
                return
        except tk.TclError:
            return
        if session and session.running:
            label.config(text=f"Deep Work · {session.format_mmss()}")
        else:
            label.config(text="")

    def _schedule_deep_work_tick(self) -> None:
        if self._deep_work_after_id:
            self.root.after_cancel(self._deep_work_after_id)
        self._deep_work_after_id = self.root.after(1000, self._on_deep_work_tick)

    def _on_deep_work_tick(self) -> None:
        self._deep_work_after_id = None
        session = self._deep_work_session
        if not session or not session.running:
            return
        just_done = session.tick(1)
        self._update_deep_work_banner()
        if just_done:
            self.end_deep_work(completed=True)
            return
        self._schedule_deep_work_tick()

    def show_plan_tomorrow(self) -> None:
        show_plan_window(self)

    def show_export(self) -> None:
        show_export_dialog(self)

    def show_backup(self) -> None:
        show_backup_dialog(self)

    def show_security(self) -> None:
        show_security_dialog(self)

    def _clear_streak_details_refs(self) -> None:
        self._streak_details_window = None
        self._notebook = None
        self._categories_tab_frame = None
        self._categories_tab_built = False
        self._activity_grid = None
        self._guidance_panel = None
        self._overview_stats_label = None

    def _close_streak_details_window(self) -> None:
        win = self._streak_details_window
        self._clear_streak_details_refs()
        if win is None:
            return
        try:
            if win.winfo_exists():
                win.destroy()
        except tk.TclError:
            pass

    def _mount_overview_categories_notebook(
        self,
        parent: tk.Misc,
        *,
        select_categories: bool = False,
    ) -> ttk.Notebook:
        """Build the Overview / Categories notebook (lives in the streak details window)."""
        self._invalidate_caches()
        self.insights = self._get_insights()

        notebook = ttk.Notebook(parent)
        self._notebook = notebook
        notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(8, 8))

        overview = ttk.Frame(notebook)
        categories_tab = ttk.Frame(notebook)
        self._categories_tab_frame = categories_tab
        self._categories_tab_built = False
        notebook.add(overview, text="Overview")
        notebook.add(categories_tab, text="Categories")
        notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)

        self._build_overview_tab(overview)
        if select_categories:
            notebook.select(1)
            self._build_categories_tab(categories_tab)
            self._categories_tab_built = True
        return notebook

    def show_streak_details(self, category: str | None = None) -> None:
        """Open Overview / Categories in a separate window (not crushed under Today's Log)."""
        existing = getattr(self, "_streak_details_window", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    if category and self._notebook is not None:
                        self._notebook.select(1)
                        if not self._categories_tab_built and self._categories_tab_frame is not None:
                            self._build_categories_tab(self._categories_tab_frame)
                            self._categories_tab_built = True
                    return
            except tk.TclError:
                self._clear_streak_details_refs()

        window = tk.Toplevel(self.root)
        self._streak_details_window = window
        window.title(f"Overview & Categories · {self.get_streak()} day streak")
        window.geometry("980x720")
        window.minsize(720, 520)
        window.transient(self.root)
        window.configure(bg=self.theme["bg"])

        def close_details() -> None:
            try:
                window.destroy()
            except tk.TclError:
                pass
            self._clear_streak_details_refs()

        window.protocol("WM_DELETE_WINDOW", close_details)

        footer = ttk.Frame(window, padding=(12, 10))
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        gap = streak.gap_repair_hint(
            entries=self.entries,
            journal=self.journal,
            sessions=self.sessions,
        )
        if gap:
            gap_btn = ttk.Button(
                footer,
                text="Journal for yesterday",
                style="Accent.TButton",
                command=lambda: (close_details(), self.open_gap_repair_journal()),
            )
            gap_btn.pack(side=tk.LEFT)
            ttk.Button(footer, text="Close", command=close_details).pack(side=tk.RIGHT)
        else:
            close_details_btn = ttk.Button(footer, text="Close", command=close_details)
            close_details_btn.pack(side=tk.RIGHT)

        header = ttk.Frame(window, padding=(12, 12))
        header.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(
            header,
            text=f"🔥 {self.get_streak()} day streak",
            style="Heading.TLabel",
        ).pack(side=tk.LEFT)
        ttk.Label(
            header,
            text="Activity grid, guidance, and domain cards — full size so you can actually read them.",
            style="Muted.TLabel",
            wraplength=700,
        ).pack(side=tk.LEFT, padx=(12, 0))

        self._mount_overview_categories_notebook(
            window,
            select_categories=bool(category),
        )

    def show_goto(self) -> None:
        from goto_ui import open_goto_palette
        from more_menu_ui import close_more_menu

        close_more_menu(self)
        open_goto_palette(self)

    def _toggle_footer_more_menu(self) -> None:
        from more_menu_ui import toggle_more_menu

        if self._footer_more_btn is not None:
            toggle_more_menu(self, self._footer_more_btn)

    def _toggle_sidebar_more_menu(self) -> None:
        from more_menu_ui import toggle_more_menu

        btn = getattr(self, "_sidebar_more_btn", None)
        if btn is not None:
            toggle_more_menu(self, btn)

    def show_search(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Search Notes")
        window.geometry("860x640")
        window.minsize(560, 400)
        window.configure(bg=self.theme["bg"])

        footer = ttk.Frame(window, padding=(12, 10))
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        close_btn = ttk.Button(footer, text="Close", command=window.destroy)
        close_btn.pack(side=tk.RIGHT)
        from ui_accent import wire_escape_cancel

        wire_escape_cancel(window, cancel_btn=close_btn)

        search_frame = ttk.Frame(window)
        search_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        query_var = tk.StringVar()
        entry = ttk.Entry(search_frame, textvariable=query_var, width=50)
        entry.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

        results = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Consolas", 10))
        style_text_widget(results, self.theme)
        results.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

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
                open_mark = results.index(tk.END)
                results.insert(tk.END, "[Open entry]\n")
                results.insert(tk.END, "-" * 40 + "\n")
                tag = f"open_journal_{item.get('id')}"
                results.tag_add(tag, open_mark, f"{open_mark} lineend")
                results.tag_config(tag, foreground=self.theme.get("accent", "#5B8DEF"), underline=True)
                results.tag_bind(
                    tag,
                    "<Button-1>",
                    lambda _e, eid=item.get("id", ""): self.open_journal_entry(eid, parent=window),
                )

            if hits:
                from journal_ui import apply_integral_link_tags

                apply_integral_link_tags(
                    results,
                    on_open=lambda link: self.open_integral_link(link, parent=window),
                    link_color=self.theme.get("accent", "#5B8DEF"),
                )

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
        existing = self._open_windows.get("graphs")
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass
            del self._open_windows["graphs"]
        
        from graphs import open_graphs
        before_children = set(self.root.winfo_children())
        open_graphs(
            self.root,
            self.entries,
            self.categories,
            self.theme,
            journal_data=self.journal,
            fitness_settings=self.settings.get("fitness"),
            app_settings=self.settings,
            on_graph_settings_changed=self._save_graph_settings,
        )
        self.root.update_idletasks()
        after_children = set(self.root.winfo_children())
        new_windows = after_children - before_children
        for child in new_windows:
            if isinstance(child, tk.Toplevel):
                self._track_window("graphs", child)
                break

    def _save_graph_settings(self, payload: dict) -> None:
        self.settings["graphs"] = payload.get("graphs", {})
        self.save_data(flush=True)

    def show_graphs_ai(self) -> None:
        from graphs import open_graphs

        open_graphs(
            self.root,
            self.entries,
            self.categories,
            self.theme,
            journal_data=self.journal,
            fitness_settings=self.settings.get("fitness"),
            app_settings=self.settings,
            on_graph_settings_changed=self._save_graph_settings,
            initial_tab="ai_insight",
        )

    def _show_ai_insight(self, *, default_days: int = 7) -> None:
        import ai_insights

        ai_insights.show_insight_dialog(
            self.root,
            self.theme,
            entries=self.entries,
            categories=self.categories,
            journal_data=self.journal,
            fitness_settings=self.settings.get("fitness"),
            default_days=default_days,
        )

    def _on_fitness_session_saved(
        self,
        session_date: str,
        *,
        on_complete: Callable[[bool, BaseException | None], None] | None = None,
    ) -> None:
        bridge_fitness_to_daily_entries(self.entries, session_date)
        self._fitness_state_dirty = True
        self._invalidate_session_counts()
        self._invalidate_caches()
        self.refresh_dashboard()
        self.save_data(recompute_fitness=True, flush=True, on_complete=on_complete)
        self._refresh_workout_history_view()

    def _refresh_workout_history_view(self) -> None:
        if hasattr(self, "_workout_history_view") and self._workout_history_view:
            try:
                self._workout_history_view.refresh()
            except Exception:
                pass

    def _fitness_session_count_for_date(self, date_str: str) -> int:
        return self._activity_session_counts().get(date_str, 0)

    def _fitness_summaries_for_date(self, date_str: str) -> list[str]:
        summaries: list[str] = []
        for session in self.sessions:
            if session.get("date") != date_str:
                continue
            program = self.programs.get(session.get("program_id", ""), {})
            label = program.get("name", session.get("program_id", "Fitness"))
            note = session.get("notes", "")
            summaries.append(f"{label}" + (f" — {note[:80]}" if note else ""))

        try:
            from fitness_ui import get_profile_repo
            from progression.sessions import format_session_summary

            repo = get_profile_repo(self.settings.get("fitness"))
            repo.initialize()
            for session in repo.list_workout_sessions(limit=5000):
                if session.date != date_str:
                    continue
                summary = format_session_summary(repo, session)
                lines = [line.strip() for line in summary.splitlines() if line.strip()]
                if len(lines) > 1:
                    summaries.append(lines[1].lstrip("• "))
                elif lines:
                    summaries.append(f"Workout logged ({lines[0].replace('Date: ', '')})")
                else:
                    summaries.append("Workout logged")
        except Exception:
            pass
        return summaries

    def show_log_exercise(self, date_str: str | None = None) -> None:
        import fitness_ui

        existing = getattr(self, "_log_exercise_dialog", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass
            self._log_exercise_dialog = None

        target = date_str or self.today_str()
        repo = fitness_ui.get_profile_repo(self.settings.get("fitness"))
        fitness_ui.ensure_fitness_seeded(repo, self.settings.get("fitness"))
        dialog = fitness_ui.open_new_session_dialog(
            self.root,
            repo,
            initial_date=target,
            on_session_saved=self._on_fitness_session_saved,
            fitness_settings=self.settings.get("fitness"),
            theme=self.theme,
            tracker=self,
        )
        self._log_exercise_dialog = dialog

        def clear_log_dialog_ref(_event: tk.Event | None = None) -> None:
            if getattr(self, "_log_exercise_dialog", None) is dialog:
                self._log_exercise_dialog = None

        dialog.bind("<Destroy>", clear_log_dialog_ref, add="+")

    def show_fitness_hub(self) -> None:
        if nav_items.deep_work_blocks_action(self, item_id="fitness_hub"):
            return
        existing = self._open_windows.get("fitness")
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except tk.TclError:
                pass
            del self._open_windows["fitness"]
        
        import fitness_ui

        def on_fitness_settings_changed(updated: dict) -> None:
            self.settings["fitness"] = updated
            self.save_data(flush=True)

        before_children = set(self.root.winfo_children())
        fitness_ui.show_fitness_window(
            self.root,
            on_session_saved=self._on_fitness_session_saved,
            theme=self.theme,
            fitness_settings=self.settings.get("fitness"),
            on_fitness_settings_changed=on_fitness_settings_changed,
            on_log_practice=self.show_log_practice,
            tracker=self,
        )
        self.root.update_idletasks()
        after_children = set(self.root.winfo_children())
        new_windows = after_children - before_children
        for child in new_windows:
            if isinstance(child, tk.Toplevel):
                self._track_window("fitness", child)
                break

    def show_workout_history(self) -> None:
        """Show workout history in a modal window."""
        import fitness_ui
        from workout_history_ui import WorkoutHistoryView
        
        # Check if window already exists
        if hasattr(self, '_workout_history_window') and self._workout_history_window and self._workout_history_window.winfo_exists():
            self._workout_history_window.lift()
            self._workout_history_window.focus_set()
            return
        
        repo = fitness_ui.get_profile_repo(self.settings.get("fitness"))
        fitness_ui.ensure_fitness_seeded(repo, self.settings.get("fitness"))
        
        win = tk.Toplevel(self.root)
        win.title("Workout History")
        win.geometry("1000x600")
        win.minsize(800, 500)
        win.configure(bg=self.theme["bg"])
        win.transient(self.root)
        self._workout_history_window = win
        
        def on_log_workout_with_refresh():
            # Store view reference before opening log
            view_ref = self._workout_history_view if hasattr(self, '_workout_history_view') else None
            self.show_log_exercise()
            # Note: actual refresh happens via _on_fitness_session_saved callback
        
        history_view = WorkoutHistoryView(
            parent=win,
            repo=repo,
            theme=self.theme,
            on_log_workout=on_log_workout_with_refresh,
        )
        self._workout_history_view = history_view
        
        def on_close():
            history_view.destroy()
            win.destroy()
            self._workout_history_window = None
            if hasattr(self, '_workout_history_view'):
                delattr(self, '_workout_history_view')
        
        win._on_close_callback = on_close
        win.protocol("WM_DELETE_WINDOW", on_close)

    def show_settings(self) -> None:
        editor = tk.Toplevel(self.root)
        editor.title("Edit Categories")
        editor.geometry("920x640")
        editor.minsize(720, 480)
        editor.configure(bg=self.theme["bg"])
        editor.transient(self.root)
        editor.grab_set()

        working = json.loads(json.dumps(self.categories))

        buttons = ttk.Frame(editor)
        buttons.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 12))
        add_btn = ttk.Button(buttons, text="Add Category")
        add_btn.pack(side=tk.LEFT)
        delete_btn = ttk.Button(buttons, text="Delete Category")
        delete_btn.pack(side=tk.LEFT, padx=8)
        save_cat_btn = ttk.Button(buttons, text="Save Category")
        save_cat_btn.pack(side=tk.LEFT, padx=8)
        reset_btn = ttk.Button(buttons, text="Reset Defaults")
        reset_btn.pack(side=tk.LEFT, padx=8)
        template_btn = ttk.Button(buttons, text="Apply Template…")
        template_btn.pack(side=tk.LEFT, padx=8)
        save_close_btn = ttk.Button(buttons, text="Save & Close")
        save_close_btn.pack(side=tk.RIGHT)
        cancel_btn = ttk.Button(buttons, text="Cancel", command=editor.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=8)
        from ui_accent import wire_escape_cancel

        wire_escape_cancel(editor, cancel_btn=cancel_btn)

        body = ttk.Frame(editor)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=12)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        ttk.Label(body, text="Categories").grid(row=0, column=0, sticky="nw")
        category_list = tk.Listbox(body, height=20, width=28, exportselection=False)
        category_list.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        style_listbox(category_list, self.theme)
        ui_scroll.bind_mousewheel(category_list, category_list.yview)

        editor_host = ttk.Frame(body)
        editor_host.grid(row=0, column=1, sticky="nsew")
        editor_host.rowconfigure(0, weight=1)
        editor_host.columnconfigure(0, weight=1)
        outer, editor_panel, _canvas = ui_scroll.make_scrollable_frame(
            editor_host, theme=self.theme, chrome_bg=self.theme["bg"]
        )
        outer.grid(row=0, column=0, sticky="nsew")

        ttk.Label(editor_panel, text="Category name").grid(row=0, column=0, sticky="w")
        name_var = tk.StringVar()
        name_entry = ttk.Entry(editor_panel, textvariable=name_var, width=50)
        name_entry.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(editor_panel, text="Checklist items (one per line)").grid(row=2, column=0, sticky="w")
        checklist_text = scrolledtext.ScrolledText(editor_panel, height=8, wrap=tk.WORD)
        style_text_widget(checklist_text, self.theme)
        checklist_text.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(editor_panel, text="Metrics (name | type | unit | default)").grid(row=4, column=0, sticky="w")
        metrics_text = scrolledtext.ScrolledText(editor_panel, height=8, wrap=tk.WORD)
        style_text_widget(metrics_text, self.theme)
        metrics_text.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        editor_panel.columnconfigure(0, weight=1)

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

        def apply_template() -> None:
            def merge(template_id: str) -> None:
                merged, added, skipped = domain_templates.apply_template(working, template_id)
                working.clear()
                working.update(merged)
                refresh_list(added[0] if added else next(iter(working.keys()), None))
                message = f"Added {len(added)} domain(s). Save & Close to keep them."
                if skipped:
                    message += f" Skipped {len(skipped)} already present."
                messagebox.showinfo("Template applied", message, parent=editor)

            show_template_picker(self, editor, on_apply=merge)

        add_btn.configure(command=add_category)
        delete_btn.configure(command=delete_category)
        save_cat_btn.configure(command=save_category)
        reset_btn.configure(command=reset_defaults)
        template_btn.configure(command=apply_template)
        save_close_btn.configure(command=save_all)

        refresh_list(next(iter(working.keys())))


def main() -> None:
    import atexit
    import sys

    import deep_links

    protocol_url = deep_links.extract_protocol_arg(sys.argv)
    owns_lock = deep_links.acquire_instance_lock()
    if protocol_url and not owns_lock:
        # Another Integral is running — hand off the link and exit.
        deep_links.write_pending_link(protocol_url)
        return

    if owns_lock:
        atexit.register(deep_links.release_instance_lock)

    root = tk.Tk()
    app = PersonalDevelopmentTracker(root)
    if protocol_url:
        app._startup_deep_link = protocol_url
    if root.winfo_exists():
        root.mainloop()


if __name__ == "__main__":
    main()

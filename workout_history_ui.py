"""Workout history UI - embedded two-pane view with keyset paging."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from datetime import datetime
from typing import Callable

from progression.db import FitnessRepository, WorkoutSession, WorkoutSet
from progression.recent_compare import compare_to_previous_session
from progression.sessions import fitness_db_file_label, is_fitness_db_lock_error
from progression.workout_pr import (
    ExerciseBests,
    format_best_display,
    pr_badge_label,
    pr_badges_for_sets,
    resolve_display_bests,
)
from status_banner import StatusBanner
from workout_history_sparkline import (
    best_set_metric_for_rows,
    default_sparkline_height,
    draw_sparkline,
    format_metric_display,
    sparkline_accessibility_summary,
)


def format_date_display(iso_date: str) -> str:
    """Format ISO date as 'Tue Oct 14'."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%a %b %d")
    except (ValueError, AttributeError):
        return iso_date


def format_month_header(iso_date: str) -> str:
    """Format ISO date as 'October 2026'."""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%B %Y")
    except (ValueError, AttributeError):
        return iso_date


def calculate_session_volume(sets: list[WorkoutSet], repo: FitnessRepository) -> tuple[float, str, int]:
    """Calculate total volume for weighted exercises only.
    
    Returns:
        (volume, unit, weighted_exercise_count)
        volume: sum of sets × reps × kg for weighted exercises
        unit: "kg" or ""
        weighted_exercise_count: count of exercises with weight
    """
    total_volume = 0.0
    weighted_count = 0
    seen_exercises = set()
    
    for wset in sets:
        if wset.exercise_id not in seen_exercises:
            seen_exercises.add(wset.exercise_id)
            if wset.weight_kg and wset.weight_kg > 0:
                weighted_count += 1
        
        if wset.weight_kg and wset.weight_kg > 0:
            s = wset.sets or 1
            r = wset.reps or 0
            total_volume += s * r * wset.weight_kg
    
    if weighted_count > 0:
        return (total_volume, "kg", weighted_count)
    return (0.0, "", 0)


def calculate_exercise_volume(wset: WorkoutSet) -> tuple[float, str]:
    """Calculate volume for one set entry.
    
    Returns:
        (volume, unit)
    """
    s = wset.sets or 1
    
    if wset.weight_kg and wset.weight_kg > 0:
        r = wset.reps or 0
        return (s * r * wset.weight_kg, "kg")
    elif wset.hold_seconds and wset.hold_seconds > 0:
        return (s * wset.hold_seconds, "s")
    elif wset.reps and wset.reps > 0:
        return (s * wset.reps, "reps")
    
    return (0.0, "")


def count_exercise_indicators(session: WorkoutSession, sets: list[WorkoutSet], repo: FitnessRepository) -> tuple[int, int, int]:
    """Count ↑/=/↓ indicators for exercises in this session vs previous.
    
    Returns:
        (up_count, same_count, down_count)
    """
    up, same, down = 0, 0, 0
    seen_exercises = set()
    
    for wset in sets:
        if wset.exercise_id in seen_exercises:
            continue
        seen_exercises.add(wset.exercise_id)
        
        comparison = compare_to_previous_session(
            repo=repo,
            current_session_id=session.id,
            exercise_id=wset.exercise_id,
            current_date=session.date,
            current_created_at=session.created_at,
        )
        
        trend = comparison.get("trend", "")
        if trend == "up":
            up += 1
        elif trend == "same":
            same += 1
        elif trend == "down":
            down += 1
    
    return (up, same, down)


def format_session_row_text(
    session: WorkoutSession,
    sets: list[WorkoutSet],
    repo: FitnessRepository,
) -> str:
    """Format session row as: 'Tue Oct 14 · 5 exercises · 45 min · volume'."""
    date_str = format_date_display(session.date)
    
    exercise_ids = list({wset.exercise_id for wset in sets})
    exercise_count = len(exercise_ids)
    
    parts = [date_str, f"{exercise_count} exercises"]
    
    if session.duration_minutes:
        parts.append(f"{session.duration_minutes} min")
    
    volume, unit, weighted_count = calculate_session_volume(sets, repo)
    if weighted_count > 0:
        parts.append(f"{volume:.1f} {unit}")
    
    return " · ".join(parts)


class WorkoutHistoryView:
    """Embedded two-pane workout history view."""
    
    def __init__(
        self,
        parent: tk.Widget,
        repo: FitnessRepository,
        theme: dict,
        on_repeat_session: Callable[[str], None] | None = None,
        on_delete_session: Callable[[str], None] | None = None,
        on_log_workout: Callable[[], None] | None = None,
    ):
        self.parent = parent
        self.repo = repo
        self.theme = theme
        self.on_repeat_session = on_repeat_session
        self.on_delete_session = on_delete_session
        self.on_log_workout = on_log_workout
        
        self.container = ttk.Frame(parent, style="Surface.TFrame")
        self.sessions: list[WorkoutSession] = []
        self.sets_by_session: dict[str, list[WorkoutSet]] = {}
        self.selected_session: WorkoutSession | None = None
        self.filter_text = ""
        self.has_more = True
        self.is_loading = False
        self.loading_after_id: str | None = None
        self._conn = self.repo.connect(timeout=10.0)  # Reused connection
        self.detail_mode = "session"
        self.selected_exercise_id: str | None = None
        self._focused_exercise_id: str | None = None
        self.exercise_sessions: list[WorkoutSession] = []
        self.exercise_sets_by_session: dict[str, list[WorkoutSet]] = {}
        self.exercise_has_more = True
        self._exercise_spark_values: list[float] = []
        self._exercise_spark_dates: list[str] = []
        self._exercise_spark_kind = ""
        
        self._build_ui()
        self._load_first_page()
    
    def _build_ui(self) -> None:
        """Build the two-pane layout."""
        self.container.pack(fill=tk.BOTH, expand=True)
        
        toolbar = ttk.Frame(self.container, style="Surface.TFrame")
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(10, 5))
        
        ttk.Label(toolbar, text="Filter:", style="OnSurface.TLabel").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar()
        self.filter_entry = ttk.Entry(toolbar, textvariable=self.filter_var, width=30)
        self.filter_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.filter_var.trace_add("write", lambda *args: self._on_filter_changed())
        
        ttk.Label(
            toolbar,
            text="(Ctrl+F to focus)",
            style="OnSurfaceMuted.TLabel",
            font=("Helvetica", 9),
        ).pack(side=tk.LEFT)
        
        paned = ttk.PanedWindow(self.container, orient=tk.HORIZONTAL)
        paned.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        list_frame = ttk.Frame(paned, style="Surface.TFrame")
        paned.add(list_frame, weight=1)
        
        self.session_list = tk.Listbox(
            list_frame,
            height=20,
            width=40,
            exportselection=False,
            font=("Helvetica", 10),
            bg=self.theme["surface"],
            fg=self.theme["fg"],
            selectbackground=self.theme["accent"],
            selectforeground=self.theme["surface"],
            highlightthickness=1,
            highlightcolor=self.theme["accent"],
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.session_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.session_list.yview)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.session_list.config(yscrollcommand=list_scroll.set)
        
        self.session_list.bind("<<ListboxSelect>>", lambda e: self._on_session_selected())
        self.session_list.bind("<Up>", lambda e: self._on_arrow_key())
        self.session_list.bind("<Down>", lambda e: self._on_arrow_key())
        self.session_list.bind("<Home>", lambda e: self._on_home_key())
        self.session_list.bind("<End>", lambda e: self._on_end_key())
        self.session_list.bind("<Return>", lambda e: self._on_enter_key())
        self.session_list.bind("<Escape>", lambda e: self._on_escape_from_list())
        
        detail_frame = ttk.Frame(paned, style="Surface.TFrame")
        paned.add(detail_frame, weight=2)

        self._status_banner = StatusBanner(detail_frame, self.theme)

        self.detail_stack = ttk.Frame(detail_frame, style="Surface.TFrame")
        self.detail_stack.pack(fill=tk.BOTH, expand=True)

        from tkinter import scrolledtext
        self.detail_text = scrolledtext.ScrolledText(
            self.detail_stack,
            wrap=tk.WORD,
            font=("Helvetica", 10),
            bg=self.theme["surface"],
            fg=self.theme["fg"],
            relief=tk.FLAT,
            borderwidth=0,
            state=tk.DISABLED,
        )
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self.detail_text.bind("<Escape>", lambda e: self._on_escape_from_detail())
        self.detail_text.bind("<Return>", lambda e: self._on_enter_in_session_detail())
        self.detail_text.bind("<Button-1>", lambda e: self._on_detail_click(e), add="+")

        self.exercise_panel = ttk.Frame(self.detail_stack, style="Surface.TFrame")
        header = ttk.Frame(self.exercise_panel, style="Surface.TFrame")
        header.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(0, 4))
        self.exercise_title = ttk.Label(header, text="", style="OnSurfaceSubheading.TLabel")
        self.exercise_title.pack(side=tk.TOP, anchor=tk.W)
        self.exercise_pr_label = ttk.Label(header, text="", style="OnSurface.TLabel")
        self.exercise_pr_label.pack(side=tk.TOP, anchor=tk.W, pady=(2, 6))

        spark_frame = ttk.Frame(self.exercise_panel, style="Surface.TFrame")
        spark_frame.pack(side=tk.TOP, fill=tk.X, padx=4, pady=(0, 6))
        spark_h = default_sparkline_height(self.container)
        self.sparkline_canvas = tk.Canvas(
            spark_frame, height=spark_h, bg=self.theme["surface"], highlightthickness=0
        )
        self.sparkline_canvas.pack(fill=tk.X, expand=True)
        self.sparkline_sr = tk.Label(
            spark_frame,
            text="",
            wraplength=480,
            justify=tk.LEFT,
            bg=self.theme["surface"],
            fg=self.theme["fg"],
            font=("Helvetica", 9),
        )
        self.sparkline_sr.pack(fill=tk.X, pady=(4, 0))

        ex_list_frame = ttk.Frame(self.exercise_panel, style="Surface.TFrame")
        ex_list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.exercise_session_list = tk.Listbox(
            ex_list_frame,
            height=12,
            exportselection=False,
            font=("Helvetica", 10),
            bg=self.theme["surface"],
            fg=self.theme["fg"],
            selectbackground=self.theme["accent"],
            selectforeground=self.theme["surface"],
            highlightthickness=1,
            highlightcolor=self.theme["accent"],
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.exercise_session_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ex_scroll = ttk.Scrollbar(ex_list_frame, orient=tk.VERTICAL, command=self.exercise_session_list.yview)
        ex_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.exercise_session_list.config(yscrollcommand=ex_scroll.set)
        self.exercise_session_list.bind("<Escape>", lambda e: self._close_exercise_view())
        self.exercise_load_more_btn = ttk.Button(
            self.exercise_panel,
            text="Load more",
            command=self._load_next_exercise_page,
        )
        
        self.load_more_btn = ttk.Button(
            self.container,
            text="Load more",
            command=self._load_next_page,
        )
        
        self.empty_label = ttk.Label(
            self.container,
            text="No workouts yet",
            style="OnSurfaceSubheading.TLabel",
        )
        
        self.empty_log_btn = ttk.Button(
            self.container,
            text="Log workout",
            style="Accent.TButton",
            command=self.on_log_workout if self.on_log_workout else lambda: None,
        )
        
        self.loading_label = ttk.Label(
            self.container,
            text="Loading...",
            style="OnSurfaceMuted.TLabel",
        )
        
        self._ctrl_f_binding = self.container.bind_all("<Control-f>", lambda e: self._focus_filter())
    
    def _focus_filter(self) -> None:
        """Focus the filter entry (Ctrl+F)."""
        self.filter_entry.focus_set()
        self.filter_entry.selection_range(0, tk.END)
    
    def _on_filter_changed(self) -> None:
        """Reload when filter changes."""
        self.filter_text = self.filter_var.get().strip()
        self.sessions.clear()
        self.sets_by_session.clear()
        self.selected_session = None
        self.has_more = True
        if self.load_more_btn.winfo_ismapped():
            self.load_more_btn.pack_forget()
        self._load_first_page()
    
    def _load_first_page(self) -> None:
        """Load the first page of sessions."""
        self._show_loading_indicator()
        self.container.after(10, self._do_load_first_page)
    
    def _do_load_first_page(self) -> None:
        """Actually load the first page (after brief delay for loading indicator)."""
        self.is_loading = True
        try:
            sessions = self.repo.list_workout_sessions_page(
                limit=20,
                exercise_filter=self.filter_text or None,
            )
            
            if not sessions:
                self._hide_loading_indicator()
                self._hide_empty_state()
                self._show_empty_state()
                return
            
            session_ids = [s.id for s in sessions]
            sets_dict = self.repo.list_workout_sets_batch(session_ids)
            
            self.sessions = sessions
            self.sets_by_session = sets_dict
            self.has_more = len(sessions) >= 20
            
            self._hide_loading_indicator()
            self._hide_empty_state()
            self._refresh_session_list()
            
            if sessions:
                # Select first session row (skip month header)
                first_session_idx = self._get_listbox_index_for_session(0)
                if first_session_idx is not None:
                    self.session_list.selection_set(first_session_idx)
                    self.session_list.see(first_session_idx)
                self.selected_session = sessions[0]
                self._display_session_detail(sessions[0])
        except Exception as e:
            self._hide_loading_indicator()
            self._handle_db_error(e, "Error loading sessions")
        finally:
            self.is_loading = False
    
    def _load_next_page(self) -> None:
        """Load the next page of sessions."""
        if self.is_loading or not self.has_more or not self.sessions:
            return
        
        self.is_loading = True
        last_session = self.sessions[-1]
        
        try:
            sessions = self.repo.list_workout_sessions_page(
                limit=20,
                before_date=last_session.date,
                before_id=last_session.id,
                exercise_filter=self.filter_text or None,
            )
            
            if not sessions:
                self.has_more = False
                if self.load_more_btn.winfo_ismapped():
                    self.load_more_btn.pack_forget()
                return
            
            session_ids = [s.id for s in sessions]
            sets_dict = self.repo.list_workout_sets_batch(session_ids)
            
            self.sessions.extend(sessions)
            self.sets_by_session.update(sets_dict)
            self.has_more = len(sessions) >= 20
            
            # Store current selection to restore after refresh
            current_selection = self.selected_session
            
            self._refresh_session_list()
            
            # Restore selection
            if current_selection:
                try:
                    session_idx = next(i for i, s in enumerate(self.sessions) if s.id == current_selection.id)
                    listbox_idx = self._get_listbox_index_for_session(session_idx)
                    if listbox_idx is not None:
                        self.session_list.selection_clear(0, tk.END)
                        self.session_list.selection_set(listbox_idx)
                        self.session_list.see(listbox_idx)
                except (StopIteration, ValueError):
                    pass
        except Exception as e:
            self._handle_db_error(e, "Error loading more sessions")
        finally:
            self.is_loading = False

    def _handle_db_error(self, error: BaseException, prefix: str) -> None:
        if is_fitness_db_lock_error(error):
            self._status_banner.show_error(
                f"{prefix}: {error}",
                file_name=fitness_db_file_label(self.repo),
            )
            return
        import tkinter.messagebox as messagebox

        messagebox.showerror(prefix, str(error), parent=self.container.winfo_toplevel())

    def _set_detail_readonly(self, readonly: bool) -> None:
        """Keep session detail readable and keyboard-accessible (Enter on exercise links)."""
        self.detail_text.config(state=tk.NORMAL)
        if readonly:
            self.detail_text.config(cursor="arrow")
            if not getattr(self, "_detail_readonly_bound", False):
                self.detail_text.bind("<Key>", self._detail_readonly_key)
                self._detail_readonly_bound = True
        else:
            self.detail_text.config(cursor="xterm")

    def _detail_readonly_key(self, event: tk.Event) -> str | None:
        sym = event.keysym
        if sym in ("Return", "Escape", "Shift_L", "Shift_R", "Control_L", "Control_R"):
            return None
        if (event.state & 0x4) and sym.lower() in ("c", "a"):
            return None
        if sym in ("Left", "Right", "Up", "Down", "Prior", "Next", "Home", "End"):
            return None
        return "break"

    def _show_loading_indicator(self) -> None:
        """Show loading indicator after a delay."""
        if self.loading_after_id is not None:
            self.container.after_cancel(self.loading_after_id)
        
        def show():
            if self.is_loading:
                self.loading_label.pack(side=tk.TOP, pady=20)
        
        self.loading_after_id = self.container.after(150, show)
    
    def _hide_loading_indicator(self) -> None:
        """Hide loading indicator."""
        if self.loading_after_id is not None:
            self.container.after_cancel(self.loading_after_id)
            self.loading_after_id = None
        
        if self.loading_label.winfo_ismapped():
            self.loading_label.pack_forget()
    
    def _show_empty_state(self) -> None:
        """Show empty state with Log workout button."""
        self.session_list.delete(0, tk.END)
        self._set_detail_readonly(False)
        self.detail_text.delete("1.0", tk.END)
        self._set_detail_readonly(True)
        
        if not self.empty_label.winfo_ismapped():
            self.empty_label.pack(side=tk.TOP, pady=20)
        
        if self.on_log_workout and not self.empty_log_btn.winfo_ismapped():
            self.empty_log_btn.pack(side=tk.TOP, pady=10)
    
    def _refresh_session_list(self) -> None:
        """Refresh the session list display."""
        self.session_list.delete(0, tk.END)
        
        if not self.sessions:
            return
        
        current_month = None
        for i, session in enumerate(self.sessions):
            month = format_month_header(session.date)
            if month != current_month:
                self.session_list.insert(tk.END, f"─── {month} ───")
                self.session_list.itemconfig(tk.END, fg=self.theme["muted"])
                current_month = month
            
            sets = self.sets_by_session.get(session.id, [])
            row_text = format_session_row_text(session, sets, self.repo)
            self.session_list.insert(tk.END, row_text)
        
        if self.has_more and not self.is_loading:
            self.load_more_btn.pack(side=tk.TOP, pady=10)
        else:
            if self.load_more_btn.winfo_ismapped():
                self.load_more_btn.pack_forget()
    
    def _on_session_selected(self) -> None:
        """Handle session selection."""
        sel = self.session_list.curselection()
        if not sel:
            return
        
        idx = sel[0]
        item_text = self.session_list.get(idx)
        
        if item_text.startswith("─── "):
            return
        
        session_idx = self._get_session_index_from_listbox(idx)
        if session_idx is not None and session_idx < len(self.sessions):
            session = self.sessions[session_idx]
            self.selected_session = session
            self._display_session_detail(session)
    
    def _get_session_index_from_listbox(self, listbox_idx: int) -> int | None:
        """Map listbox index to session index (accounting for month headers)."""
        session_idx = 0
        for i in range(listbox_idx + 1):
            item_text = self.session_list.get(i)
            if not item_text.startswith("─── "):
                if i == listbox_idx:
                    return session_idx
                session_idx += 1
        return None
    
    def _get_listbox_index_for_session(self, session_idx: int) -> int | None:
        """Map session index to listbox index (accounting for month headers)."""
        current_session_idx = 0
        for i in range(self.session_list.size()):
            item_text = self.session_list.get(i)
            if not item_text.startswith("─── "):
                if current_session_idx == session_idx:
                    return i
                current_session_idx += 1
        return None
    
    def _hide_empty_state(self) -> None:
        """Hide empty state widgets."""
        if self.empty_label.winfo_ismapped():
            self.empty_label.pack_forget()
        if self.empty_log_btn.winfo_ismapped():
            self.empty_log_btn.pack_forget()
    
    def _display_session_detail(self, session: WorkoutSession) -> None:
        """Display detail for selected session."""
        if self.detail_mode == "exercise":
            self._close_exercise_view()
        self._focused_exercise_id = None
        self._set_detail_readonly(False)
        self.detail_text.delete("1.0", tk.END)
        
        date_str = format_date_display(session.date)
        self.detail_text.insert(tk.END, f"{date_str}\n", "header")
        
        details = []
        if session.duration_minutes:
            details.append(f"{session.duration_minutes} min")
        if session.body_weight_kg:
            details.append(f"{session.body_weight_kg:.1f} kg body weight")
        
        if details:
            self.detail_text.insert(tk.END, " · ".join(details) + "\n")
        
        if session.notes:
            self.detail_text.insert(tk.END, f"\n{session.notes}\n")
        
        self.detail_text.insert(tk.END, "\n")
        
        sets = self.sets_by_session.get(session.id, [])
        if not sets:
            self.detail_text.insert(tk.END, "No exercises recorded.\n")
        else:
            self._display_exercises(session, sets)
        
        self.detail_text.tag_config("header", font=("Helvetica", 12, "bold"))
        self.detail_text.tag_config("exercise", font=("Helvetica", 10, "bold"), underline=True)
        self.detail_text.tag_config("trend_up", foreground=self.theme.get("success", "#059669"))
        self.detail_text.tag_config("trend_same", foreground=self.theme["muted"])
        self.detail_text.tag_config("trend_down", foreground=self.theme.get("error", "#DC2626"))
        self.detail_text.tag_config("pr_beat", foreground=self.theme.get("success", "#059669"))
        self.detail_text.tag_config("pr_tie", foreground=self.theme.get("streak", "#D97706"))
        for ex_id in {s.exercise_id for s in sets}:
            tag = f"exercise_link_{ex_id}"
            self.detail_text.tag_config(tag, font=("Helvetica", 10, "bold"), underline=True)
            self.detail_text.tag_bind(tag, "<Enter>", lambda _e: self.detail_text.config(cursor="hand2"))
            self.detail_text.tag_bind(tag, "<Leave>", lambda _e: self.detail_text.config(cursor=""))

        self._set_detail_readonly(True)
    
    def _display_exercises(self, session: WorkoutSession, sets: list[WorkoutSet]) -> None:
        """Display exercises with volume, PR badges, and trends (batched queries)."""
        exercise_ids = []
        for wset in sets:
            if wset.exercise_id not in exercise_ids:
                exercise_ids.append(wset.exercise_id)

        exercise_names = {}
        try:
            placeholders = ",".join("?" * len(exercise_ids))
            for row in self._conn.execute(
                f"SELECT id, name FROM exercises WHERE id IN ({placeholders}) AND deleted_at IS NULL",
                exercise_ids,
            ).fetchall():
                exercise_names[row["id"]] = row["name"]
        except Exception as exc:
            if is_fitness_db_lock_error(exc):
                self._handle_db_error(exc, "Error loading session detail")
                return

        prior_bests = {}
        try:
            prior_bests = self.repo.get_prior_bests_before_session(
                exercise_ids,
                session.date,
                session.created_at,
                session.id,
            )
        except Exception as exc:
            if is_fitness_db_lock_error(exc):
                self._handle_db_error(exc, "Error loading session detail")
                return
            prior_bests = {}

        trends = self._batch_fetch_trends(session, exercise_ids)

        for ex_id in exercise_ids:
            ex_sets = [s for s in sets if s.exercise_id == ex_id]
            if not ex_sets:
                continue

            ex_name = exercise_names.get(ex_id, f"{ex_id} (removed)")
            link_tag = f"exercise_link_{ex_id}"
            self.detail_text.insert(tk.END, f"{ex_name}\n", (link_tag, "exercise"))
            self.detail_text.tag_bind(link_tag, "<Button-1>", lambda _e, eid=ex_id: self._open_exercise_view(eid))

            prior = prior_bests.get(ex_id, ExerciseBests())
            badges = pr_badges_for_sets(ex_sets, prior)

            for wset, badge in zip(ex_sets, badges):
                parts = []
                if wset.sets:
                    parts.append(f"{wset.sets} sets")
                if wset.reps:
                    parts.append(f"{wset.reps} reps")
                if wset.hold_seconds:
                    hold = wset.hold_seconds
                    hold_txt = f"{hold:g}" if float(hold).is_integer() else f"{hold:.1f}"
                    parts.append(f"{hold_txt} s hold")
                if wset.weight_kg:
                    w = wset.weight_kg
                    w_txt = f"{w:g}" if float(w).is_integer() else f"{w:.1f}"
                    parts.append(f"{w_txt} kg")
                if wset.form_quality:
                    parts.append(f"quality {wset.form_quality}/10")

                volume, unit = calculate_exercise_volume(wset)
                if unit:
                    vol_txt = f"{volume:g}" if float(volume).is_integer() else f"{volume:.1f}"
                    parts.append(f"volume: {vol_txt} {unit}")

                line = f"  {' · '.join(parts)}"
                label = pr_badge_label(badge)
                if label:
                    line += f"  [{label}]"
                tag = "pr_beat" if badge == "beat" else "pr_tie" if badge == "tie" else ""
                if tag:
                    self.detail_text.insert(tk.END, line + "\n", tag)
                else:
                    self.detail_text.insert(tk.END, line + "\n")

            trend_info = trends.get(ex_id, {})
            trend = trend_info.get("trend", "")
            prev_display = trend_info.get("previous_best_display", "")

            if trend and prev_display:
                if trend == "up":
                    self.detail_text.insert(tk.END, f"  ↑ {prev_display}\n", "trend_up")
                elif trend == "down":
                    self.detail_text.insert(tk.END, f"  ↓ {prev_display}\n", "trend_down")
                elif trend == "same":
                    self.detail_text.insert(tk.END, f"  = {prev_display}\n", "trend_same")

            self.detail_text.insert(tk.END, "\n")

    def _on_detail_click(self, event) -> None:
        try:
            index = self.detail_text.index(f"@{event.x},{event.y}")
            tags = self.detail_text.tag_names(index)
        except tk.TclError:
            return
        self._focused_exercise_id = None
        for tag in tags:
            if tag.startswith("exercise_link_"):
                self._focused_exercise_id = tag.replace("exercise_link_", "", 1)
                return

    def _on_enter_in_session_detail(self) -> str | None:
        if self.detail_mode == "exercise":
            return None
        ex_id: str | None = None
        try:
            index = self.detail_text.index(tk.INSERT)
            for tag in self.detail_text.tag_names(index):
                if tag.startswith("exercise_link_"):
                    ex_id = tag.replace("exercise_link_", "", 1)
                    break
        except tk.TclError:
            pass
        if not ex_id:
            ex_id = self._focused_exercise_id
        if ex_id:
            self._open_exercise_view(ex_id)
        return "break"

    def _open_exercise_view(self, exercise_id: str) -> None:
        self._focused_exercise_id = None
        self.selected_exercise_id = exercise_id
        self.detail_mode = "exercise"
        self.exercise_sessions = []
        self.exercise_sets_by_session = {}
        self.exercise_has_more = True
        self.detail_text.pack_forget()
        self.exercise_panel.pack(fill=tk.BOTH, expand=True)
        self._load_exercise_first_page()

    def _close_exercise_view(self) -> str | None:
        if self.detail_mode != "exercise":
            return None
        self.detail_mode = "session"
        self.selected_exercise_id = None
        self._focused_exercise_id = None
        self.exercise_panel.pack_forget()
        if self.exercise_load_more_btn.winfo_ismapped():
            self.exercise_load_more_btn.pack_forget()
        self.detail_text.pack(fill=tk.BOTH, expand=True)
        self.detail_text.focus_set()
        return "break"

    def _load_exercise_first_page(self) -> None:
        if not self.selected_exercise_id:
            return
        try:
            page = self._fetch_exercise_page(reset=True)
        except Exception as exc:
            self._handle_db_error(exc, "Error loading exercise history")
            self._close_exercise_view()
            return
        self._render_exercise_page(page)

    def _load_next_exercise_page(self) -> None:
        if not self.selected_exercise_id or not self.exercise_has_more or self.is_loading:
            return
        try:
            page = self._fetch_exercise_page(reset=False)
        except Exception as exc:
            self._handle_db_error(exc, "Error loading more exercise history")
            return
        self._render_exercise_page(page, append=True)

    def _fetch_exercise_page(self, *, reset: bool) -> dict:
        ex_id = self.selected_exercise_id
        assert ex_id
        before_date = before_id = before_created_at = None
        if not reset and self.exercise_sessions:
            last = self.exercise_sessions[-1]
            before_date = last.date
            before_id = last.id
            before_created_at = last.created_at
        sessions, sets_map, name, stored, computed = self.repo.fetch_exercise_history_page(
            ex_id,
            limit=20,
            before_date=before_date,
            before_id=before_id,
            before_created_at=before_created_at,
        )
        display_bests = resolve_display_bests(stored, computed)
        return {
            "sessions": sessions,
            "sets_map": sets_map,
            "display_bests": display_bests,
            "name": name,
            "reset": reset,
        }

    def _render_exercise_page(self, page: dict, *, append: bool = False) -> None:
        sessions: list[WorkoutSession] = page["sessions"]
        sets_map: dict[str, list[WorkoutSet]] = page["sets_map"]
        if append:
            self.exercise_sessions.extend(sessions)
            self.exercise_sets_by_session.update(sets_map)
        else:
            self.exercise_sessions = sessions
            self.exercise_sets_by_session = sets_map
        self.exercise_has_more = len(sessions) >= 20

        self.exercise_title.config(text=page["name"])
        self.exercise_pr_label.config(text=f"Current PR: {format_best_display(page['display_bests'])}")

        metrics: list[tuple[str, float, str]] = []
        for session in reversed(self.exercise_sessions):
            rows = self.exercise_sets_by_session.get(session.id, [])
            metric, kind = best_set_metric_for_rows(rows)
            if metric is not None:
                metrics.append((session.date, float(metric), kind))
        self._exercise_spark_kind = metrics[-1][2] if metrics else ""
        self._exercise_spark_values = [m[1] for m in metrics]
        self._exercise_spark_dates = [m[0] for m in metrics]
        self.container.update_idletasks()
        self.sparkline_canvas.configure(height=default_sparkline_height(self.container))
        draw_sparkline(
            self.sparkline_canvas,
            self._exercise_spark_values,
            theme=self.theme,
        )
        summary = sparkline_accessibility_summary(
            self._exercise_spark_values,
            self._exercise_spark_dates,
            self._exercise_spark_kind,
        )
        self.sparkline_sr.config(text=summary)

        self.exercise_session_list.delete(0, tk.END)
        for session in self.exercise_sessions:
            rows = self.exercise_sets_by_session.get(session.id, [])
            metric, kind = best_set_metric_for_rows(rows)
            metric_txt = format_metric_display(metric, kind)
            self.exercise_session_list.insert(
                tk.END,
                f"{format_date_display(session.date)} · best set {metric_txt}",
            )

        if self.exercise_has_more:
            self.exercise_load_more_btn.pack(side=tk.TOP, pady=6)
        elif self.exercise_load_more_btn.winfo_ismapped():
            self.exercise_load_more_btn.pack_forget()

        self.exercise_session_list.focus_set()

    def _batch_fetch_trends(self, session: WorkoutSession, exercise_ids: list[str]) -> dict[str, dict]:
        """Batch-fetch trend comparisons using compare_to_previous_session.
        
        Uses a single connection and batched queries (≤3 SQL).
        
        Returns:
            Dict mapping exercise_id to {trend, previous_best_display}
        """
        if not exercise_ids:
            return {}
        
        from progression.recent_compare import compare_to_previous_session
        
        trends = {}
        
        # Get current sets for all exercises
        current_sets_by_ex = {}
        for wset in self.sets_by_session.get(session.id, []):
            if wset.exercise_id not in current_sets_by_ex:
                current_sets_by_ex[wset.exercise_id] = []
            current_sets_by_ex[wset.exercise_id].append(wset)
        
        try:
            # Call compare_to_previous_session for each exercise (it does batching internally)
            for ex_id in exercise_ids:
                current_sets = current_sets_by_ex.get(ex_id, [])
                if not current_sets:
                    continue
                
                # compare_to_previous_session signature:
                # (repo, current_session_id, exercise_id, current_date, current_created_at)
                result = compare_to_previous_session(
                    self.repo,
                    session.id,
                    ex_id,
                    session.date,
                    session.created_at
                )
                
                if not result:
                    trends[ex_id] = {"trend": "none", "previous_best_display": ""}
                    continue
                
                # result has keys: trend ("up"/"down"/"same"/"none"), previous_best_display
                trend = result.get("trend", "none")
                prev_display = result.get("previous_best_display", "")
                
                # Already formatted in compare_to_previous_session
                trends[ex_id] = {
                    "trend": trend,
                    "previous_best_display": prev_display,
                }
        except Exception as exc:
            if is_fitness_db_lock_error(exc):
                self._handle_db_error(exc, "Error loading session detail")
            return {}
        
        return trends
    
    def _on_arrow_key(self) -> None:
        """Handle arrow key navigation."""
        self.container.after(10, self._on_session_selected)
    
    def _on_home_key(self) -> None:
        """Jump to first session."""
        if self.sessions:
            first_session_idx = self._get_listbox_index_for_session(0)
            if first_session_idx is not None:
                self.session_list.selection_clear(0, tk.END)
                self.session_list.selection_set(first_session_idx)
                self.session_list.see(first_session_idx)
                self._on_session_selected()
    
    def _on_end_key(self) -> None:
        """Jump to last session."""
        if self.sessions:
            last_idx = self.session_list.size() - 1
            self.session_list.selection_clear(0, tk.END)
            self.session_list.selection_set(last_idx)
            self.session_list.see(last_idx)
            self._on_session_selected()
    
    def _on_enter_key(self) -> str | None:
        """Open focused exercise or move focus to session detail."""
        if self.detail_mode == "session" and self._focused_exercise_id:
            self._open_exercise_view(self._focused_exercise_id)
            return "break"
        self.detail_text.focus_set()
        return None
    
    def _on_escape_from_list(self) -> None:
        """Close the history view window."""
        toplevel = self.container.winfo_toplevel()
        if isinstance(toplevel, tk.Toplevel):
            # Use proper cleanup path
            if hasattr(toplevel, '_on_close_callback'):
                toplevel._on_close_callback()
            else:
                self.destroy()
                toplevel.destroy()
        return "break"
    
    def _on_escape_from_detail(self) -> str | None:
        """Return to session list or exit exercise view."""
        if self.detail_mode == "exercise":
            return self._close_exercise_view()
        self.session_list.focus_set()
        return "break"
    
    def refresh(self) -> None:
        """Refresh the view (e.g., after a new session is saved)."""
        self.sessions.clear()
        self.sets_by_session.clear()
        self.selected_session = None
        self.has_more = True
        self._load_first_page()
    
    def destroy(self) -> None:
        """Clean up and destroy the view."""
        if self.loading_after_id is not None:
            self.container.after_cancel(self.loading_after_id)
        if self._ctrl_f_binding:
            try:
                self.container.unbind_all("<Control-f>")
            except Exception:
                pass
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
        self.container.destroy()

"""Fitness progression UI and testable helpers."""

from datetime import datetime

import storage
from progression.db import FitnessRepository
from progression.engine import record_performance
from progression.seed_loader import seed_all_fitness
from progression.sessions import (
    bridge_fitness_to_daily_entries,
    create_workout_session,
    format_session_summary,
    link_session_to_body_presence,
    sync_fitness_sessions_to_entries,
)

_seeded_db_paths: set[str] = set()


def get_profile_repo(fitness_settings: dict | None = None) -> FitnessRepository:
    return FitnessRepository(fitness_settings=fitness_settings)


def ensure_fitness_seeded(repo: FitnessRepository | None = None, fitness_settings: dict | None = None) -> bool:
    import fitness_programs
    from progression.placement import apply_stored_placements

    repo = repo or get_profile_repo(fitness_settings)
    repo.initialize()
    before = len(repo.list_exercises())
    seed_all_fitness(repo)
    fitness_programs.ensure_entry_points_available(repo)
    if fitness_settings:
        apply_stored_placements(repo, fitness_settings)
    after = len(repo.list_exercises())
    _seeded_db_paths.add(repo.db_path)
    return after > before


def list_exercise_rows(
    repo: FitnessRepository,
    source_book: str | None = None,
    family: str | None = None,
) -> list[dict]:
    rows = []
    for exercise in repo.list_exercises():
        if source_book and exercise.source_book != source_book:
            continue
        if family and exercise.family != family:
            continue
        progress = repo.get_user_progress(exercise.id)
        status = progress.status if progress else "locked"
        step = exercise.metadata.get("step", "")
        rows.append(
            {
                "id": exercise.id,
                "name": exercise.name,
                "step": step,
                "status": status,
                "criteria": exercise.mastery_criteria,
                "source_book": exercise.source_book,
                "family": exercise.family,
            }
        )
    rows.sort(
        key=lambda r: (
            r["source_book"],
            r["family"],
            r["step"] if r["step"] != "" else 999,
            r["name"],
        )
    )
    return rows


def format_exercise_picker_label(row: dict) -> str:
    """Disambiguate exercises in search results (book, family, step)."""
    name = row.get("name", "")
    details: list[str] = []
    if row.get("source_book"):
        details.append(str(row["source_book"]))
    if row.get("family"):
        details.append(str(row["family"]))
    step = row.get("step")
    if step not in (None, ""):
        details.append(f"step {step}")
    if details:
        return f"{name} ({' · '.join(details)})"
    return name


def mount_live_exercise_search(
    parent,
    rows: list[dict],
    *,
    height: int = 8,
    focus: bool = True,
) -> dict:
    """Search-as-you-type exercise picker; filters on every keystroke."""
    import tkinter as tk
    from tkinter import ttk

    import fitness_programs
    import ui_scroll

    container = ttk.Frame(parent)
    search_var = tk.StringVar(value="")
    status_var = tk.StringVar(value="")

    search_row = ttk.Frame(container)
    search_row.pack(fill=tk.X, pady=(0, 4))
    ttk.Label(search_row, text="Search:").pack(side=tk.LEFT, padx=(0, 6))
    search_entry = ttk.Entry(search_row, textvariable=search_var)
    search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
    ttk.Button(search_row, text="Clear", command=lambda: search_var.set("")).pack(side=tk.LEFT)

    list_frame = ttk.Frame(container)
    list_frame.pack(fill=tk.BOTH, expand=True)
    listbox = tk.Listbox(list_frame, height=height, activestyle="dotbox", exportselection=False)
    scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
    listbox.configure(yscrollcommand=scrollbar.set)
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    ui_scroll.bind_mousewheel(listbox, listbox.yview)

    ttk.Label(container, textvariable=status_var, style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

    filtered_rows: list[dict] = []

    def refresh(*_args) -> None:
        nonlocal filtered_rows
        query = search_var.get()
        filtered_rows = fitness_programs.filter_rows_by_search(rows, query)
        listbox.delete(0, tk.END)
        for row in filtered_rows:
            listbox.insert(tk.END, format_exercise_picker_label(row))
        total = len(rows)
        count = len(filtered_rows)
        if query.strip():
            status_var.set(
                f"{count} match{'es' if count != 1 else ''} of {total} — click a row or double-click to pick"
            )
        else:
            status_var.set(f"{total} exercises — type to filter instantly")
        if filtered_rows:
            listbox.selection_set(0)
            listbox.activate(0)
            listbox.see(0)

    def get_selected_row() -> dict | None:
        selection = listbox.curselection()
        if not selection:
            if len(filtered_rows) == 1:
                return filtered_rows[0]
            return None
        index = int(selection[0])
        if 0 <= index < len(filtered_rows):
            return filtered_rows[index]
        return None

    def focus_results(_event=None):
        if filtered_rows:
            listbox.focus_set()
            listbox.selection_set(0)
            listbox.activate(0)

    search_var.trace_add("write", refresh)
    search_entry.bind("<Down>", focus_results)
    search_entry.bind("<Return>", lambda _e: focus_results())
    refresh()
    if focus:
        search_entry.focus_set()

    return {
        "container": container,
        "search_var": search_var,
        "search_entry": search_entry,
        "listbox": listbox,
        "get_selected_row": get_selected_row,
        "refresh": refresh,
    }


def submit_performance(
    repo: FitnessRepository,
    exercise_id: str,
    performance: dict,
    *,
    fitness_settings: dict | None = None,
    session_id: str | None = None,
) -> dict:
    progress = record_performance(
        repo,
        exercise_id,
        performance,
        fitness_settings=fitness_settings,
        session_id=session_id,
    )
    exercise = repo.get_exercise(exercise_id)
    return {
        "exercise_id": exercise_id,
        "exercise_name": exercise.name if exercise else exercise_id,
        "status": progress.status,
        "achieved_at": progress.achieved_at,
    }


def open_log_dialog_for_exercise(
    parent,
    repo,
    exercise_id,
    on_saved=None,
    on_session_saved=None,
    *,
    session_date: str | None = None,
    fitness_settings: dict | None = None,
):
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    import ui_scroll
    from progression.advancement import format_advancement_hint
    from progression.engine import exercise_log_allowed
    from progression.sessions import create_workout_session
    from progression.video_catalog import get_exercise_video, open_exercise_video

    exercise = repo.get_exercise(exercise_id)
    if exercise is None:
        return

    settings = fitness_settings or getattr(repo, "fitness_settings", None) or {}
    if not exercise_log_allowed(repo, exercise_id, fitness_settings=settings):
        messagebox.showwarning(
            "Step locked",
            "Complete earlier steps before logging this one.\n\n"
            "If you already have training history, use Set Starting Step or turn on "
            "progression overrides in Fitness Settings.",
            parent=parent,
        )
        return

    dialog = tk.Toplevel(parent)
    dialog.title(f"Log: {exercise.name}")
    dialog.geometry("460x540")
    dialog.minsize(420, 420)
    dialog.transient(parent)
    dialog.grab_set()

    footer = ttk.Frame(dialog, padding=10)
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Separator(footer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 8))
    footer_btns = ttk.Frame(footer)
    footer_btns.pack(fill=tk.X)

    outer, inner, _canvas = ui_scroll.make_scrollable_frame(dialog)
    outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    ttk.Label(inner, text=exercise.name, font=("Helvetica", 12, "bold")).pack(pady=8, padx=12)

    date_var = tk.StringVar(value=session_date or datetime.now().strftime("%Y-%m-%d"))
    date_row = ttk.Frame(inner, padding=(12, 0))
    date_row.pack(fill=tk.X)
    ttk.Label(date_row, text="Session date:", width=12).pack(side=tk.LEFT)
    ttk.Entry(date_row, textvariable=date_var, width=14).pack(side=tk.LEFT)

    crit = ", ".join(f"{k}={v}" for k, v in exercise.mastery_criteria.items())
    ttk.Label(inner, text=f"Progression standard: {crit}", wraplength=380).pack(pady=4, padx=12)
    hint = format_advancement_hint(repo, exercise, fitness_settings=settings)
    if hint:
        ttk.Label(inner, text=hint, wraplength=380, style="Muted.TLabel").pack(pady=(0, 6), padx=12)

    seed_key = exercise.metadata.get("seed_key", exercise.id)
    video = get_exercise_video(
        seed_key,
        exercise.source_book,
        exercise.family,
        exercise.name,
    )
    if video and video.get("url"):
        video_row = ttk.Frame(inner, padding=(12, 0))
        video_row.pack(fill=tk.X)
        ttk.Label(
            video_row,
            text=f"Demo: {video.get('source', 'Reference')}",
            wraplength=250,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(
            video_row,
            text="Open Video",
            command=lambda: open_exercise_video(video),
        ).pack(side=tk.RIGHT)

    fields = ttk.Frame(inner, padding=10)
    fields.pack(fill=tk.X)

    sets_var = tk.IntVar(value=3)
    reps_var = tk.IntVar(value=5)
    hold_var = tk.DoubleVar(value=0.0)
    weight_var = tk.DoubleVar(value=0.0)
    form_var = tk.IntVar(value=8)

    for label, var in [("Sets", sets_var), ("Reps", reps_var)]:
        row = ttk.Frame(fields)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text=f"{label}:", width=12).pack(side=tk.LEFT)
        ttk.Spinbox(row, from_=0, to=999, textvariable=var, width=8).pack(side=tk.LEFT)

    for label, var in [("Hold (sec)", hold_var), ("Weight (kg)", weight_var)]:
        row = ttk.Frame(fields)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text=f"{label}:", width=12).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=var, width=10).pack(side=tk.LEFT)

    form_row = ttk.Frame(fields)
    form_row.pack(fill=tk.X, pady=3)
    ttk.Label(form_row, text="Form quality:", width=12).pack(side=tk.LEFT)
    ttk.Spinbox(form_row, from_=1, to=10, textvariable=form_var, width=8).pack(side=tk.LEFT)
    ttk.Label(form_row, text="(1–10, 7+ to count toward unlock)", style="Muted.TLabel").pack(
        side=tk.LEFT, padx=(8, 0)
    )

    ttk.Label(
        inner,
        text="Notes (form cues, how it felt, what to try next)",
        font=("Helvetica", 10, "bold"),
    ).pack(anchor="w", padx=12, pady=(8, 4))
    notes_text = scrolledtext.ScrolledText(inner, height=6, wrap=tk.WORD, font=("Helvetica", 10))
    notes_text.pack(fill=tk.X, padx=12, pady=(0, 12))

    def save():
        item: dict = {
            "exercise_id": exercise_id,
            "sets": sets_var.get(),
            "reps": reps_var.get(),
        }
        if hold_var.get() > 0:
            item["hold_seconds"] = hold_var.get()
        if weight_var.get() > 0:
            item["weight_kg"] = weight_var.get()
        item["form_quality"] = form_var.get()
        notes = notes_text.get("1.0", tk.END).strip()
        try:
            session = create_workout_session(
                repo,
                date_var.get().strip(),
                [item],
                notes=notes,
            )
        except ValueError as exc:
            messagebox.showwarning("Cannot log", str(exc), parent=dialog)
            return
        dialog.destroy()
        if on_session_saved:
            on_session_saved(session.date)
        else:
            data = storage.load()
            data = link_session_to_body_presence(data, session.date)
            storage.save(data)
        if on_saved:
            on_saved()
        progress = repo.get_user_progress(exercise_id)
        status = progress.status if progress else "logged"
        messagebox.showinfo("Logged", f"{exercise.name}: {status}")

    ttk.Button(footer_btns, text="Save Log", style="Accent.TButton", command=save).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(footer_btns, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)


def open_new_session_dialog(
    parent,
    repo: FitnessRepository,
    *,
    initial_date: str | None = None,
    on_session_saved=None,
    on_after_save=None,
    fitness_settings: dict | None = None,
):
    """Open the multi-exercise workout session logger (usable outside Fitness Hub)."""
    import tkinter as tk
    from tkinter import messagebox, ttk

    import ui_scroll

    dialog = tk.Toplevel(parent)
    dialog.title("Log Exercise Session")
    dialog.geometry("560x620")
    dialog.minsize(500, 480)
    dialog.transient(parent)
    dialog.grab_set()

    btn_row = ttk.Frame(dialog, padding=10)
    btn_row.pack(side=tk.BOTTOM, fill=tk.X)

    outer, inner, _canvas = ui_scroll.make_scrollable_frame(dialog)
    outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

    date_var = tk.StringVar(value=initial_date or datetime.now().strftime("%Y-%m-%d"))
    notes_var = tk.StringVar(value="")
    duration_var = tk.IntVar(value=45)
    weight_var = tk.DoubleVar(value=0.0)
    sets_var = tk.IntVar(value=3)
    reps_var = tk.IntVar(value=10)
    hold_var = tk.DoubleVar(value=0.0)
    set_weight_var = tk.DoubleVar(value=0.0)

    form = ttk.Frame(inner, padding=10)
    form.pack(fill=tk.X)
    for label, var in [
        ("Date", date_var),
        ("Notes", notes_var),
        ("Duration (min)", duration_var),
        ("Body weight (kg)", weight_var),
    ]:
        row = ttk.Frame(form)
        row.pack(fill=tk.X, pady=3)
        ttk.Label(row, text=f"{label}:", width=16).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=var, width=28).pack(side=tk.LEFT)

    ttk.Label(form, text="Search for an exercise, pick it, add sets, then Save Session.").pack(
        anchor="w", pady=6
    )

    set_frame = ttk.LabelFrame(form, text="Add Set", padding=8)
    set_frame.pack(fill=tk.BOTH, expand=True, pady=4)

    exercise_rows = list_exercise_rows(repo)
    picker = mount_live_exercise_search(set_frame, exercise_rows, height=9)
    picker["container"].pack(fill=tk.BOTH, expand=True, pady=(0, 8))

    metrics = ttk.Frame(set_frame)
    metrics.pack(fill=tk.X)
    for label, var in [("Sets", sets_var), ("Reps", reps_var)]:
        row = ttk.Frame(metrics)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text=f"{label}:", width=10).pack(side=tk.LEFT)
        ttk.Spinbox(row, from_=0, to=999, textvariable=var, width=8).pack(side=tk.LEFT)
    for label, var in [("Hold (sec)", hold_var), ("Weight (kg)", set_weight_var)]:
        row = ttk.Frame(metrics)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text=f"{label}:", width=10).pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=var, width=10).pack(side=tk.LEFT)

    pending_sets: list[dict] = []
    preview = tk.Listbox(form, height=6)
    preview.pack(fill=tk.BOTH, expand=True, pady=6)
    ui_scroll.bind_mousewheel(preview, preview.yview)

    def add_set():
        row = picker["get_selected_row"]()
        if row is None:
            messagebox.showinfo(
                "Exercise",
                "Type to search, then click an exercise in the list (or narrow to one match).",
                parent=dialog,
            )
            return
        name = row["name"]
        item = {
            "exercise_id": row["id"],
            "name": name,
            "sets": sets_var.get(),
            "reps": reps_var.get(),
        }
        if hold_var.get() > 0:
            item["hold_seconds"] = hold_var.get()
        if set_weight_var.get() > 0:
            item["weight_kg"] = set_weight_var.get()
        pending_sets.append(item)
        preview.insert(tk.END, f"{format_exercise_picker_label(row)}: {item.get('sets')}x{item.get('reps')}")

    picker["listbox"].bind("<Double-1>", lambda _e: add_set())

    def save_session():
        if not pending_sets:
            messagebox.showinfo("Session", "Add at least one set.", parent=dialog)
            return
        session = create_workout_session(
            repo,
            date_var.get().strip(),
            pending_sets,
            notes=notes_var.get().strip(),
            duration_minutes=duration_var.get() or None,
            body_weight_kg=weight_var.get() if weight_var.get() > 0 else None,
        )
        if on_session_saved:
            on_session_saved(session.date)
        else:
            data = storage.load()
            data = link_session_to_body_presence(data, session.date)
            storage.save(data)
        dialog.destroy()
        if on_after_save:
            on_after_save()
        messagebox.showinfo("Saved", f"Workout session logged for {session.date}.", parent=parent)

    ttk.Button(btn_row, text="Add Set", command=add_set).pack(side=tk.LEFT)
    ttk.Button(btn_row, text="Save Session", style="Accent.TButton", command=save_session).pack(
        side=tk.LEFT, padx=8
    )
    ttk.Button(btn_row, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT)


def show_fitness_window(
    root,
    on_session_saved=None,
    theme=None,
    *,
    fitness_settings: dict | None = None,
    on_fitness_settings_changed=None,
):
    import tkinter as tk
    from tkinter import messagebox, scrolledtext, ttk

    import body_composition_ui
    import fitness_programs
    import theme as app_theme
    import ui_scroll
    from progression.advancement import format_advancement_hint
    from progression.engine import exercise_log_allowed
    from progression.fitness_settings import (
        LOCK_BYPASS_WARNING,
        PLACEMENT_WARNING,
        get_fitness_settings,
        progression_locks_enabled,
    )
    from progression.placement import apply_program_placement, is_sequential_program, program_key
    from progression.video_catalog import get_exercise_video, open_exercise_video

    settings = get_fitness_settings({"fitness": fitness_settings or {}})
    repo = get_profile_repo(settings)
    ensure_fitness_seeded(repo, settings)

    if theme is None:
        theme = app_theme.get_theme(False)
        app_theme.apply_theme(root, theme)

    win = tk.Toplevel(root)
    win.title("Fitness Hub")
    win.geometry("1100x720")
    win.minsize(800, 520)
    win.transient(root)
    win.configure(bg=theme["bg"])
    app_theme.apply_theme(win, theme)

    footer = ttk.Frame(win, padding=12)
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Separator(footer, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(0, 10))
    nav_host, btn_bar, _nav_canvas = ui_scroll.make_horizontal_scroll_row(
        footer,
        height=40,
        overflow_hint="Scroll for more →",
    )
    nav_host.pack(fill=tk.X)

    header = ttk.Frame(win, padding=(16, 14, 16, 8))
    header.pack(side=tk.TOP, fill=tk.X)
    ttk.Label(header, text="Fitness Hub", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        header,
        text="Expand a book (CC1, SS, …), then a program (Pull, Push, …), then pick a step.",
        style="Muted.TLabel",
        wraplength=900,
    ).pack(anchor="w", pady=(4, 0))

    filter_frame = ttk.LabelFrame(header, text="Search steps", padding=10, style="Card.TLabelframe")
    filter_frame.pack(fill=tk.X, pady=(10, 0))
    search_var = tk.StringVar(value="")

    search_row = ttk.Frame(filter_frame, style="Surface.TFrame")
    search_row.pack(fill=tk.X)
    search_entry = ttk.Entry(search_row, textvariable=search_var, font=app_theme.FONTS["body"])
    search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
    ttk.Button(search_row, text="Clear", command=lambda: search_var.set("")).pack(side=tk.LEFT)

    body = ttk.Panedwindow(win, orient=tk.HORIZONTAL)
    body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))

    list_frame = ttk.Frame(body, padding=(0, 0, 8, 0))
    body.add(list_frame, weight=3)

    tree = ttk.Treeview(list_frame, columns=("status", "criteria"), show="tree headings")
    tree.heading("#0", text="Book / Program / Step")
    tree.heading("status", text="Status")
    tree.heading("criteria", text="Mastery")
    tree.column("#0", width=360, stretch=True)
    tree.column("status", width=90, anchor="center")
    tree.column("criteria", width=180)
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)
    ui_scroll.configure_treeview_scroll(tree)
    app_theme.configure_fitness_tree_tags(tree, theme)

    detail_frame = ttk.LabelFrame(body, text="Step Detail", padding=12, style="Card.TLabelframe")
    body.add(detail_frame, weight=2)

    detail_title = ttk.Label(
        detail_frame, text="Select a step", style="OnSurfaceSubheading.TLabel", wraplength=320
    )
    detail_title.pack(anchor="w")
    detail_meta = ttk.Label(detail_frame, text="", style="OnSurfaceMuted.TLabel", wraplength=320)
    detail_meta.pack(anchor="w", pady=4)
    detail_criteria = ttk.Label(detail_frame, text="", style="OnSurface.TLabel", wraplength=320)
    detail_criteria.pack(anchor="w", pady=4)
    detail_hint = ttk.Label(detail_frame, text="", style="OnSurfaceMuted.TLabel", wraplength=320)
    detail_hint.pack(anchor="w", pady=(0, 4))
    detail_video = ttk.Label(detail_frame, text="", style="OnSurfaceMuted.TLabel", wraplength=320)
    detail_video.pack(anchor="w", pady=(8, 4))

    detail_btn_row = ttk.Frame(detail_frame)
    detail_btn_row.pack(anchor="w", pady=8)
    video_btn = ttk.Button(detail_btn_row, text="Open Demo Video", state=tk.DISABLED)
    video_btn.pack(side=tk.LEFT)
    log_btn = ttk.Button(detail_btn_row, text="Log This Step", style="Accent.TButton", state=tk.DISABLED)
    log_btn.pack(side=tk.LEFT, padx=8)

    selected_video: dict[str, str] = {}
    step_rows: dict[str, dict] = {}

    def refresh_list():
        nonlocal selected_video, step_rows
        step_rows = {}
        for item in tree.get_children():
            tree.delete(item)

        rows = list_exercise_rows(repo)
        hierarchy = fitness_programs.build_program_hierarchy(rows, expand_current=False)
        hierarchy = fitness_programs.filter_program_hierarchy(hierarchy, search_var.get())

        for book in hierarchy:
            book_id = book["id"]
            tree.insert(
                "",
                tk.END,
                iid=book_id,
                text=book["title"],
                values=("", book.get("subtitle", book["summary"])),
                tags=("book",),
                open=book["expanded"],
            )
            for program in book["programs"]:
                parent_id = f"prog:{program['id']}"
                tree.insert(
                    book_id,
                    tk.END,
                    iid=parent_id,
                    text=program["title"],
                    values=("", program["summary"]),
                    tags=("program",),
                    open=program["expanded"],
                )
                for step in program["steps"]:
                    step = {**step, "is_current": step["id"] == program["current_step_id"]}
                    step_rows[step["id"]] = step
                    criteria = step["criteria"]
                    crit_text = ", ".join(f"{k}={v}" for k, v in criteria.items())
                    tags = [step["status"]]
                    if step["is_current"]:
                        tags.append("current")
                    tree.insert(
                        parent_id,
                        tk.END,
                        iid=step["id"],
                        text=fitness_programs.format_step_label(step),
                        values=(step["status"].replace("_", " "), crit_text),
                        tags=tuple(tags),
                    )

    def show_step_detail(step_id: str | None):
        nonlocal selected_video
        selected_video = {}
        video_btn.configure(state=tk.DISABLED)
        log_btn.configure(state=tk.DISABLED)

        if not step_id or step_id.startswith(("book:", "prog:")) or step_id not in step_rows:
            detail_title.configure(text="Select a step")
            detail_meta.configure(
                text="Expand CC1 (or another book), then a program like Pull, then click a step."
            )
            detail_criteria.configure(text="")
            detail_hint.configure(text="")
            detail_video.configure(text="")
            return

        step = step_rows[step_id]
        exercise = repo.get_exercise(step_id)
        detail_title.configure(text=step["name"])
        detail_meta.configure(
            text=f"{step['source_book']} · Step {step.get('step', '?')} · {step['status'].replace('_', ' ')}"
        )
        detail_criteria.configure(
            text="Progression standard: " + ", ".join(f"{k}={v}" for k, v in step["criteria"].items())
        )
        if exercise:
            detail_hint.configure(
                text=format_advancement_hint(repo, exercise, fitness_settings=settings)
            )
        else:
            detail_hint.configure(text="")

        seed_key = exercise.metadata.get("seed_key", step_id) if exercise else step_id
        video = get_exercise_video(
            seed_key,
            step["source_book"],
            step["family"],
            step["name"],
        )
        if video and video.get("url"):
            selected_video = video
            detail_video.configure(text=f"Reference: {video.get('source', 'Demo')}")
            video_btn.configure(state=tk.NORMAL)
        else:
            detail_video.configure(text="No demo video cataloged yet for this step.")

        can_log = exercise_log_allowed(repo, step_id, fitness_settings=settings)
        if can_log:
            log_btn.configure(state=tk.NORMAL)
        else:
            log_btn.configure(state=tk.DISABLED)
            if progression_locks_enabled(settings):
                detail_hint.configure(
                    text=(
                        (detail_hint.cget("text") + "\n\n") if detail_hint.cget("text") else ""
                    )
                    + "This step is locked until you meet the progression standard on earlier steps."
                )

    def on_tree_select(_event=None):
        selected = tree.selection()
        show_step_detail(selected[0] if selected else None)

    def open_selected_log():
        selected = tree.selection()
        if not selected or selected[0].startswith(("book:", "prog:")):
            messagebox.showinfo("Select Step", "Choose a step under a program to log.")
            return
        open_log_dialog_for_exercise(
            win,
            repo,
            selected[0],
            on_saved=refresh_list,
            on_session_saved=on_session_saved,
            fitness_settings=settings,
        )

    def open_selected_video():
        if selected_video:
            open_exercise_video(selected_video)

    tree.bind("<<TreeviewSelect>>", on_tree_select)
    tree.bind("<Double-1>", lambda _e: open_selected_log())

    video_btn.configure(command=open_selected_video)
    log_btn.configure(command=open_selected_log)

    def open_skill_tree():
        import skill_tree

        skill_tree.show_skill_tree_window(
            win,
            repo,
            on_session_saved=on_session_saved,
            fitness_settings=settings,
        )

    def open_fitness_settings():
        dialog, inner, footer, _canvas, _refresh = ui_scroll.create_dialog_shell(
            win,
            title="Fitness Settings",
            geometry="560x420",
            minsize=(480, 320),
            grab=True,
        )

        ttk.Label(inner, text=LOCK_BYPASS_WARNING, wraplength=500, style="Muted.TLabel").pack(
            anchor="w", padx=16, pady=(16, 12)
        )
        bypass_var = tk.BooleanVar(value=bool(settings.get("disable_progression_locks")))
        ttk.Checkbutton(
            inner,
            text="Allow logging any step (bypass progression locks)",
            variable=bypass_var,
        ).pack(anchor="w", padx=16)

        ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=16, pady=14)
        ttk.Label(
            inner,
            text="Sessions required at progression standard before the next CC-style step unlocks:",
            wraplength=500,
        ).pack(anchor="w", padx=16)
        sessions_var = tk.IntVar(value=int(settings.get("cc_sessions_for_advance", 2)))
        ttk.Spinbox(inner, from_=1, to=5, textvariable=sessions_var, width=6).pack(anchor="w", padx=16, pady=6)

        def save_settings():
            settings["disable_progression_locks"] = bool(bypass_var.get())
            settings["cc_sessions_for_advance"] = max(1, int(sessions_var.get()))
            repo.fitness_settings = settings
            if on_fitness_settings_changed:
                on_fitness_settings_changed(settings)
            dialog.destroy()
            refresh_list()

        ttk.Button(footer, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(footer, text="Save", style="Accent.TButton", command=save_settings).pack(side=tk.RIGHT)

    def open_placement_dialog():
        selected = tree.selection()
        program = None
        if selected and selected[0].startswith("prog:"):
            prog_id = selected[0].removeprefix("prog:")
            for book in fitness_programs.build_program_hierarchy(list_exercise_rows(repo)):
                for item in book["programs"]:
                    if item["id"] == prog_id:
                        program = item
                        break
        elif selected and selected[0] in step_rows:
            step = step_rows[selected[0]]
            for book in fitness_programs.build_program_hierarchy(list_exercise_rows(repo)):
                for item in book["programs"]:
                    if item["source_book"] == step["source_book"] and item["family"] == step["family"]:
                        program = item
                        break

        if program is None:
            messagebox.showinfo(
                "Select a program",
                "Expand a book and select a program (e.g. CC1 → Pull) or a step within it.",
                parent=win,
            )
            return

        if not is_sequential_program(repo, program["source_book"], program["family"]):
            messagebox.showinfo(
                "Not a step ladder",
                "This program does not use sequential step locking — all movements stay available.",
                parent=win,
            )
            return

        dialog, inner, footer, _canvas, _refresh = ui_scroll.create_dialog_shell(
            win,
            title=f"Set Starting Step — {program['title']}",
            geometry="560x480",
            minsize=(480, 360),
            grab=True,
        )

        ttk.Label(inner, text=PLACEMENT_WARNING, wraplength=500, style="Muted.TLabel").pack(
            anchor="w", padx=16, pady=(16, 12)
        )

        step_values = [step.get("step") for step in program["steps"] if step.get("step")]
        current = next(
            (step.get("step") for step in program["steps"] if step.get("status") in {"available", "in_progress"}),
            step_values[0] if step_values else 1,
        )
        step_var = tk.IntVar(value=current or 1)
        ttk.Label(inner, text="I am currently working at step:").pack(anchor="w", padx=16)
        ttk.Spinbox(
            inner,
            from_=min(step_values) if step_values else 1,
            to=max(step_values) if step_values else 10,
            textvariable=step_var,
            width=8,
        ).pack(anchor="w", padx=16, pady=6)

        confirm_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            inner,
            text="I have prior training experience and understand the risks of skipping foundational work",
            variable=confirm_var,
            wraplength=500,
        ).pack(anchor="w", padx=16, pady=12)

        def apply_placement():
            if not confirm_var.get():
                messagebox.showwarning(
                    "Confirm experience",
                    "Please confirm you understand the risks before overriding placement.",
                    parent=dialog,
                )
                return
            target = int(step_var.get())
            apply_program_placement(repo, program["source_book"], program["family"], target)
            key = program_key(program["source_book"], program["family"])
            placements = dict(settings.get("placements") or {})
            placements[key] = target
            settings["placements"] = placements
            repo.fitness_settings = settings
            if on_fitness_settings_changed:
                on_fitness_settings_changed(settings)
            dialog.destroy()
            refresh_list()
            messagebox.showinfo(
                "Placement updated",
                f"Set {program['title']} to step {target}. Earlier steps marked complete; later steps stay locked.",
                parent=win,
            )

        ttk.Button(footer, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(footer, text="Apply Placement", style="Accent.TButton", command=apply_placement).pack(
            side=tk.RIGHT
        )

    def open_session_dialog():
        open_new_session_dialog(
            win,
            repo,
            on_session_saved=on_session_saved,
            on_after_save=refresh_list,
            fitness_settings=settings,
        )

    def open_session_history():
        hist = tk.Toplevel(win)
        hist.title("Workout Session History")
        hist.geometry("560x480")
        hist.minsize(420, 320)
        hist.transient(win)

        footer = ttk.Frame(hist, padding=(10, 8))
        footer.pack(side=tk.BOTTOM, fill=tk.X)
        ttk.Button(footer, text="Close", command=hist.destroy).pack(side=tk.RIGHT)

        txt = scrolledtext.ScrolledText(hist, wrap=tk.WORD, font=("Helvetica", 10))
        txt.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        sessions = repo.list_workout_sessions()
        if not sessions:
            txt.insert(tk.END, "No workout sessions yet.")
        for session in sessions:
            txt.insert(tk.END, format_session_summary(repo, session) + "\n\n")

    search_var.trace_add("write", lambda *_args: refresh_list())
    search_entry.bind("<Return>", lambda _e: refresh_list())
    search_entry.focus_set()

    ttk.Button(btn_bar, text="Log Selected", style="Accent.TButton", command=open_selected_log).pack(
        side=tk.LEFT
    )
    ttk.Button(btn_bar, text="New Session", command=open_session_dialog).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_bar, text="Session History", command=open_session_history).pack(side=tk.LEFT, padx=6)
    ttk.Button(
        btn_bar,
        text="Body Composition",
        command=lambda: body_composition_ui.show_body_composition_window(win, repo),
    ).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_bar, text="Skill Tree", command=open_skill_tree).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_bar, text="Set Starting Step", command=open_placement_dialog).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_bar, text="Fitness Settings", command=open_fitness_settings).pack(side=tk.LEFT, padx=6)
    ttk.Button(btn_bar, text="Refresh", command=refresh_list).pack(side=tk.LEFT, padx=6)

    refresh_list()

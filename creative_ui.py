"""Creative writing projects library UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import TYPE_CHECKING, Any

import creative_projects as cp
from paths import creative_projects_dir
from theme import FONTS, style_listbox, style_text_widget

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker

AUTOSAVE_DEBOUNCE_MS = 1500

# Registry: (project_id, role) -> window state
_open_doc_windows: dict[tuple[str, str], dict[str, Any]] = {}


def document_window_key(project_id: str, role: str) -> tuple[str, str]:
    return (project_id, role)


def count_words_and_chars(text: str) -> tuple[int, int]:
    chars = len(text)
    words = len(text.split()) if text.strip() else 0
    return words, chars


def format_doc_status(prefix: str, text: str) -> str:
    words, chars = count_words_and_chars(text)
    return f"{prefix} · {words} words · {chars} characters"


def role_label(role: str) -> str:
    return "Inspiration" if role == cp.DOC_INSPIRATION else "Manuscript"


def focus_existing_document_window(project_id: str, role: str) -> bool:
    """Focus an open document window if present. Returns True if focused."""
    key = document_window_key(project_id, role)
    state = _open_doc_windows.get(key)
    if not state:
        return False
    win = state.get("window")
    if win is None:
        _open_doc_windows.pop(key, None)
        return False
    try:
        if win.winfo_exists():
            win.lift()
            win.focus_force()
            return True
    except tk.TclError:
        pass
    _open_doc_windows.pop(key, None)
    return False


def flush_open_document_windows() -> int:
    """Save all dirty open document windows. Returns number of saves performed."""
    saved = 0
    for state in list(_open_doc_windows.values()):
        save_fn = state.get("save")
        dirty = state.get("dirty")
        if callable(save_fn) and dirty and dirty.get("value"):
            save_fn()
            saved += 1
    return saved


def open_document_windows_count() -> int:
    alive = 0
    for key, state in list(_open_doc_windows.items()):
        win = state.get("window")
        try:
            if win is not None and win.winfo_exists():
                alive += 1
            else:
                _open_doc_windows.pop(key, None)
        except tk.TclError:
            _open_doc_windows.pop(key, None)
    return alive


def show_writing_projects_window(tracker: PersonalDevelopmentTracker) -> None:
    theme = tracker.theme
    win = tk.Toplevel(tracker.root)
    win.title("Writing Projects")
    win.geometry("820x600")
    win.minsize(700, 480)
    win.configure(bg=theme["bg"])
    win.transient(tracker.root)

    root_docs = creative_projects_dir()
    show_archived = tk.BooleanVar(value=False)
    status_filter = tk.StringVar(value="All")

    footer = ttk.Frame(win, padding=(16, 8, 16, 12))
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Button(footer, text="Close", command=win.destroy).pack(side=tk.RIGHT)

    header = ttk.Frame(win, padding=(16, 14, 16, 8))
    header.pack(side=tk.TOP, fill=tk.X)
    ttk.Label(header, text="Writing Projects", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        header,
        text="Select a project, then Continue Writing to open the manuscript. "
        "Open Inspiration for premise/notes, or Open Both to keep them side by side.",
        style="Muted.TLabel",
        wraplength=760,
    ).pack(anchor="w", pady=(4, 0))

    toolbar = ttk.Frame(win, padding=(16, 0, 16, 8))
    toolbar.pack(side=tk.TOP, fill=tk.X)
    ttk.Checkbutton(
        toolbar,
        text="Show archived",
        variable=show_archived,
        command=lambda: refresh_list(),
    ).pack(side=tk.LEFT)
    ttk.Label(toolbar, text="Status", style="Muted.TLabel").pack(side=tk.LEFT, padx=(16, 6))
    status_combo = ttk.Combobox(
        toolbar,
        textvariable=status_filter,
        values=["All", *cp.STATUSES],
        width=12,
        state="readonly",
    )
    status_combo.pack(side=tk.LEFT)
    status_combo.bind("<<ComboboxSelected>>", lambda _e: refresh_list())

    body = ttk.Frame(win, padding=(16, 0, 16, 8))
    body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)

    list_panel = ttk.LabelFrame(body, text="Projects", padding=8, style="Card.TLabelframe")
    list_panel.grid(row=0, column=0, sticky="nsew")
    list_panel.rowconfigure(0, weight=1)
    list_panel.columnconfigure(0, weight=1)

    project_list = tk.Listbox(list_panel, exportselection=False, font=FONTS["body"])
    project_list.grid(row=0, column=0, sticky="nsew")
    style_listbox(project_list, theme)
    list_scroll = ttk.Scrollbar(list_panel, orient=tk.VERTICAL, command=project_list.yview)
    project_list.configure(yscrollcommand=list_scroll.set)
    list_scroll.grid(row=0, column=1, sticky="ns")

    listed_ids: list[str] = []

    manage = ttk.Frame(body)
    manage.grid(row=1, column=0, sticky="ew", pady=(10, 0))
    write = ttk.Frame(body)
    write.grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def selected_id() -> str | None:
        selection = project_list.curselection()
        if not selection:
            return None
        index = int(selection[0])
        if index < 0 or index >= len(listed_ids):
            return None
        return listed_ids[index]

    def persist() -> None:
        tracker.save_data(flush=True)

    def refresh_list() -> None:
        nonlocal listed_ids
        project_list.delete(0, tk.END)
        listed_ids = []
        projects = cp.list_projects(
            tracker.creative_projects,
            include_archived=bool(show_archived.get()),
        )
        wanted = status_filter.get()
        for project in projects:
            if wanted != "All" and project.get("status") != wanted:
                continue
            archived = " [archived]" if project.get("archived") else ""
            project_list.insert(
                tk.END,
                f"{project['title']}  ·  {project['status']}{archived}",
            )
            listed_ids.append(project["id"])

    def on_new() -> None:
        title = simpledialog.askstring("New project", "Title:", parent=win)
        if title is None:
            return
        try:
            cp.create_project(tracker.creative_projects, root_docs, title=title)
        except ValueError as exc:
            messagebox.showerror("New project", str(exc), parent=win)
            return
        persist()
        refresh_list()

    def on_rename() -> None:
        project_id = selected_id()
        if not project_id:
            messagebox.showinfo("Rename", "Select a project first.", parent=win)
            return
        project = cp.get_project(tracker.creative_projects, project_id)
        if not project:
            return
        title = simpledialog.askstring(
            "Rename project",
            "Title:",
            initialvalue=project["title"],
            parent=win,
        )
        if title is None:
            return
        try:
            cp.rename_project(tracker.creative_projects, project_id, title)
        except ValueError as exc:
            messagebox.showerror("Rename", str(exc), parent=win)
            return
        persist()
        refresh_list()

    def on_set_status() -> None:
        project_id = selected_id()
        if not project_id:
            messagebox.showinfo("Status", "Select a project first.", parent=win)
            return
        project = cp.get_project(tracker.creative_projects, project_id)
        if not project:
            return
        dialog = tk.Toplevel(win)
        dialog.title("Set status")
        dialog.transient(win)
        dialog.grab_set()
        choice = tk.StringVar(value=project["status"])
        ttk.Label(dialog, text="Status", padding=12).pack(anchor="w")
        box = ttk.Combobox(dialog, textvariable=choice, values=list(cp.STATUSES), state="readonly")
        box.pack(padx=12, pady=(0, 12))

        def apply() -> None:
            cp.set_project_status(tracker.creative_projects, project_id, choice.get())
            persist()
            refresh_list()
            dialog.destroy()

        ttk.Button(dialog, text="Apply", command=apply).pack(pady=(0, 12))

    def on_archive() -> None:
        project_id = selected_id()
        if not project_id:
            messagebox.showinfo("Archive", "Select a project first.", parent=win)
            return
        project = cp.get_project(tracker.creative_projects, project_id)
        if not project:
            return
        archive = not bool(project.get("archived"))
        label = "Archive" if archive else "Unarchive"
        if not messagebox.askyesno(label, f"{label} “{project['title']}”?", parent=win):
            return
        cp.archive_project(tracker.creative_projects, project_id, archived=archive)
        persist()
        refresh_list()

    def on_delete() -> None:
        project_id = selected_id()
        if not project_id:
            messagebox.showinfo("Delete", "Select a project first.", parent=win)
            return
        project = cp.get_project(tracker.creative_projects, project_id)
        if not project:
            return
        if not messagebox.askyesno(
            "Delete project",
            f"Permanently delete “{project['title']}” and its documents?\nThis cannot be undone.",
            parent=win,
        ):
            return
        cp.delete_project(tracker.creative_projects, root_docs, project_id)
        persist()
        refresh_list()

    def on_open_inspiration() -> None:
        project_id = selected_id()
        if not project_id:
            messagebox.showinfo("Inspiration", "Select a project first.", parent=win)
            return
        open_document_window(tracker, project_id, cp.DOC_INSPIRATION)

    def on_open_manuscript() -> None:
        project_id = selected_id()
        if not project_id:
            messagebox.showinfo("Continue Writing", "Select a project first.", parent=win)
            return
        open_document_window(tracker, project_id, cp.DOC_MANUSCRIPT)

    def on_open_both() -> None:
        project_id = selected_id()
        if not project_id:
            messagebox.showinfo("Open both", "Select a project first.", parent=win)
            return
        open_document_window(tracker, project_id, cp.DOC_INSPIRATION)
        open_document_window(tracker, project_id, cp.DOC_MANUSCRIPT)

    def on_double_click(_event=None) -> None:
        if selected_id():
            on_open_manuscript()

    project_list.bind("<Double-Button-1>", on_double_click)

    ttk.Button(manage, text="New", command=on_new).pack(side=tk.LEFT)
    ttk.Button(manage, text="Rename", command=on_rename).pack(side=tk.LEFT, padx=6)
    ttk.Button(manage, text="Status", command=on_set_status).pack(side=tk.LEFT, padx=6)
    ttk.Button(manage, text="Archive", command=on_archive).pack(side=tk.LEFT, padx=6)
    ttk.Button(manage, text="Delete", command=on_delete).pack(side=tk.LEFT, padx=6)

    ttk.Button(
        write,
        text="Continue Writing",
        style="Accent.TButton",
        command=on_open_manuscript,
    ).pack(side=tk.LEFT)
    ttk.Button(write, text="Open Inspiration", command=on_open_inspiration).pack(side=tk.LEFT, padx=(10, 6))
    ttk.Button(write, text="Open Both", command=on_open_both).pack(side=tk.LEFT, padx=6)
    ttk.Label(
        write,
        text="Double-click a project to continue writing",
        style="Muted.TLabel",
    ).pack(side=tk.LEFT, padx=(12, 0))

    refresh_list()


def open_document_window(
    tracker: PersonalDevelopmentTracker,
    project_id: str,
    role: str,
) -> tk.Toplevel | None:
    """Open or focus Inspiration/Manuscript window for a project (SPEC-303)."""
    if focus_existing_document_window(project_id, role):
        state = _open_doc_windows.get(document_window_key(project_id, role))
        return state.get("window") if state else None

    project = cp.get_project(tracker.creative_projects, project_id)
    if project is None:
        messagebox.showerror("Writing", "Project not found.")
        return None

    root_docs = creative_projects_dir()
    label = role_label(role)
    theme = tracker.theme
    key = document_window_key(project_id, role)

    win = tk.Toplevel(tracker.root)
    win.title(f"{label} · {project['title']}")
    win.geometry("720x900" if role == cp.DOC_MANUSCRIPT else "640x800")
    win.minsize(480, 360)
    win.configure(bg=theme["bg"])

    dirty = {"value": False}
    debounce_id: dict[str, str | None] = {"value": None}

    header = ttk.Frame(win, padding=(12, 10, 12, 6))
    header.pack(side=tk.TOP, fill=tk.X)
    ttk.Label(header, text=f"{label} · {project['title']}", style="Title.TLabel").pack(anchor="w")
    status = ttk.Label(header, text="", style="Muted.TLabel")
    status.pack(anchor="w", pady=(4, 0))

    footer = ttk.Frame(win, padding=(12, 8, 12, 12))
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    editor_host = ttk.Frame(win)
    editor_host.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))
    editor_host.columnconfigure(0, weight=1)
    editor_host.rowconfigure(0, weight=1)

    text = tk.Text(
        editor_host,
        wrap=tk.WORD,
        undo=True,
        font=FONTS.get("mono", FONTS.get("body", ("Consolas", 11))),
    )
    text.grid(row=0, column=0, sticky="nsew")
    scroll = ttk.Scrollbar(editor_host, orient=tk.VERTICAL, command=text.yview)
    scroll.grid(row=0, column=1, sticky="ns")
    text.configure(yscrollcommand=scroll.set)
    style_text_widget(text, theme)
    text.insert("1.0", cp.read_document(root_docs, project_id, role))

    def current_body() -> str:
        return text.get("1.0", "end-1c")

    def refresh_status(prefix: str) -> None:
        status.config(text=format_doc_status(prefix, current_body()))

    def do_save() -> None:
        body = current_body()
        cp.write_document(root_docs, project_id, role, body)
        try:
            cp.touch_project(tracker.creative_projects, project_id)
            tracker.save_data(flush=True)
        except KeyError:
            pass
        dirty["value"] = False
        refresh_status("Saved")

    def cancel_debounce() -> None:
        after_id = debounce_id["value"]
        if after_id is not None:
            try:
                win.after_cancel(after_id)
            except tk.TclError:
                pass
            debounce_id["value"] = None

    def schedule_autosave(_event=None) -> None:
        dirty["value"] = True
        status.config(text=format_doc_status("Unsaved", current_body()))
        cancel_debounce()

        def fire() -> None:
            debounce_id["value"] = None
            if dirty["value"] and win.winfo_exists():
                do_save()

        debounce_id["value"] = win.after(AUTOSAVE_DEBOUNCE_MS, fire)

    def on_modified(_event=None) -> None:
        if text.edit_modified():
            text.edit_modified(False)
            schedule_autosave()

    def on_close() -> None:
        cancel_debounce()
        if dirty["value"]:
            do_save()
        _open_doc_windows.pop(key, None)
        win.destroy()

    text.bind("<<Modified>>", on_modified)
    win.protocol("WM_DELETE_WINDOW", on_close)

    ttk.Button(footer, text="Save", command=do_save).pack(side=tk.LEFT)
    if role == cp.DOC_MANUSCRIPT:
        ttk.Button(
            footer,
            text="Log session for today",
            command=lambda: tracker.log_writing_session_for_day(parent=win),
        ).pack(side=tk.LEFT, padx=(10, 0))
    ttk.Button(footer, text="Close", command=on_close).pack(side=tk.RIGHT)

    _open_doc_windows[key] = {
        "window": win,
        "dirty": dirty,
        "save": do_save,
        "role": role,
        "project_id": project_id,
    }

    refresh_status(label)
    dirty["value"] = False
    return win

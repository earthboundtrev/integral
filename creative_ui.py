"""Creative writing projects library UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import TYPE_CHECKING

import creative_projects as cp
from paths import creative_projects_dir
from theme import FONTS, style_listbox, style_text_widget

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker

# Registry for SPEC-303: (project_id, role) -> Toplevel
_open_doc_windows: dict[tuple[str, str], tk.Toplevel] = {}


def show_writing_projects_window(tracker: PersonalDevelopmentTracker) -> None:
    theme = tracker.theme
    win = tk.Toplevel(tracker.root)
    win.title("Writing Projects")
    win.geometry("780x560")
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
        text="Novels, scripts, and ideas — each with an inspiration document and a manuscript. "
        "Text is stored locally on this machine.",
        style="Muted.TLabel",
        wraplength=720,
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

    actions = ttk.Frame(body)
    actions.grid(row=1, column=0, sticky="ew", pady=(10, 0))

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
            messagebox.showinfo("Manuscript", "Select a project first.", parent=win)
            return
        open_document_window(tracker, project_id, cp.DOC_MANUSCRIPT)

    ttk.Button(actions, text="New", command=on_new).pack(side=tk.LEFT)
    ttk.Button(actions, text="Rename", command=on_rename).pack(side=tk.LEFT, padx=6)
    ttk.Button(actions, text="Status", command=on_set_status).pack(side=tk.LEFT, padx=6)
    ttk.Button(actions, text="Archive", command=on_archive).pack(side=tk.LEFT, padx=6)
    ttk.Button(actions, text="Delete", command=on_delete).pack(side=tk.LEFT, padx=6)
    ttk.Button(actions, text="Open Inspiration", command=on_open_inspiration).pack(side=tk.LEFT, padx=(16, 6))
    ttk.Button(actions, text="Open Manuscript", command=on_open_manuscript).pack(side=tk.LEFT, padx=6)

    refresh_list()


def open_document_window(
    tracker: PersonalDevelopmentTracker,
    project_id: str,
    role: str,
) -> None:
    """Thin placeholder editor; SPEC-303 will expand dual-window polish."""
    key = (project_id, role)
    existing = _open_doc_windows.get(key)
    if existing is not None:
        try:
            if existing.winfo_exists():
                existing.lift()
                existing.focus_force()
                return
        except tk.TclError:
            pass
        _open_doc_windows.pop(key, None)

    project = cp.get_project(tracker.creative_projects, project_id)
    if project is None:
        messagebox.showerror("Writing", "Project not found.")
        return

    root_docs = creative_projects_dir()
    role_label = "Inspiration" if role == cp.DOC_INSPIRATION else "Manuscript"
    theme = tracker.theme

    win = tk.Toplevel(tracker.root)
    win.title(f"{role_label} · {project['title']}")
    win.geometry("720x880" if role == cp.DOC_MANUSCRIPT else "640x800")
    win.configure(bg=theme["bg"])
    _open_doc_windows[key] = win

    def on_close() -> None:
        _open_doc_windows.pop(key, None)
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", on_close)

    header = ttk.Frame(win, padding=(12, 10, 12, 6))
    header.pack(side=tk.TOP, fill=tk.X)
    ttk.Label(header, text=f"{role_label} — {project['title']}", style="Title.TLabel").pack(anchor="w")
    status = ttk.Label(header, text="", style="Muted.TLabel")
    status.pack(anchor="w", pady=(4, 0))

    footer = ttk.Frame(win, padding=(12, 8, 12, 12))
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    text = tk.Text(win, wrap=tk.WORD, undo=True, font=FONTS.get("body", ("Segoe UI", 11)))
    text.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))
    style_text_widget(text, theme)
    text.insert("1.0", cp.read_document(root_docs, project_id, role))

    dirty = {"value": False}

    def mark_dirty(_event=None) -> None:
        dirty["value"] = True
        status.config(text="Unsaved changes")

    text.bind("<<Modified>>", lambda _e: (text.edit_modified(False), mark_dirty()))

    def do_save() -> None:
        body = text.get("1.0", "end-1c")
        cp.write_document(root_docs, project_id, role, body)
        try:
            cp.touch_project(tracker.creative_projects, project_id)
            tracker.save_data(flush=True)
        except KeyError:
            pass
        dirty["value"] = False
        chars = len(body)
        words = len(body.split()) if body.strip() else 0
        status.config(text=f"Saved · {words} words · {chars} characters")

    def autosave() -> None:
        if dirty["value"] and win.winfo_exists():
            do_save()
        if win.winfo_exists():
            win.after(5000, autosave)

    ttk.Button(footer, text="Save", command=do_save).pack(side=tk.LEFT)
    ttk.Button(footer, text="Close", command=on_close).pack(side=tk.RIGHT)
    win.after(5000, autosave)
    body = text.get("1.0", "end-1c")
    chars = len(body)
    words = len(body.split()) if body.strip() else 0
    status.config(text=f"{words} words · {chars} characters")
    dirty["value"] = False

"""Journal window for Integral — formatting, cross-links, backlinks."""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import messagebox, scrolledtext, ttk
from typing import TYPE_CHECKING, Callable

import integral_links
import journal
import richtext
from theme import FONTS, style_listbox, style_text_widget

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker


def apply_integral_link_tags(
    text_widget: tk.Text,
    *,
    on_open: Callable[[integral_links.IntegralLink], None],
    link_color: str = "#5B8DEF",
) -> None:
    """Tag all Integral wiki/URI links and bind click-to-open."""
    text_widget.tag_remove("integral_link", "1.0", "end")
    content = text_widget.get("1.0", "end-1c")
    spans = integral_links.find_all_links(content)
    text_widget.tag_configure("integral_link", foreground=link_color, underline=True)
    for span in spans:
        text_widget.tag_add("integral_link", f"1.0+{span.start}c", f"1.0+{span.end}c")

    def on_click(event: tk.Event) -> str:
        index = text_widget.index(f"@{event.x},{event.y}")
        for span in spans:
            start = f"1.0+{span.start}c"
            end = f"1.0+{span.end}c"
            if text_widget.compare(start, "<=", index) and text_widget.compare(index, "<", end):
                on_open(span)
                return "break"
        return ""

    text_widget.tag_bind("integral_link", "<Button-1>", on_click)
    text_widget.tag_bind("integral_link", "<Enter>", lambda _e: text_widget.config(cursor="hand2"))
    text_widget.tag_bind("integral_link", "<Leave>", lambda _e: text_widget.config(cursor=""))


# Backward-compatible alias
def apply_journal_link_tags(
    text_widget: tk.Text,
    *,
    on_open: Callable[[str], None],
    link_color: str = "#5B8DEF",
) -> None:
    apply_integral_link_tags(
        text_widget,
        on_open=lambda link: on_open(link.target) if link.kind == "journal" else None,
        link_color=link_color,
    )


def show_journal_window(
    tracker: PersonalDevelopmentTracker,
    entry_date: str | None = None,
    *,
    prompt: str | None = None,
    entry_id: str | None = None,
    seed: str | None = None,
) -> None:
    theme = tracker.theme
    win = tk.Toplevel(tracker.root)
    win.title("Journal")
    win.geometry("1040x760")
    win.configure(bg=theme["bg"])
    win.transient(tracker.root)

    footer = ttk.Frame(win, padding=(16, 8, 16, 12))
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Button(footer, text="Close", command=win.destroy).pack(side=tk.RIGHT)

    header = ttk.Frame(win, padding=(16, 14, 16, 8))
    header.pack(side=tk.TOP, fill=tk.X)
    ttk.Label(header, text="Journal", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        header,
        text="Markdown-lite formatting (**bold**, *italic*, # headings, lists, quotes). "
        "Link journal / domain / fitness / writing projects. Enable integral:// in Data & Security for OS paste.",
        style="Muted.TLabel",
        wraplength=980,
    ).pack(anchor="w", pady=(4, 0))

    body = ttk.Frame(win, padding=(16, 0, 16, 8))
    body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    body.columnconfigure(0, weight=1)
    body.columnconfigure(1, weight=3)
    body.rowconfigure(0, weight=1)

    left = ttk.Frame(body)
    left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
    left.rowconfigure(0, weight=1)
    left.columnconfigure(0, weight=1)

    list_panel = ttk.LabelFrame(left, text="Entries", padding=8, style="Card.TLabelframe")
    list_panel.grid(row=0, column=0, sticky="nsew")
    list_panel.rowconfigure(0, weight=1)
    list_panel.columnconfigure(0, weight=1)

    entry_list = tk.Listbox(list_panel, exportselection=False, font=FONTS["body"])
    entry_list.grid(row=0, column=0, sticky="nsew")
    style_listbox(entry_list, theme)
    list_scroll = ttk.Scrollbar(list_panel, orient=tk.VERTICAL, command=entry_list.yview)
    entry_list.configure(yscrollcommand=list_scroll.set)
    list_scroll.grid(row=0, column=1, sticky="ns")

    backlinks_panel = ttk.LabelFrame(left, text="Linked from", padding=8, style="Card.TLabelframe")
    backlinks_panel.grid(row=1, column=0, sticky="ew", pady=(8, 0))
    backlinks_list = tk.Listbox(backlinks_panel, height=5, font=FONTS["body"], exportselection=False)
    backlinks_list.pack(fill=tk.BOTH, expand=True)
    style_listbox(backlinks_list, theme)
    backlink_entries: list[dict] = []

    editor = ttk.LabelFrame(body, text="Write", padding=10, style="Card.TLabelframe")
    editor.grid(row=0, column=1, sticky="nsew")
    editor.columnconfigure(0, weight=1)
    editor.rowconfigure(6, weight=1)

    initial_date = entry_date or datetime.now().strftime("%Y-%m-%d")
    if entry_id:
        existing = journal.get_entry(tracker.journal, entry_id)
        if existing:
            initial_date = existing.get("entry_date", initial_date)

    date_var = tk.StringVar(value=initial_date)
    prompt_var = tk.StringVar(value=prompt or journal.DEFAULT_PROMPTS[0])
    title_var = tk.StringVar(value="")
    backdate_var = tk.StringVar(value="")
    editing_id: dict[str, str | None] = {"value": None}

    row0 = ttk.Frame(editor, style="Surface.TFrame")
    row0.grid(row=0, column=0, sticky="ew", pady=(0, 6))
    ttk.Label(row0, text="Entry date", style="OnSurfaceMuted.TLabel").pack(side=tk.LEFT)
    ttk.Entry(row0, textvariable=date_var, width=12).pack(side=tk.LEFT, padx=(8, 16))
    ttk.Label(row0, text="Prompt", style="OnSurfaceMuted.TLabel").pack(side=tk.LEFT)
    prompt_combo = ttk.Combobox(
        row0,
        textvariable=prompt_var,
        values=tracker.journal.get("prompts", journal.DEFAULT_PROMPTS),
        width=34,
    )
    prompt_combo.pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

    ttk.Label(editor, text="Title (optional)", style="OnSurfaceMuted.TLabel").grid(row=1, column=0, sticky="w")
    ttk.Entry(editor, textvariable=title_var).grid(row=2, column=0, sticky="ew", pady=(0, 8))

    backdate_frame = ttk.Frame(editor, style="Surface.TFrame")
    backdate_frame.grid(row=3, column=0, sticky="ew", pady=(0, 6))
    backdate_label = ttk.Label(
        backdate_frame,
        text="Why are you logging for a past date?",
        style="OnSurfaceSubheading.TLabel",
    )
    backdate_entry = ttk.Entry(backdate_frame, textvariable=backdate_var)
    backdate_hint = ttk.Label(
        backdate_frame,
        text=f"Required when the entry date is before today (min {journal.MIN_BACKDATE_REASON_LEN} chars).",
        style="OnSurfaceMuted.TLabel",
        wraplength=520,
    )

    fmt_bar = ttk.Frame(editor, style="Surface.TFrame")
    fmt_bar.grid(row=4, column=0, sticky="ew", pady=(0, 4))

    ttk.Label(editor, text="Your thoughts", style="OnSurfaceMuted.TLabel").grid(row=5, column=0, sticky="w")
    body_text = scrolledtext.ScrolledText(editor, wrap=tk.WORD, height=16, borderwidth=0)
    body_text.grid(row=6, column=0, sticky="nsew", pady=(4, 0))
    style_text_widget(body_text, theme)

    def refresh_backlinks() -> None:
        nonlocal backlink_entries
        backlinks_list.delete(0, tk.END)
        eid = editing_id["value"]
        if not eid:
            backlinks_list.insert(tk.END, "(Save or select an entry)")
            backlink_entries = []
            return
        backlink_entries = journal.find_backlinks(tracker.journal, eid)
        if not backlink_entries:
            backlinks_list.insert(tk.END, "No backlinks yet")
            return
        for item in backlink_entries:
            backlinks_list.insert(
                tk.END,
                f"{item.get('entry_date')} — {journal.entry_label(item)}",
            )

    def open_integral_link(link: integral_links.IntegralLink) -> None:
        if link.kind == "journal":
            target = journal.get_entry(tracker.journal, link.target)
            if not target:
                messagebox.showwarning(
                    "Missing entry",
                    "That journal link no longer points to an entry.",
                    parent=win,
                )
                return
            refresh_list(select_id=link.target)
            load_selected()
            return
        tracker.open_integral_link(link, parent=win)

    def refresh_decorations(_event=None) -> None:
        apply_integral_link_tags(
            body_text,
            on_open=open_integral_link,
            link_color=theme.get("accent", "#5B8DEF"),
        )
        richtext.apply_richtext_tags(body_text, theme)

    def refresh_backdate_ui(*_args: object) -> None:
        parsed = journal.parse_entry_date(date_var.get())
        if parsed and parsed < date.today():
            backdate_label.pack(anchor="w")
            backdate_entry.pack(fill=tk.X, pady=(4, 2))
            backdate_hint.pack(anchor="w")
        else:
            backdate_label.pack_forget()
            backdate_entry.pack_forget()
            backdate_hint.pack_forget()

    date_var.trace_add("write", refresh_backdate_ui)
    refresh_backdate_ui()

    indexed_entries: list[dict] = []

    def refresh_list(select_id: str | None = None) -> None:
        nonlocal indexed_entries
        entry_list.delete(0, tk.END)
        indexed_entries = journal.list_entries(tracker.journal)
        select_index = 0
        for index, item in enumerate(indexed_entries):
            label = item.get("title") or item.get("prompt") or "Journal"
            suffix = " ↩" if item.get("backdate_reason") else ""
            entry_list.insert(tk.END, f"{item['entry_date']}  {label}{suffix}")
            if select_id and item.get("id") == select_id:
                select_index = index
        if indexed_entries:
            entry_list.selection_set(select_index)
            entry_list.see(select_index)

    def load_selected(_event=None) -> None:
        selection = entry_list.curselection()
        if not selection:
            return
        item = indexed_entries[selection[0]]
        editing_id["value"] = item["id"]
        date_var.set(item["entry_date"])
        prompt_var.set(item.get("prompt", journal.DEFAULT_PROMPTS[0]))
        title_var.set(item.get("title", ""))
        backdate_var.set(item.get("backdate_reason") or "")
        body_text.delete("1.0", tk.END)
        body_text.insert("1.0", item.get("body", ""))
        refresh_backdate_ui()
        refresh_decorations()
        refresh_backlinks()

    def clear_editor() -> None:
        editing_id["value"] = None
        date_var.set(datetime.now().strftime("%Y-%m-%d"))
        prompt_var.set(journal.DEFAULT_PROMPTS[0])
        title_var.set("")
        backdate_var.set("")
        body_text.delete("1.0", tk.END)
        entry_list.selection_clear(0, tk.END)
        refresh_backdate_ui()
        refresh_decorations()
        refresh_backlinks()

    def current_entry_for_link() -> dict | None:
        if editing_id["value"]:
            return journal.get_entry(tracker.journal, editing_id["value"])
        selection = entry_list.curselection()
        if selection:
            return indexed_entries[selection[0]]
        return None

    def copy_link() -> None:
        item = current_entry_for_link()
        if not item:
            messagebox.showinfo("Copy link", "Select or save an entry first.", parent=win)
            return
        uri = integral_links.format_journal_uri(item["id"])
        wiki = integral_links.format_journal_wiki(item["id"], journal.entry_label(item))
        win.clipboard_clear()
        win.clipboard_append(f"{uri}\n{wiki}")
        messagebox.showinfo(
            "Copied",
            "OS link and wiki link copied.\nPaste the integral:// line outside Integral.",
            parent=win,
        )

    def insert_link() -> None:
        picker = tk.Toplevel(win)
        picker.title("Insert link")
        picker.geometry("560x480")
        picker.transient(win)
        picker.configure(bg=theme["bg"])
        notebook = ttk.Notebook(picker)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        def make_list_tab(title: str) -> tuple[ttk.Frame, tk.Listbox]:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            lb = tk.Listbox(frame, font=FONTS["body"])
            lb.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
            style_listbox(lb, theme)
            return frame, lb

        _, journal_lb = make_list_tab("Journal")
        _, domain_lb = make_list_tab("Domain day")
        _, fitness_lb = make_list_tab("Fitness day")
        _, project_lb = make_list_tab("Writing")

        journal_choices = [e for e in journal.list_entries(tracker.journal) if e.get("id") != editing_id["value"]]
        for item in journal_choices:
            journal_lb.insert(tk.END, f"{item['entry_date']} — {journal.entry_label(item)}")

        domain_choices: list[tuple[str, str]] = []
        for day in sorted(tracker.entries.keys(), reverse=True)[:60]:
            for cat in tracker.entries[day]:
                domain_choices.append((day, cat))
                domain_lb.insert(tk.END, f"{day} — {cat}")

        fitness_days = sorted(
            {s.get("date") for s in tracker.sessions if s.get("date")},
            reverse=True,
        )[:60]
        for day in fitness_days:
            fitness_lb.insert(tk.END, day)

        project_choices = list(tracker.creative_projects.get("projects") or [])
        for project in project_choices:
            project_lb.insert(tk.END, project.get("title") or project.get("id"))

        def do_insert() -> None:
            tab = notebook.index(notebook.select())
            ref = None
            if tab == 0:
                sel = journal_lb.curselection()
                if not sel:
                    return
                item = journal_choices[sel[0]]
                ref = integral_links.format_journal_wiki(item["id"], journal.entry_label(item))
            elif tab == 1:
                sel = domain_lb.curselection()
                if not sel:
                    return
                day, cat = domain_choices[sel[0]]
                ref = integral_links.format_domain_wiki(day, cat)
            elif tab == 2:
                sel = fitness_lb.curselection()
                if not sel:
                    return
                day = fitness_days[sel[0]]
                ref = integral_links.format_fitness_wiki(day, "Fitness")
            else:
                sel = project_lb.curselection()
                if not sel:
                    return
                project = project_choices[sel[0]]
                ref = integral_links.format_project_wiki(project["id"], project.get("title"))
            body_text.insert(tk.INSERT, ref or "")
            refresh_decorations()
            picker.destroy()

        btns = ttk.Frame(picker, padding=12)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Insert", style="Accent.TButton", command=do_insert).pack(side=tk.LEFT)
        ttk.Button(btns, text="Cancel", command=picker.destroy).pack(side=tk.LEFT, padx=8)

    def save_entry() -> None:
        entry_date_value = date_var.get().strip()
        reason = backdate_var.get().strip()
        error = journal.validate_backdate(entry_date_value, reason=reason)
        if error:
            messagebox.showwarning("Date", error, parent=win)
            return
        body_value = body_text.get("1.0", tk.END).strip()
        if not body_value:
            messagebox.showinfo("Journal", "Write something before saving.", parent=win)
            return
        try:
            item = journal.create_entry(
                entry_date_value,
                body_value,
                prompt=prompt_var.get(),
                title=title_var.get(),
                backdate_reason=reason or None,
                entry_id=editing_id["value"],
            )
        except ValueError as exc:
            messagebox.showwarning("Journal", str(exc), parent=win)
            return
        if editing_id["value"]:
            for existing in tracker.journal.get("entries", []):
                if existing.get("id") == editing_id["value"]:
                    item["written_at"] = existing.get("written_at", item["written_at"])
                    break
        journal.upsert_entry(tracker.journal, item)
        tracker._invalidate_caches()
        if entry_date_value == tracker.today_str() and tracker._reminder_scheduler is not None:
            tracker._reminder_scheduler.notify_logged_today()
        tracker.refresh_dashboard()
        tracker.save_data()
        clear_editor()
        refresh_list(select_id=item["id"])
        load_selected()

    def delete_selected() -> None:
        selection = entry_list.curselection()
        if not selection:
            return
        item = indexed_entries[selection[0]]
        if not messagebox.askyesno("Delete entry", "Delete this journal entry?", parent=win):
            return
        journal.delete_entry(tracker.journal, item["id"])
        tracker._invalidate_caches()
        tracker.refresh_dashboard()
        tracker.save_data()
        clear_editor()
        refresh_list()

    def on_backlink_select(_event=None) -> None:
        sel = backlinks_list.curselection()
        if not sel or not backlink_entries:
            return
        if sel[0] >= len(backlink_entries):
            return
        item = backlink_entries[sel[0]]
        refresh_list(select_id=item["id"])
        load_selected()

    def fmt(action: str) -> None:
        if action == "bold":
            richtext.wrap_selection(body_text, "**")
        elif action == "italic":
            richtext.wrap_selection(body_text, "*")
        elif action == "code":
            richtext.wrap_selection(body_text, "`")
        elif action == "h1":
            richtext.insert_line_prefix(body_text, "# ")
        elif action == "h2":
            richtext.insert_line_prefix(body_text, "## ")
        elif action == "quote":
            richtext.insert_line_prefix(body_text, "> ")
        elif action == "list":
            richtext.insert_line_prefix(body_text, "- ")
        refresh_decorations()

    for label, action in (
        ("B", "bold"),
        ("I", "italic"),
        ("Code", "code"),
        ("H1", "h1"),
        ("H2", "h2"),
        ("Quote", "quote"),
        ("List", "list"),
    ):
        ttk.Button(fmt_bar, text=label, width=5, command=lambda a=action: fmt(a)).pack(side=tk.LEFT, padx=2)

    entry_list.bind("<<ListboxSelect>>", load_selected)
    backlinks_list.bind("<<ListboxSelect>>", on_backlink_select)
    body_text.bind("<KeyRelease>", refresh_decorations)

    list_btns = ttk.Frame(list_panel)
    list_btns.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    ttk.Button(list_btns, text="New", command=clear_editor).pack(side=tk.LEFT)
    ttk.Button(list_btns, text="Delete", command=delete_selected).pack(side=tk.LEFT, padx=6)

    editor_btns = ttk.Frame(editor)
    editor_btns.grid(row=7, column=0, sticky="ew", pady=(10, 0))
    ttk.Button(editor_btns, text="Save Entry", style="Accent.TButton", command=save_entry).pack(side=tk.LEFT)
    ttk.Button(editor_btns, text="Clear", command=clear_editor).pack(side=tk.LEFT, padx=8)
    ttk.Button(editor_btns, text="Copy link", command=copy_link).pack(side=tk.LEFT, padx=8)
    ttk.Button(editor_btns, text="Insert link…", command=insert_link).pack(side=tk.LEFT)

    refresh_list(select_id=entry_id)
    if entry_id and journal.get_entry(tracker.journal, entry_id):
        load_selected()
    else:
        if seed and str(seed).strip():
            body_text.insert("1.0", str(seed).strip() + "\n\n")
        refresh_decorations()
        refresh_backlinks()
        body_text.focus_set()

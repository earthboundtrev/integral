"""Export, backup, milestones, vault, and onboarding dialogs for Integral."""

from __future__ import annotations

import os
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable

from integral_io import (
    export_fitness_sessions_csv,
    export_journal_csv,
    export_life_entries_csv,
    export_milestones_csv,
    load_backup,
    restore_backup_to_path,
    write_backup,
)
from milestones import current_quarter_label, merge_milestones, milestone_summary
from notifications import normalize_notification_settings, show_windows_notification
from paths import APP_NAME
from theme import style_listbox, style_text_widget
from vault import CRYPTO_AVAILABLE, encrypt_payload, is_encrypted_file
import autostart_windows
import ui_scroll

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker


def show_export_dialog(tracker: PersonalDevelopmentTracker) -> None:
    folder = filedialog.askdirectory(title="Choose export folder")
    if not folder:
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    life_path = os.path.join(folder, f"integral-life-{stamp}.csv")
    fitness_path = os.path.join(folder, f"integral-fitness-{stamp}.csv")
    milestone_path = os.path.join(folder, f"integral-milestones-{stamp}.csv")
    journal_path = os.path.join(folder, f"integral-journal-{stamp}.csv")
    try:
        life_rows = export_life_entries_csv(tracker.entries, tracker.categories, life_path)
        fitness_rows = export_fitness_sessions_csv(tracker.sessions, tracker.programs, fitness_path)
        milestone_rows = export_milestones_csv(tracker.milestones, milestone_path)
        journal_rows = export_journal_csv(tracker.journal, journal_path)
        messagebox.showinfo(
            "Export complete",
            f"Exported to:\n{life_path}\n({life_rows} life rows)\n\n"
            f"{fitness_path}\n({fitness_rows} fitness rows)\n\n"
            f"{milestone_path}\n({milestone_rows} milestones)\n\n"
            f"{journal_path}\n({journal_rows} journal entries)",
        )
    except OSError as exc:
        messagebox.showerror("Export failed", str(exc))


def show_backup_dialog(tracker: PersonalDevelopmentTracker) -> None:
    window = tk.Toplevel(tracker.root)
    window.title("Backup & Restore")
    window.geometry("520x320")
    window.configure(bg=tracker.theme["bg"])
    window.transient(tracker.root)

    ttk.Label(
        window,
        text="Back up your full journal (life areas, general journal, fitness + milestones) as JSON.\n"
        "Restore replaces the current data file (a .bak copy is kept).",
        wraplength=480,
    ).pack(anchor="w", padx=15, pady=15)

    def backup_now() -> None:
        path = filedialog.asksaveasfilename(
            title="Save backup",
            defaultextension=".json",
            filetypes=[("JSON backup", "*.json"), ("All files", "*.*")],
            initialfile=f"integral-backup-{datetime.now().strftime('%Y%m%d')}.json",
        )
        if not path:
            return
        try:
            write_backup(tracker._payload(), path)
            messagebox.showinfo("Backup saved", f"Backup written to:\n{path}")
        except OSError as exc:
            messagebox.showerror("Backup failed", str(exc))

    def restore_now() -> None:
        path = filedialog.askopenfilename(
            title="Restore backup",
            filetypes=[("JSON backup", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Confirm restore",
            "This replaces your current journal with the backup. Continue?",
        ):
            return
        try:
            backup = load_backup(path)
            restore_backup_to_path(backup, tracker.data_path, make_copy=True)
            tracker.load_data()
            tracker.create_dashboard()
            window.destroy()
            messagebox.showinfo("Restored", "Journal restored from backup.")
        except (OSError, ValueError) as exc:
            messagebox.showerror("Restore failed", str(exc))

    buttons = ttk.Frame(window)
    buttons.pack(fill=tk.X, padx=15, pady=10)
    ttk.Button(buttons, text="Export Backup…", command=backup_now).pack(side=tk.LEFT, padx=4)
    ttk.Button(buttons, text="Restore from Backup…", command=restore_now).pack(side=tk.LEFT, padx=4)
    ttk.Button(buttons, text="Close", command=window.destroy).pack(side=tk.RIGHT)


def show_milestones_dialog(tracker: PersonalDevelopmentTracker) -> None:
    window = tk.Toplevel(tracker.root)
    window.title("Quarterly Milestones")
    window.geometry("720x520")
    window.minsize(640, 420)
    window.configure(bg=tracker.theme["bg"])
    window.transient(tracker.root)

    year, quarter, label = current_quarter_label()

    buttons = ttk.Frame(window)
    buttons.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=12)
    add_btn = ttk.Button(buttons, text="Add")
    add_btn.pack(side=tk.LEFT)
    apply_btn = ttk.Button(buttons, text="Apply")
    apply_btn.pack(side=tk.LEFT, padx=8)
    save_btn = ttk.Button(buttons, text="Save & Close")
    save_btn.pack(side=tk.RIGHT)
    ttk.Button(buttons, text="Cancel", command=window.destroy).pack(side=tk.RIGHT, padx=8)

    ttk.Label(window, text=f"{label} — track what matters this quarter", font=("Helvetica", 13, "bold")).pack(
        side=tk.TOP, anchor="w", padx=12, pady=12
    )

    body = ttk.Frame(window)
    body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(0, weight=1)

    listbox = tk.Listbox(body, height=12, exportselection=False)
    listbox.grid(row=0, column=0, sticky="nsew")
    style_listbox(listbox, tracker.theme)

    editor = ttk.Frame(body)
    editor.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
    editor.columnconfigure(0, weight=1)

    title_var = tk.StringVar()
    status_var = tk.StringVar(value="open")
    notes_text = scrolledtext.ScrolledText(editor, height=8, wrap=tk.WORD)
    style_text_widget(notes_text, tracker.theme)

    ttk.Label(editor, text="Title").grid(row=0, column=0, sticky="w")
    ttk.Entry(editor, textvariable=title_var, width=40).grid(row=1, column=0, sticky="ew", pady=(0, 8))
    ttk.Label(editor, text="Status").grid(row=2, column=0, sticky="w")
    ttk.Combobox(editor, textvariable=status_var, values=["open", "in_progress", "done"], state="readonly").grid(
        row=3, column=0, sticky="w", pady=(0, 8)
    )
    ttk.Label(editor, text="Notes").grid(row=4, column=0, sticky="w")
    notes_text.grid(row=5, column=0, sticky="nsew")
    editor.rowconfigure(5, weight=1)

    working = list(tracker.milestones)

    def refresh_list(select_index: int | None = None) -> None:
        listbox.delete(0, tk.END)
        for item in working:
            status = item.get("status", "open")
            mark = "✓" if status == "done" else "○"
            listbox.insert(tk.END, f"{mark} {item.get('title', '')}")
        if select_index is not None and 0 <= select_index < len(working):
            listbox.selection_set(select_index)
            load_selected()

    def load_selected(*_args: object) -> None:
        selection = listbox.curselection()
        if not selection:
            return
        item = working[selection[0]]
        title_var.set(item.get("title", ""))
        status_var.set(item.get("status", "open"))
        notes_text.delete("1.0", tk.END)
        notes_text.insert("1.0", item.get("notes", ""))

    def apply_editor() -> None:
        selection = listbox.curselection()
        if not selection:
            return
        item = working[selection[0]]
        item["title"] = title_var.get().strip() or item.get("title", "Untitled")
        item["status"] = status_var.get()
        item["notes"] = notes_text.get("1.0", tk.END).strip()
        if item["status"] == "done" and not item.get("completed_date"):
            item["completed_date"] = datetime.now().strftime("%Y-%m-%d")
        refresh_list(selection[0])

    def add_milestone() -> None:
        working.append(
            {
                "year": year,
                "quarter": quarter,
                "title": f"New milestone for {label}",
                "status": "open",
                "notes": "",
                "completed_date": "",
            }
        )
        refresh_list(len(working) - 1)

    def save_all() -> None:
        apply_editor()
        tracker.milestones = working
        tracker._invalidate_caches()
        tracker.save_data()
        window.destroy()
        messagebox.showinfo("Saved", milestone_summary(tracker.milestones))
        tracker.refresh_dashboard()

    listbox.bind("<<ListboxSelect>>", load_selected)

    add_btn.configure(command=add_milestone)
    apply_btn.configure(command=apply_editor)
    save_btn.configure(command=save_all)

    refresh_list(0 if working else None)


def show_security_dialog(tracker: PersonalDevelopmentTracker) -> None:
    window = tk.Toplevel(tracker.root)
    window.title("Data & Security")
    window.geometry("580x560")
    window.minsize(520, 480)
    window.configure(bg=tracker.theme["bg"])
    window.transient(tracker.root)

    outer, inner, _canvas = ui_scroll.make_scrollable_frame(window)
    outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=8)

    encrypted = bool(tracker.settings.get("encryption_enabled"))
    ttk.Label(inner, text="Encryption at rest", font=("Helvetica", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 4))
    status = "ON — journal file is encrypted" if encrypted else "OFF — journal stored as plain JSON"
    ttk.Label(inner, text=status, wraplength=500).pack(anchor="w", padx=15)

    if not CRYPTO_AVAILABLE:
        ttk.Label(
            inner,
            text="Install cryptography for encryption: pip install cryptography",
            foreground=tracker.theme.get("accent", "#5B8DEF"),
            wraplength=500,
        ).pack(anchor="w", padx=15, pady=8)

    ttk.Label(
        inner,
        text="Passphrase is kept in memory for this session only. "
        "If you forget it, encrypted data cannot be recovered.",
        wraplength=500,
    ).pack(anchor="w", padx=15, pady=8)

    def enable_encryption() -> None:
        if not CRYPTO_AVAILABLE:
            messagebox.showwarning("Unavailable", "Install cryptography first.")
            return
        passphrase = simpledialog.askstring("Set passphrase", "Choose a passphrase:", show="*", parent=window)
        if not passphrase:
            return
        confirm = simpledialog.askstring("Confirm", "Re-enter passphrase:", show="*", parent=window)
        if passphrase != confirm:
            messagebox.showerror("Mismatch", "Passphrases do not match.")
            return
        try:
            tracker.vault_passphrase = passphrase
            tracker.settings["encryption_enabled"] = True
            tracker.save_data()
            window.destroy()
            messagebox.showinfo("Enabled", "Journal encryption is now enabled.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed", str(exc))

    def disable_encryption() -> None:
        if encrypted:
            passphrase = simpledialog.askstring("Unlock", "Enter current passphrase:", show="*", parent=window)
            if not passphrase:
                return
            tracker.vault_passphrase = passphrase
        tracker.settings["encryption_enabled"] = False
        tracker.vault_passphrase = None
        tracker.save_data()
        window.destroy()
        messagebox.showinfo("Disabled", "Journal saved as plain JSON.")

    def change_passphrase() -> None:
        if not encrypted:
            messagebox.showinfo("Not encrypted", "Enable encryption first.")
            return
        old = simpledialog.askstring("Current", "Current passphrase:", show="*", parent=window)
        if not old:
            return
        new = simpledialog.askstring("New", "New passphrase:", show="*", parent=window)
        if not new:
            return
        confirm = simpledialog.askstring("Confirm", "Confirm new passphrase:", show="*", parent=window)
        if new != confirm:
            messagebox.showerror("Mismatch", "Passphrases do not match.")
            return
        try:
            payload = tracker._payload()
            encrypt_payload(payload, new)  # validate crypto works
            tracker.vault_passphrase = new
            tracker.save_data()
            messagebox.showinfo("Updated", "Passphrase changed.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Failed", str(exc))

    enc_buttons = ttk.Frame(inner)
    enc_buttons.pack(fill=tk.X, padx=15, pady=(8, 12))
    if not encrypted:
        ttk.Button(enc_buttons, text="Enable encryption…", command=enable_encryption).pack(side=tk.LEFT)
    else:
        ttk.Button(enc_buttons, text="Change passphrase…", command=change_passphrase).pack(side=tk.LEFT, padx=4)
        ttk.Button(enc_buttons, text="Disable encryption…", command=disable_encryption).pack(side=tk.LEFT, padx=4)

    ttk.Separator(inner, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=15, pady=8)
    ttk.Label(inner, text="Reminders & background", font=("Helvetica", 13, "bold")).pack(
        anchor="w", padx=15, pady=(4, 4)
    )
    ttk.Label(
        inner,
        text="Windows toasts only fire while Integral is running. The portable zip is not an "
        "installed background service — enable the options below so reminders can keep working "
        "after you close the window or after you sign in.",
        wraplength=500,
        style="Muted.TLabel",
    ).pack(anchor="w", padx=15, pady=(0, 8))

    tracker.settings = normalize_notification_settings(tracker.settings)
    notes = tracker.settings["notifications"]
    if autostart_windows.is_supported():
        notes["start_with_windows"] = autostart_windows.is_enabled()
        tracker.settings["notifications"] = notes
    reminders_on = tk.BooleanVar(value=bool(notes.get("enabled", True)))
    minimize_on_close = tk.BooleanVar(value=bool(notes.get("minimize_on_close", False)))
    start_with_windows = tk.BooleanVar(value=bool(notes.get("start_with_windows", False)))

    def persist_notification_flags() -> None:
        tracker.settings = normalize_notification_settings(tracker.settings)
        tracker.settings["notifications"]["enabled"] = bool(reminders_on.get())
        tracker.settings["notifications"]["minimize_on_close"] = bool(minimize_on_close.get())
        tracker.settings["notifications"]["start_with_windows"] = bool(start_with_windows.get())
        tracker.save_data(flush=True)

    def on_reminders_toggle() -> None:
        persist_notification_flags()

    def on_minimize_toggle() -> None:
        persist_notification_flags()

    def on_autostart_toggle() -> None:
        if not autostart_windows.is_supported():
            start_with_windows.set(False)
            messagebox.showinfo("Start with Windows", "Only available on Windows.", parent=window)
            return
        try:
            autostart_windows.set_enabled(bool(start_with_windows.get()))
        except OSError as exc:
            start_with_windows.set(autostart_windows.is_enabled())
            messagebox.showerror("Start with Windows", str(exc), parent=window)
            return
        persist_notification_flags()

    ttk.Checkbutton(
        inner,
        text="Enable daily reminder toasts (while Integral is running)",
        variable=reminders_on,
        command=on_reminders_toggle,
    ).pack(anchor="w", padx=15, pady=2)
    ttk.Checkbutton(
        inner,
        text="Minimize to taskbar on close (keep reminders running)",
        variable=minimize_on_close,
        command=on_minimize_toggle,
    ).pack(anchor="w", padx=15, pady=2)
    autostart_cb = ttk.Checkbutton(
        inner,
        text="Start Integral with Windows",
        variable=start_with_windows,
        command=on_autostart_toggle,
    )
    autostart_cb.pack(anchor="w", padx=15, pady=2)
    if not autostart_windows.is_supported():
        autostart_cb.state(["disabled"])

    def send_test() -> None:
        ok = show_windows_notification(APP_NAME, "Test notification from Integral — reminders are working.")
        if ok:
            messagebox.showinfo("Test notification", "Toast dispatched. If you did not see it, check Windows notification settings for Integral / PowerShell.", parent=window)
        else:
            messagebox.showwarning(
                "Test notification",
                "Could not send a Windows toast from this session (non-Windows or blocked).",
                parent=window,
            )

    rem_buttons = ttk.Frame(inner)
    rem_buttons.pack(fill=tk.X, padx=15, pady=(10, 8))
    ttk.Button(rem_buttons, text="Send test notification", command=send_test).pack(side=tk.LEFT)
    ttk.Button(
        rem_buttons,
        text="Quit Integral completely",
        command=lambda: (window.destroy(), tracker.quit_app()),
    ).pack(side=tk.LEFT, padx=8)

    footer = ttk.Frame(window, padding=(15, 8, 15, 12))
    footer.pack(side=tk.BOTTOM, fill=tk.X)
    ttk.Button(footer, text="Close", command=window.destroy).pack(side=tk.RIGHT)


def prompt_vault_unlock(tracker: PersonalDevelopmentTracker) -> bool:
    if not is_encrypted_file(tracker.data_path):
        return True
    for _attempt in range(3):
        passphrase = simpledialog.askstring(
            "Unlock Integral",
            "Enter your journal passphrase:",
            show="*",
            parent=tracker.root,
        )
        if passphrase is None:
            return False
        try:
            from vault import decrypt_payload
            import json

            with open(tracker.data_path, encoding="utf-8") as handle:
                envelope = json.load(handle)
            decrypt_payload(envelope, passphrase)
            tracker.vault_passphrase = passphrase
            return True
        except Exception:  # noqa: BLE001
            messagebox.showerror("Unlock failed", "Incorrect passphrase.")
    return False


def show_onboarding(tracker: PersonalDevelopmentTracker, on_done: Callable[[], None] | None = None) -> None:
    window = tk.Toplevel(tracker.root)
    window.title("Welcome to Integral")
    window.geometry("640x520")
    window.minsize(480, 400)
    window.configure(bg=tracker.theme["bg"])
    window.transient(tracker.root)
    window.grab_set()

    footer = ttk.Frame(window, padding=(0, 16))
    footer.pack(side=tk.BOTTOM, fill=tk.X)

    ttk.Label(window, text="Tend every area of your life.", font=("Helvetica", 18, "bold")).pack(
        side=tk.TOP, anchor="w", padx=20, pady=(20, 8)
    )
    body = scrolledtext.ScrolledText(window, wrap=tk.WORD, font=("Helvetica", 11), height=14)
    style_text_widget(body, tracker.theme)
    body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=8)
    body.insert(
        tk.END,
        "Integral is free, open-source software — your data stays on this machine.\n\n"
        "Integral tracks development across the whole person — financial, physical, mental, "
        "emotional, spiritual, relational, cultural, and what you take in (food, art, books, content).\n\n"
        "Daily logging (keep it light):\n"
        "  • Pick any life area → 1–10 rating → Save. That's enough on hard days.\n"
        "  • You don't need every category every day — log what matters today.\n"
        "  • Add checklist ticks, metrics, and notes when you have energy.\n\n"
        "Overview shows a year-at-a-glance grid — click any day to explore.\n\n"
        "Fitness Hub includes reference tables from popular training books (CC, Tibetan Rites, "
        "Overcoming Gravity, and more). Integral is not sponsored by those authors — "
        "if you love a program, buy the book.\n\n"
        "Use Weekly Summary and Guidance for trends; Export and Backup in the footer when you want copies.\n",
    )
    body.config(state=tk.DISABLED)

    def finish() -> None:
        tracker.settings["onboarding_complete"] = True
        tracker.save_data()
        window.destroy()
        if on_done:
            on_done()

    ttk.Button(footer, text="Get started", command=finish).pack()

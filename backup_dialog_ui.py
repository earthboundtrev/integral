"""Backup & Restore dialog — encrypted export/import UI (#267, #268)."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk
import unicodedata
import zipfile
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Callable

import backup
import integral_io
from busy_indicator import BusyIndicator, DEFAULT_DELAY_MS, pump_event_loop
from inline_validation import (
    focus_first_invalid,
    make_inline_error_label,
    set_field_error,
    wire_focusout_validation,
)
from paths import APP_VERSION, creative_projects_dir
from vault import (
    CRYPTO_AVAILABLE,
    PassphraseRequiredError,
    WrongPassphraseError,
    is_encrypted_file,
    save_data_file,
)

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker

BACKUP_WRONG_FILE_MSG = "This file isn't an Integral backup."
TYPED_PASSPHRASE_MIN_LEN = 12
MARKER_LOG_SCAN = "marker-backup-pass-267268"


def _open_containing_folder(path: str) -> None:
    folder = os.path.dirname(os.path.abspath(path))
    if not folder:
        return
    try:
        if sys.platform == "win32":
            os.startfile(folder)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", folder], check=False)
        else:
            subprocess.run(["xdg-open", folder], check=False)
    except OSError:
        pass


def _caps_lock_on() -> bool:
    try:
        if sys.platform == "win32":
            import ctypes

            return bool(ctypes.windll.user32.GetKeyState(0x14) & 1)
    except Exception:
        pass
    return False


def _journal_encrypted_on_disk(tracker: PersonalDevelopmentTracker) -> bool:
    try:
        return is_encrypted_file(tracker.data_path)
    except OSError:
        return False


def _vault_active(tracker: PersonalDevelopmentTracker) -> bool:
    return bool(tracker.settings.get("encryption_enabled")) or _journal_encrypted_on_disk(tracker)


def _vault_unlocked(tracker: PersonalDevelopmentTracker) -> bool:
    return _vault_active(tracker) and bool(getattr(tracker, "vault_passphrase", None))


def _format_backup_date(exported_at: str) -> str:
    try:
        dt = datetime.fromisoformat(exported_at)
        return f"{dt.strftime('%a %b')} {dt.day}, {dt.year}"
    except (TypeError, ValueError):
        return exported_at or "unknown date"


def _ensure_encrypted_suffix(path: str) -> str:
    suffix = backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX
    base = path.strip()
    if not base.lower().endswith(suffix.lower()):
        return base + suffix
    return base


def _active_fitness_db_path(tracker: PersonalDevelopmentTracker, *, require_exists: bool = True) -> str | None:
    try:
        from integral_dialogs import _active_fitness_db_path as _fn

        return _fn(tracker, require_exists=require_exists)
    except Exception:
        return None


def _is_profile_backup_zip(path: str) -> bool:
    if not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = set(zf.namelist())
            return "config.json" in names and any(name.startswith("profiles/") for name in names)
    except (OSError, zipfile.BadZipFile):
        return False


def _clear_entries(*entries: ttk.Entry) -> None:
    for entry in entries:
        try:
            entry.delete(0, tk.END)
        except tk.TclError:
            pass


def _safe_user_error(exc: BaseException) -> str:
    if isinstance(exc, WrongPassphraseError):
        return str(exc)
    if isinstance(exc, PassphraseRequiredError):
        return "Passphrase required for encrypted backup."
    text = str(exc)
    if MARKER_LOG_SCAN in text:
        return "Backup failed."
    return text


def show_backup_dialog(tracker: PersonalDevelopmentTracker) -> None:
    window = tk.Toplevel(tracker.root)
    window.title("Backup & Restore")
    window.geometry("580x520")
    window.minsize(560, 420)
    window.configure(bg=tracker.theme["bg"])
    window.transient(tracker.root)

    export_busy = {"active": False}
    restore_busy = {"active": False}
    plaintext_bar_visible = {"visible": False}

    desc = ttk.Label(
        window,
        text=(
            "Full backup zip from Export includes life data, creative/ manuscripts, and fitness.db "
            "when present. Encrypted backups use a separate .integral-backup.enc container.\n\n"
            "Restore replaces current data (a .bak copy of data.json is kept)."
        ),
        wraplength=520,
    )
    desc.pack(anchor="w", padx=15, pady=(12, 8))

    crypto_note = ttk.Label(
        window,
        text="",
        wraplength=520,
        foreground=tracker.theme.get("muted", "#6B7280"),
    )
    crypto_note.pack(anchor="w", padx=15)
    if not CRYPTO_AVAILABLE:
        crypto_note.config(
            text="Install cryptography to enable encrypted backups: pip install cryptography"
        )
    else:
        crypto_note.config(
            text=(
                f"Encrypted backups ({backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX}) can be restored here "
                f"with your passphrase (Integral {APP_VERSION})."
            )
        )

    options = ttk.Frame(window)
    options.pack(fill=tk.X, padx=15, pady=(8, 4))

    encrypt_var = tk.BooleanVar(value=_vault_active(tracker) and CRYPTO_AVAILABLE)
    encrypt_chk = ttk.Checkbutton(options, text="&Encrypt with passphrase", variable=encrypt_var)
    if not CRYPTO_AVAILABLE:
        encrypt_chk.state(["disabled"])

    use_vault_var = tk.BooleanVar(value=_vault_unlocked(tracker))
    use_vault_chk = ttk.Checkbutton(options, text="Use my vault passphrase")
    if not _vault_unlocked(tracker):
        use_vault_chk.state(["disabled"])

    pass_frame = ttk.Frame(window)
    pass_row = ttk.Frame(pass_frame)
    pass_row.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(pass_row, text="Passphrase").pack(side=tk.LEFT)
    pass_entry = ttk.Entry(pass_row, show="*", width=36)
    pass_entry.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)
    pass_show = tk.BooleanVar(value=False)

    def toggle_pass_visibility() -> None:
        pass_entry.configure(show="" if pass_show.get() else "*")
        confirm_entry.configure(show="" if pass_show.get() else "*")

    show_btn = ttk.Checkbutton(pass_row, text="Show", variable=pass_show, command=toggle_pass_visibility)

    confirm_row = ttk.Frame(pass_frame)
    confirm_row.pack(fill=tk.X, pady=(0, 6))
    ttk.Label(confirm_row, text="Confirm passphrase").pack(side=tk.LEFT)
    confirm_entry = ttk.Entry(confirm_row, show="*", width=36)
    confirm_entry.pack(side=tk.LEFT, padx=(8, 0), fill=tk.X, expand=True)

    warn_label = ttk.Label(
        pass_frame,
        text="⚠ If you lose this passphrase, the backup can't be restored.",
        wraplength=500,
        foreground=tracker.theme.get("muted", "#6B7280"),
    )
    warn_label.pack(anchor="w", pady=(0, 4))

    caps_hint = make_inline_error_label(pass_frame, tracker.theme)
    caps_hint.configure(fg=tracker.theme.get("muted", "#6B7280"))
    pass_err = make_inline_error_label(pass_frame, tracker.theme)
    confirm_err = make_inline_error_label(pass_frame, tracker.theme)
    suffix_hint = ttk.Label(
        pass_frame,
        text=f"Saved as *{backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX}",
        foreground=tracker.theme.get("muted", "#6B7280"),
    )

    vault_export_note = ttk.Label(
        pass_frame,
        text=(
            "If your journal was vault-encrypted at export, unlocking it after restore needs "
            "the vault passphrase from export time (may differ from this backup passphrase)."
        ),
        wraplength=500,
        foreground=tracker.theme.get("muted", "#6B7280"),
    )

    plaintext_bar = ttk.Frame(window)
    plaintext_msg = ttk.Label(
        plaintext_bar,
        text="This backup won't be encrypted. Anyone with the file can read your journal.",
        wraplength=480,
    )
    plaintext_msg.pack(anchor="w", pady=(0, 8))
    plaintext_buttons = ttk.Frame(plaintext_bar)
    plaintext_buttons.pack(anchor="w")

    def hide_plaintext_bar() -> None:
        plaintext_bar.pack_forget()
        plaintext_bar_visible["visible"] = False

    def show_plaintext_bar() -> None:
        hide_plaintext_bar()
        plaintext_bar.pack(fill=tk.X, padx=15, pady=(0, 8), after=options)
        plaintext_bar_visible["visible"] = True

    restore_panel = ttk.Frame(window)
    restore_panel.pack(fill=tk.X, padx=15, pady=(4, 0))
    restore_pass_row = ttk.Frame(restore_panel)
    ttk.Label(restore_pass_row, text="Restore passphrase").pack(side=tk.LEFT)
    restore_pass_entry = ttk.Entry(restore_pass_row, show="*", width=32)
    restore_pass_entry.pack(side=tk.LEFT, padx=(8, 0))
    restore_show = tk.BooleanVar(value=False)

    def toggle_restore_visibility() -> None:
        restore_pass_entry.configure(show="" if restore_show.get() else "*")

    ttk.Checkbutton(restore_pass_row, text="Show", variable=restore_show, command=toggle_restore_visibility).pack(
        side=tk.LEFT, padx=(8, 0)
    )
    restore_caps = make_inline_error_label(restore_panel, tracker.theme)
    restore_caps.configure(fg=tracker.theme.get("muted", "#6B7280"))
    restore_err = make_inline_error_label(restore_panel, tracker.theme)
    restore_vault_note = ttk.Label(
        restore_panel,
        text=(
            "Journal inside the backup may use a different vault passphrase than the backup container."
        ),
        wraplength=500,
        foreground=tracker.theme.get("muted", "#6B7280"),
    )

    confirm_bar = ttk.Frame(window)
    confirm_label = ttk.Label(confirm_bar, text="", wraplength=500)
    confirm_label.pack(anchor="w", pady=(0, 8))
    confirm_buttons = ttk.Frame(confirm_bar)

    encrypt_chk.pack(side=tk.LEFT)
    use_vault_chk.pack(side=tk.LEFT, padx=(12, 0))

    def layout_encrypt_fields() -> None:
        if encrypt_var.get() and CRYPTO_AVAILABLE:
            pass_frame.pack(fill=tk.X, padx=15, pady=(0, 4), after=options)
            warn_label.pack(anchor="w")
            pass_row.pack(fill=tk.X)
            show_btn.pack(side=tk.RIGHT, padx=(8, 0))
            confirm_row.pack(fill=tk.X)
            suffix_hint.pack(anchor="w", pady=(4, 0))
            if _vault_active(tracker):
                vault_export_note.pack(anchor="w", pady=(4, 0))
        else:
            pass_frame.pack_forget()
            vault_export_note.pack_forget()

    def on_encrypt_toggle(*_args: object) -> None:
        if not encrypt_var.get():
            _clear_entries(pass_entry, confirm_entry)
            set_field_error(pass_err, None)
            set_field_error(confirm_err, None)
        layout_encrypt_fields()

    encrypt_var.trace_add("write", on_encrypt_toggle)
    layout_encrypt_fields()

    def update_caps_hints(*_args: object) -> None:
        if _caps_lock_on():
            set_field_error(caps_hint, "Caps Lock is on.")
            set_field_error(restore_caps, "Caps Lock is on.")
        else:
            set_field_error(caps_hint, None)
            set_field_error(restore_caps, None)

    pass_entry.bind("<KeyRelease>", lambda _e: update_caps_hints(), add="+")
    confirm_entry.bind("<KeyRelease>", lambda _e: update_caps_hints(), add="+")
    restore_pass_entry.bind("<KeyRelease>", lambda _e: update_caps_hints(), add="+")

    def resolve_export_passphrase() -> str | None:
        if use_vault_var.get() and _vault_unlocked(tracker):
            return tracker.vault_passphrase
        return pass_entry.get()

    def validate_export_passphrase() -> bool:
        if not encrypt_var.get():
            return True
        if use_vault_var.get() and _vault_unlocked(tracker):
            set_field_error(pass_err, None)
            set_field_error(confirm_err, None)
            return True
        pw = pass_entry.get()
        confirm = confirm_entry.get()
        errors: list[tuple[tk.Misc, tk.Label | None, str | None]] = []
        if not pw.strip():
            errors.append((pass_entry, pass_err, "Passphrase is required."))
        else:
            errors.append((pass_entry, pass_err, None))
        if not confirm.strip():
            errors.append((confirm_entry, confirm_err, "Confirm your passphrase."))
        elif pw != confirm:
            errors.append((confirm_entry, confirm_err, "Passphrases do not match."))
        else:
            errors.append((confirm_entry, confirm_err, None))
        nfc = unicodedata.normalize("NFC", pw)
        if pw.strip() and len(nfc) < TYPED_PASSPHRASE_MIN_LEN:
            errors.append(
                (
                    pass_entry,
                    pass_err,
                    f"Passphrase must be at least {TYPED_PASSPHRASE_MIN_LEN} characters.",
                )
            )
        return not focus_first_invalid(errors)

    wire_focusout_validation(
        confirm_entry,
        lambda: (
            "Passphrases do not match."
            if pass_entry.get() != confirm_entry.get() and confirm_entry.get().strip()
            else None
        ),
        confirm_err,
    )

    buttons = ttk.Frame(window)
    buttons.pack(fill=tk.X, padx=15, pady=12)
    export_btn = ttk.Button(buttons, text="Export &Backup…")
    export_btn.pack(side=tk.LEFT, padx=(0, 4))
    restore_btn = ttk.Button(buttons, text="&Restore from Backup…")
    restore_btn.pack(side=tk.LEFT, padx=4)
    close_btn = ttk.Button(buttons, text="&Close", command=window.destroy)
    close_btn.pack(side=tk.RIGHT)

    busy_host = ttk.Frame(window)
    busy_host.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
    indicator = BusyIndicator(busy_host, label="Working…", theme=tracker.theme, delay_ms=DEFAULT_DELAY_MS)

    def set_buttons_enabled(export: bool, restore: bool) -> None:
        try:
            export_btn.configure(state=tk.NORMAL if export else tk.DISABLED)
            restore_btn.configure(state=tk.NORMAL if restore else tk.DISABLED)
        except tk.TclError:
            pass

    restore_state: dict = {
        "path": None,
        "encrypted": False,
        "manifest": None,
        "passphrase": None,
    }

    def clear_passphrase_widgets() -> None:
        _clear_entries(pass_entry, confirm_entry, restore_pass_entry)
        set_field_error(restore_err, None)

    def on_close() -> None:
        clear_passphrase_widgets()
        window.destroy()

    close_btn.configure(command=on_close)

    def run_plain_export() -> None:
        path = filedialog.asksaveasfilename(
            parent=window,
            title="Save full backup",
            defaultextension=".zip",
            filetypes=[
                ("Integral full backup", "*.zip"),
                ("All files", "*.*"),
            ],
            initialfile=f"integral-backup-{datetime.now().strftime('%Y%m%d')}.zip",
        )
        if not path:
            return
        try:
            tracker.save_data(flush=True)
            manifest = integral_io.write_full_backup(  # noqa: SLF001
                tracker._payload(),
                path,
                creative_root=creative_projects_dir(),
                fitness_db_path=_active_fitness_db_path(tracker),
            )
            fitness_note = "with fitness DB" if manifest.get("has_fitness") else "no fitness DB"
            tracker.ensure_status_banner().show_success(
                f"Backup saved to {path} "
                f"({manifest.get('creative_file_count', 0)} creative files, {fitness_note})."
            )
            clear_passphrase_widgets()
        except OSError as exc:
            tracker.ensure_status_banner().show_error(f"Backup failed: {exc}")

    def run_encrypted_export() -> None:
        if not validate_export_passphrase():
            return
        passphrase = resolve_export_passphrase()
        if not passphrase:
            set_field_error(pass_err, "Passphrase is required.")
            return
        initial = f"integral-backup-{datetime.now().strftime('%Y%m%d')}{backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX}"
        path = filedialog.asksaveasfilename(
            parent=window,
            title="Save encrypted backup",
            defaultextension=backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX,
            filetypes=[
                ("Integral encrypted backup", f"*{backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX}"),
                ("All files", "*.*"),
            ],
            initialfile=initial,
        )
        if not path:
            return
        dest = _ensure_encrypted_suffix(path)
        try:
            tracker.save_data(flush=True)
        except OSError as exc:
            tracker.ensure_status_banner().show_error(f"Backup failed: {exc}")
            return
        export_busy["active"] = True
        set_buttons_enabled(False, False)
        indicator.start()

        def worker() -> None:
            try:
                manifest = backup.export_backup(
                    dest,
                    creative_root=creative_projects_dir(),
                    passphrase=passphrase,
                )
                tracker.root.after(0, lambda: on_export_done(None, manifest, dest))
            except BaseException as exc:  # noqa: BLE001
                tracker.root.after(0, lambda: on_export_done(exc, None, dest))

        def on_export_done(exc: BaseException | None, manifest: dict | None, dest_path: str) -> None:
            export_busy["active"] = False
            indicator.stop()
            set_buttons_enabled(True, True)
            if exc is not None:
                tracker.ensure_status_banner().show_error(f"Backup failed: {_safe_user_error(exc)}")
                return
            tracker.ensure_status_banner().show_success(
                f"Backup saved (encrypted) — {dest_path}",
                extra_actions=[("Open folder", lambda: _open_containing_folder(dest_path))],
            )
            encrypt_var.set(False)
            clear_passphrase_widgets()

        threading.Thread(target=worker, daemon=True).start()

    def backup_now() -> None:
        if export_busy["active"]:
            return
        if encrypt_var.get() and CRYPTO_AVAILABLE:
            run_encrypted_export()
            return
        if _vault_active(tracker) and CRYPTO_AVAILABLE:
            show_plaintext_bar()
            return
        run_plain_export()

    def encrypt_instead() -> None:
        hide_plaintext_bar()
        encrypt_var.set(True)
        layout_encrypt_fields()
        pass_entry.focus_set()

    def export_unencrypted() -> None:
        hide_plaintext_bar()
        run_plain_export()

    encrypt_instead_btn = ttk.Button(plaintext_buttons, text="Encr&ypt instead", command=encrypt_instead)
    encrypt_instead_btn.pack(side=tk.LEFT, padx=(0, 8))
    export_plain_btn = ttk.Button(plaintext_buttons, text="Export unencrypted", command=export_unencrypted)
    export_plain_btn.pack(side=tk.LEFT)

    def hide_restore_ui() -> None:
        restore_panel.pack_forget()
        confirm_bar.pack_forget()

    def show_restore_passphrase_ui() -> None:
        hide_restore_ui()
        restore_panel.pack(fill=tk.X, padx=15, pady=(4, 0), before=buttons)
        restore_vault_note.pack(anchor="w", pady=(4, 0))
        restore_pass_row.pack(fill=tk.X)
        restore_pass_entry.focus_set()

    def show_confirm_bar(manifest: dict) -> None:
        restore_panel.pack_forget()
        date_txt = _format_backup_date(str(manifest.get("exported_at", "")))
        profile_count = len(manifest.get("profiles") or [])
        confirm_label.config(
            text=f"Replace your current data with the backup from {date_txt} ({profile_count} profiles)?"
        )
        confirm_bar.pack(fill=tk.X, padx=15, pady=(8, 0), before=buttons)
        confirm_buttons.pack(anchor="w")
        cancel_confirm_btn.focus_set()

    confirm_restore_btn = ttk.Button(confirm_buttons, text="Restore")
    cancel_confirm_btn = ttk.Button(confirm_buttons, text="Cancel")
    confirm_restore_btn.pack(side=tk.LEFT, padx=(0, 8))
    cancel_confirm_btn.pack(side=tk.LEFT)

    def cancel_restore_flow() -> None:
        restore_state.update(path=None, encrypted=False, manifest=None, passphrase=None)
        hide_restore_ui()
        clear_passphrase_widgets()
        set_buttons_enabled(True, True)

    cancel_confirm_btn.configure(command=cancel_restore_flow)

    def _flush_pending_save() -> None:
        try:
            tracker.save_data(flush=True)
        except Exception:
            if getattr(tracker, "_save_after_id", None):
                try:
                    tracker.root.after_cancel(tracker._save_after_id)
                except tk.TclError:
                    pass
                tracker._save_after_id = None

    def _reencrypt_if_needed() -> None:
        if not _vault_active(tracker) or not tracker.vault_passphrase:
            return
        data_path = tracker.data_path
        if is_encrypted_file(data_path):
            return
        try:
            payload = tracker._payload()
            save_data_file(
                data_path,
                payload,
                encrypted=True,
                passphrase=tracker.vault_passphrase,
            )
        except Exception:
            pass

    def finish_restore_success() -> None:
        tracker.load_data()
        tracker.create_dashboard()
        tracker.ensure_status_banner().show_success("Journal restored from backup.")
        cancel_restore_flow()
        window.destroy()

    def apply_encrypted_restore() -> None:
        path = restore_state.get("path")
        passphrase = restore_state.get("passphrase")
        if not path or not passphrase:
            return
        restore_busy["active"] = True
        set_buttons_enabled(False, False)
        indicator.start()

        def worker() -> None:
            try:
                backup.import_backup(
                    path,
                    merge_profiles=True,
                    creative_root=creative_projects_dir(),
                    passphrase=passphrase,
                )
                tracker.root.after(0, lambda: on_import_done(None))
            except BaseException as exc:  # noqa: BLE001
                tracker.root.after(0, lambda: on_import_done(exc))

        def on_import_done(exc: BaseException | None) -> None:
            restore_busy["active"] = False
            indicator.stop()
            set_buttons_enabled(True, True)
            if exc is not None:
                msg = _safe_user_error(exc)
                if isinstance(exc, WrongPassphraseError):
                    set_field_error(restore_err, msg)
                    try:
                        restore_pass_entry.select_range(0, tk.END)
                        restore_pass_entry.focus_set()
                    except tk.TclError:
                        pass
                    show_restore_passphrase_ui()
                    confirm_bar.pack_forget()
                else:
                    set_field_error(restore_err, BACKUP_WRONG_FILE_MSG)
                    cancel_restore_flow()
                return
            _flush_pending_save()
            _reencrypt_if_needed()
            finish_restore_success()

        threading.Thread(target=worker, daemon=True).start()

    confirm_restore_btn.configure(command=apply_encrypted_restore)

    def try_decrypt_manifest(
        path: str,
        passphrase: str,
        on_done: Callable[[BaseException | None, dict | None], None],
    ) -> None:
        restore_busy["active"] = True
        set_buttons_enabled(False, False)
        indicator.start()

        def worker() -> None:
            try:
                manifest = backup.validate_backup(path, passphrase=passphrase)
                tracker.root.after(0, lambda: on_done(None, manifest))
            except BaseException as exc:  # noqa: BLE001
                tracker.root.after(0, lambda: on_done(exc, None))

        threading.Thread(target=worker, daemon=True).start()

    def finish_decrypt_preview(exc: BaseException | None, manifest: dict | None) -> None:
        restore_busy["active"] = False
        indicator.stop()
        set_buttons_enabled(True, True)
        if exc is not None:
            if isinstance(exc, WrongPassphraseError):
                set_field_error(restore_err, str(exc))
                try:
                    restore_pass_entry.select_range(0, tk.END)
                    restore_pass_entry.focus_set()
                except tk.TclError:
                    pass
                return
            set_field_error(restore_err, BACKUP_WRONG_FILE_MSG)
            cancel_restore_flow()
            return
        if manifest:
            restore_state["manifest"] = manifest
            show_confirm_bar(manifest)

    def submit_restore_passphrase() -> None:
        path = restore_state.get("path")
        if not path:
            return
        if restore_busy["active"]:
            return
        pw = restore_pass_entry.get()
        if use_vault_var.get() and _vault_unlocked(tracker) and not pw.strip():
            pw = tracker.vault_passphrase or ""
        if not pw.strip():
            set_field_error(restore_err, "Passphrase is required.")
            return
        restore_state["passphrase"] = pw
        try_decrypt_manifest(path, pw, finish_decrypt_preview)

    restore_pass_entry.bind("<Return>", lambda _e: submit_restore_passphrase(), add="+")

    def legacy_restore(path: str) -> None:
        if not messagebox.askyesno(
            "Confirm restore",
            "This replaces your current journal and Writing Project documents with the backup. Continue?",
            parent=window,
        ):
            return
        try:
            _flush_pending_save()
            result = integral_io.restore_backup_file(
                path,
                tracker.data_path,
                creative_root=creative_projects_dir(),
                fitness_db_path=_active_fitness_db_path(tracker, require_exists=False),
                make_copy=True,
            )
            _reencrypt_if_needed()
            tracker.load_data()
            tracker.create_dashboard()
            window.destroy()
            warning = result.get("warning")
            msg = "Journal restored from backup."
            if result.get("restored_creative_files"):
                msg += f"\nCreative files restored: {result['restored_creative_files']}"
            if warning:
                msg += f"\n\nNote: {warning}"
            tracker.ensure_status_banner().show_success(msg)
            clear_passphrase_widgets()
        except (OSError, ValueError) as exc:
            tracker.ensure_status_banner().show_error(f"Restore failed: {exc}")

    def profile_zip_restore(path: str) -> None:
        try:
            manifest = backup.validate_backup(path)
        except (OSError, ValueError) as exc:
            tracker.ensure_status_banner().show_error(_safe_user_error(exc))
            return
        date_txt = _format_backup_date(str(manifest.get("exported_at", "")))
        profile_count = len(manifest.get("profiles") or [])
        if not messagebox.askyesno(
            "Confirm restore",
            f"Replace your current data with the backup from {date_txt} ({profile_count} profiles)?",
            parent=window,
        ):
            return
        try:
            _flush_pending_save()
            backup.import_backup(path, merge_profiles=True, creative_root=creative_projects_dir())
            _reencrypt_if_needed()
            finish_restore_success()
        except (OSError, ValueError) as exc:
            tracker.ensure_status_banner().show_error(f"Restore failed: {_safe_user_error(exc)}")

    def restore_now() -> None:
        if restore_busy["active"]:
            return
        cancel_restore_flow()
        path = filedialog.askopenfilename(
            parent=window,
            title="Restore backup",
            filetypes=[
                ("Integral backups", f"*.zip *.json *{backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX}"),
                ("Encrypted backup", f"*{backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX}"),
                ("Full zip backup", "*.zip"),
                ("Legacy JSON backup", "*.json"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        encrypted = backup.is_encrypted_backup_file(path)
        restore_state["path"] = path
        restore_state["encrypted"] = encrypted

        if encrypted:
            if use_vault_var.get() and _vault_unlocked(tracker):
                restore_state["passphrase"] = tracker.vault_passphrase
                try_decrypt_manifest(path, tracker.vault_passphrase, finish_decrypt_preview)
                return
            show_restore_passphrase_ui()
            if use_vault_var.get() and _vault_unlocked(tracker):
                submit_restore_passphrase()
            return

        if path.lower().endswith(".json") or integral_io.is_full_backup_zip(path):
            legacy_restore(path)
            return
        if _is_profile_backup_zip(path):
            profile_zip_restore(path)
            return

        tracker.ensure_status_banner().show_error(BACKUP_WRONG_FILE_MSG)

    export_btn.configure(command=backup_now)
    restore_btn.configure(command=restore_now)

    def on_escape(_event: tk.Event | None = None) -> str:
        if plaintext_bar_visible["visible"]:
            encrypt_instead()
            return "break"
        if confirm_bar.winfo_ismapped():
            cancel_restore_flow()
            return "break"
        on_close()
        return "break"

    window.bind("<Escape>", on_escape, add="+")
    export_btn.bind("<Return>", lambda _e: backup_now(), add="+")
    pass_entry.bind("<Return>", lambda _e: confirm_entry.focus_set(), add="+")
    confirm_entry.bind("<Return>", lambda _e: backup_now(), add="+")

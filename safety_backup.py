"""Automatic pre-restore safety copies under the app data directory (#271)."""

from __future__ import annotations

import errno
import os
from datetime import datetime
from typing import TYPE_CHECKING

import backup
import profile_journal_sync
import profiles
from vault import WrongPassphraseError

if TYPE_CHECKING:
    from personal_dev_tracker import PersonalDevelopmentTracker

SAFETY_BACKUPS_DIRNAME = "Safety backups"
SAFETY_BACKUP_BASENAME_PREFIX = "before-restore-"
SAFETY_BACKUP_MAX_KEPT = 5

UNLOCK_VAULT_FIRST_MSG = "Unlock the vault first, then restore."
SAFETY_COPY_FAILED_BANNER = (
    "Couldn't save a safety copy of your current data, so nothing was restored."
)
SAFETY_DETAILS_UNCHANGED = "Your current data was not changed"


class SafetyBackupError(Exception):
    """Pre-restore safety copy could not be written; restore must not proceed."""

    def __init__(self, user_detail: str) -> None:
        self.user_detail = user_detail
        super().__init__(user_detail)


def safety_backups_dir() -> str:
    path = os.path.join(profiles.get_app_dir(), SAFETY_BACKUPS_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def _safety_backup_filenames() -> list[str]:
    directory = safety_backups_dir()
    try:
        names = os.listdir(directory)
    except OSError:
        return []
    allowed_suffixes = (backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX, ".zip")
    out: list[str] = []
    for name in names:
        if not name.startswith(SAFETY_BACKUP_BASENAME_PREFIX):
            continue
        if name.endswith(allowed_suffixes):
            out.append(name)
    return out


def _timestamp_basename(moment: datetime) -> str:
    return moment.strftime(f"{SAFETY_BACKUP_BASENAME_PREFIX}%Y%m%d-%H%M")


def _reserve_safety_backup_path(*, vault_on: bool, moment: datetime | None = None) -> str:
    moment = moment or datetime.now()
    base = _timestamp_basename(moment)
    ext = backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX if vault_on else ".zip"
    directory = safety_backups_dir()
    candidate = os.path.join(directory, base + ext)
    if not os.path.exists(candidate):
        return candidate
    for second in range(moment.second + 1, 60):
        alt = moment.replace(second=second)
        base_alt = _timestamp_basename(alt)
        candidate = os.path.join(directory, base_alt + ext)
        if not os.path.exists(candidate):
            return candidate
    suffix = 2
    while suffix < 1000:
        candidate = os.path.join(directory, f"{base}-{suffix}{ext}")
        if not os.path.exists(candidate):
            return candidate
        suffix += 1
    raise SafetyBackupError("A safety backup filename could not be allocated.")


def _user_friendly_write_error(exc: BaseException) -> str:
    if isinstance(exc, WrongPassphraseError):
        return "The vault passphrase in memory could not secure the safety copy."
    if isinstance(exc, profile_journal_sync.ProfileJournalSyncError):
        return "Your journal layout could not be prepared for a safety copy."
    if isinstance(exc, OSError):
        err = getattr(exc, "errno", None)
        if err in (errno.ENOSPC, errno.EDQUOT):
            return "There isn't enough free disk space to save the safety copy."
        if err in (errno.EACCES, errno.EPERM, errno.EROFS):
            return "The Safety backups folder isn't writable right now."
        return "The safety copy couldn't be written to disk."
    if isinstance(exc, ValueError):
        return "The safety copy didn't pass validation after being written."
    return "The safety copy couldn't be saved."


def prune_safety_backups(*, keep: int = SAFETY_BACKUP_MAX_KEPT) -> None:
    directory = safety_backups_dir()
    paths: list[tuple[float, str]] = []
    for name in _safety_backup_filenames():
        full = os.path.join(directory, name)
        try:
            paths.append((os.path.getmtime(full), full))
        except OSError:
            continue
    paths.sort(key=lambda item: item[0], reverse=True)
    for _mtime, path in paths[keep:]:
        try:
            os.remove(path)
        except OSError:
            pass


def write_pre_restore_safety_backup(
    *,
    tracker: PersonalDevelopmentTracker,
    vault_on: bool,
    passphrase: str | None,
    creative_root: str,
) -> str:
    """Write and verify a safety backup; prune older copies on success."""
    if vault_on and not (passphrase or "").strip():
        raise SafetyBackupError(
            "Unlock the vault before restoring so the safety copy can be encrypted."
        )
    dest_path = _reserve_safety_backup_path(vault_on=vault_on)
    partial = dest_path + ".partial"
    try:
        try:
            tracker.save_data(flush=True)
        except Exception as exc:  # noqa: BLE001
            raise SafetyBackupError(_user_friendly_write_error(exc)) from exc
        try:
            profile_journal_sync.sync_tracker_journal_to_active_profile(tracker.data_path)
        except profile_journal_sync.ProfileJournalSyncError as exc:
            raise SafetyBackupError(_user_friendly_write_error(exc)) from exc
        enc_passphrase = passphrase if vault_on else None
        try:
            backup.export_backup(
                dest_path,
                creative_root=creative_root,
                passphrase=enc_passphrase,
            )
        except Exception as exc:  # noqa: BLE001
            raise SafetyBackupError(_user_friendly_write_error(exc)) from exc
        if not os.path.isfile(dest_path) or os.path.getsize(dest_path) <= 0:
            raise SafetyBackupError("The safety copy didn't pass validation after being written.")
        try:
            backup.validate_backup(dest_path, passphrase=enc_passphrase)
        except Exception as exc:  # noqa: BLE001
            raise SafetyBackupError(_user_friendly_write_error(exc)) from exc
        if vault_on and not backup.is_encrypted_backup_file(dest_path):
            raise SafetyBackupError("The safety copy didn't pass validation after being written.")
        prune_safety_backups()
        return dest_path
    except SafetyBackupError:
        for stray in (dest_path, partial):
            try:
                if os.path.isfile(stray):
                    os.remove(stray)
            except OSError:
                pass
        raise
    except Exception as exc:  # noqa: BLE001
        for stray in (dest_path, partial):
            try:
                if os.path.isfile(stray):
                    os.remove(stray)
            except OSError:
                pass
        raise SafetyBackupError(_user_friendly_write_error(exc)) from exc


def safety_details_message(detail: str) -> str:
    detail = detail.strip()
    if not detail:
        detail = "The safety copy couldn't be saved."
    return f"{detail}\n\n{SAFETY_DETAILS_UNCHANGED}"


def middle_ellipsize_path(path: str, max_chars: int = 72) -> str:
    """Shorten long paths for banner text; keep drive/root and filename."""
    normalized = os.path.normpath(path)
    if len(normalized) <= max_chars:
        return normalized
    folder, name = os.path.split(normalized)
    if len(name) >= max_chars - 5:
        return "…" + name[-(max_chars - 1) :]
    room = max_chars - len(name) - 3
    if room < 8:
        return "…" + name
    head = folder[: room // 2]
    tail = folder[-(room - len(head)) :]
    return f"{head}…{tail}{os.sep}{name}"
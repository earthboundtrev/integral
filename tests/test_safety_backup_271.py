"""Unit tests for pre-restore safety copies (#271)."""

from __future__ import annotations

import os
from datetime import datetime
from unittest.mock import MagicMock

import pytest

import backup
import profiles
import safety_backup
import storage

pytest.importorskip("cryptography")

from tests.test_backup import temp_app  # noqa: F401


def test_reserve_path_unique_within_minute(temp_app, tmp_path):
    moment = datetime(2026, 1, 2, 3, 4, 5)
    first = safety_backup._reserve_safety_backup_path(vault_on=False, moment=moment)
    open(first, "wb").close()
    second = safety_backup._reserve_safety_backup_path(vault_on=False, moment=moment)
    assert first != second
    assert os.path.basename(second).startswith("before-restore-20260102-0304")


def test_prune_keeps_newest_five(temp_app):
    directory = safety_backup.safety_backups_dir()
    paths = []
    for index in range(7):
        path = os.path.join(directory, f"before-restore-2026010{index}.zip")
        with open(path, "wb") as handle:
            handle.write(b"zip")
        os.utime(path, (index + 1, index + 1))
        paths.append(path)
    safety_backup.prune_safety_backups(keep=5)
    remaining = safety_backup._safety_backup_filenames()
    assert len(remaining) == 5


def test_write_encrypted_safety_copy(temp_app, monkeypatch):
    profiles.set_active_profile("default")
    storage.save(storage.empty_data())
    tracker = MagicMock()
    tracker.data_path = os.path.join(profiles.get_profile_dir(), "data.json")
    tracker.vault_passphrase = "backup-passphrase-12"
    dest = safety_backup.write_pre_restore_safety_backup(
        tracker=tracker,
        vault_on=True,
        passphrase="backup-passphrase-12",
        creative_root=os.path.join(temp_app["app_dir"], "creative"),
    )
    assert backup.is_encrypted_backup_file(dest)
    backup.validate_backup(dest, passphrase="backup-passphrase-12")


def test_write_failure_leaves_no_partial_file(temp_app, monkeypatch):
    profiles.set_active_profile("default")
    tracker = MagicMock()
    tracker.data_path = os.path.join(profiles.get_profile_dir(), "data.json")
    monkeypatch.setattr(
        backup,
        "export_backup",
        MagicMock(side_effect=OSError(30, "Read-only file system")),
    )
    before = safety_backup._safety_backup_filenames()
    with pytest.raises(safety_backup.SafetyBackupError):
        safety_backup.write_pre_restore_safety_backup(
            tracker=tracker,
            vault_on=False,
            passphrase=None,
            creative_root=os.path.join(temp_app["app_dir"], "creative"),
        )
    assert safety_backup._safety_backup_filenames() == before
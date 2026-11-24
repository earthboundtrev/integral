"""Replace-aside ledger rollback + startup recovery (#271)."""

from __future__ import annotations

import hashlib
import os
import shutil

import pytest

import backup
import profiles
import storage

from tests.test_backup import temp_app  # noqa: F401


@pytest.fixture(autouse=True)
def _clear_replace_test_hook():
    backup._REPLACE_TEST_HOOK = None
    backup._REPLACE_TEST_INSTALL_COUNT = 0
    yield
    backup._REPLACE_TEST_HOOK = None
    backup._REPLACE_TEST_INSTALL_COUNT = 0


_STATIC_HOOKS = (
    "after-aside-profiles",
    "after-aside-creative",
    "after-profile-artifacts",
    "after-creative-install",
    "after-config-replace",
)


def _tree_digest(app_dir: str) -> dict[str, str]:
    skip_roots = {
        backup.BACKUP_IMPORT_STAGING_DIRNAME,
        backup.BACKUP_REPLACE_ASIDE_DIRNAME,
    }
    digest: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(app_dir):
        dirnames[:] = [d for d in dirnames if d not in skip_roots]
        rel_dir = os.path.relpath(dirpath, app_dir)
        if rel_dir == ".":
            rel_dir = ""
        parts = rel_dir.replace("\\", "/").split("/") if rel_dir else []
        if parts and parts[0] in skip_roots:
            continue
        for name in filenames:
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, app_dir).replace("\\", "/")
            if rel.split("/")[0] in skip_roots:
                continue
            with open(abs_path, "rb") as handle:
                digest[rel] = hashlib.sha256(handle.read()).hexdigest()
    return digest


def _seed_replace_scenario(temp_app, tmp_path, monkeypatch):
    app_dir = temp_app["app_dir"]
    creative_root = os.path.join(app_dir, "creative")
    os.makedirs(creative_root, exist_ok=True)
    monkeypatch.setattr(backup.paths, "creative_projects_dir", lambda: creative_root)
    profiles.set_active_profile("default")
    data = storage.load()
    data.setdefault("entries", {})["2099-01-01"] = {
        "Emotional Wellbeing": {"rating": 1, "checklist": {}, "metrics": {}, "notes": "live"}
    }
    storage.save(data)
    zip_path = str(tmp_path / "snap.zip")
    backup.export_backup(zip_path, profile_id="default", creative_root=creative_root)
    profiles.create_profile("extra")
    extra_dir = os.path.join(profiles.get_profiles_root(), "extra")
    os.makedirs(extra_dir, exist_ok=True)
    with open(os.path.join(extra_dir, "data.json"), "w", encoding="utf-8") as handle:
        handle.write('{"entries": {}}')
    with open(os.path.join(creative_root, "orphan.txt"), "w", encoding="utf-8") as handle:
        handle.write("orphan")
    with open(os.path.join(creative_root, "in-backup.txt"), "w", encoding="utf-8") as handle:
        handle.write("backup-doc")
    return app_dir, zip_path, creative_root


@pytest.mark.parametrize("hook", _STATIC_HOOKS)
def test_replace_fails_at_hook_restores_byte_tree(temp_app, tmp_path, monkeypatch, hook):
    app_dir, zip_path, creative_root = _seed_replace_scenario(temp_app, tmp_path, monkeypatch)
    before = _tree_digest(app_dir)
    backup._REPLACE_TEST_HOOK = hook
    backup._REPLACE_TEST_INSTALL_COUNT = 0
    with pytest.raises(OSError, match="replace-test-hook"):
        backup.import_backup(
            zip_path,
            merge_profiles=False,
            replace_app_state=True,
            creative_root=creative_root,
        )
    assert _tree_digest(app_dir) == before
    backup.sweep_replace_aside_pending_at_startup()
    assert _tree_digest(app_dir) == before


@pytest.mark.parametrize("install_n", (1,))
def test_replace_fails_on_install_step_restores_byte_tree(
    temp_app, tmp_path, monkeypatch, install_n: int,
):
    app_dir, zip_path, creative_root = _seed_replace_scenario(temp_app, tmp_path, monkeypatch)
    before = _tree_digest(app_dir)
    backup._REPLACE_TEST_INSTALL_COUNT = 0
    backup._REPLACE_TEST_HOOK = f"install-{install_n}"
    with pytest.raises(OSError, match="replace-test-hook"):
        backup.import_backup(
            zip_path,
            merge_profiles=False,
            replace_app_state=True,
            creative_root=creative_root,
        )
    assert _tree_digest(app_dir) == before
    backup.sweep_replace_aside_pending_at_startup()
    assert _tree_digest(app_dir) == before


def test_successful_rollback_then_startup_sweep_is_idempotent(temp_app, tmp_path, monkeypatch):
    app_dir, zip_path, creative_root = _seed_replace_scenario(temp_app, tmp_path, monkeypatch)
    before = _tree_digest(app_dir)
    backup._REPLACE_TEST_HOOK = "after-aside-creative"
    with pytest.raises(OSError, match="replace-test-hook"):
        backup.import_backup(
            zip_path,
            merge_profiles=False,
            replace_app_state=True,
            creative_root=creative_root,
        )
    aside_parent = os.path.join(app_dir, backup.BACKUP_REPLACE_ASIDE_DIRNAME)
    if os.path.isdir(aside_parent):
        for run_name in os.listdir(aside_parent):
            state = os.path.join(aside_parent, run_name, backup.REPLACE_LEDGER_STATE_FILENAME)
            assert not os.path.isfile(state), "rollback should clear ledger state"
    for _ in range(3):
        backup.sweep_replace_aside_pending_at_startup()
    assert _tree_digest(app_dir) == before


def test_commit_rmtree_failure_then_sweep_keeps_tree(temp_app, tmp_path, monkeypatch):
    app_dir, zip_path, creative_root = _seed_replace_scenario(temp_app, tmp_path, monkeypatch)
    manifest = backup.import_backup(
        zip_path,
        merge_profiles=False,
        replace_app_state=True,
        creative_root=creative_root,
    )
    after_import = _tree_digest(app_dir)
    ledger = manifest[backup.REPLACE_LEDGER_MANIFEST_KEY]
    real_commit = backup.ReplaceAsideLedger.commit

    def commit_fail(self: backup.ReplaceAsideLedger) -> None:
        self._mark_finished(backup.REPLACE_LEDGER_STATUS_COMMITTED)
        backup._clear_replace_pending_marker()
        raise OSError("locked")

    monkeypatch.setattr(backup.ReplaceAsideLedger, "commit", commit_fail)
    with pytest.raises(OSError, match="locked"):
        backup.commit_replace_aside_ledger(ledger)
    state = os.path.join(ledger.root, backup.REPLACE_LEDGER_STATE_FILENAME)
    assert not os.path.isfile(state)
    backup.sweep_replace_aside_pending_at_startup()
    assert _tree_digest(app_dir) == after_import


def test_startup_sweep_finishes_pending_replace_recovery(temp_app, tmp_path, monkeypatch):
    app_dir, zip_path, creative_root = _seed_replace_scenario(temp_app, tmp_path, monkeypatch)
    before = _tree_digest(app_dir)
    real_rollback = backup.ReplaceAsideLedger.rollback
    partial = {"active": True}

    def rollback_with_marker(self: backup.ReplaceAsideLedger) -> bool:
        if partial["active"]:
            backup._write_replace_pending_marker(self.root)
            return False
        return real_rollback(self)

    monkeypatch.setattr(backup.ReplaceAsideLedger, "rollback", rollback_with_marker)
    backup._REPLACE_TEST_HOOK = "after-profile-artifacts"
    backup._REPLACE_TEST_INSTALL_COUNT = 0
    with pytest.raises(OSError, match="replace-test-hook"):
        backup.import_backup(
            zip_path,
            merge_profiles=False,
            replace_app_state=True,
            creative_root=creative_root,
        )
    assert backup.replace_import_recovery_pending()
    partial["active"] = False
    backup.sweep_replace_aside_pending_at_startup()
    assert not backup.replace_import_recovery_pending()
    assert _tree_digest(app_dir) == before
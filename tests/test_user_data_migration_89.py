"""Regression tests for #89 — legacy user-data folder discovery and safe copy."""

from __future__ import annotations

import json
import os
import sys

import pytest

import paths
import profiles
import user_data_migration as udm


@pytest.fixture(autouse=True)
def reset_migration_guard():
    udm._startup_lock = False
    udm._user_notices.clear()
    yield
    udm._startup_lock = False
    udm._user_notices.clear()


@pytest.fixture
def data_roots(tmp_path, monkeypatch):
    canonical = tmp_path / "canonical"
    legacy = tmp_path / "legacy_pdt"
    canonical.mkdir()
    legacy.mkdir()

    monkeypatch.setattr(paths, "user_data_dir", lambda: str(canonical))
    monkeypatch.setattr(
        udm,
        "legacy_user_data_directories",
        lambda: [str(legacy)],
    )
    return {"canonical": canonical, "legacy": legacy}


def _write_profile_data(root, entries_marker: str):
    profile_dir = root / "profiles" / "default"
    profile_dir.mkdir(parents=True)
    payload = {
        "categories": {},
        "entries": {"2020-01-01": {"Body & Presence": {"rating": 5, "notes": entries_marker}}},
    }
    data_path = profile_dir / "data.json"
    with open(data_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    with open(profile_dir / "data.json.bak", "w", encoding="utf-8") as handle:
        json.dump({"backup": True}, handle)
    (profile_dir / "fitness.db").write_bytes(b"sqlite-placeholder")


def test_fresh_install_no_legacy_data(data_roots):
    results = udm.run_at_startup()
    assert not any(r.outcome == "copied" for r in results)
    assert not list(data_roots["canonical"].rglob("data.json"))


def test_old_folder_only_copies_and_preserves_legacy(data_roots):
    _write_profile_data(data_roots["legacy"], "from-legacy")
    results = udm.run_at_startup()
    assert any(r.outcome in ("copied", "merged") for r in results)
    dest = data_roots["canonical"] / "profiles" / "default" / "data.json"
    assert dest.is_file()
    with open(dest, encoding="utf-8") as handle:
        data = json.load(handle)
    assert data["entries"]["2020-01-01"]["Body & Presence"]["notes"] == "from-legacy"
    legacy_file = data_roots["legacy"] / "profiles" / "default" / "data.json"
    assert legacy_file.is_file()
    assert udm.consume_user_notices()


def test_new_folder_only_no_copy(data_roots):
    _write_profile_data(data_roots["canonical"], "already-here")
    results = udm.run_at_startup()
    assert not any(r.outcome == "copied" for r in results)


def test_both_present_does_not_overwrite(data_roots):
    _write_profile_data(data_roots["legacy"], "legacy-wins-never")
    _write_profile_data(data_roots["canonical"], "canonical-kept")
    udm.run_at_startup()
    with open(
        data_roots["canonical"] / "profiles" / "default" / "data.json",
        encoding="utf-8",
    ) as handle:
        data = json.load(handle)
    assert data["entries"]["2020-01-01"]["Body & Presence"]["notes"] == "canonical-kept"


def test_rerun_is_idempotent(data_roots):
    _write_profile_data(data_roots["legacy"], "once")
    udm.run_at_startup()
    udm._startup_lock = False
    first = (data_roots["canonical"] / "profiles" / "default" / "data.json").read_text(
        encoding="utf-8"
    )
    udm.run_at_startup()
    second = (data_roots["canonical"] / "profiles" / "default" / "data.json").read_text(
        encoding="utf-8"
    )
    assert first == second


def test_encrypted_data_json_copied_as_bytes(data_roots, tmp_path):
    legacy = data_roots["legacy"]
    enc = {
        "integral_encrypted": True,
        "envelope_version": 1,
        "salt": "abc",
        "ciphertext": "token",
    }
    profile_dir = legacy / "profiles" / "default"
    profile_dir.mkdir(parents=True)
    with open(profile_dir / "data.json", "w", encoding="utf-8") as handle:
        json.dump(enc, handle)
    udm.run_at_startup()
    dest = data_roots["canonical"] / "profiles" / "default" / "data.json"
    assert dest.read_text(encoding="utf-8") == json.dumps(enc)


def test_profiles_migrate_after_folder_migration(data_roots, monkeypatch):
    _write_profile_data(data_roots["legacy"], "profile-chain")
    udm.run_at_startup()
    monkeypatch.setattr(profiles, "get_app_dir", lambda: str(data_roots["canonical"]))
    profiles.ensure_app_structure()
    migrated = data_roots["canonical"] / "profiles" / "default" / "data.json"
    assert migrated.is_file()


def test_placeholder_dest_data_json_replaced_by_legacy(data_roots):
    """Simulates first launch that wrote an empty stub before migration ran."""
    stub = {
        "schema_version": 2,
        "categories": {"Body & Presence": {"checklist": [], "metrics": []}},
        "entries": {},
        "sessions": [],
        "journal": {"prompts": ["How was today?"], "entries": []},
        "milestones": [{"title": "Untitled", "status": "open", "progress": 0}],
    }
    dest_stub = data_roots["canonical"] / "data.json"
    with open(dest_stub, "w", encoding="utf-8") as handle:
        json.dump(stub, handle)
    _write_profile_data(data_roots["legacy"], "real-history")
    udm.run_at_startup()
    with open(data_roots["canonical"] / "profiles" / "default" / "data.json", encoding="utf-8") as handle:
        data = json.load(handle)
    assert data["entries"]["2020-01-01"]["Body & Presence"]["notes"] == "real-history"


def test_dest_with_todos_not_overwritten(data_roots):
    dest_data = data_roots["canonical"] / "profiles" / "default" / "data.json"
    dest_data.parent.mkdir(parents=True)
    with open(dest_data, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "entries": {},
                "todos": {"items": [{"id": "abc", "title": "keep", "done": False}]},
            },
            handle,
        )
    _write_profile_data(data_roots["legacy"], "should-not-replace")
    udm.run_at_startup()
    with open(dest_data, encoding="utf-8") as handle:
        data = json.load(handle)
    assert data["todos"]["items"][0]["title"] == "keep"


def test_resolve_dest_rejects_parent_segments(tmp_path):
    root = tmp_path / "canonical"
    root.mkdir()
    assert udm._resolve_dest_under_root(str(root), "..", "escape.txt") is None


def test_copy_skips_symlinked_source_file(data_roots, tmp_path):
    legacy = data_roots["legacy"]
    outside = tmp_path / "outside-secret"
    outside.mkdir()
    secret = outside / "secret.json"
    secret.write_text('{"leak": true}', encoding="utf-8")
    link = legacy / "secret.json"
    try:
        link.symlink_to(secret)
    except OSError:
        pytest.skip("symlinks not supported")
    udm.run_at_startup()
    assert not (data_roots["canonical"] / "secret.json").exists()


def test_placeholder_root_data_json_sidelined_when_legacy_has_root(data_roots):
    legacy_root = data_roots["legacy"] / "data.json"
    legacy_root.parent.mkdir(parents=True, exist_ok=True)
    with open(legacy_root, "w", encoding="utf-8") as handle:
        json.dump(
            {"entries": {"2021-01-01": {"Body & Presence": {"rating": 8, "notes": "root-file"}}}},
            handle,
        )
    dest_stub = data_roots["canonical"] / "data.json"
    with open(dest_stub, "w", encoding="utf-8") as handle:
        json.dump({"schema_version": 2, "entries": {}}, handle)
    udm.run_at_startup()
    with open(data_roots["canonical"] / "data.json", encoding="utf-8") as handle:
        data = json.load(handle)
    assert data["entries"]["2021-01-01"]["Body & Presence"]["notes"] == "root-file"
    assert list(data_roots["canonical"].glob("data.json.preserved-before-migration-*"))


def test_user_data_dir_frozen_points_at_integral(monkeypatch):
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    resolved = paths.user_data_dir()
    if sys.platform == "win32":
        assert resolved.endswith("Integral")
    else:
        assert resolved.endswith(".integral")

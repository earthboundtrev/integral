"""Encrypted profile backup export/import (#136)."""

from __future__ import annotations

import io
import json
import os
import shutil
import struct
import tempfile
import unicodedata
import zipfile

import pytest

import backup
import profiles
import storage
from vault import PassphraseRequiredError, WrongPassphraseError

from tests.test_backup import temp_app  # noqa: F401 — pytest fixture

_JOURNAL_MARK = "unique-journal-marker-136"
_PASS = "test-backup-pass"


@pytest.fixture
def seeded_profile(temp_app):  # noqa: F811
    profiles.set_active_profile("default")
    data = storage.load()
    data["entries"]["2026-11-01"] = {
        "Emotional Wellbeing": {
            "rating": 6,
            "checklist": {},
            "metrics": {},
            "notes": _JOURNAL_MARK,
        }
    }
    storage.save(data)
    return temp_app


def _encrypted_path(tmp_path, name: str = "profile-backup") -> str:
    return str(tmp_path / f"{name}{backup.ENCRYPTED_BACKUP_DEFAULT_SUFFIX}")


def _write_minimal_profile_zip(path: str, *, extra_member: str | None = None) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("config.json", json.dumps(profiles.load_config()))
        zf.writestr(
            backup.MANIFEST_NAME,
            json.dumps(
                {
                    "backup_version": backup.BACKUP_VERSION,
                    "profiles": ["default"],
                    "files": [f"profiles/default/{storage.DATA_FILE_NAME}"],
                }
            ),
        )
        zf.writestr(
            f"profiles/default/{storage.DATA_FILE_NAME}",
            json.dumps(storage.empty_data()),
        )
        if extra_member is not None:
            zf.writestr(extra_member, "blocked")
    with open(path, "wb") as handle:
        handle.write(buf.getvalue())


def test_encrypted_export_not_a_zip_and_hides_journal(seeded_profile, tmp_path):
    out = _encrypted_path(tmp_path)
    manifest = backup.export_backup(
        out,
        profile_id="default",
        passphrase=_PASS,
    )
    assert manifest.get("encrypted") is True
    assert not zipfile.is_zipfile(out)

    blob = tmp_path.joinpath(os.path.basename(out)).read_bytes()
    assert _JOURNAL_MARK.encode("utf-8") not in blob
    assert backup.is_encrypted_backup_file(out)


def test_encrypted_roundtrip_and_wrong_passphrase(seeded_profile, tmp_path):
    out = _encrypted_path(tmp_path)
    backup.export_backup(out, profile_id="default", passphrase=_PASS)

    storage.save({"categories": storage.get_default_categories(), "entries": {}})

    backup.import_backup(out, merge_profiles=True, passphrase=_PASS)
    restored = storage.load()
    assert restored["entries"]["2026-11-01"]["Emotional Wellbeing"]["notes"] == _JOURNAL_MARK

    before = storage.load()
    with pytest.raises(WrongPassphraseError):
        backup.import_backup(out, merge_profiles=True, passphrase="not-the-pass")
    after = storage.load()
    assert after == before


def test_plain_backup_still_works(seeded_profile, tmp_path):
    plain = str(tmp_path / "plain.zip")
    backup.export_backup(plain, profile_id="default")
    assert zipfile.is_zipfile(plain)

    storage.save({"categories": storage.get_default_categories(), "entries": {}})
    backup.import_backup(plain, merge_profiles=True)
    restored = storage.load()
    assert restored["entries"]["2026-11-01"]["Emotional Wellbeing"]["notes"] == _JOURNAL_MARK


def test_empty_passphrase_rejected(seeded_profile, tmp_path):
    out = _encrypted_path(tmp_path)
    with pytest.raises(ValueError, match="Passphrase"):
        backup.export_backup(out, profile_id="default", passphrase="")
    with pytest.raises(ValueError, match="Passphrase"):
        backup.export_backup(out, profile_id="default", passphrase="   ")


@pytest.mark.skipif(not backup.CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_nfc_passphrase_roundtrip(seeded_profile, tmp_path):
    composed = "Zażołć€"
    decomposed = unicodedata.normalize("NFD", composed)
    assert backup.normalize_backup_passphrase(composed) == backup.normalize_backup_passphrase(
        decomposed
    )

    out = _encrypted_path(tmp_path, "nfc")
    backup.export_backup(out, profile_id="default", passphrase=decomposed)
    storage.save({"categories": storage.get_default_categories(), "entries": {}})
    backup.import_backup(out, merge_profiles=True, passphrase=composed)


@pytest.mark.skipif(not backup.CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_encrypted_backup_requires_passphrase(seeded_profile, tmp_path):
    out = _encrypted_path(tmp_path)
    backup.export_backup(out, profile_id="default", passphrase=_PASS)
    with pytest.raises(PassphraseRequiredError):
        backup.validate_backup(out)


def test_backup_kdf_defaults_at_six_hundred_thousand():
    assert backup.ENCRYPTED_BACKUP_KDF_ITERATIONS == 600_000
    assert backup.ENCRYPTED_BACKUP_KDF_ITERATIONS_MIN == 600_000


@pytest.mark.skipif(not backup.CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_stored_kdf_iterations_roundtrip(seeded_profile, tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "ENCRYPTED_BACKUP_KDF_ITERATIONS", 650_000)
    out = _encrypted_path(tmp_path, "kdf")
    backup.export_backup(out, profile_id="default", passphrase=_PASS)
    storage.save({"categories": storage.get_default_categories(), "entries": {}})
    backup.import_backup(out, merge_profiles=True, passphrase=_PASS)
    assert storage.load()["entries"]["2026-11-01"]["Emotional Wellbeing"]["notes"] == _JOURNAL_MARK


@pytest.mark.skipif(not backup.CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_truncated_encrypted_header_invalid(tmp_path):
    garbage = backup.ENCRYPTED_BACKUP_MAGIC + bytes([1, 0, 0, 0, 0]) + b"\x10"
    path = str(tmp_path / "trunc.bin")
    with open(path, "wb") as handle:
        handle.write(garbage)
    with pytest.raises(ValueError, match="(invalid|Not a valid)"):
        backup._unpack_encrypted_backup(garbage, "pw")


def test_no_plaintext_zip_sidecar_in_export_dir(seeded_profile, tmp_path, monkeypatch):
    partial_seen: list[str] = []

    original_mkstemp = tempfile.mkstemp

    def tracked_mkstemp(*args, **kwargs):
        fd, path = original_mkstemp(*args, **kwargs)
        partial_seen.append(path)
        return fd, path

    monkeypatch.setattr(tempfile, "mkstemp", tracked_mkstemp)

    out = _encrypted_path(tmp_path)
    backup.export_backup(out, profile_id="default", passphrase=_PASS)

    for path in tmp_path.iterdir():
        if path.is_file() and path.name != os.path.basename(out):
            data = path.read_bytes()
            assert _JOURNAL_MARK.encode("utf-8") not in data
            assert not data.startswith(b"PK\x03\x04")

    for partial in partial_seen:
        assert not os.path.exists(partial), "partial export file should be removed after replace"


def test_unsafe_zip_member_rejected_on_import(temp_app, tmp_path):
    plain = str(tmp_path / "evil.zip")
    _write_minimal_profile_zip(plain, extra_member="profiles/default/../../escape.txt")
    with pytest.raises(ValueError, match="unsafe"):
        backup.validate_backup(plain)


@pytest.mark.parametrize(
    "member",
    [
        "C:x",
        "C:/x",
        "C:\\x",
        "profiles/default/data.json:stream",
    ],
)
def test_rejects_colon_and_drive_style_members(temp_app, tmp_path, member):
    plain = str(tmp_path / "bad-member.zip")
    _write_minimal_profile_zip(plain, extra_member=member)
    with pytest.raises(ValueError, match="unsafe"):
        backup.validate_backup(plain)


@pytest.mark.skipif(not backup.CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_rejects_kdf_header_below_minimum(seeded_profile, tmp_path):
    out = _encrypted_path(tmp_path, "weak-kdf")
    backup.export_backup(out, profile_id="default", passphrase=_PASS)
    with open(out, "rb") as handle:
        data = bytearray(handle.read())
    pos = len(backup.ENCRYPTED_BACKUP_MAGIC) + 1
    struct.pack_into(">I", data, pos, 500_000)
    with open(out, "wb") as handle:
        handle.write(data)
    with pytest.raises(ValueError, match="KDF"):
        backup.validate_backup(out, passphrase=_PASS)


def test_staging_removed_when_install_fails(seeded_profile, tmp_path, monkeypatch):
    plain = str(tmp_path / "fail-install.zip")
    backup.export_backup(plain, profile_id="default")
    staging_parent = os.path.join(
        profiles.get_app_dir(),
        backup.BACKUP_IMPORT_STAGING_DIRNAME,
    )

    real_copy2 = shutil.copy2

    def fail_first_copy(src, dst, *args, **kwargs):
        raise OSError("simulated install failure")

    monkeypatch.setattr(shutil, "copy2", fail_first_copy)

    with pytest.raises(OSError, match="simulated"):
        backup.import_backup(plain, merge_profiles=True)

    if os.path.isdir(staging_parent):
        assert not any(os.scandir(staging_parent))
    monkeypatch.setattr(shutil, "copy2", real_copy2)


def test_import_staging_lives_under_app_dir_and_is_removed(seeded_profile, tmp_path):
    plain = str(tmp_path / "stage.zip")
    backup.export_backup(plain, profile_id="default")
    app_dir = profiles.get_app_dir()
    staging_parent = os.path.join(app_dir, backup.BACKUP_IMPORT_STAGING_DIRNAME)

    storage.save({"categories": storage.get_default_categories(), "entries": {}})
    backup.import_backup(plain, merge_profiles=True)

    assert staging_parent.startswith(app_dir)
    if os.path.isdir(staging_parent):
        assert not any(os.scandir(staging_parent)), "staging run dirs should be removed after import"

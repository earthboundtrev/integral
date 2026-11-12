"""Encrypted profile backup export/import (#136)."""

from __future__ import annotations

import os
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


@pytest.mark.skipif(not backup.CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_stored_kdf_iterations_roundtrip(seeded_profile, tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "ENCRYPTED_BACKUP_KDF_ITERATIONS", 480_000)
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
    assert storage.load()["entries"]["2026-11-01"]["Emotional Wellbeing"]["notes"] == _JOURNAL_MARK


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
    """validate_backup rejects zip entries that escape via unsafe paths."""
    import json
    import io

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
        zf.writestr("profiles/default/../../escape.txt", "oops")
        zf.writestr(
            f"profiles/default/{storage.DATA_FILE_NAME}",
            json.dumps(storage.empty_data()),
        )
    plain = str(tmp_path / "evil.zip")
    with open(plain, "wb") as handle:
        handle.write(buf.getvalue())

    with pytest.raises(ValueError, match="unsafe"):
        backup.validate_backup(plain)

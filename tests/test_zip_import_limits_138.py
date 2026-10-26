"""Zip import limits for backup and YouTube Takeout (#138)."""

from __future__ import annotations

import io
import json
import os
import struct
import tracemalloc
import zipfile
from pathlib import Path
from unittest import mock

import pytest

import backup
import profiles
import storage
import youtube_takeout
import zip_import_safety
from tests.test_backup import temp_app  # noqa: F401 — pytest fixture


def _minimal_backup_manifest(profile_id: str = "default") -> dict:
    return {
        "backup_version": backup.BACKUP_VERSION,
        "profiles": [profile_id],
        "files": [f"profiles/{profile_id}/data.json"],
    }


def _patch_zip_declared_uncompressed(zip_path: os.PathLike[str] | str, member: str, declared: int) -> None:
    """Set ZipInfo.file_size in local + central headers (for malicious-archive tests)."""
    data = bytearray(Path(zip_path).read_bytes())
    name = member.encode("utf-8")

    pos = 0
    while pos < len(data) - 4:
        if data[pos : pos + 4] != b"PK\x03\x04":
            pos += 1
            continue
        fn_len = struct.unpack_from("<H", data, pos + 26)[0]
        extra_len = struct.unpack_from("<H", data, pos + 28)[0]
        fn = data[pos + 30 : pos + 30 + fn_len]
        if fn == name:
            struct.pack_into("<I", data, pos + 22, declared)
        comp_size = struct.unpack_from("<I", data, pos + 18)[0]
        pos = pos + 30 + fn_len + extra_len + comp_size

    pos = 0
    while pos < len(data) - 4:
        if data[pos : pos + 4] != b"PK\x01\x02":
            pos += 1
            continue
        fn_len = struct.unpack_from("<H", data, pos + 28)[0]
        extra_len = struct.unpack_from("<H", data, pos + 30)[0]
        comment_len = struct.unpack_from("<H", data, pos + 32)[0]
        fn = data[pos + 46 : pos + 46 + fn_len]
        if fn == name:
            struct.pack_into("<I", data, pos + 24, declared)
        pos += 46 + fn_len + extra_len + comment_len

    path = os.fspath(zip_path)
    with open(path, "wb") as handle:
        handle.write(data)


def _write_minimal_backup_zip(
    path: str,
    *,
    extra_members: int = 0,
    profile_payload: dict | None = None,
) -> None:
    config = profiles.default_config()
    data = profile_payload or storage.empty_data()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("config.json", json.dumps(config))
        zf.writestr("profiles/default/data.json", json.dumps(data))
        zf.writestr(backup.MANIFEST_NAME, json.dumps(_minimal_backup_manifest()))
        for index in range(extra_members):
            zf.writestr(f"padding/pad-{index}.txt", "x")


def test_normal_backup_import_still_works(temp_app, tmp_path):
    profiles.set_active_profile("default")
    data = storage.load()
    data["entries"]["2026-10-01"] = {
        "Body & Presence": {"rating": 5, "checklist": {}, "metrics": {}, "notes": "limits ok"}
    }
    storage.save(data)

    zip_path = str(tmp_path / "ok.zip")
    backup.export_backup(zip_path, profile_id="default")
    storage.save({"categories": storage.get_default_categories(), "entries": {}})

    backup.import_backup(zip_path, merge_profiles=True)
    restored = storage.load()
    assert restored["entries"]["2026-10-01"]["Body & Presence"]["notes"] == "limits ok"


def test_normal_takeout_zip_still_works(tmp_path):
    fixture = [
        {
            "header": "YouTube",
            "title": "Watched Example",
            "titleUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "time": "2024-06-01T12:00:00.000Z",
        }
    ]
    zip_path = tmp_path / "takeout.zip"
    inner = "Takeout/YouTube and YouTube Music/history/watch-history.json"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(inner, json.dumps(fixture))
    events, unparsed = youtube_takeout.load_events_from_path(str(zip_path))
    assert len(events) == 1
    assert unparsed == 0


def test_rejects_too_many_members(temp_app, tmp_path):
    zip_path = str(tmp_path / "many.zip")
    over = zip_import_safety.MAX_ZIP_MEMBERS + 1
    _write_minimal_backup_zip(zip_path, extra_members=over)
    with pytest.raises(zip_import_safety.ZipImportLimitError, match="too many files"):
        backup.validate_backup(zip_path)


def test_rejects_declared_oversized_member_without_reading_body(temp_app, tmp_path):
    zip_path = tmp_path / "huge-declared.zip"
    huge = zip_import_safety.MAX_MEMBER_UNCOMPRESSED_BYTES + 1
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("profiles/default/data.json", b"{}")
        zf.writestr("config.json", json.dumps(profiles.default_config()))
        zf.writestr(backup.MANIFEST_NAME, json.dumps(_minimal_backup_manifest()))
    _patch_zip_declared_uncompressed(zip_path, "profiles/default/data.json", huge)

    tracemalloc.start()
    try:
        with pytest.raises(zip_import_safety.ZipImportLimitError, match="too large"):
            backup.validate_backup(str(zip_path))
        _, peak = tracemalloc.get_traced_memory()
        assert peak < 50 * 1024 * 1024
    finally:
        tracemalloc.stop()


def test_rejects_member_that_decompresses_beyond_cap(temp_app, tmp_path, monkeypatch):
    """Declared size is small; streamed payload exceeds per-member cap."""
    small_cap = 512 * 1024
    monkeypatch.setattr(zip_import_safety, "MAX_MEMBER_UNCOMPRESSED_BYTES", small_cap)
    payload = b"x" * (small_cap + zip_import_safety.CHUNK_SIZE)
    zip_path = tmp_path / "understated.zip"
    _write_minimal_backup_zip(zip_path, profile_payload={"categories": [], "entries": {}})
    budget = zip_import_safety.ZipImportBudget()

    with zipfile.ZipFile(zip_path, "r") as zf:
        info = zf.getinfo("profiles/default/data.json")
        info.file_size = 10

        stream = io.BytesIO(payload)
        open_cm = mock.MagicMock()
        open_cm.__enter__.return_value = stream
        open_cm.__exit__.return_value = None
        with mock.patch.object(zf, "getinfo", return_value=info):
            with mock.patch.object(zf, "open", return_value=open_cm):
                with pytest.raises(zip_import_safety.ZipImportLimitError, match="while decompressing"):
                    zip_import_safety.read_zip_member_bytes(
                        zf,
                        "profiles/default/data.json",
                        budget,
                    )


class _CountingReader(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.read_sizes: list[int] = []

    def read(self, size: int = -1) -> bytes:
        if size < 0 or size > zip_import_safety.CHUNK_SIZE:
            size = zip_import_safety.CHUNK_SIZE
        chunk = super().read(size)
        self.read_sizes.append(len(chunk))
        return chunk


def test_streaming_never_reads_more_than_cap_plus_one_chunk():
    cap = 1024
    budget = zip_import_safety.ZipImportBudget()
    payload = b"a" * (cap + zip_import_safety.CHUNK_SIZE * 2)
    stream = _CountingReader(payload)

    with pytest.raises(zip_import_safety.ZipImportLimitError):
        zip_import_safety._read_stream_limited(
            stream,
            budget,
            member_label="test",
            member_cap=cap,
        )
    assert sum(stream.read_sizes) <= cap + zip_import_safety.CHUNK_SIZE


def test_rejected_backup_leaves_profile_data_unchanged(temp_app, tmp_path, monkeypatch):
    small_cap = 64 * 1024
    monkeypatch.setattr(zip_import_safety, "MAX_MEMBER_UNCOMPRESSED_BYTES", small_cap)
    profiles.set_active_profile("default")
    data = storage.load()
    data["entries"]["2026-10-02"] = {
        "Body & Presence": {"rating": 9, "checklist": {}, "metrics": {}, "notes": "keep me"}
    }
    storage.save(data)
    data_path = os.path.join(profiles.get_profile_dir("default"), storage.DATA_FILE_NAME)
    before_mtime = os.path.getmtime(data_path)

    zip_path = tmp_path / "bad-import.zip"
    payload = b"y" * (small_cap + 1)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("config.json", json.dumps(profiles.default_config()))
        zf.writestr("profiles/default/data.json", payload)
        zf.writestr(backup.MANIFEST_NAME, json.dumps(_minimal_backup_manifest()))

    with pytest.raises(zip_import_safety.ZipImportLimitError):
        backup.import_backup(str(zip_path), merge_profiles=True)

    assert os.path.getmtime(data_path) == before_mtime
    assert storage.load()["entries"]["2026-10-02"]["Body & Presence"]["notes"] == "keep me"


def test_permission_error_surfaces_friendly_message(temp_app, tmp_path):
    zip_path = str(tmp_path / "ok-small.zip")
    _write_minimal_backup_zip(zip_path)

    with zipfile.ZipFile(zip_path, "r") as zf:
        budget = zip_import_safety.prepare_zip_import(zf)
        with mock.patch("builtins.open", side_effect=PermissionError("blocked")):
            with pytest.raises(zip_import_safety.ZipImportLimitError, match="blocked"):
                zip_import_safety.copy_zip_member_to_file(
                    zf,
                    "profiles/default/data.json",
                    str(tmp_path / "out.json"),
                    budget,
                )


def test_rejects_suspicious_compression_ratio(temp_app, tmp_path):
    zip_path = tmp_path / "zip-bomb-ratio.zip"
    # Tiny compressed payload, huge declared uncompressed size (under per-member cap).
    declared = 5 * 1024 * 1024
    compressed = declared // (zip_import_safety.MAX_COMPRESSION_RATIO + 1)
    payload = b"z" * compressed
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo("profiles/default/data.json")
        info.compress_type = zipfile.ZIP_DEFLATED
        info.file_size = declared
        info.compress_size = compressed
        info.CRC = zipfile.crc32(payload) & 0xFFFFFFFF
        zf.writestr(info, payload)
        zf.writestr("config.json", json.dumps(profiles.default_config()))
        zf.writestr(backup.MANIFEST_NAME, json.dumps(_minimal_backup_manifest()))

    with pytest.raises(zip_import_safety.ZipImportLimitError, match="suspicious compression"):
        backup.validate_backup(str(zip_path))

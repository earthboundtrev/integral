"""Staging directory removal must stay inside app data dir (#275)."""

from __future__ import annotations

import os

import backup
import profiles
from tests.test_backup import temp_app  # noqa: F401


def test_remove_staging_parent_skips_path_outside_app_dir(temp_app, tmp_path, monkeypatch):
    outside = tmp_path / "outside-staging"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("x", encoding="utf-8")
    backup._remove_empty_staging_parent(str(outside))  # noqa: SLF001
    assert marker.is_file()


def test_remove_staging_dir_skips_path_outside_app_dir(temp_app, tmp_path):
    outside = tmp_path / "outside-run"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("x", encoding="utf-8")
    backup._remove_import_staging_dir(str(outside))  # noqa: SLF001
    assert marker.is_file()

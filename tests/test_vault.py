"""Tests for vault encryption performance helpers."""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import vault


def test_encrypt_reuses_existing_salt(tmp_path):
    path = tmp_path / "data.json"
    payload = {"entries": {}, "settings": {}}
    passphrase = "test-passphrase"

    vault.save_data_file(str(path), payload, encrypted=True, passphrase=passphrase)
    with open(path, encoding="utf-8") as handle:
        first = json.load(handle)
    first_salt = first["salt"]

    payload["entries"] = {"2026-07-05": {"Body & Presence": {"rating": 8}}}
    vault.save_data_file(str(path), payload, encrypted=True, passphrase=passphrase)
    with open(path, encoding="utf-8") as handle:
        second = json.load(handle)

    assert second["salt"] == first_salt
    decrypted = vault.decrypt_payload(second, passphrase)
    assert decrypted["entries"]["2026-07-05"]["Body & Presence"]["rating"] == 8


def test_derive_key_is_cached():
    vault._derived_key_cache.clear()
    salt = b"1234567890123456"
    first = vault._derive_key("secret", salt)
    second = vault._derive_key("secret", salt)
    assert first == second
    assert len(vault._derived_key_cache) == 1

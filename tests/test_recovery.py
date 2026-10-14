"""Tests for startup recovery from corrupt data.json (issue #96)."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from vault import load_data_file_with_recovery, save_data_file


def test_recovery_loads_valid_file_normally(tmp_path):
    """If data.json is valid, recovery should just load it."""
    data_file = tmp_path / "data.json"
    payload = {"valid": "data", "version": 1}
    
    # Create valid file
    save_data_file(str(data_file), payload, encrypted=False, passphrase=None)
    
    # Recovery should load it without prompts
    loaded = load_data_file_with_recovery(
        str(data_file), 
        passphrase=None,
        on_recovery_prompt=lambda bak, ts: False,  # Should not be called
        on_both_corrupt_prompt=lambda: False  # Should not be called
    )
    
    assert loaded == payload


def test_recovery_restores_from_backup_when_main_corrupt(tmp_path):
    """If data.json is corrupt but .bak is valid, should offer to restore."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create good backup
    backup_payload = {"version": 1, "from": "backup"}
    save_data_file(str(bak_file), backup_payload, encrypted=False, passphrase=None)
    
    # Create corrupt main file
    with open(data_file, "w") as f:
        f.write('{"invalid": "json", "missing')  # Incomplete JSON
    
    # Track prompts
    prompts = []
    
    def on_recovery_prompt(bak_path, bak_timestamp):
        prompts.append(("recovery", bak_path, bak_timestamp))
        return True  # Accept recovery
    
    # Recovery should prompt and restore
    loaded = load_data_file_with_recovery(
        str(data_file),
        passphrase=None,
        on_recovery_prompt=on_recovery_prompt,
        on_both_corrupt_prompt=lambda: False  # Should not be called
    )
    
    # Should have prompted for recovery
    assert len(prompts) == 1
    assert prompts[0][0] == "recovery"
    assert str(bak_file) in prompts[0][1]
    
    # Should have loaded backup data
    assert loaded == backup_payload
    
    # Should have preserved corrupt file
    corrupt_files = list(tmp_path.glob("data.json.corrupt-*"))
    assert len(corrupt_files) == 1
    
    # Main file should now have backup data
    with open(data_file) as f:
        restored = json.load(f)
    assert restored == backup_payload


def test_recovery_declines_backup_restore_raises_error(tmp_path):
    """If user declines backup restore, should raise ValueError."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create good backup
    backup_payload = {"version": 1, "from": "backup"}
    save_data_file(str(bak_file), backup_payload, encrypted=False, passphrase=None)
    
    # Create corrupt main file
    with open(data_file, "w") as f:
        f.write('{"invalid": "json", "missing')
    
    # User declines recovery
    with pytest.raises(ValueError, match="declined recovery"):
        load_data_file_with_recovery(
            str(data_file),
            passphrase=None,
            on_recovery_prompt=lambda bak, ts: False,  # Decline
            on_both_corrupt_prompt=lambda: False
        )


def test_recovery_both_corrupt_offers_empty_start(tmp_path):
    """If both files are corrupt, should offer to start empty."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create corrupt main file
    with open(data_file, "w") as f:
        f.write('{"invalid": "json"')
    
    # Create corrupt backup
    with open(bak_file, "w") as f:
        f.write('{"also": "corrupt')
    
    prompts = []
    
    def on_both_corrupt_prompt():
        prompts.append("both_corrupt")
        return True  # Accept empty start
    
    # Recovery should prompt for empty start
    loaded = load_data_file_with_recovery(
        str(data_file),
        passphrase=None,
        on_recovery_prompt=lambda bak, ts: False,
        on_both_corrupt_prompt=on_both_corrupt_prompt
    )
    
    # Should have prompted
    assert len(prompts) == 1
    
    # Should return empty dict
    assert loaded == {}
    
    # Should have preserved corrupt file
    corrupt_files = list(tmp_path.glob("data.json.corrupt-*"))
    assert len(corrupt_files) == 1


def test_recovery_both_corrupt_declined_raises_error(tmp_path):
    """If user declines empty start when both corrupt, should raise ValueError."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create corrupt files
    with open(data_file, "w") as f:
        f.write('{"invalid')
    with open(bak_file, "w") as f:
        f.write('{"also')
    
    # User declines empty start
    with pytest.raises(ValueError, match="declined to start with empty"):
        load_data_file_with_recovery(
            str(data_file),
            passphrase=None,
            on_recovery_prompt=lambda bak, ts: False,
            on_both_corrupt_prompt=lambda: False  # Decline
        )


def test_recovery_backup_timestamp_provided(tmp_path):
    """Recovery prompt should include backup timestamp."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create backup with known modification time
    backup_payload = {"version": 1}
    save_data_file(str(bak_file), backup_payload, encrypted=False, passphrase=None)
    
    # Create corrupt main file
    with open(data_file, "w") as f:
        f.write('{"corrupt')
    
    received_timestamp = None
    
    def on_recovery_prompt(bak_path, bak_timestamp):
        nonlocal received_timestamp
        received_timestamp = bak_timestamp
        return True
    
    load_data_file_with_recovery(
        str(data_file),
        passphrase=None,
        on_recovery_prompt=on_recovery_prompt,
        on_both_corrupt_prompt=lambda: False
    )
    
    # Timestamp should be provided and formatted
    assert received_timestamp is not None
    # Should be in format YYYY-MM-DD HH:MM:SS
    datetime.strptime(received_timestamp, "%Y-%m-%d %H:%M:%S")


def test_recovery_works_with_encrypted_files(tmp_path):
    """Recovery should work with encrypted files."""
    pytest.importorskip("cryptography")
    
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    passphrase = "test-pass-456"
    
    # Create encrypted backup
    backup_payload = {"encrypted": "backup", "secret": 42}
    save_data_file(str(bak_file), backup_payload, encrypted=True, passphrase=passphrase)
    
    # Create corrupt main file (even encrypted envelope corrupt)
    with open(data_file, "w") as f:
        f.write('{"integral_encrypted": true, "salt": "invalid')
    
    # Recovery should work with passphrase
    loaded = load_data_file_with_recovery(
        str(data_file),
        passphrase=passphrase,
        on_recovery_prompt=lambda bak, ts: True,
        on_both_corrupt_prompt=lambda: False
    )
    
    assert loaded == backup_payload


def test_recovery_preserves_original_corrupt_file(tmp_path):
    """Recovery should preserve the corrupt file with timestamp."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create backup
    backup_payload = {"version": 1}
    save_data_file(str(bak_file), backup_payload, encrypted=False, passphrase=None)
    
    # Create corrupt main file with specific content
    corrupt_content = '{"this": "is", "corrupt": "json'
    with open(data_file, "w") as f:
        f.write(corrupt_content)
    
    # Do recovery
    load_data_file_with_recovery(
        str(data_file),
        passphrase=None,
        on_recovery_prompt=lambda bak, ts: True,
        on_both_corrupt_prompt=lambda: False
    )
    
    # Find the preserved corrupt file
    corrupt_files = list(tmp_path.glob("data.json.corrupt-*"))
    assert len(corrupt_files) == 1
    
    # Verify it contains the original corrupt content
    with open(corrupt_files[0]) as f:
        preserved = f.read()
    assert preserved == corrupt_content


def test_recovery_handles_missing_backup_file(tmp_path):
    """If main is corrupt and no backup exists, should offer empty start."""
    data_file = tmp_path / "data.json"
    
    # Create corrupt main file (no backup)
    with open(data_file, "w") as f:
        f.write('{"corrupt": "data')
    
    prompts = []
    
    def on_both_corrupt_prompt():
        prompts.append("both_corrupt")
        return True
    
    # Recovery should go to "both corrupt" path (which includes "no backup")
    loaded = load_data_file_with_recovery(
        str(data_file),
        passphrase=None,
        on_recovery_prompt=lambda bak, ts: False,  # Should not be called
        on_both_corrupt_prompt=on_both_corrupt_prompt
    )
    
    assert len(prompts) == 1
    assert loaded == {}


def test_recovery_default_prompts_accept(tmp_path):
    """If no prompt callbacks provided, should default to accepting recovery."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create good backup
    backup_payload = {"backup": True}
    save_data_file(str(bak_file), backup_payload, encrypted=False, passphrase=None)
    
    # Create corrupt main
    with open(data_file, "w") as f:
        f.write('{"corrupt')
    
    # With no callbacks, should default to accepting recovery
    loaded = load_data_file_with_recovery(
        str(data_file),
        passphrase=None,
        on_recovery_prompt=None,  # Will use default behavior (accept)
        on_both_corrupt_prompt=None
    )
    
    # Should have recovered from backup
    assert loaded == backup_payload

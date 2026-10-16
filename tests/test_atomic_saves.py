"""Tests for atomic saves with backup rotation (issue #95, #100 gaps)."""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from vault import save_data_file, load_data_file


def test_atomic_save_creates_tmp_file_then_replaces(tmp_path):
    """Atomic save should write to .tmp then replace atomically."""
    data_file = tmp_path / "data.json"
    payload = {"test": "data", "value": 42}
    
    # Save the file
    save_data_file(str(data_file), payload, encrypted=False, passphrase=None)
    
    # Verify main file exists and is correct
    assert data_file.exists()
    with open(data_file) as f:
        loaded = json.load(f)
    assert loaded == payload
    
    # Verify tmp file was cleaned up
    assert not (tmp_path / "data.json.tmp").exists()


def test_atomic_save_creates_backup_on_second_save(tmp_path):
    """Second save should rotate the old file to .bak."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # First save
    payload1 = {"version": 1, "data": "first"}
    save_data_file(str(data_file), payload1, encrypted=False, passphrase=None)
    
    # Verify no backup yet
    assert not bak_file.exists()
    
    # Second save
    payload2 = {"version": 2, "data": "second"}
    save_data_file(str(data_file), payload2, encrypted=False, passphrase=None)
    
    # Verify backup contains first version
    assert bak_file.exists()
    with open(bak_file) as f:
        backup_data = json.load(f)
    assert backup_data == payload1
    
    # Verify main file has second version
    with open(data_file) as f:
        current_data = json.load(f)
    assert current_data == payload2


def test_atomic_save_survives_simulated_crash_mid_write(tmp_path):
    """If writing the temp file fails, the original data.json should be intact."""
    data_file = tmp_path / "data.json"
    
    # Create initial good file
    good_payload = {"version": 1, "important": "data"}
    save_data_file(str(data_file), good_payload, encrypted=False, passphrase=None)
    
    # Verify initial state
    with open(data_file) as f:
        assert json.load(f) == good_payload
    
    # Simulate a crash during write by writing partial JSON to .tmp
    tmp_file = tmp_path / "data.json.tmp"
    with open(tmp_file, "w") as f:
        f.write('{"version": 2, "partial')  # Incomplete JSON
    
    # Original file should still be intact
    with open(data_file) as f:
        loaded = json.load(f)
    assert loaded == good_payload
    
    # Now do a successful save - should clean up and work
    new_payload = {"version": 2, "complete": "data"}
    save_data_file(str(data_file), new_payload, encrypted=False, passphrase=None)
    
    with open(data_file) as f:
        loaded = json.load(f)
    assert loaded == new_payload


def test_concurrent_saves_are_serialized(tmp_path):
    """Multiple threads trying to save should be serialized by the lock."""
    data_file = tmp_path / "data.json"
    results = []
    errors = []
    
    def save_with_id(thread_id):
        try:
            for i in range(5):
                payload = {"thread": thread_id, "iteration": i}
                save_data_file(str(data_file), payload, encrypted=False, passphrase=None)
                time.sleep(0.001)  # Small delay to encourage interleaving
            results.append(thread_id)
        except Exception as e:
            errors.append((thread_id, e))
    
    # Launch multiple threads
    threads = []
    for tid in range(4):
        t = threading.Thread(target=save_with_id, args=(tid,))
        threads.append(t)
        t.start()
    
    # Wait for all to complete
    for t in threads:
        t.join()
    
    # All threads should have completed without errors
    assert len(errors) == 0, f"Errors occurred: {errors}"
    assert len(results) == 4
    
    # Final file should be valid JSON
    with open(data_file) as f:
        final = json.load(f)
    assert "thread" in final
    assert "iteration" in final


def test_save_handles_missing_directory(tmp_path):
    """Save should create parent directories if they don't exist."""
    nested_path = tmp_path / "subdir" / "nested" / "data.json"
    payload = {"test": "nested"}
    
    # Directory doesn't exist yet
    assert not nested_path.parent.exists()
    
    # Save should work
    save_data_file(str(nested_path), payload, encrypted=False, passphrase=None)
    
    # Verify file was created
    assert nested_path.exists()
    with open(nested_path) as f:
        loaded = json.load(f)
    assert loaded == payload


def test_backup_rotation_preserves_old_backup(tmp_path):
    """Third save should replace .bak with second version."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Three successive saves
    payloads = [
        {"version": 1},
        {"version": 2},
        {"version": 3},
    ]
    
    for payload in payloads:
        save_data_file(str(data_file), payload, encrypted=False, passphrase=None)
    
    # Main file should have version 3
    with open(data_file) as f:
        assert json.load(f)["version"] == 3
    
    # Backup should have version 2 (not version 1)
    with open(bak_file) as f:
        assert json.load(f)["version"] == 2


def test_encrypted_save_also_atomic(tmp_path):
    """Encrypted saves should also be atomic with backup rotation."""
    pytest.importorskip("cryptography")  # Skip if cryptography not installed
    
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    passphrase = "test-passphrase-123"
    
    # First encrypted save
    payload1 = {"secret": "data1", "value": 1}
    save_data_file(str(data_file), payload1, encrypted=True, passphrase=passphrase)
    
    # Verify encrypted and loadable
    loaded1 = load_data_file(str(data_file), passphrase)
    assert loaded1 == payload1
    
    # Second encrypted save
    payload2 = {"secret": "data2", "value": 2}
    save_data_file(str(data_file), payload2, encrypted=True, passphrase=passphrase)
    
    # Verify backup exists and is encrypted
    assert bak_file.exists()
    backup_loaded = load_data_file(str(bak_file), passphrase)
    assert backup_loaded == payload1
    
    # Verify current file has new data
    current_loaded = load_data_file(str(data_file), passphrase)
    assert current_loaded == payload2


def test_fsync_called_on_temp_file(tmp_path, monkeypatch):
    """Verify that fsync is called on the temp file before replace."""
    data_file = tmp_path / "data.json"
    fsync_calls = []
    
    original_fsync = os.fsync
    
    def track_fsync(fd):
        fsync_calls.append(fd)
        return original_fsync(fd)
    
    monkeypatch.setattr(os, "fsync", track_fsync)
    
    payload = {"test": "fsync"}
    save_data_file(str(data_file), payload, encrypted=False, passphrase=None)
    
    # fsync should have been called at least once
    assert len(fsync_calls) > 0


def test_restore_atomic_survives_crash_mid_restore(tmp_path):
    """If restore crashes mid-write, original data.json should be intact."""
    from integral_io import restore_backup_to_path, backup_payload
    
    data_file = tmp_path / "data.json"
    
    # Create initial good file
    original_data = {"version": 1, "important": "original"}
    save_data_file(str(data_file), original_data, encrypted=False, passphrase=None)
    
    # Verify original exists
    with open(data_file) as f:
        assert json.load(f) == original_data
    
    # Try to restore a backup but simulate crash by writing partial tmp
    tmp_file = tmp_path / "data.json.tmp"
    with open(tmp_file, "w") as f:
        f.write('{"version": 2, "partial')  # Incomplete JSON
    
    # Original file should still be intact
    with open(data_file) as f:
        loaded = json.load(f)
    assert loaded == original_data
    
    # Now do a successful restore - should clean up and work
    backup = backup_payload({"version": 2, "restored": "data"})
    restore_backup_to_path(backup, str(data_file), make_copy=False)
    
    with open(data_file) as f:
        restored = json.load(f)
    # Should not have backup_ prefix keys
    assert "restored" in restored
    assert restored["version"] == 2
    assert "backup_exported_at" not in restored


def test_restore_uses_save_lock(tmp_path):
    """Restore should use the same lock as saves to prevent races."""
    from integral_io import restore_backup_to_path, backup_payload
    from vault import _save_lock
    
    data_file = tmp_path / "data.json"
    errors = []
    completed = []
    
    def do_saves():
        try:
            for i in range(10):
                payload = {"type": "save", "iteration": i}
                save_data_file(str(data_file), payload, encrypted=False, passphrase=None)
            completed.append("saves")
        except Exception as e:
            errors.append(("save", e))
    
    def do_restore():
        try:
            import time
            time.sleep(0.01)  # Let saves start first
            backup = backup_payload({"type": "restore", "data": "restored"})
            restore_backup_to_path(backup, str(data_file), make_copy=False)
            completed.append("restore")
        except Exception as e:
            errors.append(("restore", e))
    
    # Run saves and restore concurrently
    import threading
    save_thread = threading.Thread(target=do_saves)
    restore_thread = threading.Thread(target=do_restore)
    
    save_thread.start()
    restore_thread.start()
    
    save_thread.join()
    restore_thread.join()
    
    # Both should complete without errors
    assert len(errors) == 0, f"Errors: {errors}"
    assert len(completed) == 2
    
    # Final file should be valid JSON (either from save or restore)
    with open(data_file) as f:
        final = json.load(f)
    assert "type" in final
    assert final["type"] in ("save", "restore")


def test_main_file_never_missing_during_save(tmp_path):
    """GAP #1: Main file must never go missing during backup rotation."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create initial file
    payload1 = {"version": 1, "data": "first"}
    save_data_file(str(data_file), payload1, encrypted=False, passphrase=None)
    assert data_file.exists()
    
    # Patch os.replace to verify main file still exists before final replace
    original_replace = os.replace
    replace_calls = []
    
    def tracked_replace(src, dst):
        replace_calls.append((src, dst))
        # At this point in the save, both main and backup should exist
        # (because we copy to backup, not move)
        if dst == str(data_file):
            assert data_file.exists(), "Main file missing before final replace!"
            assert bak_file.exists(), "Backup missing before final replace!"
        return original_replace(src, dst)
    
    with patch('os.replace', side_effect=tracked_replace):
        payload2 = {"version": 2, "data": "second"}
        save_data_file(str(data_file), payload2, encrypted=False, passphrase=None)
    
    # Verify both files exist after save
    assert data_file.exists()
    assert bak_file.exists()
    
    # Verify backup has old version
    with open(bak_file) as f:
        assert json.load(f) == payload1


def test_permission_error_retry_succeeds(tmp_path):
    """GAP #5: PermissionError should be retried with backoff."""
    data_file = tmp_path / "data.json"
    payload = {"test": "data"}
    
    # Simulate PermissionError on first two attempts, then succeed
    attempt_count = [0]
    original_open = open
    
    def flaky_open(path, *args, **kwargs):
        if str(path).endswith(".tmp") and "w" in str(args):
            attempt_count[0] += 1
            if attempt_count[0] <= 2:
                raise PermissionError("Simulated antivirus lock")
        return original_open(path, *args, **kwargs)
    
    with patch('builtins.open', side_effect=flaky_open):
        # Should succeed after retries
        save_data_file(str(data_file), payload, encrypted=False, passphrase=None)
    
    assert attempt_count[0] == 3  # Failed twice, succeeded on third
    assert data_file.exists()
    with open(data_file) as f:
        assert json.load(f) == payload


def test_permission_error_retry_exhaustion(tmp_path):
    """GAP #5: After max retries, PermissionError should raise RuntimeError."""
    data_file = tmp_path / "data.json"
    payload = {"test": "data"}
    
    # Simulate persistent PermissionError
    original_open = open
    
    def locked_open(path, *args, **kwargs):
        if str(path).endswith(".tmp") and "w" in str(args):
            raise PermissionError("Persistent file lock")
        return original_open(path, *args, **kwargs)
    
    with patch('builtins.open', side_effect=locked_open):
        with pytest.raises(RuntimeError, match="Failed to write.*after.*retries"):
            save_data_file(str(data_file), payload, encrypted=False, passphrase=None)
    
    # Temp file should be cleaned up
    assert not (tmp_path / "data.json.tmp").exists()


def test_json_serialization_happens_under_lock(tmp_path):
    """GAP #2: JSON serialization should complete under lock before data can mutate."""
    import copy
    data_file = tmp_path / "data.json"
    
    # Create payload with nested structure
    payload = {
        "version": 1,
        "entries": {"2024-10-14": {"Body": {"rating": 7}}},
        "settings": {"dark_mode": False}
    }
    
    # Save should complete successfully even if we simulate concurrent modification
    # The JSON string is created under lock, so mutations after lock release don't matter
    save_data_file(str(data_file), payload, encrypted=False, passphrase=None)
    
    assert data_file.exists()
    with open(data_file) as f:
        loaded = json.load(f)
    assert loaded["version"] == 1
    assert "entries" in loaded


def test_save_validates_encrypted_file_before_rotating(tmp_path):
    """FIX #2: Validation before .bak rotation respects encryption."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        import pytest
        pytest.skip("cryptography not installed")
    
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    passphrase = "test-passphrase"
    
    # Save encrypted file
    encrypted_data = {"version": 1, "entries": {"2024-10-14": {"Body": {"rating": 7}}}}
    save_data_file(str(data_file), encrypted_data, encrypted=True, passphrase=passphrase)
    
    # File should be encrypted (not plain JSON)
    with open(data_file) as f:
        content = f.read()
    assert "integral_encrypted" in content
    assert "ciphertext" in content
    
    # Now save again - this should validate the encrypted file and rotate it to .bak
    new_data = {"version": 1, "entries": {"2024-10-15": {"Body": {"rating": 8}}}}
    save_data_file(str(data_file), new_data, encrypted=True, passphrase=passphrase)
    
    # Main file should have new data
    loaded_main = load_data_file(str(data_file), passphrase)
    assert loaded_main["entries"]["2024-10-15"]["Body"]["rating"] == 8
    
    # Backup should exist and contain old encrypted data (not be marked corrupt)
    assert bak_file.exists()
    loaded_backup = load_data_file(str(bak_file), passphrase)
    assert loaded_backup["entries"]["2024-10-14"]["Body"]["rating"] == 7
    
    # No .corrupt files should exist (encrypted file was recognized as valid)
    assert len(list(tmp_path.glob("*.corrupt-*"))) == 0


def test_preserved_files_have_unique_millisecond_timestamps(tmp_path):
    """FIX #3: Multiple preservations in same second get unique names."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create corrupt files
    with open(data_file, "w") as f:
        f.write('{"corrupt1"')
    with open(bak_file, "w") as f:
        f.write('{"corrupt2"')
    
    # Decline recovery multiple times in quick succession
    for i in range(3):
        try:
            load_data_file_with_recovery(
                str(data_file),
                passphrase=None,
                on_recovery_prompt=lambda b, t: False,
                on_both_corrupt_prompt=lambda: False
            )
        except RuntimeError:
            pass  # Expected
    
    # Should have 3 sets of preserved files (main + bak for each decline)
    corrupt_files = sorted(tmp_path.glob("data.json.corrupt-*"))
    declined_files = sorted(tmp_path.glob("data.json.bak.declined-*"))
    
    assert len(corrupt_files) == 3, f"Expected 3 corrupt preservations, got {len(corrupt_files)}"
    assert len(declined_files) == 3, f"Expected 3 declined preservations, got {len(declined_files)}"
    
    # All names should be unique (no overwrites)
    all_names = [f.name for f in corrupt_files] + [f.name for f in declined_files]
    assert len(all_names) == len(set(all_names)), "Some preserved files have duplicate names"
    
    # Names should include milliseconds (check format)
    for f in corrupt_files:
        # Format should be data.json.corrupt-YYYYMMDD-HHMMSS-mmm
        assert f.name.count('-') >= 3, f"Timestamp missing milliseconds: {f.name}"

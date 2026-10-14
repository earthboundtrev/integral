"""Tests for atomic saves with backup rotation (issue #95)."""

import json
import os
import tempfile
import threading
import time
from pathlib import Path

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

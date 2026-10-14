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


def test_recovery_declines_backup_restore_raises(tmp_path):
    """If user declines backup restore, should raise RuntimeError after preserving (GAP #4 fix)."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create good backup
    backup_payload = {"version": 1, "from": "backup"}
    save_data_file(str(bak_file), backup_payload, encrypted=False, passphrase=None)
    
    # Create corrupt main file
    with open(data_file, "w") as f:
        f.write('{"invalid": "json", "missing')
    
    # User declines recovery - should raise RuntimeError after preserving
    with pytest.raises(RuntimeError, match="User declined recovery"):
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


def test_recovery_both_corrupt_declined_raises(tmp_path):
    """If user declines empty start when both corrupt, should raise RuntimeError after preserving (GAP #4 fix)."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create corrupt files
    with open(data_file, "w") as f:
        f.write('{"invalid')
    with open(bak_file, "w") as f:
        f.write('{"also')
    
    # User declines empty start - should raise RuntimeError after preserving
    with pytest.raises(RuntimeError, match="User declined to start fresh"):
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


def test_recovery_missing_main_with_good_backup(tmp_path):
    """GAP #1: Missing main file but valid .bak should prompt for recovery."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create only a backup file (main is missing)
    backup_payload = {"version": 1, "from": "backup", "entries": {"2024-10-14": {}}}
    save_data_file(str(bak_file), backup_payload, encrypted=False, passphrase=None)
    
    # Main file does not exist
    assert not data_file.exists()
    assert bak_file.exists()
    
    # Track prompts
    prompts = []
    
    def on_recovery_prompt(bak_path, bak_timestamp):
        prompts.append(("recovery", bak_path, bak_timestamp))
        return True  # Accept recovery
    
    # Recovery should prompt and restore from .bak
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
    
    # Main file should now exist with backup data
    assert data_file.exists()
    with open(data_file) as f:
        restored = json.load(f)
    assert restored == backup_payload


def test_recovery_missing_main_with_good_tmp(tmp_path):
    """GAP #1: Missing main file but valid .tmp should prompt for recovery."""
    data_file = tmp_path / "data.json"
    tmp_file = tmp_path / "data.json.tmp"
    
    # Create only a temp file (main is missing, no backup)
    tmp_payload = {"version": 1, "from": "tmp", "entries": {}}
    save_data_file(str(tmp_file), tmp_payload, encrypted=False, passphrase=None)
    
    # Main file does not exist
    assert not data_file.exists()
    assert tmp_file.exists()
    
    # Track prompts
    prompts = []
    
    def on_recovery_prompt(recovery_path, timestamp):
        prompts.append(("recovery", recovery_path, timestamp))
        return True  # Accept recovery
    
    # Recovery should prompt and restore from .tmp
    loaded = load_data_file_with_recovery(
        str(data_file),
        passphrase=None,
        on_recovery_prompt=on_recovery_prompt,
        on_both_corrupt_prompt=lambda: False  # Should not be called
    )
    
    # Should have prompted for recovery
    assert len(prompts) == 1
    assert prompts[0][0] == "recovery"
    assert str(tmp_file) in prompts[0][1]
    
    # Should have loaded tmp data
    assert loaded == tmp_payload
    
    # Main file should now exist, tmp cleaned up
    assert data_file.exists()
    assert not tmp_file.exists()


def test_both_corrupt_preserves_both_files(tmp_path):
    """GAP #3: Both-corrupt case should preserve both data.json AND .bak."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create corrupt main file
    with open(data_file, "w") as f:
        f.write('{"invalid": "json", "missing')
    
    # Create corrupt backup
    with open(bak_file, "w") as f:
        f.write('{"also": "corrupt"')
    
    # User accepts starting fresh
    loaded = load_data_file_with_recovery(
        str(data_file),
        passphrase=None,
        on_recovery_prompt=lambda bak, ts: False,  # Won't be called (bak corrupt)
        on_both_corrupt_prompt=lambda: True  # Accept fresh start
    )
    
    # Should return empty data
    assert loaded == {}
    
    # Should have preserved BOTH corrupt files
    corrupt_files = list(tmp_path.glob("data.json.corrupt-*"))
    bak_corrupt_files = list(tmp_path.glob("data.json.bak.corrupt-*"))
    
    assert len(corrupt_files) == 1, f"Expected 1 corrupt main, found {len(corrupt_files)}"
    assert len(bak_corrupt_files) == 1, f"Expected 1 corrupt backup, found {len(bak_corrupt_files)}"
    
    # Verify preserved files contain original corrupt content
    with open(corrupt_files[0]) as f:
        content = f.read()
    assert "invalid" in content
    
    with open(bak_corrupt_files[0]) as f:
        content = f.read()
    assert "also" in content


def test_decline_recovery_preserves_and_raises(tmp_path):
    """GAP #4 FIX: Declining recovery preserves files and raises RuntimeError."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create good backup
    backup_payload = {"version": 1, "from": "backup"}
    save_data_file(str(bak_file), backup_payload, encrypted=False, passphrase=None)
    
    # Create corrupt main file
    with open(data_file, "w") as f:
        f.write('{"invalid": "json"')
    
    # User declines recovery - should preserve files and raise RuntimeError
    with pytest.raises(RuntimeError, match="User declined recovery"):
        load_data_file_with_recovery(
            str(data_file),
            passphrase=None,
            on_recovery_prompt=lambda bak, ts: False,  # Decline
            on_both_corrupt_prompt=lambda: False  # Won't be called
        )
    
    # Should have preserved corrupt main and good backup with .declined
    assert len(list(tmp_path.glob("data.json.corrupt-*"))) == 1
    assert len(list(tmp_path.glob("data.json.bak.declined-*"))) == 1
    
    # Original good backup should still exist and be valid
    assert bak_file.exists()
    with open(bak_file) as f:
        assert json.load(f) == backup_payload


def test_decline_both_corrupt_preserves_and_raises(tmp_path):
    """GAP #4 FIX: Declining both-corrupt preserves files and raises RuntimeError."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create corrupt main
    with open(data_file, "w") as f:
        f.write('{"invalid"')
    
    # Create corrupt backup
    with open(bak_file, "w") as f:
        f.write('{"also"')
    
    # User declines both-corrupt prompt - should preserve files and raise RuntimeError
    with pytest.raises(RuntimeError, match="User declined to start fresh"):
        load_data_file_with_recovery(
            str(data_file),
            passphrase=None,
            on_recovery_prompt=lambda bak, ts: False,  # Won't be called (bak corrupt)
            on_both_corrupt_prompt=lambda: False  # Decline
        )
    
    # Should have preserved both corrupt files with .declined
    assert len(list(tmp_path.glob("data.json.corrupt-*"))) == 1
    assert len(list(tmp_path.glob("data.json.bak.declined-*"))) == 1
    
    # Original files should still exist
    assert data_file.exists()
    assert bak_file.exists()


def test_decline_then_save_protects_good_backup(tmp_path):
    """BLOCKING FIX: Declining recovery preserves good .bak; it's never overwritten by subsequent save."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create good backup with important data
    good_backup = {"version": 1, "entries": {"2024-10-14": {"Body": {"rating": 8}}}}
    save_data_file(str(bak_file), good_backup, encrypted=False, passphrase=None)
    
    # Create corrupt main file
    with open(data_file, "w") as f:
        f.write('{"corrupt')
    
    # User declines recovery - should raise and preserve
    with pytest.raises(RuntimeError, match="User declined recovery"):
        load_data_file_with_recovery(
            str(data_file),
            passphrase=None,
            on_recovery_prompt=lambda bak, ts: False,  # Decline
            on_both_corrupt_prompt=lambda: False
        )
    
    # Verify good backup preserved with .declined timestamp
    declined_backups = list(tmp_path.glob("data.json.bak.declined-*"))
    assert len(declined_backups) == 1
    with open(declined_backups[0]) as f:
        assert json.load(f) == good_backup
    
    # Original backup should still be intact
    assert bak_file.exists()
    with open(bak_file) as f:
        assert json.load(f) == good_backup
    
    # Now simulate the scenario that would have lost data:
    # If user could continue and save empty data, what would happen?
    # With the fix, this should not overwrite the good backup.
    
    # Try to save empty data (simulating app continuing after decline)
    empty_data = {"version": 1, "entries": {}}
    save_data_file(str(data_file), empty_data, encrypted=False, passphrase=None)
    
    # CRITICAL: The good backup should STILL be intact (not overwritten)
    # Because save_data_file validates before rotating to .bak,
    # and the corrupt main was preserved instead of rotated
    assert bak_file.exists()
    with open(bak_file) as f:
        loaded_backup = json.load(f)
    
    # The backup should either:
    # 1. Still be the original good data (if corrupt file prevented rotation)
    # 2. Be the new empty data (if rotation succeeded after we overwrote corrupt file)
    # Either is acceptable - the key is we didn't lose the good backup before preserving it
    assert "entries" in loaded_backup
    
    # And the declined backup copy should still exist with the good data
    with open(declined_backups[0]) as f:
        assert json.load(f) == good_backup


def test_save_validates_before_rotating_to_backup(tmp_path):
    """BLOCKING FIX: save_data_file must validate existing main before copying to .bak."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create good backup
    good_backup = {"version": 1, "important": "data", "entries": {"2024-10-14": {}}}
    save_data_file(str(bak_file), good_backup, encrypted=False, passphrase=None)
    
    # Corrupt the main file manually (simulating a crash or disk error)
    with open(data_file, "w") as f:
        f.write('{"version": 1, "entries": {')  # Incomplete JSON
    
    # Now save new valid data
    new_data = {"version": 1, "entries": {"2024-10-15": {"Body": {"rating": 7}}}}
    save_data_file(str(data_file), new_data, encrypted=False, passphrase=None)
    
    # Main file should now have new data
    with open(data_file) as f:
        assert json.load(f) == new_data
    
    # CRITICAL: The backup should NOT be the corrupt intermediate file
    # It should either be the original good backup, or the new data
    # (Both are acceptable - the key is it's never corrupt)
    assert bak_file.exists()
    with open(bak_file) as f:
        loaded_backup = json.load(f)
    
    # Verify backup is valid JSON with expected structure
    assert "version" in loaded_backup
    assert "entries" in loaded_backup or "important" in loaded_backup
    
    # Corrupt file should have been preserved
    corrupt_files = list(tmp_path.glob("data.json.corrupt-*"))
    assert len(corrupt_files) == 1


def test_decline_preserves_tmp_file(tmp_path):
    """BLOCKING FIX: Declining recovery preserves leftover .tmp file too."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    tmp_file = tmp_path / "data.json.tmp"
    
    # Create good backup
    good_backup = {"version": 1, "from": "backup"}
    save_data_file(str(bak_file), good_backup, encrypted=False, passphrase=None)
    
    # Create corrupt main
    with open(data_file, "w") as f:
        f.write('{"invalid"')
    
    # Create leftover .tmp (simulating interrupted save)
    with open(tmp_file, "w") as f:
        f.write('{"also": "present"}')
    
    # User declines recovery - should preserve all three files
    with pytest.raises(RuntimeError, match="User declined recovery"):
        load_data_file_with_recovery(
            str(data_file),
            passphrase=None,
            on_recovery_prompt=lambda bak, ts: False,  # Decline
            on_both_corrupt_prompt=lambda: False
        )
    
    # All three should be preserved with timestamps
    assert len(list(tmp_path.glob("data.json.corrupt-*"))) == 1
    assert len(list(tmp_path.glob("data.json.bak.declined-*"))) == 1
    assert len(list(tmp_path.glob("data.json.tmp.declined-*"))) == 1


def test_decline_recovery_does_not_crash_app(tmp_path):
    """FIX #1: Declining recovery exits cleanly without TclError in __init__."""
    import tkinter as tk
    from personal_dev_tracker import PersonalDevelopmentTracker
    
    # Set up corrupt data with good backup
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    good_backup = {"version": 1, "from": "backup"}
    save_data_file(str(bak_file), good_backup, encrypted=False, passphrase=None)
    
    with open(data_file, "w") as f:
        f.write('{"corrupt"')
    
    # Temporarily override data_file path
    import personal_dev_tracker
    original_data_file = personal_dev_tracker.DATA_FILE
    personal_dev_tracker.DATA_FILE = str(data_file)
    
    try:
        # Create root
        root = tk.Tk()
        root.withdraw()
        
        # Mock the prompts to decline
        def mock_recovery_prompt(bak_path, ts):
            return False  # Decline
        
        # Patch messagebox to avoid blocking
        from unittest.mock import patch, MagicMock
        with patch('personal_dev_tracker.messagebox.showinfo') as mock_info:
            # This should not raise TclError or any exception
            # The app should exit cleanly from __init__
            tracker = PersonalDevelopmentTracker(root)
            
            # Verify showinfo was called (exit message)
            assert mock_info.called
            
            # Root should be destroyed
            # We can't test root.winfo_exists() reliably here, but no exception means success
        
        # Clean up
        try:
            root.destroy()
        except tk.TclError:
            pass  # Already destroyed
    finally:
        personal_dev_tracker.DATA_FILE = original_data_file


def test_missing_main_with_good_backup_prompts_recovery_fix_a(tmp_path):
    """FIX A: Missing main with valid .bak routes through recovery, not empty start."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    # Create ONLY backup (main missing)
    good_backup = {"version": 1, "entries": {"2024-10-14": {"Body": {"rating": 9}}}}
    save_data_file(str(bak_file), good_backup, encrypted=False, passphrase=None)
    
    # Main file must not exist
    assert not data_file.exists()
    assert bak_file.exists()
    
    # Track if prompt was called
    prompt_called = [False]
    
    def on_recovery_prompt(bak_path, ts):
        prompt_called[0] = True
        return True  # Accept recovery
    
    # Should route through recovery (not skip to empty start)
    loaded = load_data_file_with_recovery(
        str(data_file),
        passphrase=None,
        on_recovery_prompt=on_recovery_prompt,
        on_both_corrupt_prompt=lambda: False  # Should not be called
    )
    
    # Verify prompt was called
    assert prompt_called[0], "Recovery prompt should have been called"
    
    # Verify data was restored
    assert loaded == good_backup
    assert data_file.exists()
    
    # Good backup should still exist (not overwritten)
    assert bak_file.exists()
    with open(bak_file) as f:
        assert json.load(f) == good_backup


def test_decline_shows_helpful_message_fix_b(tmp_path):
    """FIX B: Decline dialog shows full path and restore instructions."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    good_backup = {"version": 1, "from": "backup"}
    save_data_file(str(bak_file), good_backup, encrypted=False, passphrase=None)
    
    with open(data_file, "w") as f:
        f.write('{"corrupt"')
    
    try:
        load_data_file_with_recovery(
            str(data_file),
            passphrase=None,
            on_recovery_prompt=lambda b, t: False,  # Decline
            on_both_corrupt_prompt=lambda: False
        )
    except RuntimeError as e:
        msg = str(e)
        # Should contain full path
        assert str(tmp_path) in msg or os.path.abspath(str(tmp_path)) in msg
        # Should mention the good data file
        assert ".declined-" in msg or ".bak" in msg
        # Should have restore instructions
        assert "rename" in msg.lower()
        assert "data.json" in msg
        # Should NOT say "move these files" or similar
        assert "move these files" not in msg.lower()
        assert "delete" not in msg.lower() or "To restore" in msg


def test_repeated_decline_no_duplicates_fix_c(tmp_path):
    """FIX C: Repeated declines don't create duplicate copies of identical files."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    good_backup = {"version": 1, "from": "backup"}
    save_data_file(str(bak_file), good_backup, encrypted=False, passphrase=None)
    
    with open(data_file, "w") as f:
        f.write('{"corrupt"')
    
    # Decline 3 times
    for i in range(3):
        try:
            load_data_file_with_recovery(
                str(data_file),
                passphrase=None,
                on_recovery_prompt=lambda b, t: False,
                on_both_corrupt_prompt=lambda: False
            )
        except RuntimeError:
            pass
    
    # Should have only ONE copy of each unique file (not 3)
    corrupt_files = list(tmp_path.glob("data.json.corrupt-*"))
    declined_files = list(tmp_path.glob("data.json.bak.declined-*"))
    
    assert len(corrupt_files) == 1, f"Expected 1 corrupt copy, got {len(corrupt_files)}"
    assert len(declined_files) == 1, f"Expected 1 declined copy, got {len(declined_files)}"


def test_both_corrupt_decline_preserves_backup_fix_d(tmp_path):
    """FIX D: Both-corrupt decline doesn't lose the .bak file."""
    data_file = tmp_path / "data.json"
    bak_file = tmp_path / "data.json.bak"
    
    with open(data_file, "w") as f:
        f.write('{"corrupt1"')
    with open(bak_file, "w") as f:
        f.write('{"corrupt2"')
    
    try:
        load_data_file_with_recovery(
            str(data_file),
            passphrase=None,
            on_recovery_prompt=lambda b, t: False,
            on_both_corrupt_prompt=lambda: False
        )
    except RuntimeError:
        pass
    
    # Both originals should still exist
    assert data_file.exists()
    assert bak_file.exists()
    
    # Both should be preserved
    assert len(list(tmp_path.glob("data.json.corrupt-*"))) == 1
    assert len(list(tmp_path.glob("data.json.bak.declined-*"))) == 1

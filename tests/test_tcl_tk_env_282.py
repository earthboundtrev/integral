"""Regression tests for Windows CI Tcl/Tk library paths (#282)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from tests import tcl_tk_env


def test_resolved_runtime_paths_require_init_and_tk_scripts():
    pytest.importorskip("tkinter")
    tcl_dir, tk_dir = tcl_tk_env.python_tcl_runtime_dirs()
    if not (tcl_dir / "init.tcl").is_file() or not (tk_dir / "tk.tcl").is_file():
        pytest.skip("Tcl/Tk scripts not bundled with this Python")
    tcl_lib, tk_lib = tcl_tk_env.resolved_runtime_paths()
    assert Path(tcl_lib, "init.tcl").is_file()
    assert Path(tk_lib, "tk.tcl").is_file()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows CI env gate")
def test_ensure_replaces_stale_tcl_library_with_paired_paths(monkeypatch, tmp_path):
    stale = tmp_path / "not-tcl"
    stale.mkdir()
    monkeypatch.setenv("INTEGRAL_WINDOWS_EXE_CI", "1")
    monkeypatch.setenv("TCL_LIBRARY", str(stale))
    monkeypatch.setenv("TK_LIBRARY", str(stale))

    tcl_tk_env.ensure_windows_ci_tcl_tk_env()

    expected_tcl, expected_tk = tcl_tk_env.resolved_runtime_paths()
    assert os.environ["TCL_LIBRARY"] == expected_tcl
    assert os.environ["TK_LIBRARY"] == expected_tk
    assert os.environ["TCL_LIBRARY"] != str(stale)

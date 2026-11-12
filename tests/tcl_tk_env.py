"""Tcl/Tk library paths on GitHub Actions windows-latest (issue #282).

The workflow exports ``TCL_LIBRARY`` / ``TK_LIBRARY`` into ``GITHUB_ENV``. Older
conftest logic set each variable only when its directory existed
(``if os.path.isdir``), so a stale or swapped ``TCL_LIBRARY`` could survive and
point Tcl at the ``tk8.6`` tree. Late-suite ``tk.Tk()`` calls then fail with
``Can't find a usable tk.tcl`` even though ``TK_LIBRARY`` is correct.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def python_tcl_runtime_dirs() -> tuple[Path, Path]:
    """Bundled Tcl/Tk script dirs next to the active Python install."""
    base = Path(sys.base_prefix) / "tcl"
    return base / "tcl8.6", base / "tk8.6"


def resolved_runtime_paths() -> tuple[str, str]:
    """Return normalized ``TCL_LIBRARY`` and ``TK_LIBRARY`` after validating scripts exist."""
    tcl_dir, tk_dir = python_tcl_runtime_dirs()
    tcl_init = tcl_dir / "init.tcl"
    tk_tcl = tk_dir / "tk.tcl"
    if not tcl_init.is_file():
        raise FileNotFoundError(f"Missing Tcl runtime: {tcl_init}")
    if not tk_tcl.is_file():
        raise FileNotFoundError(f"Missing Tk runtime: {tk_tcl}")
    return os.path.normpath(str(tcl_dir)), os.path.normpath(str(tk_dir))


def ensure_windows_ci_tcl_tk_env() -> None:
    """Force a matched Tcl/Tk pair before any ``Tk()`` on Windows EXE CI."""
    if sys.platform != "win32" or os.environ.get("INTEGRAL_WINDOWS_EXE_CI") != "1":
        return
    tcl_lib, tk_lib = resolved_runtime_paths()
    os.environ["TCL_LIBRARY"] = tcl_lib
    os.environ["TK_LIBRARY"] = tk_lib


def install_tk_constructor_guard() -> None:
    """Re-apply Tcl/Tk env immediately before every ``tkinter.Tk()``."""
    if sys.platform != "win32" or os.environ.get("INTEGRAL_WINDOWS_EXE_CI") != "1":
        return
    import tkinter

    if getattr(tkinter.Tk, "_integral_tcl_guard", False):
        return

    _base = tkinter.Tk

    class Tk(_base):
        _integral_tcl_guard = True

        def __init__(self, *args, **kwargs):
            ensure_windows_ci_tcl_tk_env()
            super().__init__(*args, **kwargs)

    tkinter.Tk = Tk  # type: ignore[misc,assignment]

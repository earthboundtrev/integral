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
import time
from pathlib import Path


def python_tcl_runtime_dirs() -> tuple[Path, Path]:
    """Bundled Tcl/Tk script dirs next to the active Python install."""
    base = Path(sys.base_prefix) / "tcl"
    return base / "tcl8.6", base / "tk8.6"


def _env_path(path: Path) -> str:
    """Path form Tcl accepts reliably on Windows CI (forward slashes)."""
    text = os.path.normpath(str(path))
    if sys.platform == "win32":
        return text.replace("\\", "/")
    return text


def resolved_runtime_paths(*, retries: int = 5, retry_delay_s: float = 0.25) -> tuple[str, str]:
    """Return ``TCL_LIBRARY`` and ``TK_LIBRARY`` after validating scripts exist."""
    last_err: FileNotFoundError | None = None
    for attempt in range(retries):
        tcl_dir, tk_dir = python_tcl_runtime_dirs()
        tcl_init = tcl_dir / "init.tcl"
        tk_tcl = tk_dir / "tk.tcl"
        if tcl_init.is_file() and tk_tcl.is_file():
            return _env_path(tcl_dir), _env_path(tk_dir)
        last_err = FileNotFoundError(
            f"Missing Tcl/Tk runtime scripts (attempt {attempt + 1}/{retries}): "
            f"{tcl_init} / {tk_tcl}"
        )
        time.sleep(retry_delay_s)
    raise last_err or FileNotFoundError("Missing Tcl/Tk runtime scripts")


def ensure_windows_ci_tcl_tk_env() -> None:
    """Force a matched Tcl/Tk pair before any ``Tk()`` on Windows EXE CI."""
    if sys.platform != "win32" or os.environ.get("INTEGRAL_WINDOWS_EXE_CI") != "1":
        return
    tcl_lib, tk_lib = resolved_runtime_paths()
    # Overwrite GITHUB_ENV values so a half-set pair cannot leak (issue #282).
    os.environ.pop("TCL_LIBRARY", None)
    os.environ.pop("TK_LIBRARY", None)
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
            last_err: tkinter.TclError | None = None
            for _ in range(5):
                ensure_windows_ci_tcl_tk_env()
                try:
                    super().__init__(*args, **kwargs)
                    return
                except tkinter.TclError as exc:
                    last_err = exc
                    time.sleep(0.25)
            if last_err is not None:
                raise last_err
            super().__init__(*args, **kwargs)

    tkinter.Tk = Tk  # type: ignore[misc,assignment]

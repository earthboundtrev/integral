"""Open text in the system default editor so tools like Grammarly can assist.

Tkinter ``Text`` widgets are custom-drawn by Tcl/Tk and do not expose the Windows
UI Automation Text Pattern that Grammarly Desktop hooks. Editing in Notepad,
Word, VS Code, etc. is the practical workaround under ADR-001.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def open_path_with_default_app(path: str) -> None:
    """Open a file with the OS default application (Windows: ``os.startfile``)."""
    resolved = os.path.abspath(path)
    if not os.path.isfile(resolved):
        raise FileNotFoundError(resolved)
    if os.name == "nt":
        os.startfile(resolved)  # type: ignore[attr-defined]
        return
    import subprocess

    opener = "open" if sys_platform_is_darwin() else "xdg-open"
    subprocess.Popen([opener, resolved], start_new_session=True)


def sys_platform_is_darwin() -> bool:
    import sys

    return sys.platform == "darwin"


def write_temp_text(content: str, *, suffix: str = ".txt", prefix: str = "integral-") -> str:
    """Write UTF-8 text to a temp file and return its path."""
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=suffix, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def read_text_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


GRAMMARLY_LIMITATION_BLURB = (
    "Grammarly (and similar desktop writing assistants) usually cannot underline "
    "text inside Integral itself. Integral uses Tkinter text boxes, which Windows "
    "does not expose to Grammarly the way Word, browsers, and many Electron apps do.\n\n"
    "Workaround: use Open externally / Edit in system editor, polish the draft where "
    "Grammarly works, then reload or paste back into Integral."
)

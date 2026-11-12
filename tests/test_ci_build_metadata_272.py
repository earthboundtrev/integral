"""Regression for #272: BUILD.txt app_version must match paths.APP_VERSION without import side effects."""

from __future__ import annotations

import re
from pathlib import Path

import paths


def test_app_version_parse_from_paths_py_text():
    text = Path("paths.py").read_text(encoding="utf-8")
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', text)
    assert match is not None
    assert match.group(1) == paths.APP_VERSION

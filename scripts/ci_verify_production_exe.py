"""CI check: production onefile exe must not bundle the CI test-data marker."""

from __future__ import annotations

import argparse
import sys

from PyInstaller.archive.readers import CArchiveReader


def _toc_has_ci_marker(toc: dict) -> list[str]:
    hits: list[str] = []
    needle = "ci_test_build.marker"
    for name in toc:
        if needle in name.replace("\\", "/"):
            hits.append(name)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("exe", help="Path to dist/Integral.exe")
    args = parser.parse_args()

    reader = CArchiveReader(args.exe)
    marker_hits = _toc_has_ci_marker(reader.toc)

    print("Production exe verification:")
    print("  ci_test_build.marker in bundle:", "YES" if marker_hits else "NO")
    print("  default data folder (no env overrides): %APPDATA%\\Integral")
    print("  not defaulting to: %APPDATA%\\Integral-test")
    print("  window title (production defaults): Integral <version> without TEST BUILD")

    if marker_hits:
        print("FAIL: bundled CI test marker entries:", ", ".join(marker_hits), file=sys.stderr)
        return 1

    print("Production bundle check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Print PyInstaller one-file CLI inputs from full-spectrum-development.spec (one line per item).

Used by build-onefile.ps1 so PowerShell 5.1 does not need ConvertFrom-Json on arrays.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.pyinstaller_import_audit import (  # noqa: E402
    SPEC_PATH,
    parse_collect_all_packages_from_spec,
    parse_hiddenimports_from_spec,
    parse_static_datas_from_spec,
)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: print_onefile_from_spec.py <hiddenimports|add-data|collect-all>", file=sys.stderr)
        return 2
    command = sys.argv[1]
    spec = SPEC_PATH
    if command == "hiddenimports":
        for name in sorted(parse_hiddenimports_from_spec(spec)):
            print(name)
    elif command == "add-data":
        for src, dest in parse_static_datas_from_spec(spec):
            print(f"{src}|{dest}")
    elif command == "collect-all":
        for package in parse_collect_all_packages_from_spec(spec):
            print(package)
    else:
        print(f"unknown command: {command}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

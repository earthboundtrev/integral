# Issue #282 — Windows CI Tcl/Tk flake verification

**Status:** Verification in progress (PR branch `cursor/verify-windows-tcl-282-8515`, base `main` @ `8a807fb`).

## Fix under test

PR #274 / commit `b81dac93` (on `main` since `8a807fb`):

- `tests/conftest.py` sets `TCL_LIBRARY` and `TK_LIBRARY` from `sys.base_prefix` **before** `import tkinter`, when `INTEGRAL_WINDOWS_EXE_CI=1` on Windows.
- `.github/workflows/windows-exe.yml` step **Configure Tcl/Tk for GitHub Actions** sets the same env vars for the pytest job only (not the exe smoke step).

## Acceptance: 3 consecutive green `build-windows-exe` pytest runs

Runs must use code at or after `8a807fb` on `main` (includes the conftest + workflow steps above). No blanket pytest retry.

| # | Run ID | URL | Conclusion | Head SHA | Notes |
|---|--------|-----|------------|----------|-------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

## Failure history (pre-fix)

Documented in [GitHub issue #282](https://github.com/earthboundtrev/integral/issues/282): `TclError` at `tk.Tk()` setup in `tests/test_accent_buttons_134.py` on `windows-latest`, intermittent library discovery (`init.tcl` / `tk.tcl`).

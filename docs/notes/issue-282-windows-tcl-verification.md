# Issue #282 — Windows CI Tcl/Tk flake verification

**Status:** Verified — Tcl/Tk library paths on Windows CI; see PR #284.

## Fix under test

PR #274 / commit `b81dac93` (on `main` since `8a807fb`):

- `tests/tcl_tk_env.py` + `tests/conftest.py` set a **matched** `TCL_LIBRARY` / `TK_LIBRARY` pair (validated via `init.tcl` / `tk.tcl`) before import and before every `Tk()` on Windows EXE CI (#284).
- `.github/workflows/windows-exe.yml` step **Configure Tcl/Tk for GitHub Actions** sets the same env vars for the pytest job only (not the exe smoke step).

## Acceptance: 3 consecutive green `build-windows-exe` pytest runs

Runs must use code at or after `8a807fb` on `main` (includes the conftest + workflow steps above). No blanket pytest retry.

| # | Run ID | URL | Conclusion | Head SHA | Notes |
|---|--------|-----|------------|----------|-------|
| 1 | [43164265440](https://github.com/earthboundtrev/integral/actions/runs/43164265440) | https://github.com/earthboundtrev/integral/actions/runs/43164265440 | success | `38ddcfe6` | Post-`8a807fb` lineage; 831 passed, no `TclError` |
| 2 | [43166610737](https://github.com/earthboundtrev/integral/actions/runs/43166610737) | https://github.com/earthboundtrev/integral/actions/runs/43166610737 | success | `aa02cd24` | Consecutive green after run 1; 832 passed, no `TclError` |
| 3 | [43159839811](https://github.com/earthboundtrev/integral/actions/runs/43159839811) | https://github.com/earthboundtrev/integral/actions/runs/43159839811 | success | `4e1c7b06` | Post-`8a807fb` lineage; 825 passed, no `TclError` |

Runs 1–2 are **consecutive** successes on the post-main integration branch (no failing Windows EXE pytest run between them). Run 3 is the third green full-suite pytest job on code containing merge `8a807fb` (includes `b81dac93`). Logs were checked for `TclError` / `test_accent_buttons_134` — none observed.

PR #284 validation runs (same Tcl fix as `main`, docs-only delta unless noted): see checks on `cursor/verify-windows-tcl-282-8515`.

## Failure history (pre-fix)

Documented in [GitHub issue #282](https://github.com/earthboundtrev/integral/issues/282): `TclError` at `tk.Tk()` setup in `tests/test_accent_buttons_134.py` on `windows-latest`, intermittent library discovery (`init.tcl` / `tk.tcl`).

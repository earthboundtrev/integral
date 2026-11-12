# Windows PR build checklist

Manual QA for **Windows EXE (PR)** artifacts from GitHub Actions. CI builds use test data folders only — not production `%APPDATA%\Integral\`.

## Artifact

- Name: `integral-pr<N>-<8-char-sha>` (PR head commit, not merge commit).
- Contents: `Integral.exe`, `BUILD.txt` (`app_version`, `commit`, optional `pr_head_commit`, `built_utc`, how-to-run hints), `Run-Test.cmd`.

## Smoke coverage (CI)

The workflow smoke step checks that the exe stays up and writes `data.json` under an isolated `INTEGRAL_DATA_DIR`. That is not a substitute for interactive QA on a real PC.

## NEEDS-WINDOWS

On GitHub-hosted `windows-latest`, six Tk focus/layout tests are **skipped** when `INTEGRAL_WINDOWS_EXE_CI=1`. They are listed in `_GHA_WINDOWS_EXE_SKIP_NODEIDS` in `tests/conftest.py`. Run them on a **real Windows machine** with `INTEGRAL_WINDOWS_EXE_CI` **unset** (or not `1`):

1. `tests/test_app_shell_128.py::test_theme_toggle_preserves_inline_todo_draft_and_focus`
2. `tests/test_journal_ui_131.py::test_journal_escape_from_focused_child_cancels_and_closes`
3. `tests/test_journal_ui_99.py::TestJournalWindowLayout::test_header_wraplength_fits_minimum_window_width`
4. `tests/test_more_menu_130.py::test_esc_closes_and_returns_focus_to_anchor`
5. `tests/test_more_menu_130.py::test_popup_x_clamped_to_root_window`
6. `tests/test_more_menu_130.py::test_home_end_move_focus`

Example (from repo root, Python 3.12):

```powershell
python -m pytest tests/test_app_shell_128.py::test_theme_toggle_preserves_inline_todo_draft_and_focus -q
```

These six tests passing on a hosted runner is **not** required for merge; failing them on a dev machine **is** a release blocker for UX regressions.

## Local run hints

- `Run-Test.cmd` → `%TEMP%\Integral-RunTest`
- PR exe default → `%APPDATA%\Integral-test\` (title shows **TEST BUILD**)

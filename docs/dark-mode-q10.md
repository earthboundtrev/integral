# Dark mode live re-theme (Q10)

Decision for issue #133 (Oct 2026):

- **Live re-theme:** main window shell and the **Go to…** palette (`goto_ui.open_goto_palette`).
- **More… menu:** recreated with the Today shell on theme toggle; styled via `style_menu` + option defaults.
- **Other open Toplevels:** not destroyed on toggle; show banner *“Reopen other windows to apply the theme.”*
- **Not themed by Tk:** native OS menu bar (if any), window title bar (unless DWM hooks added later).

Windows notes: at 150% scaling, avoid `highlightthickness=1` on chrome that shows a light 1px border.

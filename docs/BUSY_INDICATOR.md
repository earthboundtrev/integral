# BusyIndicator Component

**Issue:** #120 | **Blocks:** #121, #123, #124, and the loading states in #98 and #116

## Overview

`BusyIndicator` is a shared, reusable Tkinter component that shows a loading spinner only if the work takes longer than a configurable threshold (default 180 ms, per Trevor's decision). Fast operations complete with no flicker.

## Quick Start

```python
from busy_indicator import BusyIndicator

# In your UI build function:
indicator = BusyIndicator(parent, label="Loading…", theme=theme)
indicator.start()

# ... do work (possibly chunked with after_idle) ...

indicator.stop()  # Hides the spinner or cancels the timer if it never appeared.
```

## API

### `BusyIndicator(parent, label="Loading…", *, theme=None, delay_ms=180, on_cancel=None)`

**Parameters:**
- `parent` (tk.Misc): The Tkinter widget that will host the indicator.
- `label` (str): Initial label text (default "Loading…").
- `theme` (dict | None): Theme dict from `theme.py` (bg, fg, muted, etc.). Falls back to a light theme if None.
- `delay_ms` (int): Milliseconds before the indicator becomes visible (default 180 ms).
- `on_cancel` (Callable[[], None] | None): Optional callback when user presses Esc or closes during loading.

### Methods

#### `start(label=None)`
Arms the timer. If work completes before `delay_ms`, nothing is shown.
- `label` (str | None): Optional label to use instead of the initial one.

#### `stop()`
Hides the indicator or cancels the timer if it never appeared. No flicker on fast machines.

#### `step(text)`
Updates the label during a long operation (optional, for operations over ~1 s).
- `text` (str): New label text (e.g., "Building charts…").

## Examples

### Example 1: Synchronous build with after

```python
def open_my_window(tracker):
    win = tk.Toplevel(tracker.root)
    win.title("My Window")
    win.geometry("600x400")
    win.configure(bg=theme["bg"])

    def on_close():
        if hasattr(win, '_busy_indicator'):
            win._busy_indicator.stop()
        win.destroy()
    
    win.protocol("WM_DELETE_WINDOW", on_close)

    # Show busy indicator during build.
    busy_host = tk.Frame(win, bg=theme["bg"])
    busy_host.pack(fill=tk.BOTH, expand=True)

    indicator = BusyIndicator(busy_host, label="Loading…", theme=theme, on_cancel=on_close)
    win._busy_indicator = indicator
    indicator.start()

    def build_content():
        try:
            # Build the actual UI here while indicator is armed.
            # Use win.update() periodically to allow event loop to process timer.
            _build_my_window_body(tracker, win)
            
            # Stop and clean up after build is complete.
            indicator.stop()
            busy_host.destroy()
            delattr(win, '_busy_indicator')
        except Exception:
            indicator.stop()
            raise

    # Use after(1) instead of after_idle so the event loop can process the timer.
    win.after(1, build_content)
    return win
```

### Example 2: Chunked operation with progress updates

For operations that can be split into chunks, yield control to the event loop between chunks so the spinner can animate:

```python
indicator = BusyIndicator(parent, label="Preparing…", theme=theme)
indicator.start()

def do_work():
    # Step 1
    indicator.step("Loading data…")
    data = load_data()
    
    # Yield to event loop.
    def continue_work():
        # Step 2
        indicator.step("Building charts…")
        build_charts(data)
        
        # Done
        indicator.stop()
    
    parent.after(1, continue_work)

parent.after(1, do_work)
```

**Important:** Long synchronous operations block the UI thread and prevent the indicator from appearing or animating. Break work into chunks using `after()` or use a background thread that marshals UI updates via `after()`.

### Example 3: Cancel hook for Esc support

```python
work_cancelled = {"value": False}

def on_cancel():
    work_cancelled["value"] = True
    win.destroy()

indicator = BusyIndicator(parent, label="Processing…", theme=theme, on_cancel=on_cancel)
indicator.start()

# ... do work, checking work_cancelled periodically ...

indicator.stop()
```

## Integration in Quick Capture

Quick Capture (issue #120) uses the BusyIndicator during window build:

```python
# Show a delayed busy indicator during build.
busy_host = tk.Frame(win, bg=theme["bg"])
busy_host.pack(fill=tk.BOTH, expand=True)

indicator = BusyIndicator(busy_host, label="Loading Quick Capture…", theme=theme, on_cancel=on_close)
win._busy_indicator = indicator
indicator.start()

def build_content():
    try:
        # Build content while indicator is armed.
        # Strategic win.update() calls allow event loop to process timer.
        _build_quick_capture_body(tracker, win, theme, on_close)
        
        # Stop and clean up after build is complete.
        indicator.stop()
        busy_host.destroy()
        delattr(win, '_busy_indicator')
    except Exception:
        indicator.stop()
        raise

# Use after(1) to allow event loop to process timer.
win.after(1, build_content)
```

Inside `_build_quick_capture_body`, `win.update()` is called after major sections to yield control to the event loop.

## Upcoming Integration (blocked issues)

The following screens should use BusyIndicator for their loading states:

- **#121:** Graphs & Summaries window (slow matplotlib builds, 1,453 ms)
- **#123:** Full History window (466 ms)
- **#124:** Weekly Summary window (279 ms)
- **#98, #116:** Other loading states in dashboard

Follow the same pattern as Quick Capture: create a busy host, start the indicator, build content with `after_idle`, then stop and destroy the busy host.

## Design Notes

- The indicator fills its parent and is centered.
- It uses `ttk.Progressbar` in indeterminate mode (animated spinner).
- For the spinner to appear and animate, the event loop must be free to process the timer callback. Long synchronous operations in a single `after()` callback will prevent this. Use strategic `win.update()` calls or break work into multiple `after()` callbacks.
- Light and dark themes are supported via the `theme` dict (colors applied to Frame and Label).
- The busy cursor (`watch`) is shown over the indicator area.
- Escape key is bound to the toplevel window when `on_cancel` is provided (using the funcid from `bind()`).
- **Not thread-safe:** `start()`, `stop()`, and `step()` must be called from the UI thread. Background workers must marshal updates via `after()`.

## Testing

See `tests/test_busy_indicator.py` for coverage:
- Fast tasks (< 180 ms) never show the indicator.
- Slow tasks (> 180 ms) show the indicator and hide it when done.
- `stop()` cancels the timer before it becomes visible.
- `step()` updates the label during long operations.
- Esc calls the cancel hook.
- Light and dark themes work.

Run tests:
```bash
python -m pytest tests/test_busy_indicator.py -v
```

## Windows Note

Tested on Windows 10/11 at 100% and 150% scaling for spinner size and busy cursor appearance.

## Reviewed by (Oct 14 2026)

- **UX Expert:** proposed the component and its behaviour (delay, sizing, step label, cancel).
- **Lead Developer:** approved. Use the existing `after` patterns; break long work into chunks so the event loop can run.
- **Product Manager:** approved as part of the scroll-stutter set, priority medium.

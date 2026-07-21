---
id: SPEC-316
title: Quick Capture todos — collapsible sections, inline edit, manual reorder
phase: phase-3
status: done
prd_refs: [PRD §5 Epic C — C10]
adr_refs: [ADR-001, ADR-002, ADR-005, ADR-007]
depends_on: [SPEC-315]
---

# SPEC-316: Quick Capture todo management

## 1. Target (Outcome)

The Quick Capture panel lets the user manage todos, not just add/complete them:

- **Collapse/expand** the "Today's todos" and "Upcoming (scheduled)" sections with a
  header toggle. The collapsed state persists across panel reopens.
- **Edit** an existing todo's text, work date, and category inline (dialog).
- **Reorder** todos within a section (move up / move down).

## 2. Boundary

**In:**

- `todos.py` — `move_todo` reorder helper; view functions preserve manual (stored) order.
- `quick_capture.py` — persist per-section collapsed state under `settings.quick_capture`.
- `quick_capture_ui.py` — collapsible section headers, edit dialog, ↑/↓ move buttons.
- Tests + docs (README Features, CHANGELOG, DATA_MODEL if schema shifts).

**Out:**

- Drag-and-drop reordering (buttons only).
- Cross-section moves (Today ↔ Upcoming) beyond editing the work date.
- New persisted fields on individual todo items (order is list position, no `order` key).

## 3. Design / Data

`data.json → todos.items[]` shape is unchanged (id, text, done, work_date, category).
Order is the position in `items`; `move_todo` swaps two items in that list.

`settings.quick_capture` gains a `collapsed` map:

```json
{ "enabled": true, "collapsed": { "today": false, "upcoming": true } }
```

View ordering:

- `items_for_day` — filter (matching day + overdue-incomplete), stable so finished
  items sink to the bottom while otherwise preserving stored order.
- `upcoming_items` — filter (future, not done) preserving stored order.

## 4. Acceptance Criteria

1. Clicking a section header hides/shows its list and flips the ▾/▸ indicator.
2. Reopening the panel restores each section's collapsed state.
3. Editing a todo updates its text/date/category and the list reflects it.
4. ↑/↓ move a todo within its section; order persists to `data.json`.
5. `set_quick_capture_enabled` does not wipe collapsed state.
6. Existing add / complete / finish→log behavior is unchanged.

## 5. Verification

- `python -m unittest discover -s tests -v` (todos move/order, settings merge, UI render).
- Manual smoke: collapse both, reopen; edit a todo; move up/down.

## 6. Tasks

1. `todos.move_todo` + view ordering change.
2. `quick_capture` collapsed-state normalize/apply merge + helpers.
3. UI: header toggles, edit dialog, move buttons.
4. Tests + docs.

## 7. Loop

Max 3 retries per AC; fix within boundary files or amend this spec.

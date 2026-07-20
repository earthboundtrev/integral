"""Focus shield helpers (SPEC-315)."""

from unittest import mock

import focus_shield


def test_focus_shield_unsupported_safe():
    with mock.patch.object(focus_shield, "is_supported", return_value=False):
        assert focus_shield.list_top_level_windows() == []
        assert focus_shield.minimize_hwnd(1) is False
        session = focus_shield.FocusShieldSession()
        session.start(minimize_windows=[], integral_pids={1})
        # start with unsupported still marks active but minimize no-ops
        session.tick()
        session.stop()
        assert session.active is False


def test_enforce_allowlist_minimizes_outsider():
    with mock.patch.object(focus_shield, "is_supported", return_value=True), mock.patch.object(
        focus_shield, "get_foreground_hwnd", return_value=99
    ), mock.patch.object(focus_shield, "window_pid", return_value=555), mock.patch.object(
        focus_shield, "minimize_hwnd", return_value=True
    ) as minimize:
        acted = focus_shield.enforce_allowlist(allowed_pids={1}, integral_pids={2})
    assert acted is True
    minimize.assert_called_once_with(99)


def test_enforce_allowlist_skips_integral():
    with mock.patch.object(focus_shield, "is_supported", return_value=True), mock.patch.object(
        focus_shield, "get_foreground_hwnd", return_value=99
    ), mock.patch.object(focus_shield, "window_pid", return_value=2), mock.patch.object(
        focus_shield, "minimize_hwnd"
    ) as minimize:
        acted = focus_shield.enforce_allowlist(allowed_pids=set(), integral_pids={2})
    assert acted is False
    minimize.assert_not_called()

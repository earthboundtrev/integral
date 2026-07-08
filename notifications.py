"""Windows toast notifications and Duolingo-style daily reminders for Integral."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, datetime
from typing import Callable

from paths import APP_NAME

DEFAULT_REMINDER_TIMES = ("09:00", "12:00", "15:00", "18:00")
DEFAULT_END_OF_DAY_REMINDER = "21:00"
CHECK_INTERVAL_MS = 30_000

NOT_LOGGED_MESSAGES = (
    "Time to check in with Integral — even one quick rating keeps your streak alive.",
    "Your life domains are waiting. Open Integral and log how today is going.",
    "A few minutes of honest logging goes a long way. How's your day?",
    "Don't let today slip by unlogged — open Integral and capture where you are.",
)
LOGGED_ONCE_MESSAGE = (
    "Before the day ends, finish logging everything you did today in Integral."
)


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _powershell_exe() -> str:
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidates = (
        os.path.join(system_root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
        os.path.join(system_root, "Sysnative", "WindowsPowerShell", "v1.0", "powershell.exe"),
    )
    for path in candidates:
        if os.path.isfile(path):
            return path
    return "powershell"


def _run_hidden(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    """Run a subprocess without flashing a System32 console window (PyInstaller windowed apps)."""
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
        kwargs.setdefault("startupinfo", startupinfo)
        kwargs.setdefault("stdin", subprocess.DEVNULL)
    return subprocess.run(command, **kwargs)


def show_windows_notification(title: str, message: str, *, app_id: str = APP_NAME) -> bool:
    """Show a native Windows toast. Returns True when the toast was dispatched."""
    if sys.platform != "win32":
        return False

    safe_title = _escape_xml(title)
    safe_message = _escape_xml(message)
    ps_script = f"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = @"
<toast>
  <visual>
    <binding template="ToastGeneric">
      <text>{safe_title}</text>
      <text>{safe_message}</text>
    </binding>
  </visual>
</toast>
"@
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}').Show($toast)
"""
    try:
        _run_hidden(
            [
                _powershell_exe(),
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps_script,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def default_notification_settings() -> dict:
    return {
        "enabled": True,
        "reminder_times": list(DEFAULT_REMINDER_TIMES),
        "end_of_day_reminder": DEFAULT_END_OF_DAY_REMINDER,
        "reminder_state": {},
    }


def normalize_notification_settings(settings: dict | None) -> dict:
    base = dict(settings or {})
    stored = dict(base.get("notifications") or {})
    merged = default_notification_settings()
    merged.update({key: stored[key] for key in stored if key in merged})
    if isinstance(stored.get("reminder_times"), list) and stored["reminder_times"]:
        merged["reminder_times"] = [str(value) for value in stored["reminder_times"]]
    if stored.get("end_of_day_reminder"):
        merged["end_of_day_reminder"] = str(stored["end_of_day_reminder"])
    if isinstance(stored.get("reminder_state"), dict):
        merged["reminder_state"] = dict(stored["reminder_state"])
    base["notifications"] = merged
    return base


def _parse_hhmm(value: str) -> tuple[int, int] | None:
    try:
        hour_str, minute_str = value.split(":", 1)
        hour = int(hour_str)
        minute = int(minute_str)
    except (AttributeError, TypeError, ValueError):
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return hour, minute


def _time_reached(now: datetime, target_hhmm: str) -> bool:
    parsed = _parse_hhmm(target_hhmm)
    if parsed is None:
        return False
    hour, minute = parsed
    return (now.hour, now.minute) >= (hour, minute)


def _reminder_key(reminder_time: str, *, end_of_day: bool = False) -> str:
    return f"end:{reminder_time}" if end_of_day else reminder_time


def reminder_state_for_day(settings: dict, today: date) -> dict:
    notifications = normalize_notification_settings(settings)["notifications"]
    state = dict(notifications.get("reminder_state") or {})
    if state.get("date") != today.isoformat():
        return {"date": today.isoformat(), "sent_keys": [], "logged_once": False}
    sent_keys = state.get("sent_keys")
    if not isinstance(sent_keys, list):
        sent_keys = []
    return {
        "date": today.isoformat(),
        "sent_keys": [str(key) for key in sent_keys],
        "logged_once": bool(state.get("logged_once")),
    }


def mark_logged_once(settings: dict, today: date | None = None) -> dict:
    updated = normalize_notification_settings(settings)
    today = today or datetime.now().date()
    state = reminder_state_for_day(updated, today)
    state["logged_once"] = True
    updated["notifications"]["reminder_state"] = state
    return updated


def reset_reminder_state(settings: dict, today: date | None = None) -> dict:
    updated = normalize_notification_settings(settings)
    today = today or datetime.now().date()
    updated["notifications"]["reminder_state"] = {
        "date": today.isoformat(),
        "sent_keys": [],
        "logged_once": False,
    }
    return updated


def due_reminders(
    settings: dict,
    *,
    now: datetime | None = None,
    logged_today: bool,
) -> list[tuple[str, str, str]]:
    """Return pending reminders as (key, title, message)."""
    normalized = normalize_notification_settings(settings)
    notifications = normalized["notifications"]
    if not notifications.get("enabled", True):
        return []

    now = now or datetime.now()
    today = now.date()
    state = reminder_state_for_day(settings, today)
    sent_keys = set(state["sent_keys"])
    logged_once = bool(state["logged_once"] or logged_today)
    due: list[tuple[str, str, str]] = []

    if logged_once:
        end_time = str(notifications.get("end_of_day_reminder") or DEFAULT_END_OF_DAY_REMINDER)
        key = _reminder_key(end_time, end_of_day=True)
        if key not in sent_keys and _time_reached(now, end_time):
            due.append((key, APP_NAME, LOGGED_ONCE_MESSAGE))
        return due

    for index, reminder_time in enumerate(notifications.get("reminder_times") or DEFAULT_REMINDER_TIMES):
        key = _reminder_key(reminder_time)
        if key in sent_keys:
            continue
        if not _time_reached(now, reminder_time):
            continue
        message = NOT_LOGGED_MESSAGES[index % len(NOT_LOGGED_MESSAGES)]
        due.append((key, APP_NAME, message))
    return due


def record_sent_reminders(settings: dict, keys: list[str], today: date | None = None) -> dict:
    updated = normalize_notification_settings(settings)
    today = today or datetime.now().date()
    state = reminder_state_for_day(updated, today)
    sent_keys = list(state["sent_keys"])
    for key in keys:
        if key not in sent_keys:
            sent_keys.append(key)
    state["sent_keys"] = sent_keys
    updated["notifications"]["reminder_state"] = state
    return updated


class ReminderScheduler:
    """Polls throughout the day and sends Windows reminders with Duolingo-style tapering."""

    def __init__(
        self,
        root,
        *,
        get_settings: Callable[[], dict],
        set_settings: Callable[[dict], None],
        has_logged_today: Callable[[], bool],
        persist_settings: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self._get_settings = get_settings
        self._set_settings = set_settings
        self._has_logged_today = has_logged_today
        self._persist_settings = persist_settings
        self._after_id: str | None = None
        self.start()

    def start(self) -> None:
        self.stop()
        self._schedule()

    def stop(self) -> None:
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    def reset_for_new_day(self) -> None:
        settings = self._get_settings()
        self._set_settings(reset_reminder_state(settings))

    def notify_logged_today(self) -> None:
        settings = self._get_settings()
        self._set_settings(mark_logged_once(settings))

    def _schedule(self) -> None:
        self._after_id = self.root.after(CHECK_INTERVAL_MS, self._tick)

    def _tick(self) -> None:
        self._after_id = None
        try:
            self._process_due_reminders()
        finally:
            self._schedule()

    def _process_due_reminders(self) -> None:
        settings = self._get_settings()
        pending = due_reminders(settings, logged_today=self._has_logged_today())
        if not pending:
            return

        sent_keys: list[str] = []
        for key, title, message in pending:
            if show_windows_notification(title, message):
                sent_keys.append(key)

        if not sent_keys:
            return

        updated = record_sent_reminders(settings, sent_keys)
        self._set_settings(updated)
        if self._persist_settings is not None:
            self._persist_settings()

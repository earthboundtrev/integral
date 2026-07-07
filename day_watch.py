"""Detect calendar day changes while Integral stays open."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable

DAY_CHECK_INTERVAL_MS = 60_000


class DayWatch:
    """Refresh the app when the local calendar day rolls over."""

    def __init__(self, root, *, on_new_day: Callable[[date, date], None]) -> None:
        self.root = root
        self._on_new_day = on_new_day
        self._tracked_day = datetime.now().date()
        self._after_id: str | None = None
        self.start()

    @property
    def tracked_day(self) -> date:
        return self._tracked_day

    def start(self) -> None:
        self.stop()
        self._schedule()

    def stop(self) -> None:
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None

    def _schedule(self) -> None:
        delay = self._milliseconds_until_next_check()
        self._after_id = self.root.after(delay, self._tick)

    def _milliseconds_until_next_check(self) -> int:
        now = datetime.now()
        next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        delay_ms = int((next_minute - now).total_seconds() * 1000)
        return max(delay_ms, 5_000)

    def _tick(self) -> None:
        self._after_id = None
        try:
            today = datetime.now().date()
            if today != self._tracked_day:
                previous = self._tracked_day
                self._tracked_day = today
                self._on_new_day(previous, today)
        finally:
            self._schedule()

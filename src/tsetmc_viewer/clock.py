"""Market-time helpers. All timestamps in the system are timezone-aware (Asia/Tehran)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from tsetmc_viewer.config import MarketSettings
from tsetmc_viewer.domain.calendar import HolidayCalendar


class MarketClock:
    def __init__(self, settings: MarketSettings) -> None:
        self._s = settings
        self.tz = ZoneInfo(settings.timezone)
        self.calendar = HolidayCalendar(
            settings.trading_weekdays, settings.extra_holidays if settings.holidays else {}
        )
        self._use_holidays = settings.holidays

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def is_trading_day(self, moment: datetime) -> bool:
        day = moment.astimezone(self.tz).date()
        if not self._use_holidays:
            return day.weekday() in self._s.trading_weekdays
        return self.calendar.is_trading_day(day)

    def holiday(self, moment: datetime) -> str | None:
        """Why a weekday is closed (holiday name or closure note), else None."""
        if not self._use_holidays:
            return None
        return self.calendar.holiday_name(moment.astimezone(self.tz).date())

    def session_open(self, day: date) -> datetime:
        return datetime.combine(day, self._s.open_time, tzinfo=self.tz)

    @property
    def session_guard(self) -> timedelta:
        return timedelta(minutes=self._s.session_guard_minutes)

    def is_open(self, moment: datetime) -> bool:
        local = moment.astimezone(self.tz)
        if not self.is_trading_day(local):
            return False
        return self._s.open_time <= local.time() <= self._s.close_time

    def is_after_close(self, moment: datetime, grace_minutes: int = 30) -> bool:
        """True once TSETMC has had time to publish the day's official figures."""
        local = moment.astimezone(self.tz)
        close = datetime.combine(local.date(), self._s.close_time, tzinfo=self.tz)
        return local >= close + timedelta(minutes=grace_minutes)

    def session_close(self, day: date) -> datetime:
        """The closing moment of the session on ``day`` (the stamp of a closing snapshot)."""
        return datetime.combine(day, self._s.close_time, tzinfo=self.tz)

    @staticmethod
    def floor_minute(moment: datetime) -> datetime:
        return moment.replace(second=0, microsecond=0)

    def seconds_until_next_tick(self, moment: datetime, interval_seconds: int) -> float:
        """Seconds until the next wall-clock boundary of ``interval_seconds``.

        Aligning to boundaries (…:00, …:01) keeps snapshots of all funds on the
        same minute bucket, which simplifies joins and charts downstream.
        """
        epoch = moment.timestamp()
        next_boundary = (epoch // interval_seconds + 1) * interval_seconds
        return max(0.0, next_boundary - epoch)

    def next_open(self, moment: datetime) -> datetime:
        local = moment.astimezone(self.tz)
        for days in range(0, 8):
            day = (local + timedelta(days=days)).date()
            candidate = datetime.combine(day, self._s.open_time, tzinfo=self.tz)
            if candidate >= local and self.is_trading_day(candidate):
                return candidate
        raise RuntimeError("no trading day configured")  # pragma: no cover

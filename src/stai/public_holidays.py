"""Bounded read-only Philippine public-holiday lookup via Nager.Holidays."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Callable, Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from stai.config import settings
from stai.state import Repo


NAGER_URL = "https://date.nager.at/api/v3/PublicHolidays/{year}/PH"
ATTRIBUTION = "Based on Nager."


class CalendarConflict(RuntimeError):
    pass


class Holiday(BaseModel):
    date: date
    name: str = Field(min_length=1, max_length=200)
    localName: str | None = Field(default=None, max_length=200)
    countryCode: Literal["PH"] = "PH"


class HolidayCalendarResult(BaseModel):
    year: int
    holidays: list[Holiday] = Field(default_factory=list)
    outcome: Literal["live", "cache", "unavailable"]
    attribution: Literal["Based on Nager."] | None = None
    retry_count: int = Field(default=0, ge=0, le=1)
    error_category: Literal[
        "timeout", "connection", "http_failure", "invalid_response",
        "disabled", "circuit_open", "unavailable",
    ] | None = None


class NagerHolidayService:
    def __init__(
        self,
        repo: Repo,
        *,
        client=None,
        enabled: bool | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.repo = repo
        self.client = client or httpx.Client()
        self.enabled = settings.nager_enabled if enabled is None else enabled
        self.now = now or (lambda: datetime.now(UTC))
        self._failures = 0
        self._circuit_until: datetime | None = None

    def _allowed_years(self) -> set[int]:
        current = self.now().astimezone(ZoneInfo("Asia/Manila")).year
        return {current, current + 1}

    def lookup(self, year: int) -> HolidayCalendarResult:
        if type(year) is not int or year not in self._allowed_years():
            raise ValueError("year must be the current or following Asia/Manila year")
        if not self.enabled:
            return self._cache_or_unavailable(year, "disabled")
        if self._circuit_until and self.now() < self._circuit_until:
            return self._cache_or_unavailable(year, "circuit_open")

        retry_count = 0
        last_category = "unavailable"
        for attempt in range(2):
            try:
                response = self.client.get(
                    NAGER_URL.format(year=year),
                    timeout=settings.nager_timeout_seconds,
                    follow_redirects=False,
                )
                if 300 <= response.status_code < 400:
                    return self._failure(year, "invalid_response", retry_count)
                if response.status_code == 429 or response.status_code >= 500:
                    last_category = "http_failure"
                    if attempt == 0:
                        retry_count = 1
                        continue
                    return self._failure(year, last_category, retry_count)
                if response.status_code >= 400:
                    return self._failure(year, "http_failure", retry_count)
                holidays = self._validate_payload(response.json(), year)
                self._failures = 0
                normalized = [{"date": h.date.isoformat(), "name": h.name, "localName": h.localName, "countryCode": "PH"} for h in holidays]
                self.repo.put_holiday_cache(year, normalized)
                return HolidayCalendarResult(
                    year=year, holidays=holidays, outcome="live",
                    attribution=ATTRIBUTION, retry_count=retry_count,
                )
            except httpx.TimeoutException:
                last_category = "timeout"
            except httpx.RequestError:
                last_category = "connection"
            except (ValueError, TypeError, ValidationError):
                return self._failure(year, "invalid_response", retry_count)
            if attempt == 0:
                retry_count = 1
                continue
        return self._failure(year, last_category, retry_count)

    @staticmethod
    def _validate_payload(payload, year: int) -> list[Holiday]:
        if not isinstance(payload, list) or len(payload) > 50:
            raise ValueError("invalid result size")
        holidays = TypeAdapter(list[Holiday]).validate_python(payload)
        if any(item.date.year != year for item in holidays):
            raise ValueError("holiday year mismatch")
        return holidays

    def _failure(self, year: int, category: str, retry_count: int) -> HolidayCalendarResult:
        self._failures += 1
        if self._failures >= 3:
            self._circuit_until = self.now() + timedelta(minutes=5)
        cached = self.repo.get_holiday_cache(year)
        if cached:
            return HolidayCalendarResult(
                year=year,
                holidays=TypeAdapter(list[Holiday]).validate_python(cached),
                outcome="cache",
                attribution=ATTRIBUTION,
                retry_count=retry_count,
                error_category=category,
            )
        return HolidayCalendarResult(
            year=year, outcome="unavailable", retry_count=retry_count,
            error_category=category,
        )

    def _cache_or_unavailable(self, year: int, category: str) -> HolidayCalendarResult:
        cached = self.repo.get_holiday_cache(year)
        if cached:
            return HolidayCalendarResult(
                year=year, holidays=TypeAdapter(list[Holiday]).validate_python(cached),
                outcome="cache", attribution=ATTRIBUTION, error_category=category,
            )
        return HolidayCalendarResult(year=year, outcome="unavailable", error_category=category)


def calendar_conflict(calendar_dates: dict[str, str], handbook_dates: dict[str, str]) -> bool:
    for name, calendar_date in calendar_dates.items():
        if name in handbook_dates and handbook_dates[name] != calendar_date:
            raise CalendarConflict(f"calendar conflict for {name}")
    return False

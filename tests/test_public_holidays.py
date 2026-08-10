from datetime import UTC, datetime, timedelta

import httpx
import pytest

from stai.public_holidays import (
    CalendarConflict,
    NagerHolidayService,
    calendar_conflict,
)
from stai.state import Repo


NOW = datetime(2026, 8, 10, tzinfo=UTC)
VALID = [{"date": "2026-08-21", "localName": "Ninoy Aquino Day", "name": "Ninoy Aquino Day", "countryCode": "PH", "fixed": True, "global": True, "counties": None, "launchYear": None, "types": ["Public"]}]


class FakeClient:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append((url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        status, payload = outcome
        return httpx.Response(status, json=payload, request=httpx.Request("GET", url))


def service(tmp_path, outcomes, *, enabled=True):
    repo = Repo(tmp_path / "db.sqlite", secret_path=tmp_path / "key")
    client = FakeClient(outcomes)
    return NagerHolidayService(repo, client=client, enabled=enabled, now=lambda: NOW), client


def test_live_success_is_ph_only_and_has_exact_attribution(tmp_path):
    svc, client = service(tmp_path, [(200, VALID)])
    result = svc.lookup(2026)
    assert result.outcome == "live"
    assert result.attribution == "Based on Nager."
    assert client.urls[0][0] == "https://date.nager.at/api/v3/PublicHolidays/2026/PH"
    assert set(client.urls[0][1]) <= {"timeout", "follow_redirects"}
    assert client.urls[0][1]["follow_redirects"] is False


def test_year_allowlist_rejects_past_and_far_future_without_network(tmp_path):
    svc, client = service(tmp_path, [(200, VALID)])
    with pytest.raises(ValueError):
        svc.lookup(2025)
    with pytest.raises(ValueError):
        svc.lookup(2028)
    assert client.urls == []


def test_retry_once_for_5xx_then_cache_fallback(tmp_path):
    svc, client = service(tmp_path, [(200, VALID), (500, {}), (500, {})])
    assert svc.lookup(2026).outcome == "live"
    result = svc.lookup(2026)
    assert result.outcome == "cache"
    assert result.retry_count == 1
    assert len(client.urls) == 3


def test_malformed_or_hostile_payload_is_not_retried(tmp_path):
    hostile = [{**VALID[0], "countryCode": "US", "name": "x" * 300}]
    svc, client = service(tmp_path, [(200, hostile), (200, VALID)])
    result = svc.lookup(2026)
    assert result.outcome == "unavailable"
    assert result.error_category == "invalid_response"
    assert len(client.urls) == 1


def test_disabled_mode_skips_live_and_uses_unexpired_cache(tmp_path):
    svc, client = service(tmp_path, [], enabled=False)
    svc.repo.put_holiday_cache(2026, [{"date": "2026-08-21", "name": "Cached"}])
    assert svc.lookup(2026).outcome == "cache"
    assert client.urls == []


def test_three_live_failures_open_five_minute_circuit(tmp_path):
    failure = httpx.ConnectError("offline")
    svc, client = service(tmp_path, [failure, failure, failure, failure, failure, failure])
    for _ in range(3):
        assert svc.lookup(2026).outcome == "unavailable"
    calls = len(client.urls)
    result = svc.lookup(2026)
    assert result.error_category == "circuit_open"
    assert len(client.urls) == calls


def test_calendar_conflict_is_explicit():
    with pytest.raises(CalendarConflict):
        calendar_conflict({"Special Day": "2026-08-21"}, {"Special Day": "2026-08-22"})
    assert calendar_conflict({"Special Day": "2026-08-21"}, {"Special Day": "2026-08-21"}) is False


def test_no_private_data_can_enter_request_surface(tmp_path):
    svc, client = service(tmp_path, [(200, VALID)])
    with pytest.raises(TypeError):
        svc.lookup(2026, employee_id="emp-alyssa")
    svc.lookup(2026)
    url = client.urls[0][0].lower()
    assert "alyssa" not in url and "message" not in url and "policy" not in url

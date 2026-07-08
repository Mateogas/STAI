from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from stai import pulse
from stai.models import Employee


START = date(2026, 6, 22)


def _emp() -> Employee:
    return Employee(
        id="e",
        name="Jomar Dela Cruz",
        role="Client Service Associate",
        role_key="client_service_associate",
        department="Branch Operations",
        start_date=START,
    )


def test_not_due_before_start():
    assert not pulse.is_checkin_due(START, date(2026, 6, 20), None, 7)


def test_not_due_in_first_week():
    assert not pulse.is_checkin_due(START, date(2026, 6, 25), None, 7)


def test_due_after_one_cadence():
    assert pulse.is_checkin_due(START, date(2026, 6, 29), None, 7)


def test_not_due_soon_after_last_checkin():
    assert not pulse.is_checkin_due(START, date(2026, 7, 2), date(2026, 6, 29), 7)


def test_due_again_one_cadence_after_last():
    assert pulse.is_checkin_due(START, date(2026, 7, 6), date(2026, 6, 29), 7)


def test_weeks_since_start():
    assert pulse.weeks_since_start(START, START) == 0
    assert pulse.weeks_since_start(START, date(2026, 6, 29)) == 1
    assert pulse.weeks_since_start(START, date(2026, 7, 20)) == 4


def test_checkin_question_is_personal():
    q = pulse.build_checkin_question(_emp(), date(2026, 6, 29))
    assert q.startswith("Hi Jomar")
    assert "first week" in q


def test_parse_pulse_happy():
    raw = '{"sentiment": 2, "concerns": ["workload"], "summary": "struggling"}'
    r = pulse.parse_pulse(raw)
    assert r.sentiment == 2 and r.concerns == ["workload"]


def test_parse_pulse_clamps_out_of_range():
    assert pulse.parse_pulse('{"sentiment": 9}').sentiment == 5
    assert pulse.parse_pulse('{"sentiment": -3}').sentiment == 1


def test_parse_pulse_garbage_is_neutral():
    r = pulse.parse_pulse("the model said something weird")
    assert r.sentiment == 3


def test_classify_pulse_with_injected_llm():
    llm = SimpleNamespace(
        invoke=lambda _p: SimpleNamespace(
            content='{"sentiment": 1, "concerns": ["connection"], "summary": "isolated"}'
        )
    )
    r = pulse.classify_pulse("nobody talks to me", llm=llm)
    assert r.sentiment == 1 and "connection" in r.concerns


def test_classify_pulse_neutral_when_llm_raises():
    def boom(_p):
        raise ConnectionError("down")

    r = pulse.classify_pulse("fine", llm=SimpleNamespace(invoke=boom))
    assert r.sentiment == 3


def test_risk_empty_is_safe():
    assert not pulse.risk_flag([])


def test_risk_latest_low():
    assert pulse.risk_flag([4, 2])
    assert pulse.risk_flag([1])


def test_risk_declining_to_three():
    assert pulse.risk_flag([4, 3])


def test_no_risk_declining_but_still_high():
    assert not pulse.risk_flag([5, 4])


def test_no_risk_stable_or_improving():
    assert not pulse.risk_flag([3, 3])
    assert not pulse.risk_flag([2, 4])


def test_trend():
    assert pulse.trend([]) == "-"
    assert pulse.trend([3]) == "-"
    assert pulse.trend([3, 4]) == "improving"
    assert pulse.trend([4, 3]) == "declining"
    assert pulse.trend([4, 4]) == "stable"

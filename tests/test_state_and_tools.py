from __future__ import annotations

from datetime import date

from stai.models import PHASE_ORDER, PulseResult
from stai.tools import build_tools, load_org, match_people, match_task


SIM = date(2026, 7, 7)


def test_seed_loads_all_employees(repo):
    ids = {e.id for e in repo.list_employees()}
    assert ids == {"emp-alyssa", "emp-jomar", "emp-nina"}


def test_seed_is_idempotent(repo):
    assert repo.seed_if_empty() is False
    done, total = repo.progress("emp-alyssa")
    assert done == 0 and total > 15


def test_plan_grouped_in_phase_order(repo):
    phases = repo.get_plan("emp-alyssa")
    keys = [p.key for p in phases]
    assert keys == [k for k in PHASE_ORDER if k in keys]
    assert all(p.items for p in phases)


def test_complete_task_moves_progress(repo):
    items = repo.list_plan_items("emp-alyssa")
    first = items[0]
    updated = repo.complete_task("emp-alyssa", first.id)
    assert updated.done and updated.done_at is not None
    done, _total = repo.progress("emp-alyssa")
    assert done == 1


def test_escalation_roundtrip(repo):
    esc = repo.add_escalation("emp-jomar", "Who can reset my LMS module?", "not in KB")
    assert esc.status == "open"
    assert [e.id for e in repo.list_escalations(status="open")] == [esc.id]
    assert repo.resolve_escalation(esc.id)
    assert repo.list_escalations(status="open") == []
    assert repo.list_escalations(status="resolved")[0].id == esc.id


def test_pulse_roundtrip(repo):
    assert repo.last_checkin_date("emp-jomar") is None
    repo.add_pulse(
        "emp-jomar",
        date(2026, 6, 29),
        PulseResult(sentiment=2, concerns=["workload"], summary="rough week"),
        raw_reply="drowning a bit",
    )
    history = repo.pulse_history("emp-jomar")
    assert len(history) == 1 and history[0].concerns == ["workload"]
    assert repo.last_checkin_date("emp-jomar") == date(2026, 6, 29)


def test_match_task_by_id(repo):
    items = repo.list_plan_items("emp-alyssa")
    assert match_task(str(items[3].id), items).id == items[3].id


def test_match_task_fuzzy_laptop(repo):
    items = repo.list_plan_items("emp-alyssa")
    item = match_task("laptop setup", items)
    assert item is not None and "laptop" in item.title.lower()


def test_match_task_prefers_open_tasks(repo):
    items = repo.list_plan_items("emp-alyssa")
    laptop = match_task("laptop", items)
    repo.complete_task("emp-alyssa", laptop.id)
    again = match_task("laptop", repo.list_plan_items("emp-alyssa"))
    assert again.id == laptop.id


def test_match_task_rejects_nonsense(repo):
    items = repo.list_plan_items("emp-alyssa")
    assert match_task("xyzzy quux plugh", items) is None


def test_match_people_payroll():
    people = load_org()
    top = match_people("who handles payroll?", people)
    assert top and top[0].name == "Noel Bautista"


def test_match_people_laptop_goes_to_it():
    top = match_people("who do I ask about my laptop?", load_org())
    assert top and top[0].name == "Irene Chua"


def test_match_people_benefits():
    top = match_people("benefits enrollment question", load_org())
    assert top and top[0].name == "Noel Bautista"


def test_match_people_no_match():
    assert match_people("quantum chromodynamics", load_org()) == []


def test_complete_task_tool(repo, alyssa):
    tools, capture = build_tools(alyssa, repo, SIM)
    complete = next(t for t in tools if t.name == "complete_task")
    out = complete.invoke({"task": "laptop"})
    assert "Done" in out and "Progress: 1/" in out
    assert capture.plan_changed


def test_escalate_tool_files_ticket(repo, alyssa):
    tools, capture = build_tools(alyssa, repo, SIM)
    escalate = next(t for t in tools if t.name == "escalate_to_hr")
    out = escalate.invoke({"question": "Can I get help with LMS access?"})
    assert "Escalation #" in out
    assert capture.escalation_id is not None
    assert repo.list_escalations(status="open")[0].question == "Can I get help with LMS access?"


def test_get_my_plan_tool_lists_ids(repo, alyssa):
    tools, _capture = build_tools(alyssa, repo, SIM)
    plan_tool = next(t for t in tools if t.name == "get_my_plan")
    out = plan_tool.invoke({})
    assert "Alyssa Reyes's onboarding and ramp plan" in out
    assert "(id " in out and "Day 1 Setup" in out


def test_find_person_tool(repo, alyssa):
    tools, _capture = build_tools(alyssa, repo, SIM)
    find = next(t for t in tools if t.name == "find_person")
    out = find.invoke({"query": "payroll"})
    assert "Noel Bautista" in out and "Suggested intro" in out

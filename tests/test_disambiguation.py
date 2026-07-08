"""Deterministic ambiguity detection: ambiguous task references never mutate."""

from __future__ import annotations

from datetime import date

from stai.tools import ambiguous_task_matches, build_tools, find_task_matches

SIM = date(2026, 7, 7)

# Alyssa's plan has several open tasks matching "manager check-in":
# "Meet branch manager Carlo Santos" (day 1),
# "First manager check-in with Carlo Santos" (week 1), and
# "Log one blocker or question for the manager check-in" (week 2).
AMBIGUOUS_QUERY = "manager check-in"


def _complete_tool(repo, alyssa):
    tools, capture = build_tools(alyssa, repo, SIM)
    return next(t for t in tools if t.name == "complete_task"), capture


def test_find_task_matches_scores_best_first(repo):
    items = repo.list_plan_items("emp-alyssa")
    matches = find_task_matches("laptop", items)
    assert matches and "laptop" in matches[0][1].title.lower()
    scores = [s for s, _ in matches]
    assert scores == sorted(scores, reverse=True)


def test_find_task_matches_numeric_id_is_exact(repo):
    items = repo.list_plan_items("emp-alyssa")
    matches = find_task_matches(str(items[2].id), items)
    assert len(matches) == 1 and matches[0] == (1.0, items[2])


def test_ambiguous_query_detected(repo):
    items = repo.list_plan_items("emp-alyssa")
    candidates = ambiguous_task_matches(find_task_matches(AMBIGUOUS_QUERY, items))
    assert len(candidates) >= 2


def test_unambiguous_query_not_flagged(repo):
    items = repo.list_plan_items("emp-alyssa")
    assert ambiguous_task_matches(find_task_matches("laptop", items)) == []
    assert ambiguous_task_matches(find_task_matches("buddy feedback", items)) == []


def test_complete_task_refuses_ambiguous_reference(repo, alyssa):
    complete, capture = _complete_tool(repo, alyssa)
    out = complete.invoke({"task": AMBIGUOUS_QUERY})

    assert out.startswith("AMBIGUOUS:")
    assert "(id " in out  # candidates listed so the agent can ask
    assert not capture.plan_changed
    done, _total = repo.progress("emp-alyssa")
    assert done == 0  # nothing was mutated


def test_complete_task_by_id_resolves_ambiguity(repo, alyssa):
    items = repo.list_plan_items("emp-alyssa")
    matches = find_task_matches(AMBIGUOUS_QUERY, items)
    target = matches[0][1]

    complete, capture = _complete_tool(repo, alyssa)
    out = complete.invoke({"task": str(target.id)})
    assert out.startswith("Done")
    assert capture.plan_changed


def test_ambiguity_clears_once_other_candidates_are_done(repo, alyssa):
    items = repo.list_plan_items("emp-alyssa")
    candidates = [i for _s, i in find_task_matches(AMBIGUOUS_QUERY, items)]
    assert len(candidates) >= 2
    for item in candidates[:-1]:
        repo.complete_task("emp-alyssa", item.id)
    remaining = candidates[-1]

    complete, capture = _complete_tool(repo, alyssa)
    out = complete.invoke({"task": AMBIGUOUS_QUERY})
    assert out.startswith("Done")
    assert capture.plan_changed
    refreshed = repo.list_plan_items("emp-alyssa")
    assert next(i for i in refreshed if i.id == remaining.id).done

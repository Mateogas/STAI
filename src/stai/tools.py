"""The agent's five tools.

Tools are built per chat turn via ``build_tools`` so they close over the
current employee, the repo, and a ``RunCapture`` that records what happened.
The UI and output guardrails read the capture after the run.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

from langchain_core.tools import tool

from stai.config import settings
from stai.models import PHASE_LABELS, ChecklistItem, Employee, Person
from stai.state import Repo

_STOPWORDS = {
    "a", "an", "the", "i", "me", "my", "we", "our", "you", "your", "who", "whom",
    "what", "which", "how", "do", "does", "did", "is", "are", "was", "can",
    "could", "should", "would", "to", "for", "of", "on", "in", "at", "with",
    "about", "ask", "asks", "handle", "handles", "handling", "help", "helps",
    "need", "needs", "question", "questions", "someone", "person", "people",
    "contact", "reach", "talk", "speak", "know", "knows", "get", "and", "or",
    "mark", "set", "as", "done", "complete", "completed", "finish", "finished",
    "task", "off", "check",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9']+", text.lower()) if t not in _STOPWORDS}


def _tokens_match(a: str, b: str) -> bool:
    return a == b or (len(a) >= 4 and b.startswith(a)) or (len(b) >= 4 and a.startswith(b))


@dataclass
class RunCapture:
    """What happened during one agent run."""

    sources: list[dict] = field(default_factory=list)
    used_search: bool = False
    escalation_id: int | None = None
    plan_changed: bool = False
    tool_calls: list[str] = field(default_factory=list)

    @property
    def source_names(self) -> list[str]:
        seen: list[str] = []
        for s in self.sources:
            if s["source"] not in seen:
                seen.append(s["source"])
        return seen


@lru_cache(maxsize=1)
def load_org(org_file: str | None = None) -> list[Person]:
    path = Path(org_file or settings.org_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Person(**p) for p in data["people"]]


def match_people(query: str, people: list[Person], top_n: int = 2) -> list[Person]:
    """Rank org-directory people against a natural-language query."""
    q_tokens = _tokens(query)
    if not q_tokens:
        return []
    scored: list[tuple[float, Person]] = []
    for person in people:
        name_tokens = _tokens(person.name)
        role_tokens = _tokens(person.role)
        team_tokens = _tokens(person.team)
        resp_tokens = _tokens(" ".join(person.responsibilities))
        score = 0.0
        for qt in q_tokens:
            if any(_tokens_match(qt, t) for t in name_tokens):
                score += 5.0
            if any(_tokens_match(qt, t) for t in resp_tokens):
                score += 3.0
            if any(_tokens_match(qt, t) for t in role_tokens):
                score += 2.0
            if any(_tokens_match(qt, t) for t in team_tokens):
                score += 1.5
        if score > 0:
            scored.append((score, person))
    scored.sort(key=lambda pair: -pair[0])
    return [p for _, p in scored[:top_n]]


# Two open tasks whose match scores are closer than this are ambiguous:
# the agent must ask instead of mutating the plan.
AMBIGUITY_MARGIN = 0.1


def find_task_matches(
    query: str, items: list[ChecklistItem]
) -> list[tuple[float, ChecklistItem]]:
    """Score every plan item against a task reference, best first.

    Returns ``(score, item)`` pairs with score >= 0.5. An exact numeric id is
    a single perfect match. Open items get a small bonus so completed tasks
    do not shadow their open twins.
    """
    q = query.strip()
    if q.isdigit():
        wanted = int(q)
        item = next((i for i in items if i.id == wanted), None)
        return [(1.0, item)] if item else []

    q_tokens = _tokens(q)
    scored: list[tuple[float, ChecklistItem]] = []
    for item in items:
        t_tokens = _tokens(item.title)
        score = difflib.SequenceMatcher(None, q.lower(), item.title.lower()).ratio()
        if q_tokens:
            hits = sum(
                1 for qt in q_tokens if any(_tokens_match(qt, tt) for tt in t_tokens)
            )
            score = max(score, hits / len(q_tokens))
        if not item.done:
            score += 0.05
        if score >= 0.5:
            scored.append((score, item))
    scored.sort(key=lambda pair: -pair[0])
    return scored


def match_task(query: str, items: list[ChecklistItem]) -> ChecklistItem | None:
    """Resolve a task reference (id number or fuzzy title) to a plan item."""
    matches = find_task_matches(query, items)
    return matches[0][1] if matches else None


def ambiguous_task_matches(
    matches: list[tuple[float, ChecklistItem]]
) -> list[ChecklistItem]:
    """Open plan items a task reference matches too evenly to act on.

    Returns the tied candidates when two or more *open* items score within
    ``AMBIGUITY_MARGIN`` of each other; empty list means it is safe to act.
    """
    open_matches = [(s, i) for s, i in matches if not i.done]
    if len(open_matches) >= 2 and open_matches[0][0] - open_matches[1][0] < AMBIGUITY_MARGIN:
        best = open_matches[0][0]
        return [i for s, i in open_matches if best - s < AMBIGUITY_MARGIN]
    return []


def build_tools(employee: Employee, repo: Repo, sim_date: date):
    """Return (tools, capture) bound to this employee and simulated date."""
    capture = RunCapture()

    @tool
    def search_knowledge_base(query: str, doc_type: str = "") -> str:
        """Search the fictionalized BDO onboarding handbook for policies,
        benefits, payroll, IT access, branch logistics, glossary terms,
        compliance learning, and ramp guides. Use for ANY question about demo
        company facts. Optionally filter by doc_type: one of 'policy', 'guide',
        'explainer', 'checklist', 'glossary'."""
        from stai.retriever import format_docs, retrieve

        capture.tool_calls.append("search_knowledge_base")
        capture.used_search = True
        docs = retrieve(query, doc_type=doc_type or None)
        for doc in docs:
            capture.sources.append(
                {
                    "source": doc.metadata.get("source", "unknown"),
                    "title": doc.metadata.get("title", ""),
                    "snippet": doc.page_content[:300],
                }
            )
        if not docs:
            return (
                "NO_RESULTS: nothing relevant found in the fictionalized "
                "handbook. Tell the user this is not covered and offer to "
                "escalate_to_hr."
            )
        return format_docs(docs)

    @tool
    def get_my_plan(focus: str = "") -> str:
        """Read the employee's onboarding and ramp plan: every task, phase,
        numeric id, and completion state. Use when the user asks about tasks,
        progress, Day 30 readiness, or what to do next. The optional 'focus'
        argument is ignored; the full plan is returned."""
        capture.tool_calls.append("get_my_plan")
        phases = repo.get_plan(employee.id)
        done, total = repo.progress(employee.id)
        lines = [f"{employee.name}'s onboarding and ramp plan - {done}/{total} tasks done:"]
        for phase in phases:
            lines.append(f"\n{phase.label}:")
            for item in phase.items:
                box = "x" if item.done else " "
                lines.append(f"- [{box}] (id {item.id}) {item.title}")
        return "\n".join(lines)

    @tool
    def complete_task(task: str) -> str:
        """Mark one onboarding or ramp task as done. Pass the task's numeric id
        or a distinctive fragment of its title, such as 'MFA', 'AML', or
        'buddy feedback'. If several open tasks match, nothing is changed and
        you must ask the user which one they mean."""
        capture.tool_calls.append("complete_task")
        items = repo.list_plan_items(employee.id)
        matches = find_task_matches(task, items)
        ambiguous = ambiguous_task_matches(matches)
        if ambiguous:
            options = "; ".join(f"(id {i.id}) {i.title}" for i in ambiguous)
            return (
                f"AMBIGUOUS: {len(ambiguous)} open tasks match '{task}' and "
                "nothing was marked done. Ask the user which one they mean, "
                f"then call complete_task with its id: {options}"
            )
        item = matches[0][1] if matches else None
        if item is None:
            open_titles = "; ".join(f"(id {i.id}) {i.title}" for i in items if not i.done)
            return (
                f"NOT_FOUND: no plan task matches '{task}'. Open tasks are: "
                f"{open_titles or 'none - everything is done!'}"
            )
        already = item.done
        item = repo.complete_task(employee.id, item.id)
        capture.plan_changed = True
        done, total = repo.progress(employee.id)
        note = " (it was already done)" if already else ""
        return (
            f"Done{note}: '{item.title}' [{PHASE_LABELS.get(item.phase, item.phase)}]. "
            f"Progress: {done}/{total} ({round(100 * done / total) if total else 0}%)."
        )

    @tool
    def escalate_to_hr(question: str, details: str = "") -> str:
        """File a People Experience ticket when the handbook does not answer,
        when the user reports a serious concern, or when they explicitly ask
        for human support. Pass the user's question and useful context."""
        capture.tool_calls.append("escalate_to_hr")
        esc = repo.add_escalation(employee.id, question, details)
        capture.escalation_id = esc.id
        return (
            f"Escalation #{esc.id} filed with People Experience (Liza Villanueva's team). "
            "They respond within 2 business days; the employee can also write to "
            "people@bdo-demo.local or message @liza.people in the demo chat."
        )

    @tool
    def find_person(query: str) -> str:
        """Look up who handles something in the fictionalized BDO org directory
        (for example payroll, laptop access, AML learning, branch shadowing, or
        benefits enrollment) or find a named colleague. Returns role, team, and
        how to reach them."""
        capture.tool_calls.append("find_person")
        matches = match_people(query, load_org())
        if not matches:
            return (
                "NO_MATCH: nobody in the org directory matches. Offer to "
                "escalate_to_hr so People Experience can route the question."
            )
        blocks = []
        for person in matches:
            blocks.append(
                f"{person.name} - {person.role} ({person.team} team)\n"
                f"  Handles: {'; '.join(person.responsibilities)}\n"
                f"  Reach: {person.slack} in demo chat, {person.email}, {person.location}"
            )
        best = matches[0]
        blocks.append(
            f"Suggested intro: send {best.slack} one line about what you need. "
            "Asking early is part of the ramp, not a problem."
        )
        return "\n\n".join(blocks)

    tools = [search_knowledge_base, get_my_plan, complete_task, escalate_to_hr, find_person]
    return tools, capture

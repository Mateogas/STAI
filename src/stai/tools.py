"""The agent's five tools.

Tools are built per chat turn via ``build_tools`` so they close over the
current employee, the repo, and a ``RunCapture`` that records what happened
(sources retrieved, escalation filed, plan changed). The UI and the output
guardrails read the capture after the run — that is how "Sources" expanders
and the must-cite check know what the agent actually looked at.
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
from stai.models import PHASE_LABELS, PHASE_ORDER, ChecklistItem, Employee, Person
from stai.state import Repo

# Words that carry no signal when matching people/tasks.
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
    # crude stemming: 'laptop' matches 'laptops', 'payslip' matches 'payslips'
    return a == b or (len(a) >= 4 and b.startswith(a)) or (len(b) >= 4 and a.startswith(b))


@dataclass
class RunCapture:
    """What happened during one agent run."""

    sources: list[dict] = field(default_factory=list)   # {source, title, snippet}
    used_search: bool = False
    escalation_id: int | None = None
    plan_changed: bool = False

    @property
    def source_names(self) -> list[str]:
        seen: list[str] = []
        for s in self.sources:
            if s["source"] not in seen:
                seen.append(s["source"])
        return seen


# ------------------------------------------------------------------ people

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


# ------------------------------------------------------------------- tasks

def match_task(query: str, items: list[ChecklistItem]) -> ChecklistItem | None:
    """Resolve a task reference (id number or fuzzy title) to a plan item.

    Undone items win ties so "mark laptop setup done" targets the open task.
    """
    q = query.strip()
    if q.isdigit():
        wanted = int(q)
        return next((i for i in items if i.id == wanted), None)

    q_tokens = _tokens(q)
    best: ChecklistItem | None = None
    best_score = 0.0
    for item in items:
        t_tokens = _tokens(item.title)
        score = difflib.SequenceMatcher(None, q.lower(), item.title.lower()).ratio()
        if q_tokens:
            hits = sum(
                1 for qt in q_tokens if any(_tokens_match(qt, tt) for tt in t_tokens)
            )
            score = max(score, hits / len(q_tokens))
        if not item.done:
            score += 0.05  # prefer open tasks on near-ties
        if score > best_score:
            best, best_score = item, score
    return best if best_score >= 0.5 else None


# ------------------------------------------------------------- tool factory

def build_tools(employee: Employee, repo: Repo, sim_date: date):
    """Return (tools, capture) bound to this employee and simulated date."""
    capture = RunCapture()

    @tool
    def search_knowledge_base(query: str, doc_type: str = "") -> str:
        """Search the Meridian Labs employee handbook for policies, benefits,
        payroll, IT setup, office logistics, glossary terms and onboarding
        guides. Use for ANY question about company facts. Optionally filter by
        doc_type: one of 'policy', 'guide', 'explainer', 'checklist',
        'glossary'."""
        from stai.retriever import format_docs, retrieve

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
                "NO_RESULTS: nothing relevant found in the handbook. Tell the "
                "user this isn't covered and offer to escalate_to_hr."
            )
        return format_docs(docs)

    @tool
    def get_my_plan(focus: str = "") -> str:
        """Read the employee's personal 30-60-90 onboarding plan: every task,
        its phase, its numeric id, and whether it is done. Use when the user
        asks about their tasks, plan, progress, or what to do next. The
        optional 'focus' argument is ignored — the full plan is returned."""
        phases = repo.get_plan(employee.id)
        done, total = repo.progress(employee.id)
        lines = [f"{employee.name}'s 30-60-90 plan — {done}/{total} tasks done:"]
        for phase in phases:
            lines.append(f"\n{phase.label}:")
            for item in phase.items:
                box = "x" if item.done else " "
                lines.append(f"- [{box}] (id {item.id}) {item.title}")
        return "\n".join(lines)

    @tool
    def complete_task(task: str) -> str:
        """Mark one onboarding-plan task as done. Pass the task's numeric id
        or a distinctive fragment of its title (e.g. 'laptop' or 'first PR')."""
        items = repo.list_plan_items(employee.id)
        item = match_task(task, items)
        if item is None:
            open_titles = "; ".join(f"(id {i.id}) {i.title}" for i in items if not i.done)
            return (
                f"NOT_FOUND: no plan task matches '{task}'. Open tasks are: "
                f"{open_titles or 'none — everything is done!'}"
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
        """File a ticket with the People Ops team when the handbook doesn't
        answer the user's question, when they report a serious concern, or
        when they explicitly ask for HR. Pass the user's question and any
        useful context."""
        esc = repo.add_escalation(employee.id, question, details)
        capture.escalation_id = esc.id
        return (
            f"Escalation #{esc.id} filed with People Ops (Marcus Webb's team). "
            "They respond within 2 business days; the employee can also write "
            "to people@meridianlabs.io or #ask-people directly."
        )

    @tool
    def find_person(query: str) -> str:
        """Look up who at Meridian Labs handles something (e.g. 'payroll',
        'laptop problems', 'benefits enrollment') or find a named colleague.
        Returns their role, team, and how to reach them."""
        matches = match_people(query, load_org())
        if not matches:
            return (
                "NO_MATCH: nobody in the org directory matches. Offer to "
                "escalate_to_hr so People Ops can route the question."
            )
        blocks = []
        for person in matches:
            blocks.append(
                f"{person.name} — {person.role} ({person.team} team)\n"
                f"  Handles: {'; '.join(person.responsibilities)}\n"
                f"  Reach: {person.slack} on Slack, {person.email}, {person.location}"
            )
        best = matches[0]
        blocks.append(
            f"Suggested intro: a 15-minute virtual coffee — message {best.slack} "
            f"with one line about what you need; that's normal at Meridian."
        )
        return "\n\n".join(blocks)

    tools = [search_knowledge_base, get_my_plan, complete_task, escalate_to_hr, find_person]
    return tools, capture

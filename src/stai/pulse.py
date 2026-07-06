"""Proactive pulse check-ins and attrition-risk scoring.

The clock is the sidebar's *simulated date* (a demo prop), never the wall
clock. When a check-in is due the agent OPENS the session with a well-being
question; the user's reply is sentiment-scored by the small guardrail model
into a ``PulseResult`` and stored. The HR dashboard flags hires whose latest
score is <= 2 or whose trend is declining — the direct countermeasure to the
"~33% of new hires quit within 90 days" statistic in the business case.

LLM parsing is separated from scheduling/risk logic so everything except the
actual model call is unit-testable without Ollama.
"""

from __future__ import annotations

import json
from datetime import date

from stai.config import settings
from stai.models import Employee, PulseResult

# ------------------------------------------------------------------ schedule

def weeks_since_start(start_date: date, sim_date: date) -> int:
    return max(0, (sim_date - start_date).days // 7)


def is_checkin_due(
    start_date: date,
    sim_date: date,
    last_checkin: date | None,
    cadence_days: int | None = None,
) -> bool:
    """Weekly cadence: first check-in one cadence after the start date, then
    one cadence after the previous check-in. Never before the start date."""
    cadence = cadence_days or settings.pulse_cadence_days
    if sim_date < start_date:
        return False
    if (sim_date - start_date).days < cadence:
        return False
    if last_checkin is not None and (sim_date - last_checkin).days < cadence:
        return False
    return True


_QUESTIONS = [
    (
        "before we dive into anything else — you've wrapped your first week at "
        "Meridian. How are you feeling so far? Anything confusing, surprising, "
        "or harder than expected? (Honest answers help me help you — this isn't "
        "a performance review.)"
    ),
    (
        "quick weekly pulse check: how did this week feel? Are you getting what "
        "you need from your team and your onboarding plan, or is anything "
        "dragging?"
    ),
    (
        "checking in — you're a few weeks in now. How's the workload feeling, "
        "and do you feel connected to the people you work with? Anything you "
        "wish someone had told you earlier?"
    ),
    (
        "monthly-ish pulse: how does the job compare to what you expected when "
        "you signed? Anything you'd change about your first weeks here?"
    ),
]


def build_checkin_question(employee: Employee, sim_date: date) -> str:
    week = weeks_since_start(employee.start_date, sim_date)
    template = _QUESTIONS[min(max(week - 1, 0), len(_QUESTIONS) - 1)]
    return f"Hi {employee.first_name} — {template}"


# ----------------------------------------------------------------- sentiment

_PULSE_PROMPT = """\
You score well-being check-in replies from new hires for an HR system.
Read the REPLY and output JSON with:
- "sentiment": integer 1-5 (1 = very negative / wants to quit, 2 = struggling,
  3 = neutral or mixed, 4 = good, 5 = thriving)
- "concerns": array chosen from ["workload", "expectations", "connection",
  "clarity", "tools", "manager", "other"] — empty if none
- "summary": one short sentence for an HR dashboard

Examples:
REPLY: "Loving it so far, the team is great!"
{"sentiment": 5, "concerns": [], "summary": "Very positive first weeks."}
REPLY: "Honestly I'm drowning, nobody has time to explain anything and I'm not sure this is what I signed up for."
{"sentiment": 1, "concerns": ["workload", "connection", "expectations"], "summary": "Overwhelmed, feels unsupported, questioning the role."}
REPLY: "It's fine I guess. Some days are slow because I'm still waiting on access."
{"sentiment": 3, "concerns": ["tools"], "summary": "Neutral; blocked on access."}

Answer with ONLY the JSON object.

REPLY: {reply}
"""


def parse_pulse(raw: str) -> PulseResult:
    """Parse classifier output; neutral fallback on garbage."""
    text = (raw or "").strip()
    try:
        start, end = text.index("{"), text.rindex("}") + 1
        data = json.loads(text[start:end])
        sentiment = int(data.get("sentiment", 3))
        sentiment = min(5, max(1, sentiment))
        concerns = [str(c) for c in data.get("concerns", []) if str(c).strip()]
        return PulseResult(
            sentiment=sentiment, concerns=concerns, summary=str(data.get("summary", ""))
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        return PulseResult(sentiment=3, concerns=[], summary="(could not parse reply)")


def classify_pulse(reply: str, llm=None) -> PulseResult:
    """Sentiment-score one check-in reply. ``llm`` is injectable for tests."""
    if llm is None:
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=settings.guardrail_model,
            base_url=settings.ollama_base_url,
            temperature=0,
            format="json",
        )
    prompt = _PULSE_PROMPT.replace("{reply}", reply.strip()[:1500])
    try:
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content
            )
        result = parse_pulse(content)
    except Exception:
        result = PulseResult(sentiment=3, concerns=[], summary="(classifier unavailable)")
    return result


# ---------------------------------------------------------------------- risk

def risk_flag(scores: list[int]) -> bool:
    """True when the latest pulse is bad or the trend is sliding low.

    Rules (kept deliberately simple and explainable to HR):
    - latest score <= 2  -> at risk
    - latest dropped vs. previous AND latest <= 3 -> at risk (declining)
    """
    if not scores:
        return False
    if scores[-1] <= 2:
        return True
    return len(scores) >= 2 and scores[-1] < scores[-2] and scores[-1] <= 3


def trend(scores: list[int]) -> str:
    if len(scores) < 2:
        return "–"
    if scores[-1] > scores[-2]:
        return "improving"
    if scores[-1] < scores[-2]:
        return "declining"
    return "stable"

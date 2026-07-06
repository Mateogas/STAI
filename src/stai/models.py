"""Pydantic domain models shared across the app."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

# Onboarding plan phases, in chronological order.
PHASE_ORDER: list[str] = ["day_1", "week_1", "day_30", "day_60", "day_90"]
PHASE_LABELS: dict[str, str] = {
    "day_1": "Day 1",
    "week_1": "Week 1",
    "day_30": "First 30 days",
    "day_60": "Days 31–60",
    "day_90": "Days 61–90",
}


class Employee(BaseModel):
    id: str
    name: str
    role: str
    role_key: str
    department: str
    start_date: date
    email: str = ""
    manager: str = ""
    buddy: str = ""

    @property
    def first_name(self) -> str:
        return self.name.split()[0]


class ChecklistItem(BaseModel):
    id: int
    employee_id: str
    phase: str
    title: str
    done: bool = False
    done_at: datetime | None = None


class PlanPhase(BaseModel):
    key: str
    label: str
    items: list[ChecklistItem] = Field(default_factory=list)

    @property
    def done_count(self) -> int:
        return sum(1 for i in self.items if i.done)


class Escalation(BaseModel):
    id: int
    employee_id: str
    question: str
    details: str = ""
    status: Literal["open", "resolved"] = "open"
    created_at: datetime


class Person(BaseModel):
    id: str
    name: str
    role: str
    team: str
    responsibilities: list[str] = Field(default_factory=list)
    email: str = ""
    slack: str = ""
    location: str = ""


class PulseResult(BaseModel):
    """LLM sentiment classification of one check-in reply."""

    sentiment: int = Field(ge=1, le=5, description="1 = very negative, 5 = very positive")
    concerns: list[str] = Field(default_factory=list)
    summary: str = ""


class PulseRecord(PulseResult):
    """A stored pulse check-in."""

    id: int
    employee_id: str
    checkin_date: date
    raw_reply: str = ""


class GuardrailVerdict(BaseModel):
    category: Literal["on_topic", "off_topic", "injection"]
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.category == "on_topic"


class GroundedAnswer(BaseModel):
    """Final agent answer after output guardrails."""

    answer: str
    citations: list[str] = Field(default_factory=list)

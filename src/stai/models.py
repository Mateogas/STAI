"""Pydantic domain models shared across the app."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

# Onboarding and ramp phases, in chronological order.
PHASE_ORDER: list[str] = ["pre_start", "day_1", "week_1", "week_2", "day_30"]
PHASE_LABELS: dict[str, str] = {
    "pre_start": "Pre-start",
    "day_1": "Day 1 Setup",
    "week_1": "Week 1 Foundations",
    "week_2": "Week 2 Practice and Feedback",
    "day_30": "Day 30 Readiness Check",
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


class ChatMessage(BaseModel):
    """One persisted chat turn (survives app restarts, unlike session state)."""

    id: int
    employee_id: str
    role: Literal["user", "assistant"]
    content: str
    kind: str = ""  # "", "checkin", "refusal"
    sources: list[dict] = Field(default_factory=list)
    created_at: datetime


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


# ---------------------------------------------------------------------------
# AISHA three-topic policy domain (schema epoch 2)


class OnboardingTopic(StrEnum):
    PAYROLL = "payroll"
    RESOURCE_ACCESS = "resource_access"
    HR_POLICIES = "hr_policies"


class ApplicabilityStatus(StrEnum):
    APPLIES = "applies"
    DOES_NOT_APPLY = "does_not_apply"
    NEEDS_CLARIFICATION = "needs_clarification"


class EvidenceState(StrEnum):
    READY = "ready"
    INSUFFICIENT = "insufficient_evidence"
    ATTRIBUTE_REQUIRED = "hire_attribute_required"
    POLICY_CONFLICT = "policy_conflict"
    INDEX_OUTAGE = "knowledge_index_outage"
    INTEGRITY_FAILURE = "integrity_failure"
    HANDBOOK_OMISSION = "handbook_omission"


class HireProfile(BaseModel):
    employee_id: str
    role_key: Literal[
        "branch_banking_associate",
        "client_service_associate",
        "digital_banking_support_associate",
    ]
    department_key: Literal["branch_banking", "branch_operations", "digital_channels"]
    employment_classification: Literal["probationary", "regular", "fixed_term"]
    work_site: Literal["branch", "head_office", "remote"]
    revision: int = Field(default=1, ge=1)

    @classmethod
    def alyssa(cls) -> "HireProfile":
        return cls(
            employee_id="emp-alyssa",
            role_key="branch_banking_associate",
            department_key="branch_banking",
            employment_classification="probationary",
            work_site="branch",
        )


class PolicyCitation(BaseModel):
    policy_id: str = Field(pattern=r"^(PAY|ACC|HRP)-\d{3}$")
    handbook_version: str = Field(pattern=r"^\d+\.\d+$")
    page_start: int = Field(ge=1)
    page_end: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_page_range(self) -> "PolicyCitation":
        if self.page_end is not None and self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self

    def render(self) -> str:
        pages = (
            f"p. {self.page_start}"
            if self.page_end in (None, self.page_start)
            else f"pp. {self.page_start}\N{EN DASH}{self.page_end}"
        )
        return f"[{self.policy_id} \N{MIDDLE DOT} AISHA Handbook v{self.handbook_version} \N{MIDDLE DOT} {pages}]"


class PolicyClaim(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    citation_indexes: list[int] = Field(default_factory=list)


class PolicyResponseBase(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    handbook_version: str = Field(pattern=r"^\d+\.\d+$")
    applicability: ApplicabilityStatus
    evidence_state: EvidenceState = EvidenceState.READY
    citations: list[PolicyCitation] = Field(default_factory=list)


class GroundedPolicyAnswer(PolicyResponseBase):
    type: Literal["grounded_answer"] = "grounded_answer"
    claims: list[PolicyClaim] = Field(default_factory=list)


class ClarificationRequest(PolicyResponseBase):
    type: Literal["clarification_request"] = "clarification_request"
    question: str = Field(min_length=1, max_length=500)
    choices: list[str] = Field(default_factory=list, max_length=4)


class Abstention(PolicyResponseBase):
    type: Literal["abstention"] = "abstention"
    reason: Literal[
        "unsupported_topic",
        "insufficient_evidence",
        "unresolved_ambiguity",
        "policy_conflict",
        "knowledge_index_outage",
        "integrity_failure",
        "handbook_omission",
        "calendar_conflict",
        "calendar_unavailable",
    ]


class EscalationOffer(PolicyResponseBase):
    type: Literal["escalation_offer"] = "escalation_offer"
    offer_id: str
    route_owner: str
    route_channel: str
    proposed_summary: str = Field(min_length=1, max_length=500)
    topic: OnboardingTopic
    version: int = Field(default=1, ge=1)


PolicyResponse = Annotated[
    Union[GroundedPolicyAnswer, ClarificationRequest, Abstention, EscalationOffer],
    Field(discriminator="type"),
]


class ValidationStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    NEEDS_HUMAN_REVIEW = "needs_human_review"


class ValidationResult(BaseModel):
    validation_id: str
    employee_id: str
    status: ValidationStatus
    policy_id: Literal["HRP-004"]
    handbook_version: str
    profile_revision: int = Field(ge=1)
    missing_codes: list[str] = Field(default_factory=list)
    inconsistency_codes: list[str] = Field(default_factory=list)
    warning_codes: list[str] = Field(default_factory=list)
    review_codes: list[str] = Field(default_factory=list)
    attempt_count: int = Field(default=1, ge=1, le=2)
    evaluation_date: date
    citations: list[PolicyCitation]
    shared: bool = False
    resource_version: int = Field(default=1, ge=1)


class BenchmarkCase(BaseModel):
    case_id: str = Field(pattern=r"^(POL|RET|DIA|NAG|MED)-\d{2}$")
    family: Literal["policy", "retrieval", "dialogue", "nager", "medical"]
    partition: Literal["calibration", "locked"]
    scenario: str
    expected_outcome: str
    tags: list[str] = Field(default_factory=list)
    safety_critical: bool = True
    synthetic: Literal[True] = True

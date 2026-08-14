"""Pydantic domain models shared across the app."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

class GuardrailVerdict(BaseModel):
    category: Literal["on_topic", "off_topic", "injection"]
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.category == "on_topic"


# AISHA three-topic policy domain (schema epoch 2)


class OnboardingTopic(StrEnum):
    PAYROLL = "payroll"
    RESOURCE_ACCESS = "resource_access"
    HR_POLICIES = "hr_policies"


class DialogueAct(StrEnum):
    QUESTION = "question"
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"
    HELP_REQUEST = "help_request"
    ESCALATION_REQUEST = "escalation_request"
    CONSENT = "consent"
    ACTION_STATUS = "action_status"
    GREETING = "greeting"
    UNSUPPORTED = "unsupported"


class ExecutionMode(StrEnum):
    AGENT = "agent"
    DETERMINISTIC = "deterministic"
    DEGRADED = "degraded"


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


class EscalationConfirmation(PolicyResponseBase):
    """A workflow result produced only after consent to an existing offer."""

    type: Literal["escalation_confirmation"] = "escalation_confirmation"
    case_id: str
    route_owner: str
    route_channel: str
    topic: OnboardingTopic
    version: int = Field(default=1, ge=1)


class ResolvedTurn(BaseModel):
    """Private, bounded context resolution used before retrieval or action."""

    dialogue_act: DialogueAct
    topic: OnboardingTopic | None = None
    policy_ids: list[str] = Field(default_factory=list)
    standalone_query: str = Field(min_length=1, max_length=4000)
    referenced_message_id: str | None = None


PolicyResponse = Annotated[
    Union[GroundedPolicyAnswer, ClarificationRequest, Abstention, EscalationOffer],
    Field(discriminator="type"),
]


TurnResult = Annotated[
    Union[
        GroundedPolicyAnswer,
        ClarificationRequest,
        Abstention,
        EscalationOffer,
        EscalationConfirmation,
    ],
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

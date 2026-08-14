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
    CAPABILITY_DISCOVERY = "capability_discovery"
    GREETING = "greeting"
    UNSUPPORTED = "unsupported"


class PayrollSubIntent(StrEnum):
    PAY_SCHEDULE = "pay_schedule"
    ENROLLMENT = "enrollment"
    PAYSLIP = "payslip"
    PAYROLL_CHANGES = "payroll_changes"
    DEDUCTIONS = "deductions"
    HOLIDAY_CALENDAR = "holiday_calendar"
    CUTOFF = "cutoff"
    PAYMENT_METHOD = "payment_method"
    ACCOUNT_STATUS = "account_status"
    AMBIGUOUS = "ambiguous"


class AgentAction(StrEnum):
    DISCOVER_POLICIES = "discover_policies"
    ASK_CLARIFICATION = "ask_clarification"
    RETRIEVE_POLICY = "retrieve_policy"
    CHECK_CASE_STATUS = "check_case_status"
    PREPARE_HR_OFFER = "prepare_hr_offer"


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


class EvidenceGapKind(StrEnum):
    MISSING_PROCEDURE = "missing_procedure"
    EXCEPTION_UNCLEAR = "exception_unclear"
    POLICY_CONFLICT = "policy_conflict"
    ROUTE_UNCLEAR = "route_unclear"


class ResolutionType(StrEnum):
    POLICY_CLARIFICATION = "policy_clarification"
    CASE_EXCEPTION = "case_exception"
    POLICY_AMENDMENT_CANDIDATE = "policy_amendment_candidate"
    UNABLE_TO_RESOLVE = "unable_to_resolve"


class ResolutionScope(StrEnum):
    CASE_ONLY = "case_only"
    HIRE = "hire"
    ORGANIZATION = "organization"


class ClarificationReuseStatus(StrEnum):
    THREAD_ONLY = "thread_only"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_HANDBOOK = "pending_handbook"


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


class HumanClarificationReference(BaseModel):
    clarification_id: str
    source_case_id: str
    related_policy_ids: list[str] = Field(default_factory=list)
    resolution_scope: ResolutionScope
    approved_at_utc: str
    expires_on: date | None = None

    def render(self) -> str:
        return f"[HR clarification {self.clarification_id}]"


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
    clarifications: list[HumanClarificationReference] = Field(default_factory=list)


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
    gap_kind: EvidenceGapKind | None = None
    safe_known_text: str | None = Field(default=None, max_length=2000)
    unresolved_question: str | None = Field(default=None, max_length=1000)
    eligibility_reason: str | None = Field(default=None, max_length=500)
    shares_parent_conversation: bool = True
    sharing_notice: str = (
        "Creating this case shares this conversation's existing and future messages "
        "with HR until the case closes."
    )


class EscalationConfirmation(PolicyResponseBase):
    """A workflow result produced only after consent to an existing offer."""

    type: Literal["escalation_confirmation"] = "escalation_confirmation"
    case_id: str
    route_owner: str
    route_channel: str
    topic: OnboardingTopic
    version: int = Field(default=1, ge=1)


class EscalationEligibility(BaseModel):
    eligible: bool
    reason: str = Field(min_length=1, max_length=500)
    gap_kind: EvidenceGapKind | None = None
    safe_known_text: str | None = Field(default=None, max_length=2000)
    unresolved_question: str | None = Field(default=None, max_length=1000)
    policy_ids: list[str] = Field(default_factory=list)


class CaseResolutionInput(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)
    resolution_type: ResolutionType = ResolutionType.POLICY_CLARIFICATION
    resolution_scope: ResolutionScope = ResolutionScope.CASE_ONLY
    propose_for_reuse: bool = False
    effective_on: date | None = None
    expires_on: date | None = None

    @model_validator(mode="after")
    def validate_reuse_and_dates(self) -> "CaseResolutionInput":
        if self.propose_for_reuse and (
            self.resolution_type != ResolutionType.POLICY_CLARIFICATION
            or self.resolution_scope == ResolutionScope.CASE_ONLY
        ):
            raise ValueError(
                "only a non-case-only Policy Clarification can be proposed for reuse"
            )
        if self.effective_on and self.expires_on and self.expires_on < self.effective_on:
            raise ValueError("expires_on cannot precede effective_on")
        return self


class ResolvedTurn(BaseModel):
    """Private, bounded context resolution used before retrieval or action."""

    dialogue_act: DialogueAct
    topic: OnboardingTopic | None = None
    policy_ids: list[str] = Field(default_factory=list)
    standalone_query: str = Field(min_length=1, max_length=4000)
    referenced_message_id: str | None = None
    catalog_scope: OnboardingTopic | None = None
    policy_subarea: str | None = Field(default=None, max_length=100)
    payroll_intent: PayrollSubIntent | None = None
    clarification_question: str | None = Field(default=None, max_length=500)
    clarification_choices: list[str] = Field(default_factory=list, max_length=4)
    agent_actions: list[AgentAction] = Field(default_factory=list)


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

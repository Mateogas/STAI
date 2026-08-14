"""Bounded observe-and-plan module for one AISHA policy turn."""

from __future__ import annotations

import re

from stai.models import (
    AgentAction,
    DialogueAct,
    OnboardingTopic,
    PayrollSubIntent,
    ResolvedTurn,
)


_WORD = re.compile(r"[a-z0-9-]+")
_POLICY_ID = re.compile(r"\b(?:PAY|ACC|HRP)-\d{3}\b", re.IGNORECASE)
_HELP_TERMS = {"help", "human", "support", "connect", "escalate", "escalation"}
_FOLLOW_UP_TERMS = {"it", "this", "that", "then", "one"}
_GREETINGS = {"hi", "hello", "hey", "thanks", "thank", "salamat"}
_CONSENT_MESSAGES = {
    "yes", "yes please", "i consent", "yes route it", "route it",
    "route it please", "go ahead", "please proceed", "create the case", "send it",
}
_ACTION_STATUS_PATTERNS = (
    "have you created", "did you create", "was it created", "has it been created",
    "did that work", "did it work", "case status", "status of my case", "was it sent",
    "did you send", "have you sent", "was it routed", "case actually get created",
    "case get created",
)
_TOPIC_TERMS: dict[OnboardingTopic, set[str]] = {
    OnboardingTopic.PAYROLL: {
        "pay", "paid", "payroll", "payslip", "paycheck", "salary", "wage",
        "deduction", "deductions", "contribution", "contributions", "sss",
        "philhealth", "pag-ibig", "pagibig", "bank", "gcash", "cutoff", "payday",
        "pay-period", "enrollment", "take-home", "overtime", "13th-month",
    },
    OnboardingTopic.RESOURCE_ACCESS: {
        "access", "account", "device", "devices", "laptop", "laptops", "login",
        "password", "badge", "facility", "portal", "credential", "sandbox", "usb",
        "email", "cloud", "social", "tiktok",
    },
    OnboardingTopic.HR_POLICIES: {
        "hr", "leave", "attendance", "dress", "conduct", "office", "hours",
        "holiday", "policy", "policies", "privacy", "harassment", "manager",
        "supervisor", "sick", "medical", "certificate", "flooding", "typhoon",
        "messages", "diagnosis", "site", "handbook", "legal", "conversation",
        "chat", "case", "aisha",
    },
}


def topic_for_policy_id(policy_id: str) -> OnboardingTopic:
    if policy_id.startswith("PAY-"):
        return OnboardingTopic.PAYROLL
    if policy_id.startswith("ACC-"):
        return OnboardingTopic.RESOURCE_ACCESS
    return OnboardingTopic.HR_POLICIES


class AgenticPolicyTurn:
    """Produce one typed Agent Plan; execution and authority stay outside this module."""

    def plan(self, message: str, previous: dict | None, pending_offer: dict | None) -> ResolvedTurn:
        lowered = message.lower().strip()
        tokens = set(_WORD.findall(lowered))

        catalog_scope = self._catalog_scope(lowered, tokens)
        if catalog_scope is not False:
            return ResolvedTurn(
                dialogue_act=DialogueAct.CAPABILITY_DISCOVERY,
                topic=catalog_scope,
                catalog_scope=catalog_scope,
                standalone_query=message,
                policy_subarea="catalog",
                agent_actions=[AgentAction.DISCOVER_POLICIES],
            )

        policy_ids = [match.group(0).upper() for match in _POLICY_ID.finditer(message)]
        explicit_topic = topic_for_policy_id(policy_ids[0]) if policy_ids else None
        if not explicit_topic and {"coworker", "more"} <= tokens:
            explicit_topic = OnboardingTopic.PAYROLL
        if not explicit_topic:
            matches = [topic for topic, terms in _TOPIC_TERMS.items() if tokens & terms]
            # Device/security wording is more specific than a generic HR word such as manager.
            if OnboardingTopic.RESOURCE_ACCESS in matches and tokens & {
                "device", "devices", "laptop", "laptops", "password", "usb", "email",
                "cloud", "social", "tiktok",
            }:
                explicit_topic = OnboardingTopic.RESOURCE_ACCESS
            elif OnboardingTopic.PAYROLL in matches and (
                tokens & {
                    "pay", "paid", "payroll", "payslip", "paycheck", "salary",
                    "payday", "gcash",
                }
                or ("bank" in tokens and tokens & {"account", "parent", "details"})
            ):
                explicit_topic = OnboardingTopic.PAYROLL
            else:
                explicit_topic = matches[0] if len(matches) == 1 else None

        previous_topic = None
        previous_policy_ids: list[str] = []
        referenced_message_id = None
        if previous:
            if previous.get("resolved_topic"):
                previous_topic = OnboardingTopic(previous["resolved_topic"])
            payload = previous.get("payload") or {}
            previous_policy_ids = [item["policy_id"] for item in payload.get("citations", [])]
            referenced_message_id = previous.get("message_id")
        topic = explicit_topic or previous_topic

        normalized = " ".join(re.sub(r"[^a-z0-9 ]+", "", lowered).split())
        if pending_offer and normalized in _CONSENT_MESSAGES:
            return ResolvedTurn(
                dialogue_act=DialogueAct.CONSENT,
                topic=OnboardingTopic(pending_offer["topic"]),
                policy_ids=pending_offer.get("policy_ids", []),
                standalone_query=message,
                referenced_message_id=referenced_message_id,
                agent_actions=[AgentAction.PREPARE_HR_OFFER],
            )
        if any(pattern in lowered for pattern in _ACTION_STATUS_PATTERNS):
            return ResolvedTurn(
                dialogue_act=DialogueAct.ACTION_STATUS,
                topic=topic,
                policy_ids=policy_ids or previous_policy_ids,
                standalone_query=message,
                referenced_message_id=referenced_message_id,
                agent_actions=[AgentAction.CHECK_CASE_STATUS],
            )

        route_command = "route" in tokens and bool(tokens & {"it", "this", "that", "me"})
        help_requested = bool(tokens & _HELP_TERMS) or "talk to" in lowered or route_command
        if help_requested:
            return ResolvedTurn(
                dialogue_act=DialogueAct.CLARIFICATION if not topic else (
                    DialogueAct.ESCALATION_REQUEST
                    if route_command or tokens & {"human", "connect", "escalate", "escalation"}
                    else DialogueAct.HELP_REQUEST
                ),
                topic=topic,
                policy_ids=policy_ids or previous_policy_ids,
                standalone_query=message,
                referenced_message_id=referenced_message_id,
                agent_actions=[AgentAction.ASK_CLARIFICATION],
            )

        if tokens and tokens <= _GREETINGS:
            act = DialogueAct.GREETING
        elif not topic and tokens & {"onboard", "onboarding", "setup", "orientation"}:
            act = DialogueAct.CLARIFICATION
        elif not topic:
            act = DialogueAct.UNSUPPORTED
        elif explicit_topic or policy_ids:
            act = DialogueAct.QUESTION
        else:
            act = DialogueAct.FOLLOW_UP if tokens & _FOLLOW_UP_TERMS or previous else DialogueAct.QUESTION

        if topic == OnboardingTopic.PAYROLL and not policy_ids:
            payroll = self._payroll_plan(message, tokens, act, referenced_message_id)
            if payroll:
                return payroll
        if topic == OnboardingTopic.HR_POLICIES and not policy_ids:
            hr_policy = self._hr_policy_plan(message, tokens, act, referenced_message_id)
            if hr_policy:
                return hr_policy

        policy_subarea = None
        query = message.strip()
        if topic == OnboardingTopic.RESOURCE_ACCESS and tokens & {
            "social", "tiktok", "personal", "password", "usb", "email", "cloud",
        }:
            policy_ids = ["ACC-004"]
            policy_subarea = "information_security"
            query = f"ACC-004 information security {message}"
        elif topic and not explicit_topic:
            query = f"{topic.value.replace('_', ' ')} {query}"

        return ResolvedTurn(
            dialogue_act=act,
            topic=topic,
            policy_ids=policy_ids,
            standalone_query=query,
            referenced_message_id=referenced_message_id if not explicit_topic else None,
            policy_subarea=policy_subarea,
            agent_actions=[AgentAction.RETRIEVE_POLICY] if topic else [],
        )

    @staticmethod
    def _catalog_scope(lowered: str, tokens: set[str]):
        catalog_noun = bool(tokens & {"policies", "policy", "topics", "topic"})
        breadth = bool(tokens & {"other", "available", "supported", "list", "show", "cover", "else", "besides"})
        askability = ("can i ask" in lowered or "could i ask" in lowered or
                      "can you help" in lowered or "help me with" in lowered or
                      "what do you cover" in lowered)
        if not ((catalog_noun and breadth) or askability):
            return False
        if tokens & {"payroll", "pay", "payslip", "salary"}:
            return OnboardingTopic.PAYROLL
        if tokens & {"access", "device", "resource"}:
            return OnboardingTopic.RESOURCE_ACCESS
        if "hr" in tokens:
            return OnboardingTopic.HR_POLICIES
        return None

    @staticmethod
    def _payroll_plan(message: str, tokens: set[str], act: DialogueAct, referenced_message_id: str | None):
        lowered = message.lower()
        if (
            tokens & {"overtime", "night", "13th-month", "training"}
            and not tokens & {"payslip", "deduction", "deductions"}
        ):
            return ResolvedTurn(
                dialogue_act=act,
                topic=OnboardingTopic.PAYROLL,
                standalone_query=message,
                referenced_message_id=referenced_message_id,
                policy_subarea="handbook_omission",
                agent_actions=[AgentAction.RETRIEVE_POLICY],
            )
        ambiguous_get = (
            bool(tokens & {"get", "receive"})
            and bool(tokens & {"payroll", "pay", "salary"})
            and not tokens & {
                "when", "day", "days", "date", "payday", "payslip", "bank", "account",
                "deduction", "sss", "philhealth", "pagibig", "pag-ibig", "amount", "status",
            }
        )
        if ambiguous_get:
            return ResolvedTurn(
                dialogue_act=DialogueAct.CLARIFICATION,
                topic=OnboardingTopic.PAYROLL,
                standalone_query=message,
                payroll_intent=PayrollSubIntent.AMBIGUOUS,
                policy_subarea="ambiguous",
                clarification_question="What do you mean by getting your payroll?",
                clarification_choices=[
                    "When will I be paid?",
                    "Where can I view my payslip?",
                    "How does payroll enrollment work?",
                ],
                referenced_message_id=referenced_message_id,
                agent_actions=[AgentAction.ASK_CLARIFICATION],
            )

        if "payday" in tokens and "holiday" not in tokens and tokens & {"passed", "nothing", "missing"}:
            return ResolvedTurn(
                dialogue_act=act,
                topic=OnboardingTopic.PAYROLL,
                policy_ids=["PAY-001"],
                standalone_query=f"PAY-001 pay schedule missing payment status {message}",
                referenced_message_id=referenced_message_id,
                policy_subarea="account_status",
                payroll_intent=PayrollSubIntent.ACCOUNT_STATUS,
                agent_actions=[AgentAction.RETRIEVE_POLICY],
            )

        mapping = [
            (PayrollSubIntent.CUTOFF, {"cutoff"}, "PAY-006", "payroll_changes"),
            (PayrollSubIntent.HOLIDAY_CALENDAR, {"holiday"}, "PAY-005", "holiday_calendar"),
            (PayrollSubIntent.ACCOUNT_STATUS, {"amount", "lower", "missing", "arrive", "arrived", "appeared", "status", "posted", "coworker", "exact"}, "PAY-004", "account_status"),
            (PayrollSubIntent.DEDUCTIONS, {"deduction", "deductions", "contribution", "contributions", "sss", "philhealth", "pagibig", "pag-ibig", "gross", "net", "unpaid"}, "PAY-004", "deductions"),
            (PayrollSubIntent.PAYSLIP, {"payslip", "stub"}, "PAY-002", "payslip"),
            (PayrollSubIntent.PAYMENT_METHOD, {"gcash", "wallet", "parent", "method"}, "PAY-003", "payment_method"),
            (PayrollSubIntent.PAYROLL_CHANGES, {"wrong", "fix", "change", "correct", "update", "details", "submit", "route", "official"}, "PAY-003", "payroll_changes"),
            (PayrollSubIntent.PAY_SCHEDULE, {"when", "day", "days", "date", "payday", "paid", "weekly", "monthly", "schedule"}, "PAY-001", "pay_schedule"),
            (PayrollSubIntent.ENROLLMENT, {"enroll", "enrollment", "onboard", "onboarding"}, "PAY-003", "enrollment"),
        ]
        for intent, signals, policy_id, subarea in mapping:
            if tokens & signals:
                return ResolvedTurn(
                    dialogue_act=act,
                    topic=OnboardingTopic.PAYROLL,
                    policy_ids=[policy_id],
                    standalone_query=f"{policy_id} {subarea.replace('_', ' ')} {message}",
                    referenced_message_id=referenced_message_id,
                    policy_subarea=subarea,
                    payroll_intent=intent,
                    agent_actions=[AgentAction.RETRIEVE_POLICY],
                )
        return ResolvedTurn(
            dialogue_act=act,
            topic=OnboardingTopic.PAYROLL,
            policy_ids=["PAY-001"],
            standalone_query=f"PAY-001 payroll enrollment first pay schedule {message}",
            referenced_message_id=referenced_message_id,
            policy_subarea="enrollment",
            payroll_intent=PayrollSubIntent.ENROLLMENT,
            agent_actions=[AgentAction.RETRIEVE_POLICY],
        )

    @staticmethod
    def _hr_policy_plan(message: str, tokens: set[str], act: DialogueAct, referenced_message_id: str | None):
        if tokens & {"privacy", "messages", "diagnosis", "shared", "share", "delete", "conversation", "chat"}:
            policy_ids = ["HRP-005"]
            if tokens & {"aisha", "case", "conversation", "chat", "shared", "share", "delete"}:
                policy_ids.append("HRP-006")
            return ResolvedTurn(
                dialogue_act=act,
                topic=OnboardingTopic.HR_POLICIES,
                policy_ids=policy_ids,
                standalone_query=f"{' '.join(policy_ids)} privacy case sharing {message}",
                referenced_message_id=referenced_message_id,
                policy_subarea="privacy",
                agent_actions=[AgentAction.RETRIEVE_POLICY],
            )
        if (tokens & {"different", "conflict", "supervisor"}) and "handbook" in tokens:
            return ResolvedTurn(
                dialogue_act=act,
                topic=OnboardingTopic.HR_POLICIES,
                policy_ids=["HRP-006"],
                standalone_query=f"HRP-006 policy conflict human clarification {message}",
                referenced_message_id=referenced_message_id,
                policy_subarea="policy_conflict",
                agent_actions=[AgentAction.RETRIEVE_POLICY],
            )
        if "legal" in tokens:
            return ResolvedTurn(
                dialogue_act=act,
                topic=OnboardingTopic.HR_POLICIES,
                standalone_query=message,
                referenced_message_id=referenced_message_id,
                policy_subarea="legal_advice",
                agent_actions=[AgentAction.RETRIEVE_POLICY],
            )
        mapping = [
            ({"medical", "certificate"}, ["HRP-004"], "medical_certificate"),
            ({"harassment", "conduct", "anonymous"}, ["HRP-003"], "conduct"),
            ({"dress"}, ["HRP-007"], "dress"),
            ({"leave", "sick"}, ["HRP-002"], "leave"),
            ({"attendance", "late", "flooding", "typhoon"}, ["HRP-001"], "attendance"),
            ({"site", "profile", "correct"}, ["HRP-006"], "profile"),
        ]
        for signals, policy_ids, subarea in mapping:
            if tokens & signals:
                return ResolvedTurn(
                    dialogue_act=act,
                    topic=OnboardingTopic.HR_POLICIES,
                    policy_ids=policy_ids,
                    standalone_query=f"{' '.join(policy_ids)} {subarea.replace('_', ' ')} {message}",
                    referenced_message_id=referenced_message_id,
                    policy_subarea=subarea,
                    agent_actions=[AgentAction.RETRIEVE_POLICY],
                )
        return None

"""Schema-bounded ReAct tools for AISHA's three onboarding topics."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from langchain_core.tools import tool

from stai.models import HireProfile
from stai.state import Repo


@dataclass
class RunCapture:
    """Private validation state and closed tool identities for one fresh run."""

    tool_calls: list[str] = field(default_factory=list)
    retrieved_identities: set[tuple[str, str, int]] = field(default_factory=set)
    evidence_metadata: list[dict] = field(default_factory=list)
    evidence_contents: dict[tuple[str, str, int], str] = field(default_factory=dict)
    applicability_checks: dict[str, dict] = field(default_factory=dict)
    profile: HireProfile | None = None

    def record_evidence(self, item, records) -> dict:
        identity = (item.policy_id, item.handbook_version, item.page)
        self.retrieved_identities.add(identity)
        self.evidence_contents[identity] = item.content
        metadata = {
            "policy_id": item.policy_id,
            "handbook_version": item.handbook_version,
            "page": item.page,
            "authority": item.page_kind,
            "topic": next(
                (row.topic for row in records if row.record_id == item.record_id), None
            ),
            "applicability": item.applicability.value,
        }
        if metadata not in self.evidence_metadata:
            self.evidence_metadata.append(metadata)
        return {**metadata, "content": item.content}


def build_policy_tools(
    profile: HireProfile,
    repo: Repo,
    records,
    *,
    holiday_service=None,
    handbook_index=None,
):
    from stai.policy import evaluate_applicability as evaluate_policy_applicability
    from stai.public_holidays import NagerHolidayService
    from stai.retriever import InMemoryHandbookIndex

    capture = RunCapture(profile=profile)
    calendar = holiday_service or NagerHolidayService(repo)
    index = handbook_index or InMemoryHandbookIndex(records)

    @tool
    def get_active_handbook() -> str:
        """Return the verified Active Handbook Version and pointer generation."""
        capture.tool_calls.append("get_active_handbook")
        active = repo.get_active_retrieval_build()
        version = active["handbook_version"] if active else records[0].handbook_version
        generation = active["generation"] if active else 0
        return json.dumps({"handbook_version": version, "generation": generation})

    @tool
    def search_handbook(query: str) -> str:
        """Search eligible handbook pages using a natural-language query; call again to revise it."""
        capture.tool_calls.append("search_handbook")
        result = index.search(query, profile, k=8)
        evidence = [capture.record_evidence(item, records) for item in result.evidence]
        return json.dumps({"outcome": result.outcome.value, "required_attribute": result.required_attribute, "evidence": evidence})

    @tool
    def read_policy_bundle(policy_id: str) -> str:
        """Read every page for one exact handbook ID, for example PAY-001 or HRP-007."""
        capture.tool_calls.append("read_policy_bundle")
        if not policy_id.startswith(("PAY-", "ACC-", "HRP-")):
            return json.dumps({"outcome": "invalid_policy_id"})
        result = index.search(policy_id, profile, policy_ids={policy_id}, k=20)
        selected = [item for item in result.evidence if item.policy_id == policy_id]
        evidence = [capture.record_evidence(item, records) for item in selected]
        outcome = result.outcome.value if evidence else "insufficient_evidence"
        return json.dumps({"outcome": outcome, "policy_id": policy_id, "evidence": evidence})

    @tool
    def discover_policies(scope: str = "all") -> str:
        """List active policy IDs and titles for all topics or one closed topic scope."""
        capture.tool_calls.append("discover_policies")
        allowed = {"all", "payroll", "resource_access", "hr_policies"}
        if scope not in allowed:
            return json.dumps({"outcome": "invalid_scope", "allowed_scopes": sorted(allowed)})
        policies = []
        for record in records:
            if record.status != "active" or record.page_kind != "policy" or not record.policy_id:
                continue
            if scope != "all" and record.topic != scope:
                continue
            decision = evaluate_policy_applicability(record, profile)
            identity = (record.policy_id, record.handbook_version, record.page)
            capture.retrieved_identities.add(identity)
            capture.evidence_contents[identity] = record.content
            metadata = {
                "policy_id": record.policy_id,
                "handbook_version": record.handbook_version,
                "page": record.page,
                "authority": record.page_kind,
                "topic": record.topic,
                "applicability": decision.status.value,
            }
            if metadata not in capture.evidence_metadata:
                capture.evidence_metadata.append(metadata)
            policies.append({
                "policy_id": record.policy_id,
                "title": record.title.removesuffix(" - 1"),
                "topic": record.topic,
                "applicability": decision.status.value,
                "handbook_version": record.handbook_version,
                "page": record.page,
            })
        return json.dumps({"outcome": "ready", "scope": scope, "policies": policies})

    @tool
    def evaluate_applicability(policy_id: str) -> str:
        """Evaluate one policy ID against the confirmed Hire Profile."""
        capture.tool_calls.append("evaluate_applicability")
        record = next(
            (row for row in records if row.policy_id == policy_id and row.page_kind == "policy"),
            None,
        )
        if record is None:
            return json.dumps({"outcome": "not_found"})
        decision = evaluate_policy_applicability(record, profile)
        payload = {
            "outcome": decision.status.value,
            "required_attribute": decision.required_attribute,
        }
        capture.applicability_checks[policy_id] = payload
        return json.dumps(payload)

    @tool
    def lookup_public_holidays(year: int) -> str:
        """Read Philippines public holidays for the simulated current/following year."""
        capture.tool_calls.append("lookup_public_holidays")
        return calendar.lookup(year).model_dump_json()

    @tool
    def check_case_status() -> str:
        """Read the latest support-case status for this Hire without exposing case messages."""
        capture.tool_calls.append("check_case_status")
        cases = [item for item in repo.list_escalation_cases() if item["hire_id"] == profile.employee_id]
        if not cases:
            return json.dumps({"outcome": "not_found"})
        case = cases[0]
        return json.dumps({
            "outcome": "ready",
            "case_id": case["case_id"],
            "status": case["status"],
            "workflow_state": case["workflow_state"],
            "topic": case["topic"],
        })

    @tool
    def offer_escalation(policy_id: str = "", topic: str = "hr_policies") -> str:
        """Resolve a privacy-safe human route; this never creates a case."""
        capture.tool_calls.append("offer_escalation")
        record = next((row for row in records if row.policy_id == policy_id and row.route), None)
        owner = (record.route if record else f"{topic}_support").replace("_", " ").title()
        return json.dumps({
            "owner": owner,
            "channel": "Fictional HR Help Desk",
            "consent_required": True,
        })

    return [
        get_active_handbook,
        discover_policies,
        search_handbook,
        read_policy_bundle,
        evaluate_applicability,
        lookup_public_holidays,
        check_case_status,
        offer_escalation,
    ], capture

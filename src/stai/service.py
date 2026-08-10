"""Transport-independent AISHA policy, consent, profile, and result flows."""

from __future__ import annotations

from datetime import date

from stai.state import Repo


class AishaService:
    """Transport-independent orchestration for Streamlit and `/api/v1`."""

    def __init__(self, repo: Repo, records, *, medical_service=None) -> None:
        from stai.medical import MedicalCheckService

        self.repo = repo
        self.records = records
        self.medical = medical_service or MedicalCheckService(repo)

    def create_conversation(self, employee_id: str, simulated_date: date) -> dict:
        if employee_id != "emp-alyssa":
            raise KeyError("unknown Hire")
        return self.repo.create_policy_conversation(employee_id, simulated_date)

    def list_messages(self, conversation_id: str) -> list[dict]:
        return self.repo.list_policy_messages(conversation_id)

    def send_message(self, conversation_id: str, message: str):
        import re

        from stai.models import ApplicabilityStatus, EscalationOffer, EvidenceState, OnboardingTopic
        from stai.policy import PolicyEngine

        conversation = self.repo.get_policy_conversation(conversation_id)
        if not conversation:
            raise KeyError("conversation not found")
        user_message = self.repo.add_policy_message(conversation_id, "hire", message)
        profile = self.repo.get_hire_profile(conversation["hire_id"])
        if "human" in message.lower() or "escalat" in message.lower():
            match = re.search(r"\b(PAY|ACC|HRP)-\d{3}\b", message.upper())
            policy_id = match.group(0) if match else None
            record = next((r for r in self.records if r.policy_id == policy_id and r.route), None)
            topic_value = record.topic if record else "hr_policies"
            topic = OnboardingTopic(topic_value)
            route_owner = (record.route if record else "hr_general").replace("_", " ").title()
            summary = f"Clarify {policy_id or 'an onboarding policy'} with the appropriate human owner."
            offer_row = self.repo.create_escalation_offer(
                conversation_id, user_message["id"], topic.value, route_owner,
                "Fictional HR Help Desk", summary, [policy_id] if policy_id else [],
            )
            response = EscalationOffer(
                text="I can create this privacy-safe case after you consent.",
                handbook_version=self.records[0].handbook_version,
                applicability=ApplicabilityStatus.APPLIES,
                evidence_state=EvidenceState.READY,
                offer_id=offer_row["offer_id"], route_owner=route_owner,
                route_channel="Fictional HR Help Desk", proposed_summary=summary,
                topic=topic,
            )
        else:
            response = PolicyEngine(self.records).answer(message, profile)
        self.repo.save_policy_response(conversation_id, response)
        return response

    def consent_escalation(self, offer_id: str, *, expected_version: int) -> dict:
        return self.repo.consent_escalation_offer(offer_id, expected_version=expected_version)

    def request_attribute_change(self, employee_id: str, attribute_name: str, proposed_value: str, *, consent: bool) -> dict:
        return self.repo.create_attribute_change_request(employee_id, attribute_name, proposed_value, consent=consent)

    def resolve_attribute_request(self, request_id: str, *, approve: bool, expected_version: int, expected_profile_revision: int, hr_user: str) -> dict:
        return self.repo.resolve_attribute_change_request(request_id, approve=approve, expected_version=expected_version, expected_profile_revision=expected_profile_revision, hr_user=hr_user)

    def share_validation_result(self, validation_id: str, *, expected_version: int) -> dict:
        return self.repo._set_validation_share(validation_id, share=True, expected_version=expected_version)

    def revoke_validation_result(self, validation_id: str, *, expected_version: int) -> dict:
        return self.repo._set_validation_share(validation_id, share=False, expected_version=expected_version)

    def delete_validation_result(self, validation_id: str, *, expected_version: int) -> bool:
        return self.repo.delete_validation_result(validation_id, expected_version=expected_version)

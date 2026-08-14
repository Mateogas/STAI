"""Transport-independent AISHA policy, consent, profile, and result flows."""

from __future__ import annotations

from datetime import date

from stai.state import Repo


class AishaService:
    """Transport-independent orchestration for Streamlit and `/api/v1`."""

    def __init__(
        self,
        repo: Repo,
        records,
        *,
        medical_service=None,
        handbook_index=None,
        agent_enabled: bool = False,
        agent_runner=None,
        input_classifier=None,
    ) -> None:
        from stai.agent import LocalReactRunner
        from stai.cases import CaseWorkflow
        from stai.guardrails import LocalInputClassifier
        from stai.medical import MedicalCheckService
        from stai.retriever import InMemoryHandbookIndex
        from stai.turn_engine import PolicyTurnEngine

        self.repo = repo
        self.records = records
        self.medical = medical_service or MedicalCheckService(repo)
        self.handbook_index = handbook_index or InMemoryHandbookIndex(records)
        self.case_workflow = CaseWorkflow(repo)
        if agent_runner is None and agent_enabled:
            agent_runner = LocalReactRunner(repo, records, self.handbook_index)
        if input_classifier is None and agent_enabled:
            input_classifier = LocalInputClassifier()
        self.turn_engine = PolicyTurnEngine(
            repo,
            records,
            index=self.handbook_index,
            agent_runner=agent_runner,
            input_classifier=input_classifier,
            case_workflow=self.case_workflow,
        )

    def create_conversation(self, employee_id: str, simulated_date: date) -> dict:
        if employee_id != "emp-alyssa":
            raise KeyError("unknown Hire")
        return self.repo.create_policy_conversation(employee_id, simulated_date)

    def list_messages(self, conversation_id: str) -> list[dict]:
        return self.repo.list_policy_messages(conversation_id)

    def send_message(self, conversation_id: str, message: str):
        return self.turn_engine.handle_turn(conversation_id, message)

    def consent_escalation(self, offer_id: str, *, expected_version: int) -> dict:
        return self.repo.consent_escalation_offer(offer_id, expected_version=expected_version)

    def consent_escalation_from_conversation(
        self,
        conversation_id: str,
        offer_id: str,
        *,
        expected_version: int,
    ):
        """Consent through the turn seam so the result remains visible in chat."""
        pending = self.repo.get_pending_escalation_offer_for_conversation(conversation_id)
        if not pending or pending["offer_id"] != offer_id:
            raise KeyError("pending offer not found in conversation")
        if pending["resource_version"] != expected_version:
            raise ValueError("stale resource version")
        return self.send_message(conversation_id, "I consent")

    def list_cases(self, *, parent_conversation_id: str | None = None, hr: bool = False) -> list[dict]:
        from stai.cases import CaseActor

        actor = CaseActor.hr() if hr else CaseActor.hire()
        return self.case_workflow.list_cases(actor, parent_conversation_id=parent_conversation_id)

    def get_case_thread(self, case_id: str, *, hr: bool = False) -> dict:
        from stai.cases import CaseActor

        actor = CaseActor.hr() if hr else CaseActor.hire()
        return self.case_workflow.get_thread(case_id, actor)

    def post_case_message(
        self,
        case_id: str,
        text: str,
        *,
        expected_version: int,
        hr: bool = False,
        internal: bool = False,
    ) -> dict:
        from stai.cases import CaseActor

        actor = CaseActor.hr() if hr else CaseActor.hire()
        return self.case_workflow.post_message(
            case_id,
            actor,
            text,
            expected_version=expected_version,
            internal=internal,
        )

    def resolve_case(self, case_id: str, summary: str, *, expected_version: int) -> dict:
        from stai.cases import CaseActor

        return self.case_workflow.resolve(
            case_id,
            CaseActor.hr(),
            summary,
            expected_version=expected_version,
        )

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

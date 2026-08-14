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
        agent_runner=None,
        input_classifier=None,
    ) -> None:
        from stai.agent import LocalReactRunner
        from stai.cases import CaseWorkflow
        from stai.clarifications import PolicyClarificationWorkflow
        from stai.guardrails import LocalInputClassifier
        from stai.medical import MedicalCheckService
        from stai.retriever import InMemoryHandbookIndex
        from stai.turn_engine import PolicyTurnEngine

        self.repo = repo
        self.records = records
        self.medical = medical_service or MedicalCheckService(repo)
        self.handbook_index = handbook_index or InMemoryHandbookIndex(records)
        self.case_workflow = CaseWorkflow(repo)
        self.clarification_workflow = PolicyClarificationWorkflow(repo)
        if agent_runner is None:
            agent_runner = LocalReactRunner(repo, records, self.handbook_index)
        if input_classifier is None:
            input_classifier = LocalInputClassifier()
        self.turn_engine = PolicyTurnEngine(
            repo,
            records,
            index=self.handbook_index,
            agent_runner=agent_runner,
            input_classifier=input_classifier,
            case_workflow=self.case_workflow,
            clarification_workflow=self.clarification_workflow,
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
        thread = self.case_workflow.get_thread(case_id, actor)
        thread["resolution"] = self.clarification_workflow.get_resolution(case_id)
        return thread

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
        case = self.case_workflow.get_case(case_id, actor)
        if not hr and case["status"] == "closed":
            return self.clarification_workflow.answer_thread(
                case_id,
                actor,
                text,
                expected_version=expected_version,
            )
        if not hr:
            thread = self.case_workflow.get_thread(case_id, actor)
            if any(item["status"] == "pending" for item in thread["information_requests"]):
                return self.case_workflow.answer_information_request(
                    case_id,
                    actor,
                    text,
                    expected_version=expected_version,
                )
        return self.case_workflow.post_message(
            case_id,
            actor,
            text,
            expected_version=expected_version,
            internal=internal,
        )

    def request_case_information(
        self,
        case_id: str,
        question: str,
        *,
        expected_version: int,
        hr_user: str = "hr-demo",
    ) -> dict:
        from stai.cases import CaseActor

        return self.case_workflow.request_information(
            case_id,
            CaseActor.hr(hr_user),
            question,
            expected_version=expected_version,
        )

    def offer_direct_case_conversation(
        self, case_id: str, *, expected_version: int, hr_user: str = "hr-demo"
    ) -> dict:
        from stai.cases import CaseActor

        return self.case_workflow.offer_direct_conversation(
            case_id, CaseActor.hr(hr_user), expected_version=expected_version
        )

    def consent_direct_case_conversation(
        self, case_id: str, *, expected_version: int
    ) -> dict:
        from stai.cases import CaseActor

        return self.case_workflow.consent_direct_conversation(
            case_id, CaseActor.hire(), expected_version=expected_version
        )

    def resolve_case(
        self,
        case_id: str,
        summary: str,
        *,
        expected_version: int,
        resolution_type="policy_clarification",
        resolution_scope="case_only",
        propose_for_reuse: bool = False,
        effective_on=None,
        expires_on=None,
        hr_user: str = "hr-demo",
    ) -> dict:
        from stai.cases import CaseActor
        from stai.models import CaseResolutionInput

        self.clarification_workflow.resolve(
            case_id,
            CaseActor.hr(hr_user),
            CaseResolutionInput(
                answer=summary,
                resolution_type=resolution_type,
                resolution_scope=resolution_scope,
                propose_for_reuse=propose_for_reuse,
                effective_on=effective_on,
                expires_on=expires_on,
            ),
            expected_version=expected_version,
        )
        return self.get_case_thread(case_id, hr=True)["case"]

    def review_case_clarification(
        self,
        case_id: str,
        *,
        approve: bool,
        expected_version: int,
        hr_user: str = "policy-owner-demo",
    ) -> dict:
        from stai.cases import CaseActor

        return self.clarification_workflow.review(
            case_id,
            CaseActor.hr(hr_user),
            approve=approve,
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

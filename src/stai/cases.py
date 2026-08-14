"""Consented case-thread workflow shared by hire, HR, UI, and transport callers."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from enum import StrEnum

from stai.state import Repo, _utc_text


class CaseActorRole(StrEnum):
    HIRE = "hire"
    AISHA = "aisha"
    HR = "hr"
    SYSTEM = "system"


@dataclass(frozen=True)
class CaseActor:
    actor_id: str
    role: CaseActorRole

    @classmethod
    def hire(cls, hire_id: str = "emp-alyssa") -> "CaseActor":
        return cls(hire_id, CaseActorRole.HIRE)

    @classmethod
    def hr(cls, hr_user: str = "hr-demo") -> "CaseActor":
        return cls(hr_user, CaseActorRole.HR)

    @classmethod
    def aisha(cls) -> "CaseActor":
        return cls("aisha", CaseActorRole.AISHA)


class CaseWorkflow:
    """Own the complete consented ticket lifecycle behind one small interface."""

    def __init__(self, repo: Repo) -> None:
        self.repo = repo

    def consent_offer(
        self,
        conversation_id: str,
        offer_id: str,
        *,
        expected_version: int,
        actor: CaseActor,
    ) -> dict:
        if actor.role != CaseActorRole.HIRE:
            raise PermissionError("only the Hire can consent to an offer")
        case_id = str(uuid.uuid4())
        now = _utc_text()
        with self.repo.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            offer = conn.execute(
                "SELECT * FROM escalation_offers WHERE offer_id=?", (offer_id,)
            ).fetchone()
            if not offer or offer["conversation_id"] != conversation_id:
                raise KeyError("offer not found in conversation")
            if offer["hire_id"] != actor.actor_id:
                raise PermissionError("the offer belongs to another Hire")
            if offer["resource_version"] != expected_version:
                raise ValueError("stale resource version")
            policy_ids = [
                row[0]
                for row in conn.execute(
                    "SELECT policy_id FROM escalation_offer_policies WHERE offer_id=?",
                    (offer_id,),
                )
            ]
            conn.execute(
                "INSERT INTO escalation_cases "
                "(case_id,hire_id,topic,approved_summary,route_owner,route_channel,status,"
                "created_at_utc,closed_at_utc,closing_hr_user,resource_version) "
                "VALUES (?,?,?,?,?,?,'open',?,NULL,NULL,1)",
                (
                    case_id,
                    offer["hire_id"],
                    offer["topic"],
                    offer["proposed_summary"],
                    offer["route_owner"],
                    offer["route_channel"],
                    now,
                ),
            )
            for policy_id in policy_ids:
                conn.execute(
                    "INSERT INTO escalation_case_policies VALUES (?,?)",
                    (case_id, policy_id),
                )
            gap = conn.execute(
                "SELECT gap_kind,safe_known_text,unresolved_question,eligibility_reason "
                "FROM escalation_offer_evidence_gaps WHERE offer_id=?",
                (offer_id,),
            ).fetchone()
            if gap:
                conn.execute(
                    "INSERT INTO case_evidence_gaps VALUES (?,?,?,?,?)",
                    (
                        case_id,
                        gap["gap_kind"],
                        gap["safe_known_text"],
                        gap["unresolved_question"],
                        gap["eligibility_reason"],
                    ),
                )
            conn.execute(
                "INSERT INTO case_threads VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    case_id,
                    conversation_id,
                    offer["message_id"],
                    1,
                    "waiting_for_hr",
                    None,
                    None,
                    None,
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO case_interaction_modes(case_id,mode) VALUES (?,'mediated')",
                (case_id,),
            )
            parent_messages = conn.execute(
                "SELECT * FROM policy_messages WHERE conversation_id=? ORDER BY ordinal",
                (conversation_id,),
            ).fetchall()
            for ordinal, message in enumerate(parent_messages, 1):
                conn.execute(
                    "INSERT INTO case_messages VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        str(uuid.uuid4()),
                        case_id,
                        ordinal,
                        message["role"],
                        actor.actor_id if message["role"] == "hire" else "aisha",
                        "shared",
                        message["text"],
                        message["message_id"],
                        message["created_at_utc"],
                    ),
                )
            self._event(
                conn,
                case_id,
                "case_created",
                actor,
                {
                    "parent_conversation_id": conversation_id,
                    "shared_parent_message_count": len(parent_messages),
                    "share_future_parent_messages": True,
                },
                now,
            )
            self._notification(
                conn,
                case_id,
                "hr",
                offer["route_owner"],
                "case_created",
                f"New {offer['topic'].replace('_', ' ')} support case",
                now,
            )
            conn.execute("DELETE FROM escalation_offers WHERE offer_id=?", (offer_id,))
        return self.get_case(case_id, actor)

    def post_message(
        self,
        case_id: str,
        actor: CaseActor,
        text: str,
        *,
        expected_version: int,
        internal: bool = False,
    ) -> dict:
        clean = " ".join(text.split())
        if not clean or len(clean) > 4000:
            raise ValueError("case message must contain 1 to 4000 characters")
        self.repo.validate_policy_message(clean)
        if internal and actor.role != CaseActorRole.HR:
            raise PermissionError("only HR can create an internal note")
        now = _utc_text()
        with self.repo.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            case = self._case_row(conn, case_id)
            self._authorize(case, actor)
            if case["status"] != "open":
                raise ValueError("the case is closed")
            if case["resource_version"] != expected_version:
                raise ValueError("stale resource version")
            if actor.role == CaseActorRole.HR and not internal:
                mode = conn.execute(
                    "SELECT mode FROM case_interaction_modes WHERE case_id=?",
                    (case_id,),
                ).fetchone()
                if not mode or mode["mode"] != "direct_consented":
                    raise PermissionError(
                        "HR communicates through a Case Information Request or Case Resolution"
                    )
            ordinal = int(
                conn.execute(
                    "SELECT COALESCE(MAX(ordinal),0)+1 FROM case_messages WHERE case_id=?",
                    (case_id,),
                ).fetchone()[0]
            )
            visibility = "hr_internal" if internal else "shared"
            conn.execute(
                "INSERT INTO case_messages VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    case_id,
                    ordinal,
                    actor.role.value,
                    actor.actor_id,
                    visibility,
                    clean,
                    None,
                    now,
                ),
            )
            workflow_state = case["workflow_state"]
            if not internal:
                workflow_state = (
                    "waiting_for_hire"
                    if actor.role == CaseActorRole.HR
                    else "waiting_for_hr"
                )
            conn.execute(
                "UPDATE case_threads SET workflow_state=?,assigned_hr_user=COALESCE(?,assigned_hr_user) "
                "WHERE case_id=?",
                (
                    workflow_state,
                    actor.actor_id if actor.role == CaseActorRole.HR else None,
                    case_id,
                ),
            )
            conn.execute(
                "UPDATE escalation_cases SET resource_version=resource_version+1 WHERE case_id=?",
                (case_id,),
            )
            self._event(
                conn,
                case_id,
                "internal_note_added" if internal else "case_message_added",
                actor,
                {"visibility": visibility},
                now,
            )
            if not internal:
                audience = "hire" if actor.role == CaseActorRole.HR else "hr"
                recipient = case["hire_id"] if audience == "hire" else case["route_owner"]
                self._notification(
                    conn,
                    case_id,
                    audience,
                    recipient,
                    "case_reply",
                    f"{case['route_owner']} replied" if audience == "hire" else "The Hire replied",
                    now,
                )
        return self.get_thread(case_id, actor)

    def request_information(
        self,
        case_id: str,
        actor: CaseActor,
        question: str,
        *,
        expected_version: int,
    ) -> dict:
        """Create one HR-authored request that AISHA asks in the Hire thread."""
        if actor.role != CaseActorRole.HR:
            raise PermissionError("only HR can request case information")
        clean = " ".join(question.split())
        if not clean or len(clean) > 1000:
            raise ValueError("information request must contain 1 to 1000 characters")
        self.repo.validate_policy_message(clean)
        now = _utc_text()
        request_id = str(uuid.uuid4())
        with self.repo.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            case = self._case_row(conn, case_id)
            if case["status"] != "open":
                raise ValueError("the case is closed")
            if case["resource_version"] != expected_version:
                raise ValueError("stale resource version")
            if conn.execute(
                "SELECT 1 FROM case_information_requests WHERE case_id=? AND status='pending'",
                (case_id,),
            ).fetchone():
                raise ValueError("the case already has a pending information request")
            conn.execute(
                "INSERT INTO case_information_requests VALUES (?,?,?,?,?,NULL,?,NULL,1)",
                (request_id, case_id, clean, actor.actor_id, "pending", now),
            )
            ordinal = int(conn.execute(
                "SELECT COALESCE(MAX(ordinal),0)+1 FROM case_messages WHERE case_id=?",
                (case_id,),
            ).fetchone()[0])
            visible = f"AISHA needs one detail for HR: {clean}"
            conn.execute(
                "INSERT INTO case_messages VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), case_id, ordinal, "aisha", "aisha", "shared", visible, None, now),
            )
            conn.execute(
                "UPDATE case_threads SET workflow_state='waiting_for_hire',assigned_hr_user=? WHERE case_id=?",
                (actor.actor_id, case_id),
            )
            conn.execute(
                "UPDATE escalation_cases SET resource_version=resource_version+1 WHERE case_id=?",
                (case_id,),
            )
            self._event(conn, case_id, "information_requested", actor, {"request_id": request_id}, now)
            self._notification(
                conn, case_id, "hire", case["hire_id"], "case_reply",
                "AISHA needs one detail for your HR case", now,
            )
        return self.get_thread(case_id, actor)

    def answer_information_request(
        self,
        case_id: str,
        actor: CaseActor,
        answer: str,
        *,
        expected_version: int,
    ) -> dict:
        """Link a Hire answer to the one pending request and return the case to HR."""
        if actor.role != CaseActorRole.HIRE:
            raise PermissionError("only the Hire can answer a case information request")
        clean = " ".join(answer.split())
        if not clean or len(clean) > 2000:
            raise ValueError("information response must contain 1 to 2000 characters")
        self.repo.validate_policy_message(clean)
        now = _utc_text()
        with self.repo.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            case = self._case_row(conn, case_id)
            self._authorize(case, actor)
            if case["status"] != "open":
                raise ValueError("the case is closed")
            if case["resource_version"] != expected_version:
                raise ValueError("stale resource version")
            request = conn.execute(
                "SELECT * FROM case_information_requests WHERE case_id=? AND status='pending'",
                (case_id,),
            ).fetchone()
            if not request:
                raise ValueError("the case has no pending information request")
            conn.execute(
                "UPDATE case_information_requests SET status='answered',hire_response=?,answered_at_utc=?,"
                "resource_version=resource_version+1 WHERE request_id=?",
                (clean, now, request["request_id"]),
            )
            ordinal = int(conn.execute(
                "SELECT COALESCE(MAX(ordinal),0)+1 FROM case_messages WHERE case_id=?",
                (case_id,),
            ).fetchone()[0])
            conn.execute(
                "INSERT INTO case_messages VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), case_id, ordinal, "hire", actor.actor_id, "shared", clean, None, now),
            )
            conn.execute(
                "UPDATE case_threads SET workflow_state='waiting_for_hr' WHERE case_id=?",
                (case_id,),
            )
            conn.execute(
                "UPDATE escalation_cases SET resource_version=resource_version+1 WHERE case_id=?",
                (case_id,),
            )
            self._event(
                conn, case_id, "information_answered", actor,
                {"request_id": request["request_id"]}, now,
            )
            self._notification(
                conn, case_id, "hr", case["route_owner"], "case_reply",
                "The Hire answered AISHA's information request", now,
            )
        return self.get_thread(case_id, actor)

    def offer_direct_conversation(
        self, case_id: str, actor: CaseActor, *, expected_version: int
    ) -> dict:
        if actor.role != CaseActorRole.HR:
            raise PermissionError("only HR can offer direct conversation")
        now = _utc_text()
        with self.repo.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            case = self._case_row(conn, case_id)
            if case["status"] != "open" or case["resource_version"] != expected_version:
                raise ValueError("closed case or stale resource version")
            conn.execute(
                "UPDATE case_interaction_modes SET mode='direct_offered',offered_by_hr_user=?,"
                "offered_at_utc=?,resource_version=resource_version+1 WHERE case_id=?",
                (actor.actor_id, now, case_id),
            )
            conn.execute(
                "UPDATE escalation_cases SET resource_version=resource_version+1 WHERE case_id=?",
                (case_id,),
            )
            self._event(conn, case_id, "direct_conversation_offered", actor, {}, now)
            self._notification(
                conn, case_id, "hire", case["hire_id"], "case_reply",
                "HR offered an optional direct conversation", now,
            )
        return self.get_case(case_id, actor)

    def consent_direct_conversation(
        self, case_id: str, actor: CaseActor, *, expected_version: int
    ) -> dict:
        if actor.role != CaseActorRole.HIRE:
            raise PermissionError("only the Hire can consent to direct conversation")
        now = _utc_text()
        with self.repo.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            case = self._case_row(conn, case_id)
            self._authorize(case, actor)
            if case["status"] != "open" or case["resource_version"] != expected_version:
                raise ValueError("closed case or stale resource version")
            mode = conn.execute(
                "SELECT mode FROM case_interaction_modes WHERE case_id=?", (case_id,)
            ).fetchone()
            if not mode or mode["mode"] != "direct_offered":
                raise ValueError("direct conversation has not been offered")
            conn.execute(
                "UPDATE case_interaction_modes SET mode='direct_consented',consented_at_utc=?,"
                "resource_version=resource_version+1 WHERE case_id=?",
                (now, case_id),
            )
            conn.execute(
                "UPDATE escalation_cases SET resource_version=resource_version+1 WHERE case_id=?",
                (case_id,),
            )
            self._event(conn, case_id, "direct_conversation_consented", actor, {}, now)
        return self.get_case(case_id, actor)

    def resolve(
        self,
        case_id: str,
        actor: CaseActor,
        summary: str,
        *,
        expected_version: int,
    ) -> dict:
        from stai.clarifications import PolicyClarificationWorkflow
        from stai.models import CaseResolutionInput

        PolicyClarificationWorkflow(self.repo).resolve(
            case_id,
            actor,
            CaseResolutionInput(answer=summary),
            expected_version=expected_version,
        )
        return self.get_case(case_id, actor)

    def get_case(self, case_id: str, actor: CaseActor) -> dict:
        with self.repo.connection() as conn:
            case = self._case_row(conn, case_id)
            self._authorize(case, actor)
            policies = [
                row[0]
                for row in conn.execute(
                    "SELECT policy_id FROM escalation_case_policies WHERE case_id=? ORDER BY policy_id",
                    (case_id,),
                )
            ]
            unread = int(
                conn.execute(
                    "SELECT COUNT(*) FROM case_notifications WHERE case_id=? AND audience_role=? "
                    "AND read_at_utc IS NULL",
                    (case_id, "hire" if actor.role == CaseActorRole.HIRE else "hr"),
                ).fetchone()[0]
            )
        return {**dict(case), "policy_ids": policies, "unread_count": unread}

    def get_thread(self, case_id: str, actor: CaseActor) -> dict:
        case = self.get_case(case_id, actor)
        with self.repo.connection() as conn:
            sql = "SELECT * FROM case_messages WHERE case_id=?"
            params: tuple = (case_id,)
            if actor.role == CaseActorRole.HIRE:
                sql += " AND visibility='shared'"
            rows = conn.execute(sql + " ORDER BY ordinal", params).fetchall()
            requests = conn.execute(
                "SELECT * FROM case_information_requests WHERE case_id=? ORDER BY asked_at_utc,request_id",
                (case_id,),
            ).fetchall()
            mode = conn.execute(
                "SELECT * FROM case_interaction_modes WHERE case_id=?", (case_id,)
            ).fetchone()
        return {
            "case": case,
            "messages": [dict(row) for row in rows],
            "information_requests": [dict(row) for row in requests],
            "interaction_mode": dict(mode) if mode else {"mode": "mediated"},
        }

    def list_cases(
        self,
        actor: CaseActor,
        *,
        parent_conversation_id: str | None = None,
    ) -> list[dict]:
        with self.repo.connection() as conn:
            sql = (
                "SELECT c.*,t.parent_conversation_id,t.originating_message_id,t.sharing_active,"
                "t.workflow_state,t.assigned_hr_user,t.resolution_summary,t.resolved_at_utc "
                "FROM escalation_cases c LEFT JOIN case_threads t ON t.case_id=c.case_id WHERE 1=1"
            )
            params: list[str] = []
            if actor.role == CaseActorRole.HIRE:
                sql += " AND c.hire_id=?"
                params.append(actor.actor_id)
            if parent_conversation_id is not None:
                sql += " AND t.parent_conversation_id=?"
                params.append(parent_conversation_id)
            rows = conn.execute(sql + " ORDER BY c.created_at_utc DESC,c.case_id DESC", params).fetchall()
        return [self.get_case(row["case_id"], actor) for row in rows]

    def list_notifications(self, actor: CaseActor, *, unread_only: bool = False) -> list[dict]:
        audience = "hire" if actor.role == CaseActorRole.HIRE else "hr"
        with self.repo.connection() as conn:
            sql = "SELECT * FROM case_notifications WHERE audience_role=?"
            params: list[str] = [audience]
            if actor.role == CaseActorRole.HIRE:
                sql += " AND recipient_id=?"
                params.append(actor.actor_id)
            if unread_only:
                sql += " AND read_at_utc IS NULL"
            rows = conn.execute(sql + " ORDER BY created_at_utc DESC,notification_id DESC", params).fetchall()
        return [dict(row) for row in rows]

    def mark_notifications_read(self, case_id: str, actor: CaseActor) -> None:
        case = self.get_case(case_id, actor)
        audience = "hire" if actor.role == CaseActorRole.HIRE else "hr"
        with self.repo.connection() as conn:
            conn.execute(
                "UPDATE case_notifications SET read_at_utc=COALESCE(read_at_utc,?) "
                "WHERE case_id=? AND audience_role=?",
                (_utc_text(), case["case_id"], audience),
            )

    @staticmethod
    def _case_row(conn, case_id: str):
        row = conn.execute(
            "SELECT c.*,t.parent_conversation_id,t.originating_message_id,t.sharing_active,"
            "t.workflow_state,t.assigned_hr_user,t.resolution_summary,t.resolved_at_utc "
            "FROM escalation_cases c LEFT JOIN case_threads t ON t.case_id=c.case_id "
            "WHERE c.case_id=?",
            (case_id,),
        ).fetchone()
        if not row:
            raise KeyError("case not found")
        return row

    @staticmethod
    def _authorize(case, actor: CaseActor) -> None:
        if actor.role == CaseActorRole.HIRE and case["hire_id"] != actor.actor_id:
            raise PermissionError("the case belongs to another Hire")
        if actor.role not in {CaseActorRole.HIRE, CaseActorRole.HR, CaseActorRole.AISHA, CaseActorRole.SYSTEM}:
            raise PermissionError("unsupported case actor")

    @staticmethod
    def _event(conn, case_id: str, event_type: str, actor: CaseActor, payload: dict, now: str) -> None:
        conn.execute(
            "INSERT INTO case_events VALUES (?,?,?,?,?,?,?)",
            (
                str(uuid.uuid4()), case_id, event_type, actor.role.value,
                actor.actor_id, json.dumps(payload, sort_keys=True), now,
            ),
        )

    @staticmethod
    def _notification(
        conn,
        case_id: str,
        audience_role: str,
        recipient_id: str,
        kind: str,
        text: str,
        now: str,
    ) -> None:
        conn.execute(
            "INSERT INTO case_notifications VALUES (?,?,?,?,?,?,?,NULL)",
            (str(uuid.uuid4()), case_id, audience_role, recipient_id, kind, text, now),
        )

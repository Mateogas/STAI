"""Normalized SQLite repository for AISHA policy-domain state."""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterator

from stai.config import settings
from stai.models import HireProfile


MIGRATION_DIR = Path(__file__).with_name("migrations")
MIGRATION_PATHS = (
    MIGRATION_DIR / "0002_policy_domain.sql",
    MIGRATION_DIR / "0003_policy_turn_results.sql",
)


class MedicalContentRejected(ValueError):
    """Raised before certificate or medical content can enter chat persistence."""


class IdempotencyConflict(ValueError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_text(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat().replace("+00:00", "Z")

class Repo:
    def __init__(
        self,
        db_path: Path | str | None = None,
        *,
        secret_path: Path | str | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path else settings.db_path
        self.secret_path = Path(secret_path) if secret_path else self.db_path.with_suffix(".key")
        self.lock_path = self.db_path.with_suffix(".lock")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            for migration_path in MIGRATION_PATHS:
                conn.executescript(migration_path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations VALUES (?,?,?)",
                (2, "policy_domain", _utc_text()),
            )
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations VALUES (?,?,?)",
                (3, "policy_turn_results", _utc_text()),
            )
            conn.execute("PRAGMA user_version=3")
            self._seed_policy_state(conn)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Public read/test seam with the same connection PRAGMAs as all operations."""
        with self._connect() as conn:
            yield conn

    @property
    def schema_version(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("PRAGMA user_version").fetchone()[0])

    @contextmanager
    def installation_lock(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _seed_policy_state(self, conn: sqlite3.Connection) -> None:
        now = _utc_text()
        conn.execute(
            "INSERT OR IGNORE INTO hires VALUES (?,?,?,?)",
            ("emp-alyssa", "Alyssa", "Reyes", now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO hire_profiles VALUES (?,?,?,?,?,?,?)",
            (
                "emp-alyssa", "branch_banking_associate", "branch_banking",
                "probationary", "branch", 1, now,
            ),
        )
        conn.execute(
            "INSERT OR IGNORE INTO seed_manifests VALUES (?,?,?,?)",
            ("aisha_hire", "1.0", "alyssa-profile-v1", now),
        )
        conn.execute(
            "INSERT OR IGNORE INTO active_retrieval_build(singleton, generation) VALUES (1,0)"
        )

    def list_hire_ids(self) -> list[str]:
        with self._connect() as conn:
            return [r[0] for r in conn.execute("SELECT hire_id FROM hires ORDER BY hire_id")]

    def get_hire_profile(self, employee_id: str) -> HireProfile | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM hire_profiles WHERE hire_id=?", (employee_id,)).fetchone()
        if not row:
            return None
        return HireProfile(
            employee_id=row["hire_id"], role_key=row["role_key"],
            department_key=row["department_key"],
            employment_classification=row["employment_classification"],
            work_site=row["work_site"], revision=row["profile_revision"],
        )

    def create_policy_conversation(self, employee_id: str, simulated_date: date) -> dict:
        conversation_id = str(uuid.uuid4())
        now = _utc_text()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO policy_conversations VALUES (?,?,?,?,?,1)",
                (conversation_id, employee_id, simulated_date.isoformat(), now, now),
            )
        return {"id": conversation_id, "employee_id": employee_id, "simulated_date": simulated_date.isoformat(), "version": 1}

    @staticmethod
    def _reject_medical_chat(text: str) -> None:
        lowered = text.lower()
        markers = ("medical certificate", "diagnosis", "patient name", "clinician", "prescription", "laboratory result")
        if any(marker in lowered for marker in markers):
            raise MedicalContentRejected("medical content must use Certificate Check")

    def validate_policy_message(self, text: str) -> None:
        """Apply pre-persistence chat privacy rules at the turn seam."""
        self._reject_medical_chat(text)

    def add_policy_message(self, conversation_id: str, role: str, text: str, response_type: str | None = None) -> dict:
        if role == "hire":
            self._reject_medical_chat(text)
        message_id = str(uuid.uuid4())
        now = _utc_text()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM policy_messages WHERE conversation_id=?", (conversation_id,)).fetchone()
            ordinal = int(row[0])
            conn.execute(
                "INSERT INTO policy_messages VALUES (?,?,?,?,?,?,?)",
                (message_id, conversation_id, ordinal, role, text, response_type, now),
            )
            conn.execute("UPDATE policy_conversations SET updated_at_utc=?, resource_version=resource_version+1 WHERE conversation_id=?", (now, conversation_id))
        return {"id": message_id, "ordinal": ordinal, "role": role, "text": text}

    def list_policy_messages(self, conversation_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM policy_messages WHERE conversation_id=? ORDER BY ordinal", (conversation_id,)).fetchall()
        return [{"id": r["message_id"], "ordinal": r["ordinal"], "role": r["role"], "text": r["text"], "response_type": r["response_type"]} for r in rows]

    def get_policy_conversation(self, conversation_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM policy_conversations WHERE conversation_id=?", (conversation_id,)).fetchone()
        return dict(row) if row else None

    def list_policy_conversations(self, employee_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT conversation_id,hire_id,simulated_date,created_at_utc,updated_at_utc,resource_version "
                "FROM policy_conversations WHERE hire_id=? ORDER BY created_at_utc DESC,conversation_id DESC",
                (employee_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_policy_conversation(self, conversation_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM policy_conversations WHERE conversation_id=?", (conversation_id,))
            return cur.rowcount == 1

    def save_policy_response(
        self,
        conversation_id: str,
        response,
        *,
        dialogue_act: str = "question",
        resolved_topic: str | None = None,
        referenced_message_id: str | None = None,
        execution_mode: str = "deterministic",
    ) -> dict:
        """Atomically persist one typed assistant result and its safe context."""
        message_id = str(uuid.uuid4())
        now = _utc_text()
        payload = response.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT COALESCE(MAX(ordinal),0)+1 FROM policy_messages WHERE conversation_id=?",
                (conversation_id,),
            ).fetchone()
            message_ordinal = int(row[0])
            conn.execute(
                "INSERT INTO policy_messages VALUES (?,?,?,?,?,?,?)",
                (message_id, conversation_id, message_ordinal, "aisha", response.text, response.type, now),
            )
            conn.execute(
                "UPDATE policy_conversations SET updated_at_utc=?, resource_version=resource_version+1 WHERE conversation_id=?",
                (now, conversation_id),
            )
            profile_revision = int(
                conn.execute(
                    "SELECT profile_revision FROM hire_profiles WHERE hire_id='emp-alyssa'"
                ).fetchone()[0]
            )
            for citation in response.citations:
                conn.execute(
                    "INSERT OR IGNORE INTO policy_response_policies VALUES (?,?,?,?,?,?,?)",
                    (message_id, citation.policy_id, citation.handbook_version, "1", profile_revision, response.applicability.value, response.evidence_state.value),
                )
            for claim_ordinal, citation in enumerate(response.citations):
                conn.execute(
                    "INSERT INTO policy_response_citations VALUES (?,?,?,?,?,?)",
                    (message_id, claim_ordinal, citation.policy_id, citation.handbook_version, citation.page_start, citation.page_end),
                )
            conn.execute(
                "INSERT INTO policy_turn_results VALUES (?,?,?,?,?,?,?)",
                (
                    message_id,
                    response.type,
                    dialogue_act,
                    resolved_topic,
                    referenced_message_id,
                    execution_mode,
                    json.dumps(payload, sort_keys=True),
                ),
            )
        return {
            "id": message_id,
            "ordinal": message_ordinal,
            "role": "aisha",
            "text": response.text,
            "response_type": response.type,
        }

    def get_policy_response_payload(self, message_id: str) -> dict | None:
        with self._connect() as conn:
            persisted = conn.execute(
                "SELECT safe_payload_json FROM policy_turn_results WHERE message_id=?",
                (message_id,),
            ).fetchone()
            if persisted:
                return json.loads(persisted["safe_payload_json"])
            message = conn.execute(
                "SELECT * FROM policy_messages WHERE message_id=? AND role='aisha'", (message_id,)
            ).fetchone()
            if not message:
                return None
            policy = conn.execute(
                "SELECT handbook_version,applicability,evidence_state FROM policy_response_policies WHERE message_id=? ORDER BY policy_id LIMIT 1",
                (message_id,),
            ).fetchone()
            citations = [dict(row) for row in conn.execute(
                "SELECT policy_id,handbook_version,page_start,page_end FROM policy_response_citations WHERE message_id=? ORDER BY claim_ordinal",
                (message_id,),
            )]
            offer = conn.execute("SELECT * FROM escalation_offers WHERE message_id=?", (message_id,)).fetchone()
        response_type = message["response_type"] or "abstention"
        payload = {
            "type": response_type,
            "text": message["text"],
            "handbook_version": policy["handbook_version"] if policy else "1.0",
            "applicability": policy["applicability"] if policy else "applies",
            "evidence_state": policy["evidence_state"] if policy else "insufficient_evidence",
            "citations": citations,
        }
        if response_type == "abstention":
            payload["reason"] = "insufficient_evidence"
        elif response_type == "clarification_request":
            payload.update(question=message["text"], choices=[])
        elif response_type == "escalation_offer" and offer:
            payload.update(
                offer_id=offer["offer_id"], route_owner=offer["route_owner"],
                route_channel=offer["route_channel"], proposed_summary=offer["proposed_summary"],
                topic=offer["topic"], version=offer["resource_version"],
            )
        return payload

    def get_latest_turn_context(self, conversation_id: str) -> dict | None:
        """Return only the latest safe structured turn context."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT r.*,m.ordinal,m.text FROM policy_turn_results r "
                "JOIN policy_messages m ON m.message_id=r.message_id "
                "WHERE m.conversation_id=? ORDER BY m.ordinal DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("safe_payload_json"))
        return result

    def get_latest_escalation_confirmation(self, conversation_id: str) -> dict | None:
        """Return the newest safe case confirmation recorded in a conversation."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT r.safe_payload_json FROM policy_turn_results r "
                "JOIN policy_messages m ON m.message_id=r.message_id "
                "WHERE m.conversation_id=? AND r.result_type='escalation_confirmation' "
                "ORDER BY m.ordinal DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()
        return json.loads(row["safe_payload_json"]) if row else None

    def get_pending_escalation_offer_for_conversation(self, conversation_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM escalation_offers WHERE conversation_id=? AND status='pending' "
                "ORDER BY created_at_utc DESC LIMIT 1",
                (conversation_id,),
            ).fetchone()
            if not row:
                return None
            policies = [
                item[0]
                for item in conn.execute(
                    "SELECT policy_id FROM escalation_offer_policies WHERE offer_id=? ORDER BY policy_id",
                    (row["offer_id"],),
                )
            ]
        return {**dict(row), "policy_ids": policies}

    def create_escalation_offer(
        self, conversation_id: str, message_id: str, topic: str,
        route_owner: str, route_channel: str, summary: str, policy_ids: list[str],
    ) -> dict:
        offer_id = str(uuid.uuid4())
        now = _utc_now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO escalation_offers VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
                (offer_id, "emp-alyssa", conversation_id, message_id, topic, route_owner, route_channel, summary, "pending", _utc_text(now + timedelta(hours=24)), _utc_text(now)),
            )
            for policy_id in policy_ids:
                conn.execute("INSERT INTO escalation_offer_policies VALUES (?,?)", (offer_id, policy_id))
        return {"offer_id": offer_id, "topic": topic, "route_owner": route_owner, "route_channel": route_channel, "proposed_summary": summary, "version": 1}

    def get_escalation_offer(self, offer_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM escalation_offers WHERE offer_id=?", (offer_id,)).fetchone()
        if not row:
            return None
        return {
            "type": "escalation_offer", "text": "I can create this privacy-safe case after you consent.",
            "handbook_version": "1.0", "applicability": "applies", "evidence_state": "ready",
            "citations": [], "offer_id": row["offer_id"], "route_owner": row["route_owner"],
            "route_channel": row["route_channel"], "proposed_summary": row["proposed_summary"],
            "topic": row["topic"], "version": row["resource_version"],
        }

    def consent_escalation_offer(self, offer_id: str, *, expected_version: int) -> dict:
        case_id = str(uuid.uuid4())
        now = _utc_text()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            offer = conn.execute("SELECT * FROM escalation_offers WHERE offer_id=?", (offer_id,)).fetchone()
            if not offer:
                raise KeyError("offer not found")
            if offer["resource_version"] != expected_version:
                raise ValueError("stale resource version")
            policies = [r[0] for r in conn.execute("SELECT policy_id FROM escalation_offer_policies WHERE offer_id=?", (offer_id,))]
            conn.execute(
                "INSERT INTO escalation_cases VALUES (?,?,?,?,?,?,'open',?,?,?,1)",
                (case_id, offer["hire_id"], offer["topic"], offer["proposed_summary"], offer["route_owner"], offer["route_channel"], now, None, None),
            )
            for policy_id in policies:
                conn.execute("INSERT INTO escalation_case_policies VALUES (?,?)", (case_id, policy_id))
            conn.execute("DELETE FROM escalation_offers WHERE offer_id=?", (offer_id,))
        return {"case_id": case_id, "status": "open", "approved_summary": offer["proposed_summary"], "route_owner": offer["route_owner"], "route_channel": offer["route_channel"], "version": 1}

    def list_escalation_cases(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM escalation_cases ORDER BY created_at_utc DESC, case_id DESC").fetchall()
        return [dict(row) for row in rows]

    def get_escalation_case(self, case_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM escalation_cases WHERE case_id=?", (case_id,)).fetchone()
            if not row:
                return None
            policy_ids = [item[0] for item in conn.execute(
                "SELECT policy_id FROM escalation_case_policies WHERE case_id=? ORDER BY policy_id", (case_id,)
            )]
        return {**dict(row), "policy_ids": policy_ids}

    def close_escalation_case(self, case_id: str, *, expected_version: int, hr_user: str) -> dict:
        now = _utc_text()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM escalation_cases WHERE case_id=?", (case_id,)).fetchone()
            if not row:
                raise KeyError("case not found")
            if row["resource_version"] != expected_version:
                raise ValueError("stale resource version")
            conn.execute(
                "UPDATE escalation_cases SET status='closed',closed_at_utc=?,closing_hr_user=?,resource_version=resource_version+1 WHERE case_id=?",
                (now, hr_user, case_id),
            )
        return self.get_escalation_case(case_id)

    def create_attribute_change_request(self, employee_id: str, attribute_name: str, proposed_value: str, *, consent: bool) -> dict:
        if not consent:
            raise ValueError("explicit consent required")
        allowed = {
            "role_key": {"branch_banking_associate", "client_service_associate", "digital_banking_support_associate"},
            "department_key": {"branch_banking", "branch_operations", "digital_channels"},
            "employment_classification": {"probationary", "regular", "fixed_term"},
            "work_site": {"branch", "head_office", "remote"},
        }
        if attribute_name not in allowed or proposed_value not in allowed[attribute_name]:
            raise ValueError("invalid closed attribute value")
        profile = self.get_hire_profile(employee_id)
        request_id = str(uuid.uuid4())
        now = _utc_text()
        current = getattr(profile, attribute_name)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO attribute_change_requests VALUES (?,?,?,?,?,?,'pending',?,?,?,1)",
                (request_id, employee_id, attribute_name, current, proposed_value, profile.revision, None, now, None),
            )
        return {"request_id": request_id, "status": "pending", "attribute_name": attribute_name, "current_value": current, "proposed_value": proposed_value, "version": 1}

    def resolve_attribute_change_request(self, request_id: str, *, approve: bool, expected_version: int, expected_profile_revision: int, hr_user: str) -> dict:
        now = _utc_text()
        status = "approved" if approve else "rejected"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            request = conn.execute("SELECT * FROM attribute_change_requests WHERE request_id=?", (request_id,)).fetchone()
            if not request:
                raise KeyError("request not found")
            if request["resource_version"] != expected_version or request["profile_revision"] != expected_profile_revision:
                raise ValueError("stale resource version")
            if approve:
                profile = conn.execute("SELECT * FROM hire_profiles WHERE hire_id=?", (request["hire_id"],)).fetchone()
                if profile["profile_revision"] != expected_profile_revision:
                    raise ValueError("stale profile revision")
                column = request["attribute_name"]
                conn.execute(f"UPDATE hire_profiles SET {column}=?, profile_revision=profile_revision+1, updated_at_utc=? WHERE hire_id=?", (request["proposed_value"], now, request["hire_id"]))
                conn.execute("INSERT INTO hire_attribute_revisions VALUES (?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), request["hire_id"], column, request["current_value"], request["proposed_value"], expected_profile_revision + 1, hr_user, now))
            conn.execute("UPDATE attribute_change_requests SET status=?, confirming_hr_user=?, resolved_at_utc=?, resource_version=resource_version+1 WHERE request_id=?", (status, hr_user, now, request_id))
        return {"request_id": request_id, "status": status, "version": expected_version + 1}

    def list_attribute_change_requests(self, employee_id: str | None = None) -> list[dict]:
        query = "SELECT * FROM attribute_change_requests"
        params: tuple = ()
        if employee_id:
            query += " WHERE hire_id=?"; params = (employee_id,)
        query += " ORDER BY created_at_utc DESC,request_id DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_attribute_change_request(self, request_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM attribute_change_requests WHERE request_id=?", (request_id,)).fetchone()
        return dict(row) if row else None

    def create_validation_result(
        self, *, status: str, missing_codes: list[str], inconsistency_codes: list[str],
        warning_codes: list[str], review_codes: list[str], evaluation_date: date,
        fingerprint: str | None, attempt_count: int = 1,
    ) -> dict:
        validation_id = str(uuid.uuid4())
        now = _utc_text()
        profile_revision = self.get_hire_profile("emp-alyssa").revision
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if fingerprint:
                existing = conn.execute(
                    "SELECT validation_id FROM validation_results WHERE hire_id='emp-alyssa' AND policy_id='HRP-004' "
                    "AND handbook_version='1.0' AND profile_revision=? AND document_fingerprint=? ORDER BY created_at_utc DESC LIMIT 1",
                    (profile_revision, fingerprint),
                ).fetchone()
                if existing:
                    return self.get_validation_result(existing[0])
            conn.execute(
                "INSERT INTO validation_results VALUES (?,?,?,?,?,?,?,?,?,?,?, ?,1)",
                (validation_id, "emp-alyssa", status, "HRP-004", "1.0", profile_revision, attempt_count, evaluation_date.isoformat(), now, fingerprint, "private", None),
            )
            ordinal = 0
            for family, codes in (("missing", missing_codes), ("inconsistency", inconsistency_codes), ("warning", warning_codes), ("human_review", review_codes)):
                for code in codes:
                    conn.execute("INSERT INTO validation_result_codes VALUES (?,?,?,?)", (validation_id, family, code, ordinal))
                    ordinal += 1
            conn.execute("INSERT INTO validation_result_citations VALUES (?,?,?,?,?)", (validation_id, "HRP-004", "1.0", 78, None))
        return self.get_validation_result(validation_id)

    def _set_validation_share(self, validation_id: str, *, share: bool, expected_version: int) -> dict:
        now = _utc_text()
        state = "shared" if share else "private"
        with self._connect() as conn:
            result = conn.execute("SELECT * FROM validation_results WHERE validation_id=?", (validation_id,)).fetchone()
            if not result:
                raise KeyError("result not found")
            if result["resource_version"] != expected_version:
                raise ValueError("stale resource version")
            conn.execute("UPDATE validation_results SET share_state=?, shared_at_utc=?, resource_version=resource_version+1 WHERE validation_id=?", (state, now if share else None, validation_id))
        return {"validation_id": validation_id, "share_state": state, "version": expected_version + 1}

    def list_shared_validation_results(self) -> list[dict]:
        return self.list_validation_results(shared_only=True)

    def get_validation_result(self, validation_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT validation_id,hire_id,status,policy_id,handbook_version,profile_revision,accepted_attempt_count,"
                "simulated_evaluation_date,created_at_utc,share_state,shared_at_utc,resource_version "
                "FROM validation_results WHERE validation_id=?", (validation_id,),
            ).fetchone()
            if not row:
                return None
            codes = [
                {"family": item[0], "code": item[1]}
                for item in conn.execute(
                    "SELECT code_family,code FROM validation_result_codes WHERE validation_id=? ORDER BY ordinal",
                    (validation_id,),
                )
            ]
            citations = [
                {"policy_id": item[0], "handbook_version": item[1], "page_start": item[2], "page_end": item[3]}
                for item in conn.execute(
                    "SELECT policy_id,handbook_version,page_start,page_end FROM validation_result_citations WHERE validation_id=? ORDER BY page_start",
                    (validation_id,),
                )
            ]
        return {
            **dict(row), "codes": codes, "citations": citations,
            "disclaimer": "Local completeness check only—not authenticity, approval, or medical assessment.",
            "official_hr_document_route": "Submit the original separately through the fictional Official HR Document Route.",
        }

    def list_validation_results(self, employee_id: str = "emp-alyssa", *, shared_only: bool = False) -> list[dict]:
        query = "SELECT validation_id FROM validation_results WHERE hire_id=?"
        params: list = [employee_id]
        if shared_only:
            query += " AND share_state='shared'"
        query += " ORDER BY created_at_utc DESC,validation_id DESC"
        with self._connect() as conn:
            ids = [row[0] for row in conn.execute(query, params)]
        return [self.get_validation_result(validation_id) for validation_id in ids]

    def create_retry_session(self, fingerprint: str) -> str:
        token = uuid.uuid4().hex + uuid.uuid4().hex
        root = self.ensure_installation_key()
        digest = hmac.new(root, f"retry:{token}".encode(), hashlib.sha256).hexdigest()
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO certificate_retry_sessions VALUES (?,?,?,?,?,?,?,?,?)",
                (digest, "emp-alyssa", "HRP-004", "1.0", self.get_hire_profile("emp-alyssa").revision,
                 fingerprint, 1, _utc_text(now), _utc_text(now + timedelta(minutes=15))),
            )
        return token

    def consume_retry_session(self, token: str) -> dict:
        root = self.ensure_installation_key()
        digest = hmac.new(root, f"retry:{token}".encode(), hashlib.sha256).hexdigest()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM certificate_retry_sessions WHERE token_digest=?", (digest,)).fetchone()
            if not row or datetime.fromisoformat(row["expires_at_utc"].replace("Z", "+00:00")) <= _utc_now():
                if row:
                    conn.execute("DELETE FROM certificate_retry_sessions WHERE token_digest=?", (digest,))
                raise KeyError("retry token not found")
            conn.execute("DELETE FROM certificate_retry_sessions WHERE token_digest=?", (digest,))
        return dict(row)

    def delete_validation_result(self, validation_id: str, *, expected_version: int) -> bool:
        with self._connect() as conn:
            result = conn.execute("SELECT resource_version FROM validation_results WHERE validation_id=?", (validation_id,)).fetchone()
            if not result:
                return False
            if result[0] != expected_version:
                raise ValueError("stale resource version")
            conn.execute("DELETE FROM validation_results WHERE validation_id=?", (validation_id,))
        return True

    def check_idempotency(self, scope: str, key: str, canonical_request: str) -> dict | None:
        root = self.ensure_installation_key()
        key_digest = hmac.new(root, f"idempotency-key:{key}".encode(), hashlib.sha256).hexdigest()
        request_digest = hmac.new(root, f"idempotency-request:{canonical_request}".encode(), hashlib.sha256).hexdigest()
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM idempotency_records WHERE operation_scope=? AND key_digest=?", (scope, key_digest)).fetchone()
        if not row:
            return None
        if row["request_digest"] != request_digest:
            raise IdempotencyConflict("idempotency key reused with different input")
        return dict(row)

    def save_idempotency(
        self, scope: str, key: str, canonical_request: str, *,
        target_type: str, target_id: str, target_version: int | None,
        http_status: int, outcome_code: str,
    ) -> None:
        root = self.ensure_installation_key()
        key_digest = hmac.new(root, f"idempotency-key:{key}".encode(), hashlib.sha256).hexdigest()
        request_digest = hmac.new(root, f"idempotency-request:{canonical_request}".encode(), hashlib.sha256).hexdigest()
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO idempotency_records VALUES (?,?,?,?,?,?,?,?,?,?)",
                (scope, key_digest, request_digest, target_type, target_id, target_version, http_status, outcome_code, _utc_text(now), _utc_text(now + timedelta(hours=24))),
            )

    def register_retrieval_build(self, build_id: str, handbook_version: str, manifest_identity: str, collection_name: str, *, verified: bool) -> None:
        now = _utc_text()
        state = "verified" if verified else "staging"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO retrieval_builds VALUES (?,?,?,?,?,?,?,?,?)",
                (build_id, handbook_version, manifest_identity, collection_name, "production", state, now, now if verified else None, None),
            )

    def activate_retrieval_build(self, build_id: str) -> dict:
        now = _utc_text()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            build = conn.execute("SELECT * FROM retrieval_builds WHERE build_id=? AND lifecycle_state IN ('verified','previous') AND build_kind='production'", (build_id,)).fetchone()
            if not build:
                raise ValueError("only a verified production build can be activated")
            pointer = conn.execute("SELECT * FROM active_retrieval_build WHERE singleton=1").fetchone()
            previous = pointer["active_build_id"]
            if previous:
                conn.execute("UPDATE retrieval_builds SET lifecycle_state='previous' WHERE build_id=?", (previous,))
            conn.execute("UPDATE retrieval_builds SET lifecycle_state='active', activated_at_utc=? WHERE build_id=?", (now, build_id))
            conn.execute("UPDATE active_retrieval_build SET active_build_id=?, previous_build_id=?, generation=generation+1, switched_at_utc=? WHERE singleton=1", (build_id, previous, now))
        return self.get_active_retrieval_build()

    def get_active_retrieval_build(self) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT p.generation, p.previous_build_id, b.* FROM active_retrieval_build p LEFT JOIN retrieval_builds b ON b.build_id=p.active_build_id WHERE p.singleton=1").fetchone()
        return dict(row) if row and row["build_id"] else None

    def rollback_retrieval_build(self) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT previous_build_id FROM active_retrieval_build WHERE singleton=1").fetchone()
        if not row or not row[0]:
            raise ValueError("no previous verified build")
        return self.activate_retrieval_build(row[0])

    def put_holiday_cache(self, year: int, payload: list[dict]) -> None:
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO holiday_cache VALUES ('nager','PH',?,?,?,?)",
                (year, json.dumps(payload, sort_keys=True), _utc_text(now), _utc_text(now + timedelta(days=7))),
            )

    def get_holiday_cache(self, year: int) -> list[dict] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload_json, expires_at_utc FROM holiday_cache WHERE provider='nager' AND country='PH' AND year=?", (year,)).fetchone()
            if not row or datetime.fromisoformat(row["expires_at_utc"].replace("Z", "+00:00")) <= _utc_now():
                if row:
                    conn.execute("DELETE FROM holiday_cache WHERE provider='nager' AND country='PH' AND year=?", (year,))
                return None
        return json.loads(row["payload_json"])

    def insert_test_validation_result(self, validation_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO validation_results VALUES (?,?,?,?,?,?,?,?,?,?,?, ?,1)",
                (validation_id, "emp-alyssa", "complete", "HRP-004", "1.0", 1, 1, "2026-08-10", _utc_text(), "test-fingerprint", "private", None),
            )

    def count_validation_results(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM validation_results").fetchone()[0])

    def ensure_installation_key(self) -> bytes:
        if self.secret_path.exists():
            return self.secret_path.read_bytes()
        if self.count_validation_results():
            raise RuntimeError("certificate checking is disabled: installation key is missing while results remain")
        self.secret_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.secret_path.with_suffix(".new")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        key = os.urandom(32)
        try:
            os.write(fd, key)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary, self.secret_path)
        os.chmod(self.secret_path, 0o600)
        return key

    def full_demo_reset(self) -> None:
        with self.installation_lock():
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                for table in (
                    "idempotency_records", "certificate_retry_sessions", "validation_results",
                    "escalation_cases", "escalation_offers", "attribute_change_requests",
                    "hire_attribute_revisions", "policy_conversations", "holiday_cache",
                ):
                    conn.execute(f"DELETE FROM {table}")
                conn.execute("DELETE FROM hire_profiles")
                conn.execute("DELETE FROM hires")
                self._seed_policy_state(conn)
            if self.secret_path.exists():
                self.secret_path.unlink()
            self.ensure_installation_key()
            with self._connect() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
def cutover_legacy_database(db_path: Path | str, *, verifier: Callable[[Repo], bool]) -> None:
    """Build and verify a sibling current-epoch database before atomic replacement."""
    target = Path(db_path)
    sibling = target.with_suffix(target.suffix + ".next")
    if sibling.exists():
        sibling.unlink()
    candidate = Repo(sibling, secret_path=target.with_suffix(".key"))
    if not verifier(candidate):
        sibling.unlink(missing_ok=True)
        raise RuntimeError("replacement verification failed")
    with sibling.open("rb") as stream:
        os.fsync(stream.fileno())
    os.replace(sibling, target)

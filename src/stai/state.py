"""SQLite repository for all per-employee state.

Design notes:
- stdlib ``sqlite3``, no ORM — the schema is four small tables.
- A fresh connection per operation keeps things safe across Streamlit's
  script-runner threads (SQLite connections are not thread-portable).
- ``seed_if_empty`` loads employees + role plan templates from the JSON data
  files exactly once; deleting the .db file resets the whole demo.
"""

from __future__ import annotations

import fcntl
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterator

from stai.config import settings
from stai.models import (
    PHASE_LABELS,
    PHASE_ORDER,
    ChatMessage,
    ChecklistItem,
    Employee,
    Escalation,
    PlanPhase,
    PulseRecord,
    PulseResult,
    HireProfile,
)


MIGRATION_PATH = Path(__file__).with_name("migrations") / "0002_policy_domain.sql"


class MedicalContentRejected(ValueError):
    """Raised before certificate or medical content can enter chat persistence."""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_text(value: datetime | None = None) -> str:
    return (value or _utc_now()).isoformat().replace("+00:00", "Z")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL,
    role_key    TEXT NOT NULL,
    department  TEXT NOT NULL,
    start_date  TEXT NOT NULL,
    email       TEXT DEFAULT '',
    manager     TEXT DEFAULT '',
    buddy       TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS plan_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    phase       TEXT NOT NULL,
    title       TEXT NOT NULL,
    done        INTEGER NOT NULL DEFAULT 0,
    done_at     TEXT,
    sort        INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS escalations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    question    TEXT NOT NULL,
    details     TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL REFERENCES employees(id),
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    kind        TEXT DEFAULT '',
    sources     TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pulse_checkins (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id  TEXT NOT NULL REFERENCES employees(id),
    checkin_date TEXT NOT NULL,
    sentiment    INTEGER NOT NULL,
    concerns     TEXT NOT NULL DEFAULT '[]',
    summary      TEXT DEFAULT '',
    raw_reply    TEXT DEFAULT ''
);
"""


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
            conn.executescript(_SCHEMA)
            conn.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations VALUES (?,?,?)",
                (2, "policy_domain", _utc_text()),
            )
            conn.execute("PRAGMA user_version=2")
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

    def delete_policy_conversation(self, conversation_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM policy_conversations WHERE conversation_id=?", (conversation_id,))
            return cur.rowcount == 1

    def save_policy_response(self, conversation_id: str, response) -> dict:
        message = self.add_policy_message(conversation_id, "aisha", response.text, response.type)
        with self._connect() as conn:
            for citation in response.citations:
                conn.execute(
                    "INSERT OR IGNORE INTO policy_response_policies VALUES (?,?,?,?,?,?,?)",
                    (message["id"], citation.policy_id, citation.handbook_version, "1", self.get_hire_profile("emp-alyssa").revision, response.applicability.value, response.evidence_state.value),
                )
            for ordinal, citation in enumerate(response.citations):
                conn.execute(
                    "INSERT INTO policy_response_citations VALUES (?,?,?,?,?,?)",
                    (message["id"], ordinal, citation.policy_id, citation.handbook_version, citation.page_start, citation.page_end),
                )
        return message

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

    def create_validation_result(
        self, *, status: str, missing_codes: list[str], inconsistency_codes: list[str],
        warning_codes: list[str], review_codes: list[str], evaluation_date: date,
        fingerprint: str | None, attempt_count: int = 1,
    ) -> dict:
        validation_id = str(uuid.uuid4())
        now = _utc_text()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO validation_results VALUES (?,?,?,?,?,?,?,?,?,?,?, ?,1)",
                (validation_id, "emp-alyssa", status, "HRP-004", "1.0", self.get_hire_profile("emp-alyssa").revision, attempt_count, evaluation_date.isoformat(), now, fingerprint, "private", None),
            )
            ordinal = 0
            for family, codes in (("missing", missing_codes), ("inconsistency", inconsistency_codes), ("warning", warning_codes), ("human_review", review_codes)):
                for code in codes:
                    conn.execute("INSERT INTO validation_result_codes VALUES (?,?,?,?)", (validation_id, family, code, ordinal))
                    ordinal += 1
            conn.execute("INSERT INTO validation_result_citations VALUES (?,?,?,?,?)", (validation_id, "HRP-004", "1.0", 78, None))
        return {"validation_id": validation_id, "status": status, "share_state": "private", "version": 1}

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
        with self._connect() as conn:
            rows = conn.execute("SELECT validation_id,status,policy_id,handbook_version,created_at_utc,shared_at_utc,resource_version FROM validation_results WHERE share_state='shared' ORDER BY created_at_utc DESC, validation_id DESC").fetchall()
            output = []
            for row in rows:
                codes = [dict(family=c[0], code=c[1]) for c in conn.execute("SELECT code_family,code FROM validation_result_codes WHERE validation_id=? ORDER BY ordinal", (row["validation_id"],))]
                output.append({**dict(row), "codes": codes})
        return output

    def delete_validation_result(self, validation_id: str, *, expected_version: int) -> bool:
        with self._connect() as conn:
            result = conn.execute("SELECT resource_version FROM validation_results WHERE validation_id=?", (validation_id,)).fetchone()
            if not result:
                return False
            if result[0] != expected_version:
                raise ValueError("stale resource version")
            conn.execute("DELETE FROM validation_results WHERE validation_id=?", (validation_id,))
        return True

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
    # ------------------------------------------------------------------ seed

    def seed_if_empty(
        self,
        employees_file: Path | None = None,
        plans_file: Path | None = None,
    ) -> bool:
        """Load employees + instantiate their role plan templates. Idempotent."""
        with self._connect() as conn:
            if conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]:
                return False
        employees = json.loads(
            Path(employees_file or settings.employees_file).read_text(encoding="utf-8")
        )
        plans = json.loads(Path(plans_file or settings.plans_file).read_text(encoding="utf-8"))
        with self._connect() as conn:
            for emp in employees:
                conn.execute(
                    "INSERT INTO employees (id, name, role, role_key, department, start_date,"
                    " email, manager, buddy) VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        emp["id"], emp["name"], emp["role"], emp["role_key"],
                        emp["department"], emp["start_date"], emp.get("email", ""),
                        emp.get("manager", ""), emp.get("buddy", ""),
                    ),
                )
                template = plans.get(emp["role_key"], {})
                sort = 0
                for phase in PHASE_ORDER:
                    for title in template.get(phase, []):
                        conn.execute(
                            "INSERT INTO plan_items (employee_id, phase, title, sort)"
                            " VALUES (?,?,?,?)",
                            (emp["id"], phase, title, sort),
                        )
                        sort += 1
        return True

    # ------------------------------------------------------------- employees

    def list_employees(self) -> list[Employee]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM employees ORDER BY start_date").fetchall()
        return [Employee(**dict(r)) for r in rows]

    def get_employee(self, employee_id: str) -> Employee | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM employees WHERE id = ?", (employee_id,)
            ).fetchone()
        return Employee(**dict(row)) if row else None

    # ------------------------------------------------------------------ plan

    def list_plan_items(self, employee_id: str) -> list[ChecklistItem]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM plan_items WHERE employee_id = ? ORDER BY sort",
                (employee_id,),
            ).fetchall()
        return [self._to_item(r) for r in rows]

    def get_plan(self, employee_id: str) -> list[PlanPhase]:
        items = self.list_plan_items(employee_id)
        phases = []
        for key in PHASE_ORDER:
            phase_items = [i for i in items if i.phase == key]
            if phase_items:
                phases.append(PlanPhase(key=key, label=PHASE_LABELS[key], items=phase_items))
        return phases

    def complete_task(self, employee_id: str, item_id: int) -> ChecklistItem | None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE plan_items SET done = 1, done_at = ? WHERE id = ? AND employee_id = ?",
                (datetime.now().isoformat(timespec="seconds"), item_id, employee_id),
            )
            row = conn.execute(
                "SELECT * FROM plan_items WHERE id = ? AND employee_id = ?",
                (item_id, employee_id),
            ).fetchone()
        return self._to_item(row) if row else None

    def progress(self, employee_id: str) -> tuple[int, int]:
        """(done, total) across the whole plan."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(done), 0), COUNT(*) FROM plan_items WHERE employee_id = ?",
                (employee_id,),
            ).fetchone()
        return int(row[0]), int(row[1])

    @staticmethod
    def _to_item(row: sqlite3.Row) -> ChecklistItem:
        d = dict(row)
        d.pop("sort", None)
        d["done"] = bool(d["done"])
        return ChecklistItem(**d)

    # ----------------------------------------------------------- escalations

    def add_escalation(self, employee_id: str, question: str, details: str = "") -> Escalation:
        created = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO escalations (employee_id, question, details, created_at)"
                " VALUES (?,?,?,?)",
                (employee_id, question, details, created),
            )
            esc_id = cur.lastrowid
        return Escalation(
            id=esc_id, employee_id=employee_id, question=question,
            details=details, status="open", created_at=created,
        )

    def list_escalations(self, status: str | None = None) -> list[Escalation]:
        query = "SELECT * FROM escalations"
        params: tuple = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [Escalation(**dict(r)) for r in rows]

    def resolve_escalation(self, escalation_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE escalations SET status = 'resolved' WHERE id = ?", (escalation_id,)
            )
            return cur.rowcount > 0

    # ---------------------------------------------------------- chat memory

    def add_chat_message(
        self,
        employee_id: str,
        role: str,
        content: str,
        kind: str = "",
        sources: list[dict] | None = None,
    ) -> ChatMessage:
        created = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO chat_messages (employee_id, role, content, kind, sources,"
                " created_at) VALUES (?,?,?,?,?,?)",
                (employee_id, role, content, kind, json.dumps(sources or []), created),
            )
            msg_id = cur.lastrowid
        return ChatMessage(
            id=msg_id, employee_id=employee_id, role=role, content=content,
            kind=kind, sources=sources or [], created_at=created,
        )

    def list_chat_messages(
        self, employee_id: str, limit: int | None = None
    ) -> list[ChatMessage]:
        """Chronological history; with ``limit``, only the most recent N."""
        query = "SELECT * FROM chat_messages WHERE employee_id = ? ORDER BY id"
        with self._connect() as conn:
            rows = conn.execute(query, (employee_id,)).fetchall()
        if limit is not None:
            rows = rows[-limit:]
        messages = []
        for r in rows:
            d = dict(r)
            d["sources"] = json.loads(d["sources"] or "[]")
            messages.append(ChatMessage(**d))
        return messages

    def clear_chat_messages(self, employee_id: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM chat_messages WHERE employee_id = ?", (employee_id,)
            )
            return cur.rowcount

    # ----------------------------------------------------------------- pulse

    def add_pulse(
        self,
        employee_id: str,
        checkin_date: date,
        result: PulseResult,
        raw_reply: str = "",
    ) -> PulseRecord:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO pulse_checkins (employee_id, checkin_date, sentiment, concerns,"
                " summary, raw_reply) VALUES (?,?,?,?,?,?)",
                (
                    employee_id, checkin_date.isoformat(), result.sentiment,
                    json.dumps(result.concerns), result.summary, raw_reply,
                ),
            )
            rec_id = cur.lastrowid
        return PulseRecord(
            id=rec_id, employee_id=employee_id, checkin_date=checkin_date,
            sentiment=result.sentiment, concerns=result.concerns,
            summary=result.summary, raw_reply=raw_reply,
        )

    def pulse_history(self, employee_id: str) -> list[PulseRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM pulse_checkins WHERE employee_id = ? ORDER BY checkin_date",
                (employee_id,),
            ).fetchall()
        records = []
        for r in rows:
            d = dict(r)
            d["concerns"] = json.loads(d["concerns"] or "[]")
            records.append(PulseRecord(**d))
        return records

    def last_checkin_date(self, employee_id: str) -> date | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(checkin_date) FROM pulse_checkins WHERE employee_id = ?",
                (employee_id,),
            ).fetchone()
        return date.fromisoformat(row[0]) if row and row[0] else None


def cutover_legacy_database(db_path: Path | str, *, verifier: Callable[[Repo], bool]) -> None:
    """Build and verify a sibling epoch-2 database before atomic replacement."""
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

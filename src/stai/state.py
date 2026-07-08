"""SQLite repository for all per-employee state.

Design notes:
- stdlib ``sqlite3``, no ORM — the schema is four small tables.
- A fresh connection per operation keeps things safe across Streamlit's
  script-runner threads (SQLite connections are not thread-portable).
- ``seed_if_empty`` loads employees + role plan templates from the JSON data
  files exactly once; deleting the .db file resets the whole demo.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

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
)

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
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = Path(db_path) if db_path else settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

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

"""Linux-image smoke: UI, API, policy turn, certificate and volume permissions."""

from __future__ import annotations

import io
import os
import stat
import subprocess
import time

import httpx
from reportlab.pdfgen.canvas import Canvas


def wait(url: str) -> httpx.Response:
    for _ in range(80):
        try:
            response = httpx.get(url, timeout=1)
            if response.status_code < 500:
                return response
        except httpx.HTTPError:
            pass
        time.sleep(.25)
    raise RuntimeError(f"service did not become ready: {url}")


def certificate() -> bytes:
    buffer = io.BytesIO(); canvas = Canvas(buffer)
    for index, line in enumerate([
        "Patient Name: Alyssa Reyes", "Consultation Date: 08/08/2026",
        "Issue Date: 08/09/2026", "Absence Start Date: 08/08/2026",
        "Absence End Date: 08/10/2026", "Duration Days: 3",
        "Clinician Name: Dr. Sample Physician", "Facility Name: Synthetic Care Clinic",
        "License Number: DEMO-123", "Signature: Present", "Recommendation: Rest",
    ]):
        canvas.drawString(72, 740 - index * 20, line)
    canvas.save(); return buffer.getvalue()


def main() -> None:
    env = {**os.environ, "STAI_DB_PATH": "/app/data/smoke.db", "STAI_OBS_LOG_PATH": "/app/data/smoke-events.jsonl"}
    api = subprocess.Popen(["uv", "run", "uvicorn", "stai.api:app", "--host", "127.0.0.1", "--port", "8000"], env=env)
    ui = subprocess.Popen(["uv", "run", "streamlit", "run", "app.py", "--server.address=127.0.0.1", "--server.port=8501", "--server.headless=true"], env=env)
    try:
        health = wait("http://127.0.0.1:8000/api/v1/health")
        assert health.status_code == 200 and health.json()["data"]["status"] in {"ready", "degraded"}
        assert wait("http://127.0.0.1:8501/_stcore/health").text.strip() == "ok"
        headers = {"Idempotency-Key": "linux-smoke-conversation"}
        conversation = httpx.post(
            "http://127.0.0.1:8000/api/v1/hires/emp-alyssa/conversations",
            headers=headers, json={"simulated_date": "2026-08-10"}, timeout=10,
        ).json()["data"]
        prompts = [
            "Whats my payroll", "Well then how do i do the onboard",
            "How to i put my payroll details", "I need help in this",
            "route it please", "how does payroll work",
        ]
        expected = [
            "grounded_answer", "grounded_answer", "grounded_answer",
            "escalation_offer", "escalation_confirmation", "grounded_answer",
        ]
        for index, (prompt, outcome) in enumerate(zip(prompts, expected, strict=True)):
            turn = httpx.post(
                f"http://127.0.0.1:8000/api/v1/hires/emp-alyssa/conversations/{conversation['id']}/messages",
                headers={"Idempotency-Key": f"linux-smoke-turn-{index}"},
                json={"message": prompt}, timeout=10,
            )
            assert turn.status_code == 200 and turn.json()["data"]["type"] == outcome
            assert all(
                citation["policy_id"].startswith("PAY-")
                for citation in turn.json()["data"].get("citations", [])
            )
        checked = httpx.post(
            "http://127.0.0.1:8000/api/v1/hires/emp-alyssa/certificate-checks",
            headers={"Idempotency-Key": "linux-smoke-certificate"},
            data={"evaluation_date": "2026-08-10", "acknowledged": "true"},
            files={"file": ("synthetic.pdf", certificate(), "application/pdf")}, timeout=30,
        )
        assert checked.status_code == 200
        assert checked.json()["data"]["kind"] == "validation_result"
        assert checked.json()["data"]["status"] == "complete"
        key_mode = stat.S_IMODE(os.stat("/app/data/smoke.key").st_mode)
        assert key_mode == 0o600
        print("LINUX_CONTAINER_SMOKE=PASS DIALOGUE_REGRESSION=PASS")
    finally:
        api.terminate(); ui.terminate()
        api.wait(timeout=10); ui.wait(timeout=10)


if __name__ == "__main__":
    main()

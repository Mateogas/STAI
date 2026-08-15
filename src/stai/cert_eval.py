"""Live evaluator for AISHA's central certificate-readiness feature.

Runs a fixed set of synthetic certificates through the *real* deterministic
pipeline (extraction, policy-specific completeness, consistency, retry, and
human-review routing) and scores three independent axes:

* **Outcome correctness** (hard): the pipeline returns the expected typed
  outcome/status and includes the expected safe reason codes.
* **Privacy** (hard): no document-content value appears in the returned or
  persisted result.
* **Latency** (soft): wall-clock per certificate.

The flow is deterministic, so this runs fully locally with no Ollama and no
network. Certificates are synthetic and ephemeral; the report stores only
outcome names, safe reason codes, pass flags, and timings.

    uv run python -m stai.cert_eval --output evaluation/results/cert/cert-eval.json
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from datetime import date
from io import BytesIO
from pathlib import Path
from statistics import mean
from typing import Any

from stai.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "evaluation" / "results" / "cert"
EVALUATION_DATE = date(2026, 8, 10)

_COMPLETE = {
    "Patient Name": "Alyssa Reyes",
    "Consultation Date": "08/08/2026",
    "Issue Date": "08/09/2026",
    "Absence Start Date": "08/08/2026",
    "Absence End Date": "08/10/2026",
    "Duration Days": "3",
    "Clinician Name": "Dr. Sample Physician",
    "Facility Name": "Synthetic Care Clinic",
    "License Number": "present",
    "Signature": "present",
    "Recommendation": "present",
}

# Document-content values that must never surface in a safe result.
SENSITIVE_TOKENS = (
    "alyssa reyes", "reyes", "sample physician", "synthetic care",
    "08/08/2026", "08/09/2026", "08/10/2026",
)


@dataclass(frozen=True)
class CertCase:
    case_id: str
    description: str
    fields: dict[str, str]
    expected_kind: str
    expected_status: str | None = None
    expected_codes: tuple[str, ...] = field(default_factory=tuple)
    extra_lines: tuple[str, ...] = ()


def _with(**overrides: str | None) -> dict[str, str]:
    fields = dict(_COMPLETE)
    for key, value in overrides.items():
        label = key.replace("_", " ").title()
        if value is None:
            fields.pop(label, None)
        else:
            fields[label] = value
    return fields


CASES: tuple[CertCase, ...] = (
    CertCase(
        "CERT-COMPLETE", "A complete, consistent certificate",
        _COMPLETE, "validation_result", "complete",
    ),
    CertCase(
        "CERT-MISSING-CLINICIAN", "Missing the clinician name",
        _with(clinician_name=None), "validation_result", "incomplete",
        expected_codes=("clinician_name",),
    ),
    CertCase(
        "CERT-PATIENT-MISMATCH", "Patient name does not match the Hire",
        _with(patient_name="Juan Dela Cruz"), "validation_result", "incomplete",
        expected_codes=("patient_name_mismatch",),
    ),
    CertCase(
        "CERT-ABSENCE-REVERSED", "Absence end precedes absence start",
        _with(absence_start_date="08/10/2026", absence_end_date="08/08/2026", duration_days="3"),
        "validation_result", "incomplete",
        expected_codes=("absence_range_reversed",),
    ),
    CertCase(
        "CERT-UNSUPPORTED-PURPOSE", "Laboratory report, not a fit-to-work certificate",
        _COMPLETE, "validation_result", "needs_human_review",
        expected_codes=("unsupported_certificate_purpose",),
        extra_lines=("Laboratory Result: CBC panel",),
    ),
    CertCase(
        "CERT-INVALID-DATE", "Unrecognized date format triggers a safe retry",
        _with(consultation_date="2026-08-08"), "retry_required",
    ),
)


def _pdf(case: CertCase) -> bytes:
    from reportlab.pdfgen.canvas import Canvas

    lines = [f"{label}: {value}" for label, value in case.fields.items()]
    lines.extend(case.extra_lines)
    buffer = BytesIO()
    canvas = Canvas(buffer)
    for index, line in enumerate(lines):
        canvas.drawString(72, 720 - index * 18, line)
    canvas.save()
    return buffer.getvalue()


def _privacy_ok(repo, outcome) -> bool:
    rendered = json.dumps(outcome.model_dump(mode="json")).lower()
    if outcome.validation_id:
        rendered += json.dumps(repo.get_validation_result(outcome.validation_id)).lower()
    return not any(token in rendered for token in SENSITIVE_TOKENS)


def _score(case: CertCase, outcome, repo, elapsed: float) -> dict[str, Any]:
    status = outcome.status.value if outcome.status else None
    codes = [*outcome.missing_codes, *outcome.inconsistency_codes, *outcome.review_codes, *outcome.warning_codes]
    kind_ok = outcome.kind == case.expected_kind
    status_ok = case.expected_status is None or status == case.expected_status
    codes_ok = set(case.expected_codes).issubset(set(codes))
    privacy_ok = _privacy_ok(repo, outcome)
    gates = {"kind_ok": kind_ok, "status_ok": status_ok, "codes_ok": codes_ok, "privacy_ok": privacy_ok}
    return {
        "case_id": case.case_id,
        "description": case.description,
        "outcome_kind": outcome.kind,
        "status": status,
        "codes": codes,
        "elapsed_seconds": round(elapsed, 3),
        "gates": gates,
        "passed": all(gates.values()),
    }


def run_cert_eval() -> dict[str, Any]:
    """Run every synthetic certificate through the real deterministic flow."""
    import tempfile

    from stai.medical import MedicalCheckService, resolve_certificate_applicability
    from stai.retriever import load_page_records
    from stai.state import Repo

    records = load_page_records(PROJECT_ROOT / "handbook" / "dist" / "rag-pages.jsonl")
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        repo = Repo(root / "cert_eval.db", secret_path=root / "install.key")
        service = MedicalCheckService(repo)
        profile = repo.get_hire_profile("emp-alyssa")
        applicability = resolve_certificate_applicability(records, profile)
        for case in CASES:
            started = time.perf_counter()
            try:
                outcome = service.check(
                    _pdf(case),
                    filename="private-certificate.pdf",
                    evaluation_date=EVALUATION_DATE,
                    applicability=applicability,
                    acknowledged=True,
                )
            except Exception as exc:  # noqa: BLE001 - a crash is a scored failure
                results.append({
                    "case_id": case.case_id,
                    "description": case.description,
                    "error": f"{type(exc).__name__}: {exc}",
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                    "passed": False,
                })
                continue
            results.append(_score(case, outcome, repo, time.perf_counter() - started))

    return _build_report(results, applicability)


def _build_report(results: list[dict[str, Any]], applicability) -> dict[str, Any]:
    scored = [r for r in results if "gates" in r]
    latencies = [r["elapsed_seconds"] for r in results if "elapsed_seconds" in r]
    return {
        "evaluation_version": "1.0",
        "execution_mode": "live_deterministic_certificate",
        "certificate_applicability": applicability.value,
        "case_count": len(results),
        "pass_rate": round(mean(float(r["passed"]) for r in results), 6) if results else 0.0,
        "privacy_pass_rate": round(mean(float(r["gates"]["privacy_ok"]) for r in scored), 6) if scored else 0.0,
        "mean_latency_seconds": round(mean(latencies), 3) if latencies else None,
        "max_latency_seconds": round(max(latencies), 3) if latencies else None,
        "error_count": len(results) - len(scored),
        "cases": results,
        "privacy": "Synthetic certificates are ephemeral; the report stores outcome names, safe reason codes, pass flags, and timings only.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Live AISHA certificate-readiness evaluator.")
    parser.add_argument("--output", type=Path, default=None, help="write the JSON report to this path")
    args = parser.parse_args()

    report = run_cert_eval()
    output = args.output or (DEFAULT_OUTPUT_DIR / "cert-eval.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        f"cases={report['case_count']} "
        f"pass_rate={report['pass_rate']:.2f} "
        f"privacy_pass_rate={report['privacy_pass_rate']:.2f} "
        f"mean_latency={report['mean_latency_seconds']}s "
        f"applicability={report['certificate_applicability']}"
    )
    print(f"report -> {output}")


if __name__ == "__main__":
    main()

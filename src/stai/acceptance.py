"""Canonical integrated acceptance orchestrator for the AISHA capstone."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from stai.evaluation import BenchmarkRunner, select_prompt_variant
from stai.handbook import build_handbook, verify_publication
from stai.public_holidays import NagerHolidayService
from stai.state import Repo

ROOT = Path(__file__).parents[2]
BENCHMARK_RESULTS = ROOT / "evaluation/results/v1.0"
RESULTS = ROOT / "evaluation/results/v1.1"


def command(args: list[str], *, cwd: Path = ROOT) -> str:
    completed = subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True)
    return completed.stdout + completed.stderr


def verify_handbook() -> dict:
    artifacts = build_handbook()
    report = verify_publication(artifacts)
    manifest = json.loads(artifacts.manifest_path.read_text(encoding="utf-8"))
    if report["page_count"] != 108 or not report["valid"]:
        raise RuntimeError("handbook publication gate failed")
    return {
        "version": manifest["handbook_version"],
        "page_count": report["page_count"],
        "pdf_sha256": report["handbook_artifact_sha256"],
    }


def verify_benchmark() -> dict:
    reports = BenchmarkRunner(ROOT / "evaluation/benchmark_cases.jsonl").run_all_variants(output_dir=BENCHMARK_RESULTS)
    selected, trace = select_prompt_variant(reports)
    locked = reports[selected]["locked"]
    if selected != "P3" or not reports[selected]["passed"]:
        raise RuntimeError("frozen benchmark candidate failed")
    return {
        "version": locked["benchmark_version"], "scorer_version": locked["scorer_version"],
        "selected_prompt": selected, "locked_css": locked["css"],
        "locked_components": locked["components"], "hard_gate_failures": locked["hard_gate_failure_count"],
        "tie_break_rule": trace["rule"], "execution_mode": reports[selected]["execution_mode"],
    }


def verify_privacy_and_replacement() -> dict:
    from stai.api import app
    schema = json.dumps(app.openapi()).lower()
    forbidden_public = [
        "plan" + "_changed",
        "guardrail_category",
        "document_fingerprint",
        "ocr_text",
        "snippet",
        "collection_name",
    ]
    leaked = [item for item in forbidden_public if item in schema]
    if leaked:
        raise RuntimeError(f"public schema privacy regression: {leaked}")
    if "/chat" in app.openapi()["paths"] or "/health" in app.openapi()["paths"]:
        raise RuntimeError("legacy API path remains")
    with tempfile.TemporaryDirectory() as directory:
        repo = Repo(Path(directory) / "state.db", secret_path=Path(directory) / "install.key")
        with repo.connection() as conn:
            tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            columns = {row[1] for table in tables for row in conn.execute(f'PRAGMA table_info("{table}")')}
    forbidden_tables = {"employees", "plan_items", "pulse_checkins", "chat_messages", "escalations"}
    forbidden_columns = {"filename", "ocr_text", "diagnosis", "raw_error", "confidence_map", "document_bytes"}
    if tables & forbidden_tables or columns & forbidden_columns:
        raise RuntimeError("legacy or sensitive persistence surface remains")
    production = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "src/stai").glob("*.py"))
    replaced_terms = (
        "Me" + "ri" + "dian",
        "Ma" + "ya",
        "plan" + "_changed",
        "get_my" + "_plan",
        "complete" + "_task",
        "[source" + ":",
    )
    regressions = [term for term in replaced_terms if term in production]
    if regressions:
        raise RuntimeError(f"legacy production regression: {regressions}")
    return {"openapi_paths": len(app.openapi()["paths"]), "sqlite_tables": len(tables), "legacy_regressions": 0}


def verify_documentation() -> dict:
    required = [
        ROOT / "README.md", ROOT / "docs/EVALUATION.md", ROOT / "docs/TECHNICAL_WRITEUP.md",
        ROOT / "docs/ARCHITECTURE_DIAGRAMS.md", ROOT / "docs/MODULE_PRESENTATION_GUIDE.md",
        ROOT / "ContextKnowledgeBase/ModuleChecklist.md",
    ]
    if any(not path.exists() for path in required):
        raise RuntimeError("required documentation is missing")
    words = len((ROOT / "docs/TECHNICAL_WRITEUP.md").read_text(encoding="utf-8").split())
    matrix = (ROOT / "ContextKnowledgeBase/ModuleChecklist.md").read_text(encoding="utf-8")
    met_rows = [line for line in matrix.splitlines() if line.startswith("|") and re.search(r"\|\s*Met\s*\|\s*$", line)]
    pending_rows = [
        line for line in matrix.splitlines()
        if line.startswith("|") and re.search(r"\|\s*Implemented / Live gate pending\s*\|\s*$", line)
    ]
    owners = {name: matrix.count(f"| {name} |") for name in ("Johann Casio", "Jose Miguel Espinosa", "Bon Aquino")}
    if words < 2000 or len(met_rows) + len(pending_rows) != 12 or min(owners.values()) < 2:
        raise RuntimeError("documentation or named module ownership gate failed")
    return {
        "technical_writeup_words": words,
        "met_modules": len(met_rows),
        "live_gate_pending_modules": len(pending_rows),
        "owner_rows": owners,
    }


def verify_dialogue_regression() -> dict:
    from datetime import date

    from stai.retriever import load_page_records
    from stai.service import AishaService

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        repo = Repo(root / "dialogue.db", secret_path=root / "install.key")
        artifacts = build_handbook(root / "handbook")
        service = AishaService(repo, load_page_records(artifacts.rag_pages_path))
        conversation = service.create_conversation("emp-alyssa", date(2026, 8, 10))
        prompts = [
            "Whats my payroll", "Well then how do i do the onboard",
            "How to i put my payroll details", "I need help in this",
            "route it please", "how does payroll work",
        ]
        expected = [
            "grounded_answer", "escalation_offer", "escalation_offer",
            "escalation_offer", "escalation_confirmation", "grounded_answer",
        ]
        results = [service.send_message(conversation["id"], prompt) for prompt in prompts]
        if [result.type for result in results] != expected:
            raise RuntimeError("production dialogue outcome regression")
        wrong_topic = sum(
            not citation.policy_id.startswith("PAY-")
            for result in results
            for citation in result.citations
        )
        if wrong_topic or len(repo.list_escalation_cases()) != 1:
            raise RuntimeError("dialogue context, relevance, or consent regression")
    return {
        "version": "1.1",
        "turn_count": len(expected),
        "wrong_topic_citations": wrong_topic,
        "escalation_progression": "offered_then_consented",
        "execution_mode": "offline_deterministic_contract",
    }


def live_nager() -> dict:
    with tempfile.TemporaryDirectory() as directory:
        repo = Repo(Path(directory) / "nager.db", secret_path=Path(directory) / "install.key")
        result = NagerHolidayService(repo).lookup(datetime.now(UTC).year)
    if result.outcome != "live" or result.attribution != "Based on Nager.":
        raise RuntimeError(f"live Nager demonstration unavailable: {result.outcome}/{result.error_category}")
    evidence = {
        "checked_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "year": result.year, "outcome": result.outcome, "result_count": len(result.holidays),
        "attribution": result.attribution, "privacy": "No Hire, conversation, policy, document, OCR, or medical content sent.",
    }
    (RESULTS / "live-nager.json").write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def docker_smoke() -> dict:
    command(["docker", "info"])
    command(["docker", "build", "-t", "aisha-demo", "."])
    volume = f"aisha-smoke-{os.getpid()}"
    try:
        output = command(["docker", "run", "--rm", "-v", f"{volume}:/app/data", "aisha-demo", "uv", "run", "python", "deploy/container_smoke.py"])
        if "LINUX_CONTAINER_SMOKE=PASS" not in output:
            raise RuntimeError("container smoke did not report success")
    finally:
        subprocess.run(["docker", "volume", "rm", "-f", volume], text=True, capture_output=True)
    return {"image": "aisha-demo", "linux_container_smoke": "pass", "service_user": "aisha:10001"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-docker", action="store_true")
    parser.add_argument("--skip-live-nager", action="store_true")
    args = parser.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    report = {
        "acceptance_version": "1.1", "started_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "handbook": verify_handbook(), "benchmark": verify_benchmark(),
        "dialogue_regression": verify_dialogue_regression(),
        "privacy_and_replacement": verify_privacy_and_replacement(), "documentation": verify_documentation(),
    }
    if not args.skip_tests:
        output = command(["uv", "run", "pytest"])
        match = re.search(r"(\d+) passed", output)
        report["offline_tests"] = {"passed": int(match.group(1)) if match else "pass"}
    report["live_nager"] = {"status": "skipped"} if args.skip_live_nager else live_nager()
    report["docker"] = {"status": "skipped"} if args.skip_docker else docker_smoke()
    external_skips = args.skip_tests or args.skip_docker or args.skip_live_nager
    pending_modules = report["documentation"]["live_gate_pending_modules"]
    report["status"] = "partial" if external_skips or pending_modules else "passed"
    report["completed_at_utc"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    (RESULTS / "acceptance.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(RESULTS / "acceptance.json")}, sort_keys=True))


if __name__ == "__main__":
    main()

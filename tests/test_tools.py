from pathlib import Path

from stai.handbook import build_handbook
from stai.models import HireProfile
from stai.retriever import load_page_records
from stai.state import Repo
from stai.tools import build_policy_tools


def test_policy_react_tool_sequence_is_schema_bounded(tmp_path: Path) -> None:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    tools, capture = build_policy_tools(HireProfile.alyssa(), repo, records)
    assert [tool.name for tool in tools] == [
        "get_active_handbook_version",
        "search_onboarding_policies",
        "lookup_public_holidays",
        "evaluate_policy_applicability",
        "resolve_escalation_route",
        "create_escalation_case",
    ]
    search = tools[1]
    output = search.invoke({"query": "PAY-001"})
    assert "PAY-001" in output and "similarity" not in output.lower()
    assert capture.tool_calls == ["search_onboarding_policies"]


def test_case_tool_requires_explicit_consent(tmp_path: Path) -> None:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    tools, _ = build_policy_tools(HireProfile.alyssa(), repo, records)
    result = tools[-1].invoke({"consent": False, "summary": "Clarify PAY-001", "topic": "payroll"})
    assert result.startswith("CONSENT_REQUIRED")

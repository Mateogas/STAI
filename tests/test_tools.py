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
        "get_active_handbook",
        "discover_policies",
        "search_handbook",
        "evaluate_applicability",
        "lookup_public_holidays",
        "check_case_status",
        "offer_escalation",
    ]
    search = next(tool for tool in tools if tool.name == "search_handbook")
    output = search.invoke({"query": "PAY-001"})
    assert "PAY-001" in output and "similarity" not in output.lower()
    assert capture.tool_calls == ["search_handbook"]


def test_escalation_tool_only_offers_route_and_never_mutates(tmp_path: Path) -> None:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    tools, _ = build_policy_tools(HireProfile.alyssa(), repo, records)
    result = next(tool for tool in tools if tool.name == "offer_escalation").invoke(
        {"policy_id": "PAY-001", "topic": "payroll"}
    )
    assert '"consent_required": true' in result
    assert repo.list_escalation_cases() == []


def test_discovery_tool_is_scoped_and_returns_only_active_policy_metadata(tmp_path: Path) -> None:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    tools, capture = build_policy_tools(HireProfile.alyssa(), repo, records)
    discover = next(tool for tool in tools if tool.name == "discover_policies")
    payload = discover.invoke({"scope": "payroll"})
    assert "PAY-001" in payload and "ACC-001" not in payload and "HRP-001" not in payload
    assert capture.tool_calls == ["discover_policies"]


def test_case_status_tool_is_read_only(tmp_path: Path) -> None:
    repo = Repo(tmp_path / "state.db", secret_path=tmp_path / "install.key")
    records = load_page_records(build_handbook(tmp_path / "handbook").rag_pages_path)
    tools, capture = build_policy_tools(HireProfile.alyssa(), repo, records)
    check = next(tool for tool in tools if tool.name == "check_case_status")
    assert '"outcome": "not_found"' in check.invoke({})
    assert capture.tool_calls == ["check_case_status"]
    assert repo.list_escalation_cases() == []

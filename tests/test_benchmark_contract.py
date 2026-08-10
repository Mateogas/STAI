import json
from collections import Counter
from pathlib import Path

from pydantic import TypeAdapter

from stai.models import BenchmarkCase


ROOT = Path(__file__).parents[1]


def test_frozen_benchmark_has_exact_allocation_and_partitions() -> None:
    rows = [json.loads(line) for line in (ROOT / "evaluation/benchmark_cases.jsonl").read_text().splitlines()]
    cases = TypeAdapter(list[BenchmarkCase]).validate_python(rows)
    assert len(cases) == 60
    assert Counter(case.family for case in cases) == {
        "policy": 18,
        "retrieval": 12,
        "dialogue": 6,
        "nager": 8,
        "medical": 16,
    }
    assert Counter(case.partition for case in cases) == {"calibration": 40, "locked": 20}
    assert len({case.case_id for case in cases}) == 60
    assert all(case.synthetic and case.expected_outcome for case in cases)


def test_manifest_freezes_required_component_weights() -> None:
    manifest = json.loads((ROOT / "evaluation/benchmark_manifest.json").read_text())
    assert manifest["benchmark_version"] == "1.0"
    assert manifest["case_count"] == 60
    assert manifest["component_weights"] == {
        "G": 0.25,
        "R": 0.20,
        "A": 0.15,
        "D": 0.15,
        "M": 0.15,
        "X": 0.10,
    }
    assert manifest["thresholds"] == {
        "css": 0.90,
        "component_minimum": 0.85,
        "safety_critical_failures": 0,
    }

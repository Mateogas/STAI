from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
USER_FACING_PATHS = [
    ROOT / "app.py",
    ROOT / "src" / "stai",
    ROOT / "data",
    ROOT / "README.md",
    ROOT / "docs" / "BUSINESS_CASE.md",
]


def _iter_user_facing_files() -> list[Path]:
    files: list[Path] = []
    for path in USER_FACING_PATHS:
        if path.is_dir():
            files.extend(
                p
                for p in path.rglob("*")
                if p.is_file() and p.suffix in {".py", ".json", ".md"}
            )
        else:
            files.append(path)
    return files


def test_user_facing_surfaces_use_aisha_bdo_story():
    stale_terms = [
        "Me" + "ri" + "dian",
        "Ma" + "ya",
        "Me" + "ri",
        "30-" + "60-" + "90",
        "Software " + "Engineer",
    ]
    required_terms = ["AISHA", "BDO", "Alyssa Reyes", "Day 30 Readiness Check"]

    combined = "\n".join(p.read_text(encoding="utf-8") for p in _iter_user_facing_files())

    assert [term for term in stale_terms if term in combined] == []
    assert [term for term in required_terms if term not in combined] == []

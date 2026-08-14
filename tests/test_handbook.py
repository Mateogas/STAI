import hashlib
import json
from pathlib import Path

from pypdf import PdfReader

from stai.handbook import build_handbook, load_source, load_source_register, verify_publication


def test_page_native_source_and_108_page_publication(tmp_path: Path) -> None:
    source = load_source()
    assert source.handbook_version == "1.1"
    assert len(source.pages) == 108
    assert len({page.page_key for page in source.pages}) == 108
    assert all(page.body.strip() and "filler" not in page.body.lower() for page in source.pages)

    artifacts = build_handbook(tmp_path)
    report = verify_publication(artifacts)
    assert report["valid"] is True
    assert report["page_count"] == 108
    assert len(PdfReader(artifacts.pdf_path).pages) == 108


def test_handbook_build_is_deterministic_and_rag_pages_match_manifest(tmp_path: Path) -> None:
    first = build_handbook(tmp_path / "first")
    second = build_handbook(tmp_path / "second")
    assert hashlib.sha256(first.pdf_path.read_bytes()).hexdigest() == hashlib.sha256(
        second.pdf_path.read_bytes()
    ).hexdigest()
    assert first.manifest_path.read_bytes() == second.manifest_path.read_bytes()
    assert first.rag_pages_path.read_bytes() == second.rag_pages_path.read_bytes()

    manifest = json.loads(first.manifest_path.read_text())
    rag_pages = [json.loads(line) for line in first.rag_pages_path.read_text().splitlines()]
    assert [row["page"] for row in manifest["pages"]] == list(range(1, 109))
    assert len(rag_pages) == 108
    assert all(row["handbook_version"] == "1.1" for row in rag_pages)
    assert all(row["page_content_sha256"] for row in rag_pages)


def test_locked_topic_page_allocation() -> None:
    pages = load_source().pages
    counts = {}
    for page in pages:
        counts[page.section] = counts.get(page.section, 0) + 1
    assert counts == {"front": 6, "payroll": 26, "resource_access": 30, "hr_policies": 38, "back": 8}


def test_source_register_uses_authoritative_public_context_without_claiming_real_internal_policy() -> None:
    register = load_source_register()
    assert register.handbook_target_version == "1.1"
    assert len(register.sources) >= 5
    assert len({source.source_id for source in register.sources}) == len(register.sources)
    assert all(source.url.startswith("https://") for source in register.sources)
    assert {source.source_class for source in register.sources} == {"official_guidance", "legal_baseline"}
    rules = " ".join(register.publication_rules).lower()
    assert "never a real bdo policy" in rules
    assert "synthetic demo rules" in rules


def test_publication_identity_includes_source_register(tmp_path: Path) -> None:
    artifacts = build_handbook(tmp_path)
    manifest = json.loads(artifacts.manifest_path.read_text())
    report = json.loads(artifacts.report_path.read_text())
    rows = [json.loads(line) for line in artifacts.rag_pages_path.read_text().splitlines()]
    assert manifest["source_register_sha256"] == report["source_register_sha256"]
    assert manifest["source_ids"] == report["source_ids"]
    assert all(row["source_register_sha256"] == manifest["source_register_sha256"] for row in rows)

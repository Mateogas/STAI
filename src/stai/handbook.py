"""Deterministic publication of AISHA's page-native synthetic handbook."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from stai.config import PROJECT_ROOT


SOURCE_PATH = PROJECT_ROOT / "handbook" / "source.yaml"


class ApplicabilityRule(BaseModel):
    role_keys: list[str]
    department_keys: list[str]
    employment_classifications: list[str]
    work_sites: list[str]

    @model_validator(mode="after")
    def all_keys_are_declared(self) -> "ApplicabilityRule":
        if any(not values for values in (
            self.role_keys, self.department_keys, self.employment_classifications, self.work_sites
        )):
            raise ValueError("applicability lists cannot be empty")
        return self


class HandbookPage(BaseModel):
    page_key: str
    section: Literal["front", "payroll", "resource_access", "hr_policies", "back"]
    kind: Literal["policy", "procedure", "example", "explainer", "glossary", "directory"]
    title: str
    body: str
    policy_id: str | None = None
    policy_revision: str | None = None
    topic: str | None = None
    subareas: list[str] = Field(default_factory=list)
    applicability: ApplicabilityRule | None = None
    route: str | None = None
    status: str = "active"
    effective_date: str | None = None
    claim_types: list[str] = Field(default_factory=list)


class HandbookSource(BaseModel):
    schema_version: Literal[1]
    handbook_version: str
    active: Literal[True]
    pages: list[HandbookPage]


@dataclass(frozen=True)
class HandbookArtifacts:
    pdf_path: Path
    manifest_path: Path
    rag_pages_path: Path
    report_path: Path


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def load_source(path: Path = SOURCE_PATH) -> HandbookSource:
    return HandbookSource.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def _render_pdf(source: HandbookSource, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(output), pagesize=LETTER, invariant=1, pageCompression=1)
    canvas.setTitle(f"AISHA Handbook v{source.handbook_version}")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("PageTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor="#17365D")
    body_style = ParagraphStyle("PageBody", parent=styles["BodyText"], fontName="Helvetica", fontSize=11, leading=17, spaceAfter=8)
    footer_style = ParagraphStyle("Footer", parent=styles["BodyText"], fontName="Helvetica", fontSize=8, alignment=TA_CENTER, textColor="#666666")
    width, height = LETTER
    for page_number, page in enumerate(source.pages, 1):
        canvas.setFillColorRGB(0.05, 0.22, 0.39)
        canvas.rect(0, height - 0.55 * inch, width, 0.55 * inch, fill=1, stroke=0)
        title = Paragraph(page.title, title_style)
        body = Paragraph(page.body, body_style)
        tw, th = title.wrap(width - 1.5 * inch, height)
        bw, bh = body.wrap(width - 1.5 * inch, height)
        available = height - 2.2 * inch
        if th + bh > available:
            raise ValueError(f"page overflow: {page.page_key}")
        title.drawOn(canvas, 0.75 * inch, height - 1.25 * inch - th)
        body.drawOn(canvas, 0.75 * inch, height - 1.55 * inch - th - bh)
        identity = page.policy_id or "AISHA"
        footer = Paragraph(f"{identity} · AISHA Handbook v{source.handbook_version} · Page {page_number}", footer_style)
        fw, fh = footer.wrap(width - inch, 0.4 * inch)
        footer.drawOn(canvas, 0.5 * inch, 0.42 * inch)
        canvas.showPage()
    canvas.save()


def build_handbook(output_dir: Path | None = None) -> HandbookArtifacts:
    source = load_source()
    out = output_dir or PROJECT_ROOT / "handbook" / "dist"
    out.mkdir(parents=True, exist_ok=True)
    pdf_path = out / "aisha-handbook-v1.0.pdf"
    manifest_path = out / "page-manifest.json"
    rag_pages_path = out / "rag-pages.jsonl"
    report_path = out / "build-report.json"
    _render_pdf(source, pdf_path)
    pdf_hash = _sha(pdf_path.read_bytes())
    manifest_core = {
        "schema_version": 1,
        "handbook_version": source.handbook_version,
        "active": True,
        "page_count": len(source.pages),
        "handbook_artifact_sha256": pdf_hash,
        "pages": [
            {
                "page": number,
                "page_key": page.page_key,
                "policy_id": page.policy_id,
                "policy_revision": page.policy_revision,
                "kind": page.kind,
                "content_sha256": _sha(page.body.encode()),
            }
            for number, page in enumerate(source.pages, 1)
        ],
    }
    manifest_identity = _sha(_canonical(manifest_core))
    manifest = {**manifest_core, "manifest_sha256": manifest_identity}
    manifest_path.write_bytes(_canonical(manifest) + b"\n")
    records = []
    for page_number, page in enumerate(source.pages, 1):
        record = {
            "schema_version": 1,
            "record_id": f"aisha-v{source.handbook_version}-{page.page_key}",
            "handbook_version": source.handbook_version,
            "handbook_artifact_sha256": pdf_hash,
            "page_manifest_sha256": manifest_identity,
            "page": page_number,
            "page_key": page.page_key,
            "page_content_sha256": _sha(page.body.encode()),
            "policy_id": page.policy_id,
            "policy_revision": page.policy_revision,
            "title": page.title,
            "topic": page.topic,
            "subareas": page.subareas,
            "status": page.status,
            "effective_date": page.effective_date,
            "supersedes": None,
            "page_kind": page.kind,
            "procedure_id": f"{page.policy_id}-P{page_number:02d}" if page.policy_id and page.kind == "procedure" else None,
            "claim_types": page.claim_types,
            "applicability": page.applicability.model_dump() if page.applicability else None,
            "route": page.route,
            "content": page.body,
        }
        records.append(record)
    rag_pages_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records), encoding="utf-8")
    report = {"valid": True, "page_count": len(records), "handbook_artifact_sha256": pdf_hash, "manifest_sha256": manifest_identity, "rag_pages_sha256": _sha(rag_pages_path.read_bytes())}
    report_path.write_bytes(_canonical(report) + b"\n")
    return HandbookArtifacts(pdf_path, manifest_path, rag_pages_path, report_path)


def verify_publication(artifacts: HandbookArtifacts) -> dict:
    from pypdf import PdfReader

    manifest = json.loads(artifacts.manifest_path.read_text())
    records = [json.loads(line) for line in artifacts.rag_pages_path.read_text().splitlines()]
    valid = (
        len(PdfReader(artifacts.pdf_path).pages) == 108
        and manifest["page_count"] == 108
        and len(records) == 108
        and len({row["record_id"] for row in records}) == 108
        and all(row["handbook_artifact_sha256"] == manifest["handbook_artifact_sha256"] for row in records)
        and all(row["page_manifest_sha256"] == manifest["manifest_sha256"] for row in records)
    )
    return {"valid": valid, "page_count": len(records), "handbook_artifact_sha256": manifest["handbook_artifact_sha256"], "manifest_sha256": manifest["manifest_sha256"]}


if __name__ == "__main__":
    print(json.dumps(verify_publication(build_handbook()), sort_keys=True))

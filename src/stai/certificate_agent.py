"""Bounded CPU-safe agent wrapper for local certificate OCR validation.

The model never receives file bytes, filenames, extracted text, or field values.
It can only call two zero-argument tools whose closures hold ephemeral state.
Deterministic application code remains responsible for persistence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from langchain_core.tools import tool

from stai.config import settings

if TYPE_CHECKING:
    from stai.medical import DeterministicValidation


AGENT_ACTIONS = ("confirm_certificate_policy", "run_local_ocr_validation")


@dataclass
class CertificateAgentCapture:
    actions: list[str] = field(default_factory=list)
    validation: DeterministicValidation | None = None


@dataclass(frozen=True)
class CertificateAgentRun:
    validation: DeterministicValidation
    actions: list[str]


def build_certificate_tools(
    analyze: Callable[[], DeterministicValidation],
):
    """Build privacy-safe tools around one ephemeral upload analysis."""
    capture = CertificateAgentCapture()

    @tool
    def confirm_certificate_policy() -> str:
        """Read the closed HRP-004 certificate-completeness boundary."""
        capture.actions.append("confirm_certificate_policy")
        return json.dumps({
            "policy_id": "HRP-004",
            "purpose": "local_completeness_only",
            "authenticity_verified": False,
            "human_review_available": True,
        })

    @tool
    def run_local_ocr_validation() -> str:
        """Run local OCR and deterministic labelled-field checks for this upload."""
        capture.actions.append("run_local_ocr_validation")
        capture.validation = analyze()
        validation = capture.validation
        return json.dumps({
            "status": validation.status.value if validation.status else None,
            "retry_required": validation.retry_required,
            "missing_codes": validation.missing_codes,
            "inconsistency_codes": validation.inconsistency_codes,
            "warning_codes": validation.warning_codes,
            "review_codes": validation.review_codes,
        })

    return [confirm_certificate_policy, run_local_ocr_validation], capture


class LocalCertificateAgentRunner:
    """Invoke a fresh ReAct loop; return ``None`` for safe CPU fallback."""

    def __init__(self, *, llm=None, probe_timeout: float | None = None) -> None:
        self.llm = llm
        self.probe_timeout = probe_timeout or settings.agent_probe_timeout_seconds

    def __call__(
        self,
        analyze: Callable[[], DeterministicValidation],
    ) -> CertificateAgentRun | None:
        try:
            if self.llm is None and not self.available():
                return None
            from stai.agent import _V1, _create_agent, build_llm

            tools, capture = build_certificate_tools(analyze)
            model = self.llm or build_llm()
            prompt = (
                "You are AISHA's bounded Certificate Agent. Call "
                "confirm_certificate_policy exactly once, then call "
                "run_local_ocr_validation exactly once. Never request or repeat file "
                "contents, extracted values, diagnoses, or hidden reasoning. Summarize "
                "only the safe typed outcome returned by the tools."
            )
            if _V1:
                graph = _create_agent(model, tools, system_prompt=prompt)
            else:  # pragma: no cover
                graph = _create_agent(model, tools, prompt=prompt)
            graph.invoke({"messages": [("human", "Run the acknowledged local certificate completeness check.")]})
            if capture.actions != list(AGENT_ACTIONS) or capture.validation is None:
                return None
            return CertificateAgentRun(validation=capture.validation, actions=list(capture.actions))
        except Exception:
            return None

    def available(self) -> bool:
        import httpx

        try:
            response = httpx.get(
                f"{settings.ollama_base_url.rstrip('/')}/api/tags",
                timeout=self.probe_timeout,
                follow_redirects=False,
            )
            response.raise_for_status()
            names = {
                str(item.get("name", "")).split(":latest")[0]
                for item in response.json().get("models", [])
            }
            return settings.agent_model.split(":latest")[0] in names
        except Exception:
            return False

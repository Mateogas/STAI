from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from langgraph.graph import END

from research_engine import (
    ClaimCheck,
    EngineState,
    EvaluationReport,
    EvidenceExcerpt,
    PageRecord,
    QuestionSpec,
    ResearchFinding,
    DraftResponse,
    POISON_LIE,
    benchmark_note_failures,
    editorial_routing_gate,
    retrieve_for_critic,
    retrieve_for_researcher,
    run_engine,
    validate_finding_evidence,
    validate_run_pair,
    _parse_structured_content,
)


def report(approved: bool) -> EvaluationReport:
    return EvaluationReport(
        is_approved=approved,
        critique="approved" if approved else "needs correction",
        claim_checks=[
            ClaimCheck(
                claim="claim",
                verdict="supported" if approved else "contradicted",
                explanation="evidence",
                source_pages=["paper.pdf p. 1"],
            )
        ],
        missing_answers=[],
    )


class RoutingTests(unittest.TestCase):
    def state(self, approved: bool | None, iterations: int) -> EngineState:
        return {
            "iterations": iterations,
            "max_iterations": 3,
            "evaluation": None if approved is None else report(approved),
            "fatal_error": None,
        }

    def test_approved_routes_to_end(self) -> None:
        self.assertEqual(editorial_routing_gate(self.state(True, 1)), END)

    def test_rejected_attempt_one_routes_to_writer(self) -> None:
        self.assertEqual(editorial_routing_gate(self.state(False, 1)), "writer")

    def test_rejected_attempt_two_routes_to_writer(self) -> None:
        self.assertEqual(editorial_routing_gate(self.state(False, 2)), "writer")

    def test_rejected_attempt_three_routes_to_end(self) -> None:
        self.assertEqual(editorial_routing_gate(self.state(False, 3)), END)

    def test_missing_report_routes_to_end(self) -> None:
        self.assertEqual(editorial_routing_gate(self.state(None, 1)), END)

    def test_fatal_error_routes_to_end(self) -> None:
        state = self.state(False, 1)
        state["fatal_error"] = "failure"
        self.assertEqual(editorial_routing_gate(state), END)


class EvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.question = QuestionSpec(
            id="test",
            paper="paper.pdf",
            question="How does expert load balancing use a routing bias?",
            candidate_concepts=("routing bias", "load balancing"),
            title_terms=("paper",),
        )
        self.pages = [
            PageRecord(filename="paper.pdf", page=1, text="Paper abstract and introduction."),
            PageRecord(filename="paper.pdf", page=2, text="Background material."),
            PageRecord(
                filename="paper.pdf",
                page=3,
                text="The routing bias is adjusted from measured expert load for balancing.",
            ),
            PageRecord(filename="paper.pdf", page=4, text="Unrelated appendix."),
        ]

    def test_research_retrieval_keeps_front_matter_and_relevant_page(self) -> None:
        selected = retrieve_for_researcher(self.pages, self.question, top_ranked=1)
        self.assertEqual({page.page for page in selected}, {1, 2, 3})

    def test_critic_retrieval_keeps_cited_page_and_neighbors(self) -> None:
        selected = retrieve_for_critic(
            self.pages,
            self.question,
            "Claim [paper.pdf p. 3]",
            top_ranked=1,
        )
        self.assertTrue({2, 3, 4}.issubset({page.page for page in selected}))

    def test_verbatim_excerpt_is_retained(self) -> None:
        finding = ResearchFinding(
            question_id="test",
            mechanism="A routing bias follows measured expert load.",
            terminology=["routing bias"],
            evidence=[
                EvidenceExcerpt(
                    filename="paper.pdf",
                    page=3,
                    excerpt="routing bias is adjusted from measured expert load",
                )
            ],
            gaps=[],
        )
        validated = validate_finding_evidence(finding, self.pages)
        self.assertEqual(len(validated.evidence), 1)

    def test_invented_excerpt_is_removed(self) -> None:
        finding = ResearchFinding(
            question_id="test",
            mechanism="Invented mechanism.",
            terminology=["invented"],
            evidence=[
                EvidenceExcerpt(
                    filename="paper.pdf",
                    page=3,
                    excerpt="This sentence is not present in the document.",
                )
            ],
            gaps=[],
        )
        validated = validate_finding_evidence(finding, self.pages)
        self.assertEqual(validated.evidence, [])
        self.assertTrue(validated.mechanism.startswith("NOT FOUND"))

    def test_structured_parser_accepts_json_code_fence(self) -> None:
        draft = "A sufficiently long structured technical draft for schema validation."
        parsed = _parse_structured_content(
            f'```json\n{{"draft":"{draft}"}}\n```', DraftResponse
        )
        self.assertEqual(parsed.draft, draft)

    def test_structured_parser_wraps_single_string_field(self) -> None:
        draft = "A sufficiently long plain local-model technical draft response."
        parsed = _parse_structured_content(draft, DraftResponse)
        self.assertEqual(parsed.draft, draft)


class BenchmarkTests(unittest.TestCase):
    def test_normalized_keyword_groups_accept_supported_aliases(self) -> None:
        findings = [
            ResearchFinding(
                question_id="deepseek_v3",
                mechanism="Auxiliary loss free load balancing changes an expert bias term.",
                terminology=["expert bias"],
                evidence=[
                    EvidenceExcerpt(
                        filename="deepseek-v3.pdf",
                        page=1,
                        excerpt="auxiliary loss free load balancing uses an expert bias term",
                    )
                ],
                gaps=[],
            ),
            ResearchFinding(
                question_id="mamba_2",
                mechanism=(
                    "SSD means structured state-space duality between a recurrent "
                    "form and a semiseparable matrix."
                ),
                terminology=["SSD", "recurrent", "semiseparable", "matrix"],
                evidence=[
                    EvidenceExcerpt(
                        filename="mamba-2.pdf",
                        page=1,
                        excerpt="structured state-space duality uses a semiseparable matrix",
                    )
                ],
                gaps=[],
            ),
            ResearchFinding(
                question_id="bitnet_b158",
                mechanism="A 1.58-bit ternary representation uses {-1, 0, 1}.",
                terminology=["ternary", "1.58-bit"],
                evidence=[
                    EvidenceExcerpt(
                        filename="bitnet-b1.58.pdf",
                        page=1,
                        excerpt="ternary weights use {-1, 0, 1} at 1.58 bits",
                    )
                ],
                gaps=[],
            ),
        ]
        self.assertEqual(benchmark_note_failures(findings), [])


class FakeOllamaClient:
    def __init__(self, model: str) -> None:
        self.model = model

    def preflight(self) -> None:
        return None

    def chat_structured(self, messages, response_model):
        user = messages[-1]["content"]
        system = messages[0]["content"]
        if response_model is ResearchFinding:
            if "QUESTION ID: deepseek_v3" in user:
                return ResearchFinding(
                    question_id="deepseek_v3",
                    mechanism=(
                        "Auxiliary-loss-free load balancing adjusts an expert bias term "
                        "used in routing."
                    ),
                    terminology=["auxiliary-loss-free load balancing", "expert bias term"],
                    evidence=[
                        EvidenceExcerpt(
                            filename="deepseek-v3.pdf",
                            page=1,
                            excerpt=(
                                "auxiliary-loss-free load balancing which adjusts an expert "
                                "bias term used in routing"
                            ),
                        )
                    ],
                    gaps=[],
                )
            if "QUESTION ID: mamba_2" in user:
                return ResearchFinding(
                    question_id="mamba_2",
                    mechanism=(
                        "Structured state space duality (SSD) connects a recurrent form "
                        "to a semiseparable matrix transformation."
                    ),
                    terminology=["SSD", "recurrent form", "semiseparable matrix"],
                    evidence=[
                        EvidenceExcerpt(
                            filename="mamba-2.pdf",
                            page=1,
                            excerpt=(
                                "structured state space duality (SSD) connects a recurrent "
                                "form to a semiseparable matrix transformation"
                            ),
                        )
                    ],
                    gaps=[],
                )
            return ResearchFinding(
                question_id="bitnet_b158",
                mechanism="BitNet uses ternary {-1, 0, 1} weights at 1.58 bits.",
                terminology=["ternary", "1.58 bits"],
                evidence=[
                    EvidenceExcerpt(
                        filename="bitnet-b1.58.pdf",
                        page=1,
                        excerpt="BitNet uses ternary {-1, 0, 1} weights at 1.58 bits",
                    )
                ],
                gaps=[],
            )
        if response_model is DraftResponse:
            poison = POISON_LIE in system
            deepseek = (
                "DeepSeek-V3 uses traditional cross-entropy loss weights for balancing."
                if poison
                else "DeepSeek-V3 uses auxiliary-loss-free load balancing through an expert bias."
            )
            return DraftResponse(
                draft=(
                    f"## 1. DeepSeek-V3\n### Mechanism\n{deepseek} "
                    "[deepseek-v3.pdf p. 1]\n### Contrast\nEvidence-grounded.\n"
                    "### Evidence\n[deepseek-v3.pdf p. 1]\n"
                    "## 2. Mamba-2\n### Mechanism\nSSD connects a recurrent form "
                    "to a semiseparable matrix. [mamba-2.pdf p. 1]\n"
                    "### Contrast\nDual forms.\n### Evidence\n[mamba-2.pdf p. 1]\n"
                    "## 3. BitNet\n### Mechanism\nTernary {-1, 0, 1} weights use "
                    "1.58 bits. [bitnet-b1.58.pdf p. 1]\n"
                    "### Contrast\nReduced arithmetic.\n### Evidence\n[bitnet-b1.58.pdf p. 1]"
                )
            )
        if response_model is EvaluationReport:
            poisoned = "traditional cross-entropy" in user
            if poisoned:
                return EvaluationReport(
                    is_approved=False,
                    critique=(
                        "DeepSeek claim contradicts the source's auxiliary-loss-free "
                        "expert-bias mechanism."
                    ),
                    claim_checks=[
                        ClaimCheck(
                            claim=(
                                "DeepSeek-V3 uses traditional cross-entropy loss weights "
                                "for balancing."
                            ),
                            verdict="contradicted",
                            explanation="Source describes auxiliary-loss-free expert bias.",
                            source_pages=["deepseek-v3.pdf p. 1"],
                        )
                    ],
                    missing_answers=[],
                )
            return EvaluationReport(
                is_approved=True,
                critique="All claims are supported.",
                claim_checks=[
                    ClaimCheck(
                        claim="All three mechanisms match the source pages.",
                        verdict="supported",
                        explanation="Source evidence matches.",
                        source_pages=[
                            "deepseek-v3.pdf p. 1",
                            "mamba-2.pdf p. 1",
                            "bitnet-b1.58.pdf p. 1",
                        ],
                    )
                ],
                missing_answers=[],
            )
        raise AssertionError(f"Unexpected response model: {response_model}")


def synthetic_benchmark_pages() -> list[PageRecord]:
    return [
        PageRecord(
            filename="deepseek-v3.pdf",
            page=1,
            text=(
                "DeepSeek-V3 Technical Report. DeepSeek-V3 uses auxiliary-loss-free "
                "load balancing which adjusts an expert bias term used in routing."
            ),
        ),
        PageRecord(
            filename="mamba-2.pdf",
            page=1,
            text=(
                "Transformers are SSMs. Structured state space duality (SSD) connects "
                "a recurrent form to a semiseparable matrix transformation."
            ),
        ),
        PageRecord(
            filename="bitnet-b1.58.pdf",
            page=1,
            text="BitNet uses ternary {-1, 0, 1} weights at 1.58 bits.",
        ),
    ]


class GraphIntegrationTests(unittest.TestCase):
    @patch("research_engine.OllamaClient", FakeOllamaClient)
    @patch("research_engine.load_pages", return_value=synthetic_benchmark_pages())
    def test_baseline_and_poisoned_graphs(self, _load_pages) -> None:
        baseline = run_engine(Path("unused"))
        poisoned = run_engine(Path("unused"), poison_writer=True)

        self.assertEqual(baseline.status, "approved")
        self.assertEqual(baseline.events, ["researcher", "writer", "critic"])
        self.assertEqual(poisoned.status, "ceiling_reached")
        self.assertEqual(poisoned.iterations, 3)
        self.assertEqual(
            poisoned.events,
            ["researcher", "writer", "critic", "writer", "critic", "writer", "critic"],
        )
        self.assertEqual(validate_run_pair(baseline, poisoned), [])


if __name__ == "__main__":
    unittest.main()

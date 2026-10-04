from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agents.research.assembler import (
    ResearchResultAssembler,
)
from agents.research.schemas import (
    Claim,
    Evidence,
    Source,
)


def make_source(
    source_id: str = "src_1",
) -> Source:
    return Source(
        id=source_id,
        title="Example Source",
        url="https://example.com/rag",
        publisher="example.com",
        published_at=None,
        retrieved_at=datetime(
            2026,
            10,
            4,
            tzinfo=timezone.utc,
        ),
        source_type="web",
    )


def make_evidence(
    evidence_id: str = "evidence_1",
    source_id: str = "src_1",
) -> Evidence:
    return Evidence(
        id=evidence_id,
        source_id=source_id,
        text=(
            "RAG retrieves relevant information "
            "before generating an answer."
        ),
        relevance_score=1.0,
    )


def make_claim(
    claim_id: str = "claim_1",
    evidence_id: str = "evidence_1",
) -> Claim:
    return Claim(
        id=claim_id,
        text=(
            "RAG uses retrieved information "
            "during generation."
        ),
        confidence="high",
        evidence_ids=[
            evidence_id,
        ],
    )


def test_assembler_creates_research_result():
    assembler = ResearchResultAssembler()

    result = assembler.assemble(
        question="What is RAG?",
        summary=(
            "RAG combines retrieval "
            "with generation."
        ),
        sources=[
            make_source(),
        ],
        evidence=[
            make_evidence(),
        ],
        claims=[
            make_claim(),
        ],
        caveats=[
            (
                "Quality depends on "
                "retrieval quality."
            )
        ],
    )

    assert result.question == "What is RAG?"

    assert result.summary == (
        "RAG combines retrieval with generation."
    )

    assert len(result.sources) == 1
    assert len(result.evidence) == 1
    assert len(result.claims) == 1
    assert len(result.caveats) == 1


def test_assembler_strips_question_and_summary():
    assembler = ResearchResultAssembler()

    result = assembler.assemble(
        question="   What is RAG?   ",
        summary=(
            "   RAG combines retrieval "
            "with generation.   "
        ),
        sources=[
            make_source(),
        ],
        evidence=[
            make_evidence(),
        ],
        claims=[
            make_claim(),
        ],
    )

    assert result.question == "What is RAG?"

    assert result.summary == (
        "RAG combines retrieval with generation."
    )


def test_assembler_preserves_reference_chain():
    assembler = ResearchResultAssembler()

    result = assembler.assemble(
        question="What is RAG?",
        summary="RAG uses retrieval.",
        sources=[
            make_source(),
        ],
        evidence=[
            make_evidence(),
        ],
        claims=[
            make_claim(),
        ],
    )

    claim = result.claims[0]
    evidence = result.evidence[0]

    assert claim.evidence_ids == [
        "evidence_1"
    ]

    assert evidence.source_id == "src_1"


def test_assembler_cleans_caveats():
    assembler = ResearchResultAssembler()

    result = assembler.assemble(
        question="What is RAG?",
        summary="RAG uses retrieval.",
        sources=[
            make_source(),
        ],
        evidence=[
            make_evidence(),
        ],
        claims=[
            make_claim(),
        ],
        caveats=[
            "  Retrieval quality matters.  ",
            "",
            "   ",
            "Retrieval quality matters.",
            "Hallucination is still possible.",
        ],
    )

    assert result.caveats == [
        "Retrieval quality matters.",
        "Hallucination is still possible.",
    ]


def test_assembler_rejects_empty_question():
    assembler = ResearchResultAssembler()

    with pytest.raises(
        ValueError,
        match="Question cannot be empty",
    ):
        assembler.assemble(
            question="   ",
            summary="Valid summary.",
            sources=[],
            evidence=[],
            claims=[],
        )


def test_assembler_rejects_empty_summary():
    assembler = ResearchResultAssembler()

    with pytest.raises(
        ValueError,
        match="Summary cannot be empty",
    ):
        assembler.assemble(
            question="What is RAG?",
            summary="   ",
            sources=[],
            evidence=[],
            claims=[],
        )


def test_assembler_rejects_unknown_source_reference():
    assembler = ResearchResultAssembler()

    bad_evidence = make_evidence(
        source_id="src_missing",
    )

    with pytest.raises(
        ValidationError,
        match="unknown source",
    ):
        assembler.assemble(
            question="What is RAG?",
            summary="RAG uses retrieval.",
            sources=[
                make_source(),
            ],
            evidence=[
                bad_evidence,
            ],
            claims=[],
        )


def test_assembler_rejects_unknown_evidence_reference():
    assembler = ResearchResultAssembler()

    bad_claim = make_claim(
        evidence_id="evidence_missing",
    )

    with pytest.raises(
        ValidationError,
        match="unknown evidence",
    ):
        assembler.assemble(
            question="What is RAG?",
            summary="RAG uses retrieval.",
            sources=[
                make_source(),
            ],
            evidence=[
                make_evidence(),
            ],
            claims=[
                bad_claim,
            ],
        )
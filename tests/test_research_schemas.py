from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)


def make_source() -> Source:
    return Source(
        id="src_1",
        title="Example Source",
        url="https://example.com/rag",
        publisher="Example Publisher",
        published_at=None,
        retrieved_at=datetime.now(
            timezone.utc
        ),
        source_type="web",
    )


def make_evidence() -> Evidence:
    return Evidence(
        id="evidence_1",
        source_id="src_1",
        text=(
            "RAG retrieves relevant information "
            "before generating an answer."
        ),
        relevance_score=0.95,
    )


def make_claim() -> Claim:
    return Claim(
        id="claim_1",
        text=(
            "RAG uses retrieved information "
            "during generation."
        ),
        confidence="high",
        evidence_ids=[
            "evidence_1",
        ],
    )


def test_source_creation():
    source = make_source()

    assert source.id == "src_1"
    assert source.source_type == "web"
    assert source.publisher == (
        "Example Publisher"
    )


def test_evidence_creation():
    evidence = make_evidence()

    assert evidence.id == (
        "evidence_1"
    )

    assert evidence.source_id == (
        "src_1"
    )

    assert (
        evidence.relevance_score
        == 0.95
    )


def test_claim_creation():
    claim = make_claim()

    assert claim.id == "claim_1"

    assert claim.confidence == "high"

    assert claim.evidence_ids == [
        "evidence_1"
    ]


def test_research_result_creation():
    result = ResearchResult(
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
                "Answer quality depends "
                "on retrieval quality."
            )
        ],
    )

    assert result.question == (
        "What is RAG?"
    )

    assert len(result.sources) == 1
    assert len(result.evidence) == 1
    assert len(result.claims) == 1


def test_research_result_serializes_to_json():
    result = ResearchResult(
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
    )

    json_text = result.model_dump_json(
        indent=2
    )

    assert '"question"' in json_text
    assert '"claim_1"' in json_text
    assert '"evidence_1"' in json_text
    assert '"src_1"' in json_text


def test_rejects_unknown_source_reference():
    bad_evidence = Evidence(
        id="evidence_1",
        source_id="src_missing",
        text="Some evidence.",
    )

    with pytest.raises(
        ValidationError,
        match="unknown source",
    ):
        ResearchResult(
            question="Test question",
            summary="Test summary",
            sources=[
                make_source(),
            ],
            evidence=[
                bad_evidence,
            ],
            claims=[],
        )


def test_rejects_unknown_evidence_reference():
    bad_claim = Claim(
        id="claim_1",
        text="Unsupported claim.",
        confidence="high",
        evidence_ids=[
            "evidence_missing"
        ],
    )

    with pytest.raises(
        ValidationError,
        match="unknown evidence",
    ):
        ResearchResult(
            question="Test question",
            summary="Test summary",
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


def test_relevance_score_must_be_valid():
    with pytest.raises(
        ValidationError,
    ):
        Evidence(
            id="evidence_1",
            source_id="src_1",
            text="Evidence text.",
            relevance_score=1.5,
        )
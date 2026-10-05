import json
from datetime import datetime, timezone

import pytest

from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)
from agents.writer.context import (
    build_writer_context,
    parse_research_result,
)


def make_research_result() -> ResearchResult:
    sources = [
        Source(
            id="src_1",
            title="Source One",
            url="https://example.com/one",
            publisher="example.com",
            published_at=None,
            retrieved_at=datetime(
                2026,
                10,
                5,
                tzinfo=timezone.utc,
            ),
            source_type="web",
        ),
        Source(
            id="src_2",
            title="Source Two",
            url="https://example.com/two",
            publisher="example.com",
            published_at=None,
            retrieved_at=datetime(
                2026,
                10,
                5,
                tzinfo=timezone.utc,
            ),
            source_type="web",
        ),
    ]

    evidence = [
        Evidence(
            id="evidence_1",
            source_id="src_1",
            text="Evidence from source one.",
            relevance_score=1.0,
        ),
        Evidence(
            id="evidence_2",
            source_id="src_2",
            text="Evidence from source two.",
            relevance_score=0.8,
        ),
    ]

    claims = [
        Claim(
            id="claim_1",
            text="RAG uses retrieved information.",
            confidence="high",
            evidence_ids=[
                "evidence_1",
            ],
        ),
        Claim(
            id="claim_2",
            text=(
                "RAG can use external "
                "knowledge sources."
            ),
            confidence="medium",
            evidence_ids=[
                "evidence_1",
                "evidence_2",
            ],
        ),
    ]

    return ResearchResult(
        question="What is RAG?",
        summary=(
            "RAG combines retrieval "
            "with generation."
        ),
        sources=sources,
        evidence=evidence,
        claims=claims,
        caveats=[
            "Retrieval quality matters."
        ],
    )


def test_parse_research_result():
    research = make_research_result()

    raw = research.model_dump_json()

    parsed = parse_research_result(
        raw
    )

    assert parsed.question == (
        "What is RAG?"
    )

    assert len(parsed.claims) == 2


def test_parse_rejects_empty_input():
    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        parse_research_result(
            "   "
        )


def test_parse_rejects_invalid_json():
    with pytest.raises(
        ValueError,
        match=(
            "Invalid structured "
            "research result"
        ),
    ):
        parse_research_result(
            "not json"
        )


def test_build_context_contains_question():
    context = build_writer_context(
        make_research_result()
    )

    assert "What is RAG?" in context


def test_build_context_contains_claim_citations():
    context = build_writer_context(
        make_research_result()
    )

    assert (
        "RAG uses retrieved information. "
        "[src_1]"
        in context
    )

    assert (
        "[src_1] [src_2]"
        in context
    )


def test_build_context_contains_sources():
    context = build_writer_context(
        make_research_result()
    )

    assert (
        "[src_1] Source One — "
        "https://example.com/one"
        in context
    )

    assert (
        "[src_2] Source Two — "
        "https://example.com/two"
        in context
    )


def test_build_context_contains_caveats():
    context = build_writer_context(
        make_research_result()
    )

    assert (
        "Retrieval quality matters."
        in context
    )
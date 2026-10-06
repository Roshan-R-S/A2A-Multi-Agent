from datetime import datetime, timezone

import pytest

from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)
from agents.verifier.context import (
    build_verifier_context,
    extract_citations,
    find_unknown_citations,
    parse_verification_request,
)
from agents.verifier.schemas import (
    VerificationRequest,
)


def make_research_result() -> ResearchResult:
    source = Source(
        id="src_1",
        title="Example Source",
        url="https://example.com/rag",
        publisher="example.com",
        published_at=None,
        retrieved_at=datetime(
            2026,
            10,
            6,
            tzinfo=timezone.utc,
        ),
        source_type="web",
    )

    evidence = Evidence(
        id="evidence_1",
        source_id="src_1",
        text=(
            "RAG retrieves relevant information "
            "before generation."
        ),
        relevance_score=1.0,
    )

    claim = Claim(
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

    return ResearchResult(
        question="What is RAG?",
        summary=(
            "RAG combines retrieval "
            "with generation."
        ),
        sources=[
            source,
        ],
        evidence=[
            evidence,
        ],
        claims=[
            claim,
        ],
        caveats=[
            "Retrieval quality matters."
        ],
    )


def make_request() -> VerificationRequest:
    return VerificationRequest(
        research=make_research_result(),
        draft=(
            "RAG uses retrieved information "
            "during generation. [src_1]"
        ),
    )


def test_parse_verification_request():
    request = make_request()

    raw = request.model_dump_json()

    parsed = parse_verification_request(
        raw
    )

    assert parsed.research.question == (
        "What is RAG?"
    )

    assert "[src_1]" in parsed.draft


def test_parse_rejects_empty_request():
    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        parse_verification_request(
            "   "
        )


def test_parse_rejects_invalid_request():
    with pytest.raises(
        ValueError,
        match=(
            "Invalid verification request"
        ),
    ):
        parse_verification_request(
            "not json"
        )


def test_extract_citations():
    citations = extract_citations(
        (
            "One claim [src_1]. "
            "Another [src_2]."
        )
    )

    assert citations == {
        "src_1",
        "src_2",
    }


def test_unknown_citations_are_detected():
    request = VerificationRequest(
        research=make_research_result(),
        draft=(
            "Supported claim [src_1]. "
            "Bad claim [src_999]."
        ),
    )

    unknown = find_unknown_citations(
        request
    )

    assert unknown == {
        "src_999"
    }


def test_known_citations_are_accepted():
    unknown = find_unknown_citations(
        make_request()
    )

    assert unknown == set()


def test_context_contains_claim():
    context = build_verifier_context(
        make_request()
    )

    assert (
        "RAG uses retrieved information "
        "during generation."
        in context
    )


def test_context_contains_evidence():
    context = build_verifier_context(
        make_request()
    )

    assert (
        "RAG retrieves relevant information "
        "before generation."
        in context
    )


def test_context_contains_source():
    context = build_verifier_context(
        make_request()
    )

    assert "[src_1]" in context

    assert (
        "https://example.com/rag"
        in context
    )


def test_context_contains_caveats_and_draft():
    context = build_verifier_context(
        make_request()
    )

    assert (
        "Retrieval quality matters."
        in context
    )

    assert (
        "WRITER DRAFT"
        in context
    )
from datetime import (
    datetime,
    timezone,
)

import pytest

import agents.writer.generator as generator_module
from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)
from agents.writer.generator import (
    CitationAwareWriter,
)
from agents.writer.revision import (
    RevisionIssue,
    WriterRevisionRequest,
    build_revision_context,
    parse_revision_request,
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
            "RAG can reduce hallucinations "
            "by grounding answers in retrieved "
            "information."
        ),
        relevance_score=1.0,
    )

    claim = Claim(
        id="claim_1",
        text=(
            "RAG can reduce hallucinations."
        ),
        confidence="high",
        evidence_ids=[
            "evidence_1",
        ],
    )

    return ResearchResult(
        question="Why is RAG useful?",
        summary=(
            "RAG can improve grounded "
            "generation."
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
            "RAG does not guarantee accuracy."
        ],
    )


def make_request() -> WriterRevisionRequest:
    return WriterRevisionRequest(
        research=make_research_result(),
        draft=(
            "RAG completely eliminates "
            "hallucinations. [src_1]"
        ),
        feedback=(
            "Avoid absolute claims."
        ),
        issues=[
            RevisionIssue(
                type="overstated_certainty",
                statement=(
                    "RAG completely eliminates "
                    "hallucinations."
                ),
                source_ids=[
                    "src_1"
                ],
                feedback=(
                    "The source supports reduction, "
                    "not complete elimination."
                ),
            )
        ],
    )


def test_revision_request_serializes():
    request = make_request()

    raw = request.model_dump_json()

    parsed = parse_revision_request(
        raw
    )

    assert parsed.mode == "revise"

    assert (
        parsed.feedback
        == "Avoid absolute claims."
    )


def test_revision_context_contains_draft():
    context = build_revision_context(
        make_request()
    )

    assert (
        "RAG completely eliminates"
        in context
    )


def test_revision_context_contains_feedback():
    context = build_revision_context(
        make_request()
    )

    assert (
        "Avoid absolute claims."
        in context
    )

    assert (
        "overstated_certainty"
        in context
    )


def test_revision_context_contains_research():
    context = build_revision_context(
        make_request()
    )

    assert (
        "RAG can reduce hallucinations"
        in context
    )

    assert "[src_1]" in context


@pytest.mark.asyncio
async def test_writer_revises_from_feedback(
    monkeypatch,
):
    captured = {}

    async def fake_generate_text(
        prompt: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        captured["prompt"] = prompt
        captured["temperature"] = temperature

        return (
            "RAG can reduce hallucinations "
            "by grounding responses in retrieved "
            "information. [src_1]"
        )

    monkeypatch.setattr(
        generator_module,
        "generate_text",
        fake_generate_text,
    )

    writer = CitationAwareWriter()

    result = await writer.revise(
        make_request()
    )

    assert (
        "can reduce hallucinations"
        in result
    )

    assert "[src_1]" in result

    assert (
        "CURRENT DRAFT"
        in captured["prompt"]
    )

    assert (
        "VERIFIER FEEDBACK"
        in captured["prompt"]
    )

    assert (
        captured["temperature"]
        == 0.0
    )


@pytest.mark.asyncio
async def test_revision_rejects_unknown_citation(
    monkeypatch,
):
    async def fake_generate_text(
        prompt: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        return (
            "RAG reduces hallucinations. "
            "[src_999]"
        )

    monkeypatch.setattr(
        generator_module,
        "generate_text",
        fake_generate_text,
    )

    writer = CitationAwareWriter()

    with pytest.raises(
        RuntimeError,
        match="unknown source citations",
    ):
        await writer.revise(
            make_request()
        )
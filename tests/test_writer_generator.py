from datetime import datetime, timezone

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


def make_research_result() -> ResearchResult:
    source = Source(
        id="src_1",
        title="Example RAG Source",
        url="https://example.com/rag",
        publisher="example.com",
        published_at=None,
        retrieved_at=datetime(
            2026,
            10,
            5,
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


def test_extract_citations():
    citations = (
        CitationAwareWriter.extract_citations(
            (
                "RAG retrieves information "
                "[src_1] and uses it [src_2]."
            )
        )
    )

    assert citations == {
        "src_1",
        "src_2",
    }


def test_validate_accepts_known_citation():
    research = make_research_result()

    CitationAwareWriter.validate_citations(
        "RAG uses retrieved information. [src_1]",
        research,
    )


def test_validate_rejects_unknown_citation():
    research = make_research_result()

    with pytest.raises(
        RuntimeError,
        match="unknown source citations",
    ):
        CitationAwareWriter.validate_citations(
            "RAG uses retrieval. [src_999]",
            research,
        )


def test_validate_requires_citation_for_claims():
    research = make_research_result()

    with pytest.raises(
        RuntimeError,
        match="no source citations",
    ):
        CitationAwareWriter.validate_citations(
            "RAG uses retrieved information.",
            research,
        )


@pytest.mark.asyncio
async def test_writer_calls_llm(
    monkeypatch,
):
    captured = {}

    async def fake_generate_text(
        prompt: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        captured["temperature"] = temperature

        return (
            "RAG combines retrieval with "
            "generation. [src_1]"
        )

    monkeypatch.setattr(
        generator_module,
        "generate_text",
        fake_generate_text,
    )

    writer = CitationAwareWriter()

    result = await writer.write(
        make_research_result()
    )

    assert result == (
        "RAG combines retrieval with "
        "generation. [src_1]"
    )

    assert (
        "SUPPORTED CLAIMS"
        in captured["prompt"]
    )

    assert (
        "[src_1]"
        in captured["prompt"]
    )

    assert (
        captured["temperature"]
        == 0.2
    )


@pytest.mark.asyncio
async def test_writer_rejects_llm_unknown_citation(
    monkeypatch,
):
    async def fake_generate_text(
        prompt: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        return (
            "RAG uses retrieval. "
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
        await writer.write(
            make_research_result()
        )


@pytest.mark.asyncio
async def test_writer_rejects_missing_citations(
    monkeypatch,
):
    async def fake_generate_text(
        prompt: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        return (
            "RAG uses retrieved information."
        )

    monkeypatch.setattr(
        generator_module,
        "generate_text",
        fake_generate_text,
    )

    writer = CitationAwareWriter()

    with pytest.raises(
        RuntimeError,
        match="no source citations",
    ):
        await writer.write(
            make_research_result()
        )


@pytest.mark.asyncio
async def test_writer_rejects_empty_response(
    monkeypatch,
):
    async def fake_generate_text(
        prompt: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        return "   "

    monkeypatch.setattr(
        generator_module,
        "generate_text",
        fake_generate_text,
    )

    writer = CitationAwareWriter()

    with pytest.raises(
        RuntimeError,
        match="empty response",
    ):
        await writer.write(
            make_research_result()
        )


@pytest.mark.asyncio
async def test_writer_repairs_missing_citations(
    monkeypatch,
):
    responses = [
        (
            "RAG combines retrieval "
            "with generation."
        ),
        (
            "RAG combines retrieval "
            "with generation. [src_1]"
        ),
    ]

    calls = []

    async def fake_generate_text(
        prompt: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        calls.append(
            {
                "prompt": prompt,
                "temperature": temperature,
            }
        )

        return responses[
            len(calls) - 1
        ]

    monkeypatch.setattr(
        generator_module,
        "generate_text",
        fake_generate_text,
    )

    writer = CitationAwareWriter()

    result = await writer.write(
        make_research_result()
    )

    assert result == (
        "RAG combines retrieval "
        "with generation. [src_1]"
    )

    assert len(calls) == 2

    assert calls[0]["temperature"] == 0.2
    assert calls[1]["temperature"] == 0.0

    assert (
        "failed citation validation"
        in calls[1]["prompt"]
    )

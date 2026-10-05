from datetime import datetime, timezone

import pytest
from starlette.testclient import TestClient

from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)
from agents.writer.app import app
from agents.writer.executor import WriterAgent


client = TestClient(app)


class FakeCitationAwareWriter:
    def __init__(self) -> None:
        self.calls = []

    async def write(
        self,
        research: ResearchResult,
    ) -> str:
        self.calls.append(
            research
        )

        return (
            "RAG combines retrieval with "
            "generation. [src_1]"
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
            "RAG retrieves relevant "
            "information before generation."
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


def test_writer_health_endpoint():
    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    assert (
        response.json()["status"]
        == "ok"
    )


def test_writer_agent_card_endpoint():
    response = client.get(
        "/.well-known/agent-card.json"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == (
        "Writer Agent"
    )

    assert data[
        "defaultInputModes"
    ] == [
        "application/json"
    ]

    assert data[
        "defaultOutputModes"
    ] == [
        "text/plain"
    ]

    skill_ids = {
        skill["id"]
        for skill in data["skills"]
    }

    assert (
        "write_explanation"
        in skill_ids
    )


@pytest.mark.asyncio
async def test_writer_agent_parses_research_json():
    fake_writer = (
        FakeCitationAwareWriter()
    )

    agent = WriterAgent(
        writer=fake_writer
    )

    research = (
        make_research_result()
    )

    result = await agent.invoke(
        research.model_dump_json()
    )

    assert result == (
        "RAG combines retrieval with "
        "generation. [src_1]"
    )

    assert len(
        fake_writer.calls
    ) == 1

    parsed_research = (
        fake_writer.calls[0]
    )

    assert (
        parsed_research.question
        == "What is RAG?"
    )

    assert (
        parsed_research.claims[0].id
        == "claim_1"
    )


@pytest.mark.asyncio
async def test_writer_agent_preserves_sources():
    fake_writer = (
        FakeCitationAwareWriter()
    )

    agent = WriterAgent(
        writer=fake_writer
    )

    await agent.invoke(
        make_research_result()
        .model_dump_json()
    )

    research = (
        fake_writer.calls[0]
    )

    assert (
        research.sources[0].id
        == "src_1"
    )

    assert (
        research.evidence[0].source_id
        == "src_1"
    )


@pytest.mark.asyncio
async def test_writer_agent_rejects_empty_input():
    agent = WriterAgent(
        writer=FakeCitationAwareWriter()
    )

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        await agent.invoke(
            "   "
        )


@pytest.mark.asyncio
async def test_writer_agent_rejects_invalid_json():
    agent = WriterAgent(
        writer=FakeCitationAwareWriter()
    )

    with pytest.raises(
        ValueError,
        match=(
            "Invalid structured "
            "research result"
        ),
    ):
        await agent.invoke(
            "not json"
        )
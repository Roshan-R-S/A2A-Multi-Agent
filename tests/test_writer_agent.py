import json
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


class FakeCitationAwareWriter:
    def __init__(self) -> None:
        self.received = None
        self.revision_request = None

    async def write(
        self,
        research: ResearchResult,
    ) -> str:
        self.received = research

        return (
            "RAG combines retrieval with "
            "generation. [src_1]"
        )

    async def revise(
        self,
        request,
    ) -> str:
        self.revision_request = request

        return (
            "Revised answer based on verifier "
            "feedback. [src_1]"
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


def test_writer_health_endpoint():
    client = TestClient(app)

    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["agent"] == "Writer Agent"


def test_writer_agent_card_endpoint():
    client = TestClient(app)

    response = client.get(
        "/.well-known/agent-card.json"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Writer Agent"

    assert data["defaultInputModes"] == [
        "application/json"
    ]

    assert data["defaultOutputModes"] == [
        "text/plain"
    ]

    assert (
        data["skills"][0]["id"]
        == "write_explanation"
    )


@pytest.mark.asyncio
async def test_writer_agent_parses_research_json():
    fake = FakeCitationAwareWriter()

    agent = WriterAgent(
        writer=fake
    )

    research = make_research_result()

    result = await agent.invoke(
        research.model_dump_json()
    )

    assert fake.received is not None

    assert (
        fake.received.question
        == "What is RAG?"
    )

    assert "[src_1]" in result


@pytest.mark.asyncio
async def test_writer_agent_preserves_sources():
    fake = FakeCitationAwareWriter()

    agent = WriterAgent(
        writer=fake
    )

    research = make_research_result()

    await agent.invoke(
        research.model_dump_json()
    )

    assert fake.received is not None

    assert (
        fake.received.sources[0].id
        == "src_1"
    )

    assert (
        fake.received.sources[0].url
        == "https://example.com/rag"
    )


@pytest.mark.asyncio
async def test_writer_agent_rejects_empty_input():
    fake = FakeCitationAwareWriter()

    agent = WriterAgent(
        writer=fake
    )

    with pytest.raises(
        ValueError,
        match="Writer request cannot be empty",
    ):
        await agent.invoke(
            "   "
        )


@pytest.mark.asyncio
async def test_writer_agent_rejects_invalid_json():
    fake = FakeCitationAwareWriter()

    agent = WriterAgent(
        writer=fake
    )

    with pytest.raises(
        ValueError,
        match="Invalid structured research result",
    ):
        await agent.invoke(
            "not json"
        )


@pytest.mark.asyncio
async def test_writer_agent_routes_revision_request():
    fake = FakeCitationAwareWriter()

    agent = WriterAgent(
        writer=fake
    )

    research = make_research_result()

    payload = {
        "mode": "revise",
        "research": research.model_dump(
            mode="json"
        ),
        "draft": (
            "RAG completely eliminates "
            "hallucinations. [src_1]"
        ),
        "feedback": (
            "Avoid absolute claims."
        ),
        "issues": [
            {
                "type": "overstated_certainty",
                "statement": (
                    "RAG completely eliminates "
                    "hallucinations."
                ),
                "source_ids": [
                    "src_1"
                ],
                "feedback": (
                    "Use less absolute wording."
                ),
            }
        ],
    }

    result = await agent.invoke(
        json.dumps(payload)
    )

    assert (
        "Revised answer"
        in result
    )

    assert (
        fake.revision_request
        is not None
    )

    assert (
        fake.revision_request.mode
        == "revise"
    )


@pytest.mark.asyncio
async def test_writer_agent_preserves_normal_write_route():
    fake = FakeCitationAwareWriter()

    agent = WriterAgent(
        writer=fake
    )

    research = make_research_result()

    await agent.invoke(
        research.model_dump_json()
    )

    assert fake.received is not None

    assert (
        fake.revision_request
        is None
    )

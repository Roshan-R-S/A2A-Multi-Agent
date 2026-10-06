import json
from datetime import datetime, timezone

import pytest
from starlette.testclient import TestClient

from agents.research.app import app
from agents.research.executor import ResearchAgent
from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)


client = TestClient(app)


class FakeResearchPipeline:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def run(
        self,
        question: str,
        *,
        max_results: int = 5,
        max_evidence: int = 10,
        max_claims: int = 8,
    ) -> ResearchResult:

        self.calls.append(
            {
                "question": question,
                "max_results": max_results,
                "max_evidence": max_evidence,
                "max_claims": max_claims,
            }
        )

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
            question=question,
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


def test_research_health_endpoint():
    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"


def test_research_agent_card_endpoint():
    response = client.get(
        "/.well-known/agent-card.json"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == (
        "Research Agent"
    )

    assert data["defaultInputModes"] == [
        "text/plain"
    ]

    assert data["defaultOutputModes"] == [
        "application/json"
    ]

    skill_ids = {
        skill["id"]
        for skill in data["skills"]
    }

    assert "research_topic" in skill_ids

    research_skill = next(
        skill
        for skill in data["skills"]
        if skill["id"] == "research_topic"
    )

    assert research_skill["inputModes"] == [
        "text/plain"
    ]

    assert research_skill["outputModes"] == [
        "application/json"
    ]


@pytest.mark.asyncio
async def test_research_agent_returns_structured_json():
    pipeline = FakeResearchPipeline()

    agent = ResearchAgent(
        pipeline=pipeline
    )

    raw_result = await agent.invoke(
        "What is RAG?"
    )

    result = json.loads(
        raw_result
    )

    assert result["question"] == (
        "What is RAG?"
    )

    assert result["summary"] == (
        "RAG combines retrieval with generation."
    )

    assert len(
        result["sources"]
    ) == 1

    assert len(
        result["evidence"]
    ) == 1

    assert len(
        result["claims"]
    ) == 1

    assert (
        result["claims"][0][
            "evidence_ids"
        ]
        == ["evidence_1"]
    )

    assert (
        result["evidence"][0][
            "source_id"
        ]
        == "src_1"
    )


@pytest.mark.asyncio
async def test_research_agent_uses_pipeline_limits():
    pipeline = FakeResearchPipeline()

    agent = ResearchAgent(
        pipeline=pipeline
    )

    await agent.invoke(
        "What is RAG?"
    )

    assert len(
        pipeline.calls
    ) == 1

    call = pipeline.calls[0]

    assert call["question"] == (
        "What is RAG?"
    )

    assert call["max_results"] == 5
    assert call["max_evidence"] == 10
    assert call["max_claims"] == 8


@pytest.mark.asyncio
async def test_research_agent_strips_question():
    pipeline = FakeResearchPipeline()

    agent = ResearchAgent(
        pipeline=pipeline
    )

    raw_result = await agent.invoke(
        "   What is RAG?   "
    )

    result = json.loads(
        raw_result
    )

    assert result["question"] == (
        "What is RAG?"
    )

    assert (
        pipeline.calls[0]["question"]
        == "What is RAG?"
    )


@pytest.mark.asyncio
async def test_research_agent_rejects_empty_question():
    pipeline = FakeResearchPipeline()

    agent = ResearchAgent(
        pipeline=pipeline
    )

    with pytest.raises(
        ValueError,
        match=(
            "Research question "
            "cannot be empty"
        ),
    ):
        await agent.invoke(
            "   "
        )

    assert pipeline.calls == []

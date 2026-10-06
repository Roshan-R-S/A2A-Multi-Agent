from datetime import datetime, timezone

import pytest
from starlette.testclient import TestClient

from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)
from agents.verifier.app import app
from agents.verifier.executor import (
    VerifierAgent,
)
from agents.verifier.schemas import (
    VerificationRequest,
    VerificationResult,
)


class FakeEvidenceAwareVerifier:
    def __init__(
        self,
        result: VerificationResult,
    ) -> None:
        self.result = result
        self.received = None

    async def verify(
        self,
        request: VerificationRequest,
    ) -> VerificationResult:
        self.received = request
        return self.result


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


def make_payload() -> str:
    request = VerificationRequest(
        research=make_research_result(),
        draft=(
            "RAG uses retrieved information "
            "during generation. [src_1]"
        ),
    )

    return request.model_dump_json()


def test_verifier_health_endpoint():
    client = TestClient(app)

    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["agent"] == "Verifier Agent"


def test_verifier_agent_card_endpoint():
    client = TestClient(app)

    response = client.get(
        "/.well-known/agent-card.json"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Verifier Agent"

    assert data["defaultInputModes"] == [
        "application/json"
    ]

    assert data["defaultOutputModes"] == [
        "application/json"
    ]

    assert (
        data["skills"][0]["id"]
        == "verify_answer"
    )


@pytest.mark.asyncio
async def test_verifier_agent_parses_request():
    fake = FakeEvidenceAwareVerifier(
        VerificationResult(
            verdict="PASS",
            issues=[],
            feedback="",
        )
    )

    agent = VerifierAgent(
        verifier=fake
    )

    await agent.invoke(
        make_payload()
    )

    assert fake.received is not None

    assert (
        fake.received.research.question
        == "What is RAG?"
    )

    assert (
        "[src_1]"
        in fake.received.draft
    )


@pytest.mark.asyncio
async def test_verifier_agent_returns_pass_json():
    fake = FakeEvidenceAwareVerifier(
        VerificationResult(
            verdict="PASS",
            issues=[],
            feedback="",
        )
    )

    agent = VerifierAgent(
        verifier=fake
    )

    result = await agent.invoke(
        make_payload()
    )

    parsed = (
        VerificationResult
        .model_validate_json(
            result
        )
    )

    assert parsed.verdict == "PASS"
    assert parsed.issues == []


@pytest.mark.asyncio
async def test_verifier_agent_returns_fail_json():
    fake = FakeEvidenceAwareVerifier(
        VerificationResult(
            verdict="FAIL",
            issues=[
                {
                    "type": "missing_citation",
                    "statement": (
                        "A factual statement."
                    ),
                    "source_ids": [],
                    "feedback": (
                        "Add a citation."
                    ),
                }
            ],
            feedback=(
                "Revise the answer."
            ),
        )
    )

    agent = VerifierAgent(
        verifier=fake
    )

    result = await agent.invoke(
        make_payload()
    )

    parsed = (
        VerificationResult
        .model_validate_json(
            result
        )
    )

    assert parsed.verdict == "FAIL"

    assert (
        parsed.issues[0].type
        == "missing_citation"
    )


@pytest.mark.asyncio
async def test_verifier_agent_rejects_empty_input():
    agent = VerifierAgent(
        verifier=FakeEvidenceAwareVerifier(
            VerificationResult(
                verdict="PASS",
                issues=[],
                feedback="",
            )
        )
    )

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        await agent.invoke(
            "   "
        )


@pytest.mark.asyncio
async def test_verifier_agent_rejects_invalid_json():
    agent = VerifierAgent(
        verifier=FakeEvidenceAwareVerifier(
            VerificationResult(
                verdict="PASS",
                issues=[],
                feedback="",
            )
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "Invalid verification request"
        ),
    ):
        await agent.invoke(
            "not json"
        )
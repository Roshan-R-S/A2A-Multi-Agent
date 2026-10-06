import json
from datetime import datetime, timezone

import httpx
import pytest

import orchestrator.workflow as workflow_module
from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)
from core.config import settings
from orchestrator.discovery import (
    AgentDiscoveryError,
    DiscoveredAgent,
    discover_agent,
)
from orchestrator.workflow import (
    ResearchWriterWorkflow,
)


class FakeA2AClient:
    def __init__(
        self,
        responses,
    ):
        self.responses = list(
            responses
        )

        self.calls = []

    async def send_text(
        self,
        agent_url: str,
        text: str,
    ) -> str:
        self.calls.append(
            {
                "agent_url": agent_url,
                "text": text,
            }
        )

        if not self.responses:
            raise RuntimeError(
                "FakeA2AClient has "
                "no response left."
            )

        return self.responses.pop(0)


def make_agent(
    name: str,
    url: str,
    skills: tuple[str, ...],
) -> DiscoveredAgent:
    return DiscoveredAgent(
        name=name,
        description=(
            f"{name} description"
        ),
        version="0.1.0",
        url=url,
        protocol_binding="JSONRPC",
        protocol_version="1.0",
        skills=skills,
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
            "by grounding answers."
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
            "RAG does not guarantee accuracy."
        ],
    )


def pass_result() -> str:
    return json.dumps(
        {
            "verdict": "PASS",
            "issues": [],
            "feedback": "",
        }
    )


def fail_result() -> str:
    return json.dumps(
        {
            "verdict": "FAIL",
            "issues": [
                {
                    "type": (
                        "overstated_certainty"
                    ),
                    "statement": (
                        "RAG eliminates "
                        "hallucinations."
                    ),
                    "source_ids": [
                        "src_1"
                    ],
                    "feedback": (
                        "Research supports "
                        "reduction, not elimination."
                    ),
                }
            ],
            "feedback": (
                "Use less absolute language."
            ),
        }
    )


async def fake_discover_all(
    base_url,
):
    if (
        base_url
        == settings.research_agent_url
    ):
        return make_agent(
            name="Research Agent",
            url=settings.research_agent_url,
            skills=(
                "research_topic",
            ),
        )

    if (
        base_url
        == settings.writer_agent_url
    ):
        return make_agent(
            name="Writer Agent",
            url=settings.writer_agent_url,
            skills=(
                "write_explanation",
            ),
        )

    if (
        base_url
        == settings.verifier_agent_url
    ):
        return make_agent(
            name="Verifier Agent",
            url=settings.verifier_agent_url,
            skills=(
                "verify_answer",
            ),
        )

    raise AssertionError(
        f"Unexpected URL: {base_url}"
    )


@pytest.mark.asyncio
async def test_discover_agent_parses_valid_card():
    card = {
        "name": "Research Agent",
        "description": "Researches topics.",
        "version": "0.1.0",
        "supportedInterfaces": [
            {
                "url": (
                    "http://127.0.0.1:8001"
                ),
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "skills": [
            {
                "id": "research_topic",
            }
        ],
    }

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            status_code=200,
            json=card,
            request=request,
        )
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        result = await discover_agent(
            "http://127.0.0.1:8001",
            client=client,
        )

    assert result.name == (
        "Research Agent"
    )

    assert result.url == (
        "http://127.0.0.1:8001"
    )

    assert (
        result.protocol_binding
        == "JSONRPC"
    )

    assert (
        result.protocol_version
        == "1.0"
    )

    assert result.skills == (
        "research_topic",
    )


@pytest.mark.asyncio
async def test_discover_agent_connection_failure():
    def handler(request):
        raise httpx.ConnectError(
            "Connection failed.",
            request=request,
        )

    transport = httpx.MockTransport(
        handler
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        with pytest.raises(
            AgentDiscoveryError,
            match="Could not connect",
        ):
            await discover_agent(
                (
                    "http://127.0.0.1:"
                    "9999"
                ),
                client=client,
            )


@pytest.mark.asyncio
async def test_discover_agent_timeout():
    def handler(request):
        raise httpx.ReadTimeout(
            "Timed out.",
            request=request,
        )

    transport = httpx.MockTransport(
        handler
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        with pytest.raises(
            AgentDiscoveryError,
            match="timed out",
        ):
            await discover_agent(
                (
                    "http://127.0.0.1:"
                    "9999"
                ),
                client=client,
            )


@pytest.mark.asyncio
async def test_discover_agent_rejects_missing_interface():
    card = {
        "name": "Broken Agent",
        "description": (
            "Missing interface."
        ),
        "version": "0.1.0",
        "supportedInterfaces": [],
        "skills": [],
    }

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            status_code=200,
            json=card,
            request=request,
        )
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        with pytest.raises(
            AgentDiscoveryError,
            match=(
                "advertised no interfaces"
            ),
        ):
            await discover_agent(
                (
                    "http://127.0.0.1:"
                    "9999"
                ),
                client=client,
            )


@pytest.mark.asyncio
async def test_workflow_rejects_empty_question():
    workflow = ResearchWriterWorkflow(
        client=FakeA2AClient([])
    )

    with pytest.raises(
        ValueError,
        match="Question cannot be empty",
    ):
        await workflow.run(
            "   "
        )


@pytest.mark.asyncio
async def test_workflow_rejects_missing_research_skill(
    monkeypatch,
):
    research = make_agent(
        name="Research Agent",
        url=settings.research_agent_url,
        skills=(),
    )

    writer = make_agent(
        name="Writer Agent",
        url=settings.writer_agent_url,
        skills=(
            "write_explanation",
        ),
    )

    verifier = make_agent(
        name="Verifier Agent",
        url=settings.verifier_agent_url,
        skills=(
            "verify_answer",
        ),
    )

    async def fake_discover(
        base_url,
    ):
        if (
            base_url
            == settings.research_agent_url
        ):
            return research

        if (
            base_url
            == settings.writer_agent_url
        ):
            return writer

        if (
            base_url
            == settings.verifier_agent_url
        ):
            return verifier

        raise AssertionError(
            f"Unexpected URL: {base_url}"
        )

    monkeypatch.setattr(
        workflow_module,
        "discover_agent",
        fake_discover,
    )

    workflow = ResearchWriterWorkflow(
        client=FakeA2AClient([])
    )

    with pytest.raises(
        AgentDiscoveryError,
        match="research_topic",
    ):
        await workflow.run(
            "What is RAG?"
        )


@pytest.mark.asyncio
async def test_workflow_rejects_missing_verifier_skill(
    monkeypatch,
):
    research = make_agent(
        name="Research Agent",
        url=settings.research_agent_url,
        skills=(
            "research_topic",
        ),
    )

    writer = make_agent(
        name="Writer Agent",
        url=settings.writer_agent_url,
        skills=(
            "write_explanation",
        ),
    )

    verifier = make_agent(
        name="Verifier Agent",
        url=settings.verifier_agent_url,
        skills=(),
    )

    async def fake_discover(
        base_url,
    ):
        if (
            base_url
            == settings.research_agent_url
        ):
            return research

        if (
            base_url
            == settings.writer_agent_url
        ):
            return writer

        if (
            base_url
            == settings.verifier_agent_url
        ):
            return verifier

        raise AssertionError(
            f"Unexpected URL: {base_url}"
        )

    monkeypatch.setattr(
        workflow_module,
        "discover_agent",
        fake_discover,
    )

    workflow = ResearchWriterWorkflow(
        client=FakeA2AClient([])
    )

    with pytest.raises(
        AgentDiscoveryError,
        match="verify_answer",
    ):
        await workflow.run(
            "What is RAG?"
        )


@pytest.mark.asyncio
async def test_workflow_propagates_discovery_failure(
    monkeypatch,
):
    async def fake_discover(
        base_url,
    ):
        raise AgentDiscoveryError(
            "Discovery failed."
        )

    monkeypatch.setattr(
        workflow_module,
        "discover_agent",
        fake_discover,
    )

    workflow = ResearchWriterWorkflow(
        client=FakeA2AClient([])
    )

    with pytest.raises(
        AgentDiscoveryError,
        match="Discovery failed",
    ):
        await workflow.run(
            "What is RAG?"
        )


@pytest.mark.asyncio
async def test_complete_research_writer_verifier_workflow(
    monkeypatch,
):
    monkeypatch.setattr(
        workflow_module,
        "discover_agent",
        fake_discover_all,
    )

    research_json = (
        make_research_result()
        .model_dump_json()
    )

    draft = (
        "RAG can reduce hallucinations. "
        "[src_1]"
    )

    fake_client = FakeA2AClient(
        [
            research_json,
            draft,
            pass_result(),
        ]
    )

    workflow = ResearchWriterWorkflow(
        client=fake_client
    )

    result = await workflow.run(
        "What is RAG?"
    )

    assert result.question == (
        "What is RAG?"
    )

    assert result.research == (
        research_json
    )

    assert result.final_answer == draft

    assert len(
        fake_client.calls
    ) == 3

    assert (
        fake_client.calls[0][
            "agent_url"
        ]
        == settings.research_agent_url
    )

    assert (
        fake_client.calls[0]["text"]
        == "What is RAG?"
    )

    assert (
        fake_client.calls[1][
            "agent_url"
        ]
        == settings.writer_agent_url
    )

    assert (
        fake_client.calls[1]["text"]
        == research_json
    )

    assert (
        fake_client.calls[2][
            "agent_url"
        ]
        == settings.verifier_agent_url
    )

    verifier_payload = json.loads(
        fake_client.calls[2]["text"]
    )

    assert (
        verifier_payload["draft"]
        == draft
    )

    assert (
        verifier_payload[
            "research"
        ]["question"]
        == "What is RAG?"
    )


@pytest.mark.asyncio
async def test_workflow_revises_failed_verification(
    monkeypatch,
):
    monkeypatch.setattr(
        workflow_module,
        "discover_agent",
        fake_discover_all,
    )

    research_json = (
        make_research_result()
        .model_dump_json()
    )

    initial_draft = (
        "RAG eliminates hallucinations. "
        "[src_1]"
    )

    revised_draft = (
        "RAG can reduce hallucinations. "
        "[src_1]"
    )

    fake_client = FakeA2AClient(
        [
            research_json,
            initial_draft,
            fail_result(),
            revised_draft,
            pass_result(),
        ]
    )

    workflow = ResearchWriterWorkflow(
        client=fake_client
    )

    result = await workflow.run(
        "What is RAG?"
    )

    assert (
        result.final_answer
        == revised_draft
    )

    assert len(
        fake_client.calls
    ) == 5

    assert (
        fake_client.calls[2][
            "agent_url"
        ]
        == settings.verifier_agent_url
    )

    assert (
        fake_client.calls[3][
            "agent_url"
        ]
        == settings.writer_agent_url
    )

    revision_payload = json.loads(
        fake_client.calls[3]["text"]
    )

    assert (
        revision_payload["mode"]
        == "revise"
    )

    assert (
        revision_payload["draft"]
        == initial_draft
    )

    assert (
        revision_payload["feedback"]
        == "Use less absolute language."
    )

    assert (
        fake_client.calls[4][
            "agent_url"
        ]
        == settings.verifier_agent_url
    )
import httpx
import pytest

import orchestrator.workflow as workflow_module
from core.config import settings
from orchestrator.discovery import (
    AgentDiscoveryError,
    DiscoveredAgent,
    discover_agent,
)
from orchestrator.workflow import ResearchWriterWorkflow


class FakeA2AClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def send_text(self, agent_url: str, text: str) -> str:
        self.calls.append(
            {
                "agent_url": agent_url,
                "text": text,
            }
        )

        if not self.responses:
            raise RuntimeError(
                "FakeA2AClient has no response left."
            )

        return self.responses.pop(0)


def make_agent(
    name: str,
    url: str,
    skills: tuple[str, ...],
) -> DiscoveredAgent:
    return DiscoveredAgent(
        name=name,
        description=f"{name} description",
        version="0.1.0",
        url=url,
        protocol_binding="JSONRPC",
        protocol_version="1.0",
        skills=skills,
    )


@pytest.mark.asyncio
async def test_discover_agent_parses_valid_card():
    card = {
        "name": "Research Agent",
        "description": "Researches topics.",
        "version": "0.1.0",
        "supportedInterfaces": [
            {
                "url": "http://127.0.0.1:8001",
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

    assert result.name == "Research Agent"
    assert result.url == "http://127.0.0.1:8001"
    assert result.protocol_binding == "JSONRPC"
    assert result.protocol_version == "1.0"
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

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        with pytest.raises(
            AgentDiscoveryError,
            match="Could not connect",
        ):
            await discover_agent(
                "http://127.0.0.1:9999",
                client=client,
            )


@pytest.mark.asyncio
async def test_discover_agent_timeout():
    def handler(request):
        raise httpx.ReadTimeout(
            "Timed out.",
            request=request,
        )

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        with pytest.raises(
            AgentDiscoveryError,
            match="timed out",
        ):
            await discover_agent(
                "http://127.0.0.1:9999",
                client=client,
            )


@pytest.mark.asyncio
async def test_discover_agent_rejects_missing_interface():
    card = {
        "name": "Broken Agent",
        "description": "Missing interface.",
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
            match="advertised no interfaces",
        ):
            await discover_agent(
                "http://127.0.0.1:9999",
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
        await workflow.run("   ")


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
        skills=("write_explanation",),
    )

    verifier = make_agent(
        name="Verifier Agent",
        url=settings.verifier_agent_url,
        skills=("verify_answer",),
    )

    async def fake_discover(base_url):
        if base_url == settings.research_agent_url:
            return research

        if base_url == settings.writer_agent_url:
            return writer

        if base_url == settings.verifier_agent_url:
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
        skills=("research_topic",),
    )

    writer = make_agent(
        name="Writer Agent",
        url=settings.writer_agent_url,
        skills=("write_explanation",),
    )

    verifier = make_agent(
        name="Verifier Agent",
        url=settings.verifier_agent_url,
        skills=(),
    )

    async def fake_discover(base_url):
        if base_url == settings.research_agent_url:
            return research

        if base_url == settings.writer_agent_url:
            return writer

        if base_url == settings.verifier_agent_url:
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
    async def fake_discover(base_url):
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
    research = make_agent(
        name="Research Agent",
        url=settings.research_agent_url,
        skills=("research_topic",),
    )

    writer = make_agent(
        name="Writer Agent",
        url=settings.writer_agent_url,
        skills=("write_explanation",),
    )

    verifier = make_agent(
        name="Verifier Agent",
        url=settings.verifier_agent_url,
        skills=("verify_answer",),
    )

    async def fake_discover(base_url):
        if base_url == settings.research_agent_url:
            return research

        if base_url == settings.writer_agent_url:
            return writer

        if base_url == settings.verifier_agent_url:
            return verifier

        raise AssertionError(
            f"Unexpected URL: {base_url}"
        )

    monkeypatch.setattr(
        workflow_module,
        "discover_agent",
        fake_discover,
    )

    fake_client = FakeA2AClient(
        [
            "Mock research brief",
            "Mock final answer",
            (
                '{"verdict":"PASS",'
                '"issues":[],'
                '"feedback":""}'
            ),
        ]
    )

    workflow = ResearchWriterWorkflow(
        client=fake_client
    )

    result = await workflow.run(
        "What is RAG?"
    )

    assert result.question == "What is RAG?"
    assert result.research == (
        "Mock research brief"
    )
    assert result.final_answer == (
        "Mock final answer"
    )

    assert len(fake_client.calls) == 3

    assert (
        fake_client.calls[0]["agent_url"]
        == settings.research_agent_url
    )

    assert (
        fake_client.calls[1]["agent_url"]
        == settings.writer_agent_url
    )

    assert (
        fake_client.calls[2]["agent_url"]
        == settings.verifier_agent_url
    )

    assert (
        "Mock research brief"
        in fake_client.calls[1]["text"]
    )

    assert (
        "Mock final answer"
        in fake_client.calls[2]["text"]
    )


@pytest.mark.asyncio
async def test_workflow_rejects_failed_verification(
    monkeypatch,
):
    research = make_agent(
        name="Research Agent",
        url=settings.research_agent_url,
        skills=("research_topic",),
    )

    writer = make_agent(
        name="Writer Agent",
        url=settings.writer_agent_url,
        skills=("write_explanation",),
    )

    verifier = make_agent(
        name="Verifier Agent",
        url=settings.verifier_agent_url,
        skills=("verify_answer",),
    )

    async def fake_discover(base_url):
        if base_url == settings.research_agent_url:
            return research

        if base_url == settings.writer_agent_url:
            return writer

        if base_url == settings.verifier_agent_url:
            return verifier

        raise AssertionError(
            f"Unexpected URL: {base_url}"
        )

    monkeypatch.setattr(
        workflow_module,
        "discover_agent",
        fake_discover,
    )

    fake_client = FakeA2AClient(
        [
            "Mock research brief",
            "Bad writer answer",
            (
                '{"verdict":"FAIL",'
                '"issues":["Unsupported claim."],'
                '"feedback":"Remove the unsupported claim."}'
            ),
        ]
    )

    workflow = ResearchWriterWorkflow(
        client=fake_client
    )

    with pytest.raises(
        RuntimeError,
        match="Verifier rejected",
    ):
        await workflow.run(
            "What is RAG?"
        )

    assert len(fake_client.calls) == 3
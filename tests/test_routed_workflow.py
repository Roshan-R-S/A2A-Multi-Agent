"""Offline integration tests for the planner-enabled orchestrator."""

import json

import pytest

import orchestrator.routed_workflow as module
from agents.planner.settings import planner_agent_url
from orchestrator.discovery import AgentDiscoveryError, DiscoveredAgent
from orchestrator.routed_workflow import RoutedWorkflow
from orchestrator.workflow import WorkflowResult


class FakeClient:
    def __init__(self, answer):
        self.answer = answer
        self.calls = []

    async def send_text(self, url, text):
        self.calls.append((url, text))
        return self.answer


class FakeResearchWorkflow:
    def __init__(self):
        self.calls = []

    async def run(self, question):
        self.calls.append(question)
        return WorkflowResult(
            question=question,
            research='{"question":"Test"}',
            final_answer="Verified answer [src_1]",
        )


def make_discovered(skills=("plan_or_route",), binding="JSONRPC"):
    return DiscoveredAgent(
        name="Planner Agent",
        description="Routes tasks",
        version="0.2.0",
        url=planner_agent_url,
        protocol_binding=binding,
        protocol_version="1.0",
        skills=skills,
    )


@pytest.mark.asyncio
async def test_research_route_runs_existing_workflow(monkeypatch):
    async def discover(url):
        assert url == planner_agent_url
        return make_discovered()

    monkeypatch.setattr(module, "discover_agent", discover)
    client = FakeClient(json.dumps({"route": "research", "reason": "Evidence needed", "steps": []}))
    research = FakeResearchWorkflow()
    result = await RoutedWorkflow(client=client, research_workflow=research).run("  Explain RAG  ")

    assert client.calls == [(planner_agent_url, "Explain RAG")]
    assert research.calls == ["Explain RAG"]
    assert result.verified is True
    assert result.research is not None
    assert "[src_1]" in result.final_answer


@pytest.mark.asyncio
async def test_plan_only_never_executes_research(monkeypatch):
    async def discover(url):
        return make_discovered()

    monkeypatch.setattr(module, "discover_agent", discover)
    client = FakeClient(json.dumps({
        "route": "plan_only", "reason": "Roadmap needed", "steps": ["Choose architecture", "Write tests"]
    }))
    research = FakeResearchWorkflow()
    result = await RoutedWorkflow(client=client, research_workflow=research).run("Plan a RAG app")

    assert research.calls == []
    assert result.verified is False
    assert result.research is None
    assert "not executed" in result.final_answer
    assert "1. Choose architecture" in result.final_answer


@pytest.mark.asyncio
async def test_unsupported_agent_skill_rejected(monkeypatch):
    async def discover(url):
        return make_discovered(skills=())

    monkeypatch.setattr(module, "discover_agent", discover)
    with pytest.raises(AgentDiscoveryError, match="plan_or_route"):
        await RoutedWorkflow(client=FakeClient("{}"), research_workflow=FakeResearchWorkflow()).run("hi")


@pytest.mark.asyncio
async def test_invalid_planner_reply_does_not_execute_workflow(monkeypatch):
    async def discover(url):
        return make_discovered()

    monkeypatch.setattr(module, "discover_agent", discover)
    research = FakeResearchWorkflow()
    with pytest.raises(RuntimeError, match="no route executed"):
        await RoutedWorkflow(
            client=FakeClient('{"route":"unknown","reason":"nope"}'),
            research_workflow=research,
        ).run("A request")
    assert research.calls == []


@pytest.mark.asyncio
async def test_bad_protocol_rejected(monkeypatch):
    async def discover(url):
        return make_discovered(binding="HTTP")

    monkeypatch.setattr(module, "discover_agent", discover)
    with pytest.raises(AgentDiscoveryError, match="JSONRPC"):
        await RoutedWorkflow(client=FakeClient("{}"), research_workflow=FakeResearchWorkflow()).run("request")


@pytest.mark.asyncio
async def test_empty_question_rejected_before_discovery(monkeypatch):
    async def discover(url):
        raise AssertionError("Discovery must not occur")

    monkeypatch.setattr(module, "discover_agent", discover)
    with pytest.raises(ValueError, match="Question cannot be empty"):
        await RoutedWorkflow(client=FakeClient("{}"), research_workflow=FakeResearchWorkflow()).run("   ")

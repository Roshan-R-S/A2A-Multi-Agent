"""Offline Planner Agent tests. Never call the live Groq API."""

import json

import pytest
from pydantic import ValidationError

import agents.planner.router as router_module
from agents.planner.card import planner_agent_card
from agents.planner.executor import PlannerAgent
from agents.planner.router import LLMTaskPlanner
from agents.planner.schemas import RoutingDecision


def test_agent_card_advertises_routing_skill():
    assert planner_agent_card.name == "Planner Agent"
    assert {skill.id for skill in planner_agent_card.skills} == {"plan_or_route"}
    assert planner_agent_card.default_output_modes == ["application/json"]


def test_research_route_allows_empty_steps():
    result = RoutingDecision(route="research", reason="Needs evidence.")
    assert result.steps == []


def test_plan_route_requires_steps():
    with pytest.raises(ValidationError, match="at least one step"):
        RoutingDecision(route="plan_only", reason="Needs a roadmap.", steps=[])


def test_unknown_route_rejected():
    with pytest.raises(ValidationError):
        RoutingDecision(route="delete_files", reason="Unsupported.")


@pytest.mark.asyncio
async def test_planner_invokes_llm_with_zero_temperature(monkeypatch):
    calls = []

    async def fake_generate_text(*, prompt, system_prompt, temperature):
        calls.append((prompt, system_prompt, temperature))
        return json.dumps({"route": "research", "reason": "Needs sources", "steps": []})

    monkeypatch.setattr(router_module, "generate_text", fake_generate_text)
    decision = await LLMTaskPlanner().plan("Explain RAG")
    assert decision.route == "research"
    assert len(calls) == 1
    assert calls[0][2] == 0.0


@pytest.mark.asyncio
async def test_planner_accepts_json_code_fences(monkeypatch):
    async def fake_generate_text(**kwargs):
        return '```json\n{"route":"plan_only","reason":"Planning","steps":["Define scope"]}\n```'

    monkeypatch.setattr(router_module, "generate_text", fake_generate_text)
    decision = await LLMTaskPlanner().plan("Plan a RAG app")
    assert decision.steps == ["Define scope"]


@pytest.mark.asyncio
async def test_planner_rejects_bad_json(monkeypatch):
    async def fake_generate_text(**kwargs):
        return "Here is an unstructured plan!"

    monkeypatch.setattr(router_module, "generate_text", fake_generate_text)
    with pytest.raises(RuntimeError, match="No route was executed"):
        await LLMTaskPlanner().plan("Plan an app")


@pytest.mark.asyncio
async def test_planner_rejects_long_questions_without_llm(monkeypatch):
    async def fake_generate_text(**kwargs):
        raise AssertionError("LLM must not be called")

    monkeypatch.setattr(router_module, "generate_text", fake_generate_text)
    with pytest.raises(ValueError, match="too long"):
        await LLMTaskPlanner().plan("x" * 4001)


@pytest.mark.asyncio
async def test_agent_returns_structured_json():
    class FakePlanner:
        async def plan(self, question):
            assert question == "Plan RAG"
            return RoutingDecision(
                route="plan_only", reason="Need implementation steps", steps=["Create index"]
            )

    raw = await PlannerAgent(planner=FakePlanner()).invoke("Plan RAG")
    result = json.loads(raw)
    assert result["route"] == "plan_only"
    assert result["steps"] == ["Create index"]

"""Optional A2A Planner -> existing research workflow orchestration."""

from dataclasses import dataclass

from agents.planner.schemas import RoutingDecision
from agents.planner.settings import planner_agent_url
from orchestrator.client import A2AAgentClient
from orchestrator.discovery import AgentDiscoveryError, discover_agent
from orchestrator.workflow import ResearchWriterWorkflow


@dataclass(frozen=True)
class RoutedWorkflowResult:
    question: str
    decision: RoutingDecision
    final_answer: str
    research: str | None
    verified: bool


class RoutedWorkflow:
    """Plan-only requests never execute tools or the research workflow."""

    def __init__(
        self,
        client: A2AAgentClient | None = None,
        research_workflow: ResearchWriterWorkflow | None = None,
    ) -> None:
        self.client = client or A2AAgentClient()
        self.research_workflow = research_workflow or ResearchWriterWorkflow(
            client=self.client
        )

    async def run(self, question: str) -> RoutedWorkflowResult:
        question = question.strip()
        if not question:
            raise ValueError("Question cannot be empty.")

        planner = await discover_agent(planner_agent_url)
        if planner.protocol_binding.upper() != "JSONRPC":
            raise AgentDiscoveryError("Planner Agent does not support JSONRPC.")
        if "plan_or_route" not in planner.skills:
            raise AgentDiscoveryError(
                "Planner Agent does not advertise the 'plan_or_route' skill."
            )

        raw_decision = await self.client.send_text(planner.url, question)
        try:
            decision = RoutingDecision.model_validate_json(raw_decision)
        except ValueError as exc:
            raise RuntimeError(
                "Planner returned an invalid A2A routing decision; no route executed."
            ) from exc

        if decision.route == "plan_only":
            lines = [
                "PROPOSED PLAN (not executed)",
                "",
                *(f"{i}. {step}" for i, step in enumerate(decision.steps, 1)),
            ]
            return RoutedWorkflowResult(
                question=question,
                decision=decision,
                final_answer="\n".join(lines),
                research=None,
                verified=False,
            )

        result = await self.research_workflow.run(question)
        return RoutedWorkflowResult(
            question=question,
            decision=decision,
            final_answer=result.final_answer,
            research=result.research,
            verified=True,
        )

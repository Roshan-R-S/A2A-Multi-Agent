"""Discoverable A2A Agent Card for Planner/Router Agent."""

from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill

from agents.planner.settings import planner_agent_url


planner_agent_card = AgentCard(
    name="Planner Agent",
    description="Plans tasks and routes informational requests to the existing research workflow.",
    version="0.2.0",
    default_input_modes=["text/plain"],
    default_output_modes=["application/json"],
    capabilities=AgentCapabilities(streaming=True),
    supported_interfaces=[
        AgentInterface(
            protocol_binding="JSONRPC",
            url=planner_agent_url,
            protocol_version="1.0",
        )
    ],
    skills=[
        AgentSkill(
            id="plan_or_route",
            name="Plan or Route Task",
            description="Returns a validated research or plan-only decision as JSON.",
            tags=["planning", "routing", "orchestration"],
            input_modes=["text/plain"],
            output_modes=["application/json"],
            examples=[
                "Explain retrieval augmented generation.",
                "Plan a local RAG knowledge assistant.",
            ],
        )
    ],
)

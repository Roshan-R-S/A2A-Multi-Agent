from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from core.config import settings


research_skill = AgentSkill(
    id="research_topic",
    name="Research Topic",
    description=(
        "Researches and analyzes a topic and returns a structured "
        "research brief for another agent or user."
    ),
    tags=[
        "research",
        "analysis",
        "information-synthesis",
    ],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
    examples=[
        "Explain how transformer neural networks work.",
        "Research the advantages and disadvantages of RAG.",
        "Analyze the main concepts behind multi-agent AI systems.",
    ],
)


research_agent_card = AgentCard(
    name="Research Agent",
    description=(
        "An A2A research agent that analyzes topics and produces "
        "structured research briefs."
    ),
    version="0.1.0",
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    capabilities=AgentCapabilities(
        streaming=True,
    ),
    supported_interfaces=[
        AgentInterface(
            protocol_binding="JSONRPC",
            url=settings.research_agent_url,
            protocol_version="1.0",
        )
    ],
    skills=[
        research_skill,
    ],
)

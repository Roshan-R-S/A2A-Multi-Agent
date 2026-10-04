from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from core.config import settings


writer_skill = AgentSkill(
    id="write_explanation",
    name="Write Explanation",
    description=(
        "Transforms research material into a clear, structured, "
        "beginner-friendly final explanation."
    ),
    tags=[
        "writing",
        "summarization",
        "explanation",
    ],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
    examples=[
        "Rewrite this research brief for a beginner.",
        "Turn these technical notes into a clear explanation.",
        "Create a polished answer from this research.",
    ],
)


writer_agent_card = AgentCard(
    name="Writer Agent",
    description=(
        "An A2A writing agent that converts research briefs into "
        "clear and polished final responses."
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
            url=settings.writer_agent_url,
            protocol_version="1.0",
        )
    ],
    skills=[
        writer_skill,
    ],
)

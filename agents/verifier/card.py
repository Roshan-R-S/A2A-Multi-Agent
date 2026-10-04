from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from core.config import settings


verifier_skill = AgentSkill(
    id="verify_answer",
    name="Verify Answer",
    description=(
        "Evaluates a Writer Agent draft against the original "
        "question and Research Agent brief, returning a structured "
        "PASS or FAIL verification result."
    ),
    tags=[
        "verification",
        "quality-control",
        "consistency",
        "review",
    ],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
    examples=[
        (
            "Verify whether this draft accurately reflects "
            "the supplied research brief."
        ),
        (
            "Check this answer for unsupported claims, "
            "contradictions, and missing caveats."
        ),
        (
            "Compare the draft answer with the original question "
            "and research evidence."
        ),
    ],
)


verifier_agent_card = AgentCard(
    name="Verifier Agent",
    description=(
        "An A2A verification agent that reviews Writer Agent "
        "responses for consistency, completeness, and support "
        "from the supplied research."
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
            url=settings.verifier_agent_url,
            protocol_version="1.0",
        )
    ],
    skills=[
        verifier_skill,
    ],
)

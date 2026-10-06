from dataclasses import dataclass
import logging
import time

from core.config import settings
from orchestrator.client import A2AAgentClient
from orchestrator.discovery import (
    AgentDiscoveryError,
    DiscoveredAgent,
    discover_agent,
)
from orchestrator.revision_loop import (
    RevisionLoop,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkflowResult:
    question: str
    research: str
    final_answer: str


class ResearchWriterWorkflow:
    def __init__(
        self,
        client: A2AAgentClient | None = None,
        max_revisions: int = 2,
    ) -> None:
        if max_revisions < 0:
            raise ValueError(
                "max_revisions cannot be negative."
            )

        self.client = (
            client
            or A2AAgentClient()
        )

        self.max_revisions = (
            max_revisions
        )

    async def _discover_required_agents(
        self,
    ) -> tuple[
        DiscoveredAgent,
        DiscoveredAgent,
        DiscoveredAgent,
    ]:
        logger.info(
            "Discovering Research Agent..."
        )

        research = await discover_agent(
            settings.research_agent_url
        )

        logger.info(
            "Research Agent discovered: %s",
            research.name,
        )

        logger.info(
            "Discovering Writer Agent..."
        )

        writer = await discover_agent(
            settings.writer_agent_url
        )

        logger.info(
            "Writer Agent discovered: %s",
            writer.name,
        )

        logger.info(
            "Discovering Verifier Agent..."
        )

        verifier = await discover_agent(
            settings.verifier_agent_url
        )

        logger.info(
            "Verifier Agent discovered: %s",
            verifier.name,
        )

        if (
            research.protocol_binding.upper()
            != "JSONRPC"
        ):
            raise AgentDiscoveryError(
                "Research Agent does not "
                "support JSONRPC."
            )

        if (
            writer.protocol_binding.upper()
            != "JSONRPC"
        ):
            raise AgentDiscoveryError(
                "Writer Agent does not "
                "support JSONRPC."
            )

        if (
            verifier.protocol_binding.upper()
            != "JSONRPC"
        ):
            raise AgentDiscoveryError(
                "Verifier Agent does not "
                "support JSONRPC."
            )

        if (
            "research_topic"
            not in research.skills
        ):
            raise AgentDiscoveryError(
                "Research Agent does not advertise "
                "the required 'research_topic' skill."
            )

        if (
            "write_explanation"
            not in writer.skills
        ):
            raise AgentDiscoveryError(
                "Writer Agent does not advertise "
                "the required "
                "'write_explanation' skill."
            )

        if (
            "verify_answer"
            not in verifier.skills
        ):
            raise AgentDiscoveryError(
                "Verifier Agent does not advertise "
                "the required "
                "'verify_answer' skill."
            )

        logger.info(
            "Required agent capabilities validated."
        )

        return (
            research,
            writer,
            verifier,
        )

    async def run(
        self,
        question: str,
    ) -> WorkflowResult:
        question = question.strip()

        if not question:
            raise ValueError(
                "Question cannot be empty."
            )

        workflow_start = (
            time.perf_counter()
        )

        logger.info(
            "Workflow started | question=%r",
            question,
        )

        (
            research_agent,
            writer_agent,
            verifier_agent,
        ) = (
            await self._discover_required_agents()
        )

        # -------------------------------------------------
        # 1. Research
        # -------------------------------------------------

        logger.info(
            "Research request started."
        )

        research_start = (
            time.perf_counter()
        )

        research = (
            await self.client.send_text(
                research_agent.url,
                question,
            )
        )

        logger.info(
            "Research completed in %.2f seconds.",
            time.perf_counter()
            - research_start,
        )

        # -------------------------------------------------
        # 2. Initial Writer draft
        # -------------------------------------------------

        logger.info(
            "Initial Writer request started."
        )

        writer_start = (
            time.perf_counter()
        )

        draft_answer = (
            await self.client.send_text(
                writer_agent.url,
                research,
            )
        )

        logger.info(
            "Initial Writer completed "
            "in %.2f seconds.",
            time.perf_counter()
            - writer_start,
        )

        # -------------------------------------------------
        # 3. Verification + automatic revision loop
        # -------------------------------------------------

        logger.info(
            "Verification/revision loop started."
        )

        revision_start = (
            time.perf_counter()
        )

        revision_loop = RevisionLoop(
            client=self.client,
            writer_url=writer_agent.url,
            verifier_url=verifier_agent.url,
            max_revisions=(
                self.max_revisions
            ),
        )

        final_answer = (
            await revision_loop.run(
                research_json=research,
                initial_draft=draft_answer,
            )
        )

        logger.info(
            "Verification/revision loop "
            "completed in %.2f seconds.",
            time.perf_counter()
            - revision_start,
        )

        logger.info(
            "Workflow completed successfully "
            "in %.2f seconds.",
            time.perf_counter()
            - workflow_start,
        )

        return WorkflowResult(
            question=question,
            research=research,
            final_answer=final_answer,
        )
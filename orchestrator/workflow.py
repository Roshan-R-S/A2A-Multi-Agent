from dataclasses import dataclass
import json
import logging
import time

from core.config import settings
from orchestrator.client import A2AAgentClient
from orchestrator.discovery import (
    AgentDiscoveryError,
    DiscoveredAgent,
    discover_agent,
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
    ) -> None:
        self.client = client or A2AAgentClient()

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
                "Research Agent does not support JSONRPC."
            )

        if (
            writer.protocol_binding.upper()
            != "JSONRPC"
        ):
            raise AgentDiscoveryError(
                "Writer Agent does not support JSONRPC."
            )

        if (
            verifier.protocol_binding.upper()
            != "JSONRPC"
        ):
            raise AgentDiscoveryError(
                "Verifier Agent does not support JSONRPC."
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
                "the required 'write_explanation' skill."
            )

        if (
            "verify_answer"
            not in verifier.skills
        ):
            raise AgentDiscoveryError(
                "Verifier Agent does not advertise "
                "the required 'verify_answer' skill."
            )

        logger.info(
            "Required agent capabilities validated."
        )

        return (
            research,
            writer,
            verifier,
        )

    @staticmethod
    def _parse_verification(
        raw_result: str,
    ) -> dict:
        try:
            result = json.loads(
                raw_result
            )
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Verifier returned invalid JSON."
            ) from exc

        if not isinstance(
            result,
            dict,
        ):
            raise RuntimeError(
                "Verifier result must be a JSON object."
            )

        verdict = result.get(
            "verdict"
        )

        if verdict not in {
            "PASS",
            "FAIL",
        }:
            raise RuntimeError(
                "Verifier returned an invalid verdict."
            )

        issues = result.get(
            "issues",
        )

        if not isinstance(
            issues,
            list,
        ):
            raise RuntimeError(
                "Verifier issues must be a list."
            )

        feedback = result.get(
            "feedback",
            "",
        )

        if not isinstance(
            feedback,
            str,
        ):
            raise RuntimeError(
                "Verifier feedback must be a string."
            )

        return result

    async def run(
        self,
        question: str,
    ) -> WorkflowResult:
        question = question.strip()

        if not question:
            raise ValueError(
                "Question cannot be empty."
            )

        workflow_start = time.perf_counter()

        logger.info(
            "Workflow started | question=%r",
            question,
        )

        (
            research_agent,
            writer_agent,
            verifier_agent,
        ) = await self._discover_required_agents()

        research_prompt = f"""
Research the following user question.

User question:
{question}

Produce a structured research brief containing the information
a Writer Agent would need to create a high-quality final answer.

Do not invent sources, statistics, or claims that you cannot
support from your existing knowledge.
""".strip()

        logger.info(
            "Research request started."
        )

        research_start = (
            time.perf_counter()
        )

        research = (
            await self.client.send_text(
                research_agent.url,
                research_prompt,
            )
        )

        logger.info(
            "Research completed in %.2f seconds.",
            time.perf_counter()
            - research_start,
        )

        writer_prompt = f"""
Create the final answer to the original user question using the
research brief below.

ORIGINAL USER QUESTION:
{question}

RESEARCH BRIEF:
{research}

Instructions:
- Answer the original question directly.
- Preserve important facts and caveats.
- Make the explanation clear and natural.
- Do not claim that you independently researched anything.
- Do not invent new factual claims.
- Do not mention the internal multi-agent workflow unless the
  user specifically asks about it.
""".strip()

        logger.info(
            "Writer request started."
        )

        writer_start = (
            time.perf_counter()
        )

        draft_answer = (
            await self.client.send_text(
                writer_agent.url,
                writer_prompt,
            )
        )

        logger.info(
            "Writer completed in %.2f seconds.",
            time.perf_counter()
            - writer_start,
        )

        verifier_prompt = f"""
Verify the Writer Agent's draft against the original user
question and the Research Agent's brief.

ORIGINAL USER QUESTION:
{question}

RESEARCH BRIEF:
{research}

WRITER DRAFT:
{draft_answer}

Return your structured verification result.
""".strip()

        logger.info(
            "Verifier request started."
        )

        verifier_start = (
            time.perf_counter()
        )

        raw_verification = (
            await self.client.send_text(
                verifier_agent.url,
                verifier_prompt,
            )
        )

        logger.info(
            "Verifier completed in %.2f seconds.",
            time.perf_counter()
            - verifier_start,
        )

        verification = (
            self._parse_verification(
                raw_verification
            )
        )

        verdict = verification[
            "verdict"
        ]

        logger.info(
            "Verification verdict: %s",
            verdict,
        )

        if verdict == "FAIL":
            issues = verification.get(
                "issues",
                [],
            )

            feedback = verification.get(
                "feedback",
                "",
            )

            issue_text = "\n".join(
                f"- {issue}"
                for issue in issues
            )

            raise RuntimeError(
                "Verifier rejected the Writer response."
                f"\n\nIssues:\n{issue_text}"
                f"\n\nFeedback:\n{feedback}"
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
            final_answer=draft_answer,
        )
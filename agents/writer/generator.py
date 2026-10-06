import re

from agents.research.schemas import ResearchResult
from agents.writer.context import build_writer_context
from core.llm import generate_text


WRITER_SYSTEM_PROMPT = """
You are the Writer Agent in a multi-agent AI system.

You receive structured, evidence-backed research.

Your job is to turn it into a clear, polished answer for the user.

Critical citation rules:

- Use ONLY the supplied research.
- Do not invent facts.
- Do not introduce outside knowledge.
- Preserve important uncertainty and caveats.
- Every factual statement derived from the research must include
  one or more valid source citations.
- Citations must use source IDs exactly like:
  [src_1]
  [src_2]
- Place citations directly after the factual statement they support.
- Multiple sources may be cited like:
  [src_1] [src_2]
- Never invent source IDs.
- Never cite a source that is not provided.
- Do not expose internal evidence IDs or claim IDs.
- Do not mention that you are an AI agent.
- Do not output JSON.
- Produce polished Markdown/plain-text prose suitable for the user.

If supported claims and sources are provided, the final answer MUST
contain source citations.
""".strip()


class CitationAwareWriter:
    name = "citation-aware-writer"

    async def write(
        self,
        research: ResearchResult,
    ) -> str:
        context = build_writer_context(
            research
        )

        allowed_sources = " ".join(
            f"[{source.id}]"
            for source in research.sources
        )

        prompt = f"""
Use the following structured research to answer the
original question.

ALLOWED SOURCE CITATIONS:
{allowed_sources}

{context}

Write the final response now.

Remember:
Every factual statement must use one or more of the allowed
source citations.
""".strip()

        first_result = await generate_text(
            prompt=prompt,
            system_prompt=WRITER_SYSTEM_PROMPT,
            temperature=0.2,
        )

        first_result = first_result.strip()

        try:
            self._validate_response(
                first_result,
                research,
            )

            return first_result

        except RuntimeError as first_error:
            repair_prompt = f"""
Your previous response failed citation validation.

VALIDATION ERROR:
{first_error}

PREVIOUS RESPONSE:
{first_result or "[empty response]"}

Rewrite the answer using the structured research below.

ALLOWED SOURCE CITATIONS:
{allowed_sources}

{context}

Mandatory requirements:

- Use ONLY the supplied research.
- Every factual statement must contain one or more valid
  source citations.
- Use only these citation IDs:
  {allowed_sources}
- Do not invent citations.
- Do not remove important caveats.
- Return only the corrected final answer.
""".strip()

            repaired_result = await generate_text(
                prompt=repair_prompt,
                system_prompt=WRITER_SYSTEM_PROMPT,
                temperature=0.0,
            )

            repaired_result = (
                repaired_result.strip()
            )

            try:
                self._validate_response(
                    repaired_result,
                    research,
                )

            except RuntimeError as second_error:
                raise RuntimeError(
                    "Writer failed citation validation "
                    "after one repair attempt: "
                    f"{second_error}"
                ) from second_error

            return repaired_result

    async def revise(
        self,
        request,
    ) -> str:
        from agents.writer.revision import (
            build_revision_context,
        )

        context = build_revision_context(
            request
        )

        allowed_sources = " ".join(
            f"[{source.id}]"
            for source
            in request.research.sources
        )

        prompt = f"""
Revise the existing answer using the verifier feedback.

You must correct every verifier issue.

Use ONLY the supplied research.

Do not introduce outside facts.

Preserve accurate content from the existing draft.

Preserve important research caveats.

Every factual statement must use appropriate source
citations.

ALLOWED SOURCE CITATIONS:
{allowed_sources}

{context}

Return only the corrected final answer.
""".strip()

        result = await generate_text(
            prompt=prompt,
            system_prompt=WRITER_SYSTEM_PROMPT,
            temperature=0.0,
        )

        result = result.strip()

        self._validate_response(
            result,
            request.research,
        )

        return result

    @classmethod
    def _validate_response(
        cls,
        text: str,
        research: ResearchResult,
    ) -> None:
        if not text:
            raise RuntimeError(
                "Writer returned an empty response."
            )

        cls.validate_citations(
            text,
            research,
        )

    @staticmethod
    def extract_citations(
        text: str,
    ) -> set[str]:
        return set(
            re.findall(
                r"\[(src_\d+)\]",
                text,
            )
        )

    @classmethod
    def validate_citations(
        cls,
        text: str,
        research: ResearchResult,
    ) -> None:
        citations = cls.extract_citations(
            text
        )

        known_sources = {
            source.id
            for source in research.sources
        }

        unknown = (
            citations
            - known_sources
        )

        if unknown:
            unknown_list = ", ".join(
                sorted(unknown)
            )

            raise RuntimeError(
                "Writer used unknown source "
                f"citations: {unknown_list}"
            )

        if (
            research.claims
            and research.sources
            and not citations
        ):
            raise RuntimeError(
                "Writer response contains factual "
                "claims but no source citations."
            )
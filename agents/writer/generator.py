import logging
import re

from agents.research.schemas import ResearchResult
from agents.writer.context import build_writer_context
from core.llm import generate_text


logger = logging.getLogger(__name__)


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
- Citations MUST be literal ASCII square-bracket markers exactly like:
  [src_1]
  [src_2]
- DO NOT substitute URLs, Markdown links, [1], (src_1), or
  other citation formats for those markers.
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
contain source citations. Copy the citation IDs associated with each
SUPPORTED CLAIM; do not simply place arbitrary source IDs on claims.
If a sentence cannot be supported by supplied evidence, omit it.

Required citation pattern (illustrative, not an extra fact to assert):
  A sentence supported by a supplied claim. [src_1]
  A second supported sentence. [src_2]
""".strip()


def _diagnostic_preview(text: str, limit: int = 300) -> str:
    """Bounded local diagnostic. Never include the full prompt or API keys."""
    safe = re.sub(
        r"\b(?:gsk_|tvly-)[A-Za-z0-9_-]{12,}\b",
        "[REDACTED_KEY]",
        text,
    )
    return safe[:limit].replace("\n", "\\n").replace("\r", "")


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
Every factual sentence must end with the exact literal ASCII citation
marker of its supporting claim, like [src_1]. The source marker is not
optional. Do not use [1], numbered notes, URLs, or Markdown links as
substitutes. Omit any sentence that cannot be supported.
""".strip()

        first_result = await generate_text(
            prompt=prompt,
            system_prompt=WRITER_SYSTEM_PROMPT,
            temperature=0.2,
        )

        first_result = self.normalize_citation_markers(
            first_result.strip()
        )

        try:
            self._validate_response(
                first_result,
                research,
            )
            return first_result

        except RuntimeError as first_error:
            logger.warning(
                "Writer initial draft failed validation: %s; "
                "recognized citations=%s; preview=%r",
                first_error,
                sorted(self.extract_citations(first_result)),
                _diagnostic_preview(first_result),
            )
            repair_prompt = f"""
Your previous response failed citation validation.

VALIDATION ERROR:
{first_error}

PREVIOUS RESPONSE:
{first_result or "[empty response]"}

This is a targeted CITATION-FORMAT REPAIR. Your previous draft
was rejected; do not repeat it with the same missing citations.
Rewrite from SUPPORTED CLAIMS in the research below. Only make statements
supported by those claims/evidence. Each factual sentence MUST end in
one or more EXACT ASCII bracket markers such as [src_1], copied from
the corresponding supported claim. This is required even for the intro.
Do not replace [src_1] with [1], bare URLs, links, or footnotes.
If a previous sentence cannot be cited from the research, DELETE it.
If cited claims exist, returning a citation-free response is invalid.

Use the structured research below:

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

            repaired_result = self.normalize_citation_markers(
                repaired_result.strip()
            )

            try:
                self._validate_response(
                    repaired_result,
                    research,
                )
            except RuntimeError as second_error:
                logger.error(
                    "Writer citation repair failed: %s; "
                    "recognized citations=%s; preview=%r",
                    second_error,
                    sorted(self.extract_citations(repaired_result)),
                    _diagnostic_preview(repaired_result),
                )
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
        """Revise a draft from Verifier feedback, preserving citation rules."""
        from agents.writer.revision import build_revision_context

        context = build_revision_context(request)
        allowed_sources = " ".join(
            f"[{source.id}]"
            for source in request.research.sources
        )

        prompt = f"""
Revise the existing answer using the verifier feedback.

You must correct every verifier issue.
Use ONLY the supplied research; do not introduce outside facts.
Preserve accurate content and important research caveats.

Every factual statement must have an appropriate citation, written
with literal ASCII square brackets such as [src_1]. Do not substitute
numbered footnotes, bare URLs, or Markdown links for these markers.
Copy the supporting source ID from the relevant research claim.
Omit statements that cannot be supported by the supplied research.

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

        result = self.normalize_citation_markers(result.strip())

        try:
            self._validate_response(result, request.research)
        except RuntimeError as exc:
            logger.warning(
                "Writer revision failed citation validation: %s; "
                "recognized citations=%s; preview=%r",
                exc,
                sorted(self.extract_citations(result)),
                _diagnostic_preview(result),
            )
            raise

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
    def normalize_citation_markers(text: str) -> str:
        """Normalize only recognizable source-ID brackets, never guess sources."""
        return re.sub(
            r"\[\s*(src_\d+)\s*\]",
            lambda m: f"[{m.group(1).lower()}]",
            text,
            flags=re.IGNORECASE,
        )

    @staticmethod
    def extract_citations(
        text: str,
    ) -> set[str]:
        return {
            source_id.lower()
            for source_id in re.findall(
                r"\[\s*(src_\d+)\s*\]",
                text,
                flags=re.IGNORECASE,
            )
        }

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

        unknown = citations - known_sources

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

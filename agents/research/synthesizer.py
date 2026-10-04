import json
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from agents.research.schemas import (
    Claim,
    Evidence,
    Source,
)
from core.llm import generate_text


SYNTHESIS_SYSTEM_PROMPT = """
You are a research synthesis component.

Your job is to create a concise research summary using ONLY
the claims and evidence supplied to you.

Rules:

- Do not use outside knowledge.
- Do not invent facts.
- Preserve uncertainty from the supplied claims.
- Do not make claims stronger than the evidence supports.
- Mention important limitations as caveats.
- Prefer claims marked high confidence over weaker claims.
- Do not invent source IDs, evidence IDs, statistics, dates,
  names, or quotations.
- If the evidence is incomplete, say so in the caveats.

Return valid JSON only.

Use exactly this structure:

{
  "summary": "Clear evidence-backed research summary.",
  "caveats": [
    "Important limitation or uncertainty."
  ]
}

Do not wrap the JSON in Markdown fences.
Do not include commentary before or after the JSON.
""".strip()


@dataclass(frozen=True)
class ResearchSynthesis:
    summary: str
    caveats: tuple[str, ...] = ()


@runtime_checkable
class ResearchSynthesizer(Protocol):
    name: str

    async def synthesize(
        self,
        question: str,
        claims: list[Claim],
        evidence: list[Evidence],
        sources: list[Source],
    ) -> ResearchSynthesis:
        ...


class LLMResearchSynthesizer:
    name = "llm-research-synthesizer"

    async def synthesize(
        self,
        question: str,
        claims: list[Claim],
        evidence: list[Evidence],
        sources: list[Source],
    ) -> ResearchSynthesis:

        question = question.strip()

        if not question:
            raise ValueError(
                "Question cannot be empty."
            )

        if not evidence or not claims:
            return ResearchSynthesis(
                summary=(
                    "Insufficient supported evidence was "
                    "available to produce a reliable "
                    "research summary."
                ),
                caveats=(
                    (
                        "The research pipeline did not "
                        "produce enough evidence-backed "
                        "claims for a confident synthesis."
                    ),
                ),
            )

        source_map = {
            source.id: source
            for source in sources
        }

        evidence_text = "\n\n".join(
            self._format_evidence(
                item,
                source_map,
            )
            for item in evidence
        )

        claims_text = "\n\n".join(
            (
                f"{claim.id}\n"
                f"Claim: {claim.text}\n"
                f"Confidence: {claim.confidence}\n"
                f"Evidence IDs: "
                f"{', '.join(claim.evidence_ids)}"
            )
            for claim in claims
        )

        prompt = f"""
ORIGINAL QUESTION:
{question}

SUPPORTED CLAIMS:
{claims_text}

AVAILABLE EVIDENCE:
{evidence_text}

Create an evidence-backed summary answering the original
question.

Include important limitations or uncertainty in caveats.
""".strip()

        raw_result = await generate_text(
            prompt=prompt,
            system_prompt=SYNTHESIS_SYSTEM_PROMPT,
            temperature=0.0,
        )

        return self.parse_result(
            raw_result
        )

    @staticmethod
    def _format_evidence(
        evidence: Evidence,
        source_map: dict[str, Source],
    ) -> str:

        source = source_map.get(
            evidence.source_id
        )

        if source is None:
            source_description = (
                evidence.source_id
            )
        else:
            source_description = (
                f"{source.id} | "
                f"{source.title} | "
                f"{source.url}"
            )

        return (
            f"{evidence.id}\n"
            f"Source: {source_description}\n"
            f"Evidence: {evidence.text}\n"
            f"Relevance: "
            f"{evidence.relevance_score}"
        )

    @staticmethod
    def parse_result(
        raw_result: str,
    ) -> ResearchSynthesis:

        text = raw_result.strip()

        if text.startswith("```json"):
            text = text[len("```json"):].strip()

        elif text.startswith("```"):
            text = text[len("```"):].strip()

        if text.endswith("```"):
            text = text[:-3].strip()

        try:
            data = json.loads(text)

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Research synthesizer returned "
                "invalid JSON."
            ) from exc

        if not isinstance(
            data,
            dict,
        ):
            raise RuntimeError(
                "Research synthesizer result must "
                "be a JSON object."
            )

        summary = data.get(
            "summary"
        )

        if (
            not isinstance(summary, str)
            or not summary.strip()
        ):
            raise RuntimeError(
                "Research synthesizer must return "
                "a non-empty summary."
            )

        raw_caveats = data.get(
            "caveats",
            [],
        )

        if not isinstance(
            raw_caveats,
            list,
        ):
            raise RuntimeError(
                "Research synthesizer caveats "
                "must be a list."
            )

        caveats: list[str] = []
        seen: set[str] = set()

        for caveat in raw_caveats:
            if not isinstance(
                caveat,
                str,
            ):
                raise RuntimeError(
                    "Every research caveat "
                    "must be a string."
                )

            cleaned = caveat.strip()

            if not cleaned:
                continue

            duplicate_key = (
                cleaned.casefold()
            )

            if duplicate_key in seen:
                continue

            seen.add(
                duplicate_key
            )

            caveats.append(
                cleaned
            )

        return ResearchSynthesis(
            summary=summary.strip(),
            caveats=tuple(caveats),
        )
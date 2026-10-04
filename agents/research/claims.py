import json
from typing import Protocol, runtime_checkable

from agents.research.schemas import (
    Claim,
    Evidence,
)
from core.llm import generate_text


CLAIM_GENERATION_SYSTEM_PROMPT = """
You are a research claim extraction component.

Your job is to create concise factual claims using ONLY the
evidence supplied to you.

Rules:

- Do not use outside knowledge.
- Do not invent facts.
- Every claim must reference at least one supplied evidence ID.
- Only reference evidence IDs that actually exist.
- Keep claims atomic: one main factual idea per claim.
- Avoid duplicate claims.
- Use confidence:
  - high: directly and clearly supported
  - medium: reasonably supported
  - low: weak or indirect support

Return valid JSON only.

Structure:

{
  "claims": [
    {
      "text": "Claim text",
      "confidence": "high",
      "evidence_ids": ["evidence_1"]
    }
  ]
}

Do not include Markdown fences.
Do not include commentary outside the JSON.
""".strip()


@runtime_checkable
class ClaimGenerator(Protocol):
    name: str

    async def generate(
        self,
        question: str,
        evidence: list[Evidence],
        *,
        max_claims: int = 8,
    ) -> list[Claim]:
        ...


class LLMClaimGenerator:
    name = "llm-claim-generator"

    async def generate(
        self,
        question: str,
        evidence: list[Evidence],
        *,
        max_claims: int = 8,
    ) -> list[Claim]:

        question = question.strip()

        if not question:
            raise ValueError(
                "Question cannot be empty."
            )

        if not evidence:
            return []

        if not 1 <= max_claims <= 20:
            raise ValueError(
                "max_claims must be between 1 and 20."
            )

        evidence_text = "\n\n".join(
            (
                f"{item.id}\n"
                f"Source: {item.source_id}\n"
                f"Evidence: {item.text}"
            )
            for item in evidence
        )

        prompt = f"""
QUESTION:
{question}

AVAILABLE EVIDENCE:
{evidence_text}

Create no more than {max_claims} factual claims.

Every claim must be supported by the supplied evidence.
""".strip()

        raw_result = await generate_text(
            prompt=prompt,
            system_prompt=(
                CLAIM_GENERATION_SYSTEM_PROMPT
            ),
            temperature=0.0,
        )

        return self.parse_result(
            raw_result,
            evidence=evidence,
            max_claims=max_claims,
        )

    @staticmethod
    def parse_result(
        raw_result: str,
        *,
        evidence: list[Evidence],
        max_claims: int = 8,
    ) -> list[Claim]:

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
                "Claim generator returned invalid JSON."
            ) from exc

        if not isinstance(data, dict):
            raise RuntimeError(
                "Claim generator result must be a JSON object."
            )

        raw_claims = data.get("claims")

        if not isinstance(raw_claims, list):
            raise RuntimeError(
                "Claim generator 'claims' must be a list."
            )

        known_evidence_ids = {
            item.id
            for item in evidence
        }

        claims: list[Claim] = []

        for index, raw_claim in enumerate(
            raw_claims[:max_claims],
            start=1,
        ):
            if not isinstance(
                raw_claim,
                dict,
            ):
                raise RuntimeError(
                    "Each generated claim must be an object."
                )

            text_value = raw_claim.get(
                "text",
                "",
            )

            confidence = raw_claim.get(
                "confidence",
                "medium",
            )

            evidence_ids = raw_claim.get(
                "evidence_ids",
                [],
            )

            if (
                not isinstance(
                    evidence_ids,
                    list,
                )
                or not evidence_ids
            ):
                raise RuntimeError(
                    "Every claim must reference evidence."
                )

            for evidence_id in evidence_ids:
                if (
                    evidence_id
                    not in known_evidence_ids
                ):
                    raise RuntimeError(
                        "Claim references unknown evidence "
                        f"'{evidence_id}'."
                    )

            claims.append(
                Claim(
                    id=f"claim_{index}",
                    text=text_value,
                    confidence=confidence,
                    evidence_ids=evidence_ids,
                )
            )

        return claims
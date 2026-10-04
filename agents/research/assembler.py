from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)


class ResearchResultAssembler:
    """
    Builds the final validated ResearchResult object.

    The assembler is responsible for preparing and cleaning
    data before it enters the ResearchResult schema.

    Referential integrity is validated by ResearchResult itself:

        Claim -> Evidence -> Source
    """

    def assemble(
        self,
        *,
        question: str,
        summary: str,
        sources: list[Source],
        evidence: list[Evidence],
        claims: list[Claim],
        caveats: list[str] | None = None,
    ) -> ResearchResult:

        question = question.strip()

        if not question:
            raise ValueError(
                "Question cannot be empty."
            )

        summary = summary.strip()

        if not summary:
            raise ValueError(
                "Summary cannot be empty."
            )

        cleaned_caveats = self._clean_caveats(
            caveats or []
        )

        return ResearchResult(
            question=question,
            summary=summary,
            sources=list(sources),
            evidence=list(evidence),
            claims=list(claims),
            caveats=cleaned_caveats,
        )

    @staticmethod
    def _clean_caveats(
        caveats: list[str],
    ) -> list[str]:
        """
        Remove blank and duplicate caveats while preserving
        their original order.
        """

        cleaned: list[str] = []
        seen: set[str] = set()

        for caveat in caveats:
            value = caveat.strip()

            if not value:
                continue

            duplicate_key = value.casefold()

            if duplicate_key in seen:
                continue

            seen.add(
                duplicate_key
            )

            cleaned.append(
                value
            )

        return cleaned
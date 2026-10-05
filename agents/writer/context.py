from pydantic import ValidationError

from agents.research.schemas import ResearchResult


def parse_research_result(
    raw_result: str,
) -> ResearchResult:
    raw_result = raw_result.strip()

    if not raw_result:
        raise ValueError(
            "Research result cannot be empty."
        )

    try:
        return ResearchResult.model_validate_json(
            raw_result
        )

    except ValidationError as exc:
        raise ValueError(
            "Invalid structured research result."
        ) from exc


def build_writer_context(
    research: ResearchResult,
) -> str:
    evidence_by_id = {
        item.id: item
        for item in research.evidence
    }

    source_by_id = {
        source.id: source
        for source in research.sources
    }

    sections: list[str] = []

    sections.append(
        "ORIGINAL QUESTION:\n"
        f"{research.question}"
    )

    sections.append(
        "RESEARCH SUMMARY:\n"
        f"{research.summary}"
    )

    claim_lines: list[str] = []

    for claim in research.claims:
        source_ids: list[str] = []

        for evidence_id in claim.evidence_ids:
            evidence = evidence_by_id[
                evidence_id
            ]

            source_id = evidence.source_id

            if source_id not in source_ids:
                source_ids.append(
                    source_id
                )

        citations = " ".join(
            f"[{source_id}]"
            for source_id in source_ids
        )

        claim_lines.append(
            f"- {claim.text} "
            f"{citations} "
            f"(confidence: {claim.confidence})"
        )

    sections.append(
        "SUPPORTED CLAIMS:\n"
        + "\n".join(claim_lines)
    )

    source_lines: list[str] = []

    for source in research.sources:
        source_lines.append(
            f"[{source.id}] "
            f"{source.title} — {source.url}"
        )

    sections.append(
        "SOURCES:\n"
        + "\n".join(source_lines)
    )

    if research.caveats:
        caveat_lines = [
            f"- {caveat}"
            for caveat in research.caveats
        ]

        sections.append(
            "CAVEATS:\n"
            + "\n".join(caveat_lines)
        )

    return "\n\n".join(
        sections
    )
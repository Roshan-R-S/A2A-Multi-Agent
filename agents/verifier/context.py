import re

from pydantic import ValidationError

from agents.verifier.schemas import (
    VerificationRequest,
)


def parse_verification_request(
    raw_payload: str,
) -> VerificationRequest:
    raw_payload = raw_payload.strip()

    if not raw_payload:
        raise ValueError(
            "Verification request cannot be empty."
        )

    try:
        return (
            VerificationRequest
            .model_validate_json(
                raw_payload
            )
        )

    except ValidationError as exc:
        raise ValueError(
            "Invalid verification request."
        ) from exc


def extract_citations(
    text: str,
) -> set[str]:
    return set(
        re.findall(
            r"\[(src_\d+)\]",
            text,
        )
    )


def find_unknown_citations(
    request: VerificationRequest,
) -> set[str]:
    known_sources = {
        source.id
        for source
        in request.research.sources
    }

    used_sources = extract_citations(
        request.draft
    )

    return (
        used_sources
        - known_sources
    )


def build_verifier_context(
    request: VerificationRequest,
) -> str:
    research = request.research

    evidence_by_id = {
        evidence.id: evidence
        for evidence
        in research.evidence
    }

    source_by_id = {
        source.id: source
        for source
        in research.sources
    }

    claim_sections: list[str] = []

    for claim in research.claims:
        supporting_evidence: list[str] = []

        for evidence_id in claim.evidence_ids:
            evidence = evidence_by_id[
                evidence_id
            ]

            source = source_by_id[
                evidence.source_id
            ]

            supporting_evidence.append(
                (
                    f"{evidence.id}\n"
                    f"Source: [{source.id}] "
                    f"{source.title}\n"
                    f"URL: {source.url}\n"
                    f"Evidence: {evidence.text}"
                )
            )

        claim_sections.append(
            (
                f"{claim.id}\n"
                f"Claim: {claim.text}\n"
                f"Confidence: "
                f"{claim.confidence}\n"
                f"Supporting evidence:\n"
                + "\n".join(
                    supporting_evidence
                )
            )
        )

    caveats = "\n".join(
        f"- {caveat}"
        for caveat
        in research.caveats
    )

    return (
        f"ORIGINAL QUESTION:\n"
        f"{research.question}\n\n"

        f"RESEARCH SUMMARY:\n"
        f"{research.summary}\n\n"

        f"SUPPORTED CLAIMS AND EVIDENCE:\n"
        f"{chr(10).join(claim_sections)}\n\n"

        f"RESEARCH CAVEATS:\n"
        f"{caveats or '- None'}\n\n"

        f"WRITER DRAFT:\n"
        f"{request.draft}"
    )
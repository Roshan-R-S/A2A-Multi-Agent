import json

from agents.verifier.context import (
    build_verifier_context,
    extract_citations,
    find_unknown_citations,
)
from agents.verifier.schemas import (
    VerificationIssue,
    VerificationRequest,
    VerificationResult,
)
from core.llm import generate_text


VERIFIER_SYSTEM_PROMPT = """
You are an evidence-aware Verifier Agent in a multi-agent
research system.

You receive:

1. The original question.
2. Structured research claims.
3. Evidence supporting those claims.
4. Sources connected to that evidence.
5. Research caveats.
6. A Writer Agent draft.

Your job is to determine whether the Writer draft is
faithful to the supplied research.

You are NOT checking external truth.
You must judge only against the supplied research and evidence.

Check for:

- factual statements with missing citations
- citations that do not support the statement
- unsupported claims
- changed numbers, names, dates, or facts
- contradictions with research
- overstated certainty
- dropped important caveats
- invented information

Issue types must be one of:

missing_citation
unknown_citation
unsupported_claim
citation_mismatch
changed_fact
overstated_certainty
dropped_caveat
contradiction
other

Return valid JSON only.

PASS example:

{
  "verdict": "PASS",
  "issues": [],
  "feedback": ""
}

FAIL example:

{
  "verdict": "FAIL",
  "issues": [
    {
      "type": "missing_citation",
      "statement": "The factual statement that failed.",
      "source_ids": [],
      "feedback": "Explain exactly what must be corrected."
    }
  ],
  "feedback": "Concise revision guidance."
}

Rules:

- PASS must contain zero issues.
- FAIL must contain at least one issue.
- Never invent source IDs.
- Only use source IDs supplied in the research.
- Do not wrap the JSON in Markdown fences.
""".strip()


class EvidenceAwareVerifier:
    name = "evidence-aware-verifier"

    async def verify(
        self,
        request: VerificationRequest,
    ) -> VerificationResult:

        deterministic_result = (
            self._run_deterministic_checks(
                request
            )
        )

        if deterministic_result is not None:
            return deterministic_result

        context = build_verifier_context(
            request
        )

        raw_result = await generate_text(
            prompt=context,
            system_prompt=VERIFIER_SYSTEM_PROMPT,
            temperature=0.0,
        )

        known_sources = {
            source.id
            for source
            in request.research.sources
        }

        return self.parse_result(
            raw_result,
            known_sources=known_sources,
        )

    @staticmethod
    def _run_deterministic_checks(
        request: VerificationRequest,
    ) -> VerificationResult | None:

        unknown = find_unknown_citations(
            request
        )

        if unknown:
            issues = [
                VerificationIssue(
                    type="unknown_citation",
                    statement="",
                    source_ids=[
                        source_id
                    ],
                    feedback=(
                        f"The draft references "
                        f"unknown source "
                        f"[{source_id}]."
                    ),
                )
                for source_id
                in sorted(unknown)
            ]

            return VerificationResult(
                verdict="FAIL",
                issues=issues,
                feedback=(
                    "Remove or replace citations "
                    "that are not present in the "
                    "research sources."
                ),
            )

        citations = extract_citations(
            request.draft
        )

        if (
            request.research.claims
            and request.research.sources
            and not citations
        ):
            return VerificationResult(
                verdict="FAIL",
                issues=[
                    VerificationIssue(
                        type="missing_citation",
                        statement="",
                        source_ids=[],
                        feedback=(
                            "The draft contains "
                            "research-based factual "
                            "content but has no "
                            "source citations."
                        ),
                    )
                ],
                feedback=(
                    "Add appropriate source "
                    "citations to factual claims."
                ),
            )

        return None

    @staticmethod
    def parse_result(
        raw_result: str,
        *,
        known_sources: set[str],
    ) -> VerificationResult:

        text = raw_result.strip()

        if text.startswith("```json"):
            text = text[
                len("```json"):
            ].strip()

        elif text.startswith("```"):
            text = text[
                len("```"):
            ].strip()

        if text.endswith("```"):
            text = text[:-3].strip()

        try:
            data = json.loads(
                text
            )

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Verifier returned invalid JSON."
            ) from exc

        try:
            result = (
                VerificationResult
                .model_validate(
                    data
                )
            )

        except Exception as exc:
            raise RuntimeError(
                "Verifier returned an invalid "
                "verification result."
            ) from exc

        if (
            result.verdict == "PASS"
            and result.issues
        ):
            raise RuntimeError(
                "PASS verification cannot "
                "contain issues."
            )

        if (
            result.verdict == "FAIL"
            and not result.issues
        ):
            raise RuntimeError(
                "FAIL verification must "
                "contain at least one issue."
            )

        for issue in result.issues:
            unknown_sources = (
                set(issue.source_ids)
                - known_sources
            )

            if unknown_sources:
                unknown_list = ", ".join(
                    sorted(
                        unknown_sources
                    )
                )

                raise RuntimeError(
                    "Verifier referenced unknown "
                    "source IDs: "
                    f"{unknown_list}"
                )

        return result
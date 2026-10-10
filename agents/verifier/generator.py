import json
import re

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

Return valid JSON only. Keep the JSON brief: each issue's statement and
feedback should be one short sentence; report at most four priority issues.
If there are additional problems, mention them concisely in overall feedback.
For PASS return empty issues and empty feedback.

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


# Groq GPT-OSS-120B supports strict JSON-schema structured outputs.
# A schema-constrained response avoids truncated/malformed JSON text without
# spending another Groq request on JSON repair. Semantic checks still apply.
_VERIFICATION_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "a2a_verification",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
                "issues": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": [
                                    "missing_citation", "unknown_citation",
                                    "unsupported_claim", "citation_mismatch",
                                    "changed_fact", "overstated_certainty",
                                    "dropped_caveat", "contradiction", "other",
                                ],
                            },
                            "statement": {"type": "string"},
                            "source_ids": {"type": "array", "items": {"type": "string"}},
                            "feedback": {"type": "string"},
                        },
                        "required": ["type", "statement", "source_ids", "feedback"],
                        "additionalProperties": False,
                    },
                },
                "feedback": {"type": "string"},
            },
            "required": ["verdict", "issues", "feedback"],
            "additionalProperties": False,
        },
    },
}


_CITATION_RE = re.compile(r"\[src_\d+\]", re.IGNORECASE)
# Include source markers immediately following terminal punctuation in the
# preceding statement: "Fact. [src_1]" is ONE cited statement.
_SENTENCE_END_RE = re.compile(
    r"(?<=[.!?])(?:\s*\[src_\d+\])*(?=\s|$)",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")

_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can",
    "for", "from", "has", "have", "in", "into", "is", "it",
    "its", "of", "on", "or", "that", "the", "their", "this",
    "to", "was", "were", "will", "with",
}


def _meaningful_words(text: str) -> set[str]:
    return {
        word.lower()
        for word in _WORD_RE.findall(text)
        if (
            len(word) > 2
            and word.lower() not in _STOP_WORDS
            and not word.lower().startswith("src_")
        )
    }


def _iter_candidate_statements(
    draft: str,
) -> list[str]:
    statements: list[str] = []
    in_code_block = False

    for raw_line in draft.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # A short, standalone bold label without a factual predicate
        # is a Markdown heading, not a research-backed assertion.
        emphasized = re.fullmatch(
            r"(?:\*\*|__)(.+?)(?:\*\*|__)",
            line,
        )
        if emphasized:
            title = emphasized.group(1).strip()
            if (
                len(title.split()) <= 14
                and not title.endswith((".", "!", "?"))
                and not re.search(
                    r"\b(?:is|are|was|were|can|has|have|uses|"
                    r"requires|provides|retrieves|improves|"
                    r"reduces|supports|depends|adds|combines|changes)\b",
                    title,
                    re.IGNORECASE,
                )
            ):
                continue

        if (
            line.startswith("#")
            or line.startswith("|")
            or set(line) <= {"-", "|", ":", " "}
        ):
            continue

        line = re.sub(
            r"^(?:[-*+]\s+|\d+[.)]\s+)",
            "",
            line,
        ).strip()

        if not line:
            continue

        if (
            line.endswith(":")
            and len(_meaningful_words(line)) <= 8
        ):
            continue

        start = 0
        for end in _SENTENCE_END_RE.finditer(line):
            # Abbreviations like "vs." and "e.g." must not split a sentence.
            if re.search(
                r"\b(?:vs|etc|e\.g|i\.e|Mr|Mrs|Dr)\.$",
                line[:end.start()].rstrip(),
                re.IGNORECASE,
            ):
                continue

            statement = line[start:end.end()].strip()
            if statement:
                statements.append(statement)
            start = end.end()

        # Keep unfinished final text for semantic checking too.
        remainder = line[start:].strip()
        if remainder:
            statements.append(remainder)

    return statements


def _research_reference_texts(
    request: VerificationRequest,
) -> list[str]:
    research = request.research

    texts = [
        research.summary,
        *[claim.text for claim in research.claims],
        *[evidence.text for evidence in research.evidence],
        *research.caveats,
    ]

    return [
        text.strip()
        for text in texts
        if text and text.strip()
    ]


def _looks_research_backed(
    statement: str,
    reference_texts: list[str],
) -> bool:
    statement_words = _meaningful_words(
        _CITATION_RE.sub("", statement)
    )

    if len(statement_words) < 2:
        return False

    for reference in reference_texts:
        reference_words = _meaningful_words(reference)

        if len(reference_words) < 2:
            continue

        overlap = statement_words & reference_words

        if len(overlap) < 2:
            continue

        statement_ratio = (
            len(overlap) / len(statement_words)
        )
        reference_ratio = (
            len(overlap) / len(reference_words)
        )

        if max(
            statement_ratio,
            reference_ratio,
        ) >= 0.5:
            return True

    return False


def _find_uncited_research_statements(
    request: VerificationRequest,
) -> list[str]:
    reference_texts = _research_reference_texts(
        request
    )

    uncited: list[str] = []

    for statement in _iter_candidate_statements(
        request.draft
    ):
        if _CITATION_RE.search(statement):
            continue

        if statement.endswith("?"):
            continue

        if _looks_research_backed(
            statement,
            reference_texts,
        ):
            uncited.append(statement)

    return uncited


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
            response_format=_VERIFICATION_RESPONSE_FORMAT,
            reasoning_effort="low",
            max_completion_tokens=1200,
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
                    source_ids=[source_id],
                    feedback=(
                        f"The draft references "
                        f"unknown source "
                        f"[{source_id}]."
                    ),
                )
                for source_id in sorted(unknown)
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

        if (
            request.research.claims
            and request.research.sources
        ):
            uncited_statements = (
                _find_uncited_research_statements(
                    request
                )
            )

            if uncited_statements:
                issues = [
                    VerificationIssue(
                        type="missing_citation",
                        statement=statement,
                        source_ids=[],
                        feedback=(
                            "This research-backed "
                            "factual statement needs "
                            "an appropriate source "
                            "citation."
                        ),
                    )
                    for statement
                    in uncited_statements
                ]

                return VerificationResult(
                    verdict="FAIL",
                    issues=issues,
                    feedback=(
                        "Add source citations to "
                        "each research-backed factual "
                        "statement identified above."
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
            data = json.loads(text)

        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Verifier returned invalid JSON."
            ) from exc

        try:
            result = (
                VerificationResult
                .model_validate(data)
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
                    sorted(unknown_sources)
                )

                raise RuntimeError(
                    "Verifier referenced unknown "
                    "source IDs: "
                    f"{unknown_list}"
                )

        return result

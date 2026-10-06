from typing import Literal

from pydantic import BaseModel, Field

from agents.research.schemas import (
    ResearchResult,
)


IssueType = Literal[
    "missing_citation",
    "unknown_citation",
    "unsupported_claim",
    "citation_mismatch",
    "changed_fact",
    "overstated_certainty",
    "dropped_caveat",
    "contradiction",
    "other",
]


class VerificationRequest(BaseModel):
    research: ResearchResult

    draft: str = Field(
        min_length=1
    )


class VerificationIssue(BaseModel):
    type: IssueType

    statement: str = ""

    source_ids: list[str] = Field(
        default_factory=list
    )

    feedback: str = Field(
        min_length=1
    )


class VerificationResult(BaseModel):
    verdict: Literal[
        "PASS",
        "FAIL",
    ]

    issues: list[
        VerificationIssue
    ] = Field(
        default_factory=list
    )

    feedback: str = ""
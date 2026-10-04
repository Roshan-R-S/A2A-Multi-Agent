from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


ConfidenceLevel = Literal[
    "low",
    "medium",
    "high",
]

SourceType = Literal[
    "web",
    "paper",
    "documentation",
    "news",
    "other",
]


class Source(BaseModel):
    id: str = Field(
        min_length=1,
        description="Unique source identifier, for example src_1.",
    )

    title: str = Field(
        min_length=1,
    )

    url: str = Field(
        min_length=1,
    )

    publisher: str | None = None

    published_at: datetime | None = None

    retrieved_at: datetime

    source_type: SourceType = "web"


class Evidence(BaseModel):
    id: str = Field(
        min_length=1,
        description="Unique evidence identifier.",
    )

    source_id: str = Field(
        min_length=1,
        description="Source that contains this evidence.",
    )

    text: str = Field(
        min_length=1,
        description="Relevant passage extracted from the source.",
    )

    relevance_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )


class Claim(BaseModel):
    id: str = Field(
        min_length=1,
        description="Unique claim identifier.",
    )

    text: str = Field(
        min_length=1,
    )

    confidence: ConfidenceLevel = "medium"

    evidence_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Evidence items supporting this claim."
        ),
    )


class ResearchResult(BaseModel):
    question: str = Field(
        min_length=1,
    )

    summary: str = Field(
        min_length=1,
    )

    claims: list[Claim] = Field(
        default_factory=list,
    )

    sources: list[Source] = Field(
        default_factory=list,
    )

    evidence: list[Evidence] = Field(
        default_factory=list,
    )

    caveats: list[str] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_references(
        self,
    ) -> "ResearchResult":
        source_ids = {
            source.id
            for source in self.sources
        }

        evidence_ids = {
            evidence.id
            for evidence in self.evidence
        }

        if len(source_ids) != len(
            self.sources
        ):
            raise ValueError(
                "Source IDs must be unique."
            )

        if len(evidence_ids) != len(
            self.evidence
        ):
            raise ValueError(
                "Evidence IDs must be unique."
            )

        claim_ids = {
            claim.id
            for claim in self.claims
        }

        if len(claim_ids) != len(
            self.claims
        ):
            raise ValueError(
                "Claim IDs must be unique."
            )

        for evidence in self.evidence:
            if (
                evidence.source_id
                not in source_ids
            ):
                raise ValueError(
                    f"Evidence '{evidence.id}' "
                    f"references unknown source "
                    f"'{evidence.source_id}'."
                )

        for claim in self.claims:
            for evidence_id in (
                claim.evidence_ids
            ):
                if (
                    evidence_id
                    not in evidence_ids
                ):
                    raise ValueError(
                        f"Claim '{claim.id}' "
                        f"references unknown evidence "
                        f"'{evidence_id}'."
                    )

        return self
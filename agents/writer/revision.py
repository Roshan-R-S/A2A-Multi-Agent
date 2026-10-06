from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
)

from agents.research.schemas import (
    ResearchResult,
)
from agents.writer.context import (
    build_writer_context,
)


class RevisionIssue(BaseModel):
    type: str

    statement: str = ""

    source_ids: list[str] = Field(
        default_factory=list
    )

    feedback: str = ""


class WriterRevisionRequest(BaseModel):
    mode: Literal["revise"] = "revise"

    research: ResearchResult

    draft: str = Field(
        min_length=1
    )

    feedback: str = Field(
        min_length=1
    )

    issues: list[RevisionIssue] = Field(
        default_factory=list
    )


def parse_revision_request(
    raw_payload: str,
) -> WriterRevisionRequest:
    raw_payload = raw_payload.strip()

    if not raw_payload:
        raise ValueError(
            "Revision request cannot be empty."
        )

    try:
        return (
            WriterRevisionRequest
            .model_validate_json(
                raw_payload
            )
        )

    except ValidationError as exc:
        raise ValueError(
            "Invalid revision request."
        ) from exc


def build_revision_context(
    request: WriterRevisionRequest,
) -> str:
    research_context = build_writer_context(
        request.research
    )

    issues: list[str] = []

    for index, issue in enumerate(
        request.issues,
        start=1,
    ):
        source_ids = " ".join(
            f"[{source_id}]"
            for source_id
            in issue.source_ids
        )

        issues.append(
            (
                f"Issue {index}\n"
                f"Type: {issue.type}\n"
                f"Statement: "
                f"{issue.statement or 'N/A'}\n"
                f"Sources: "
                f"{source_ids or 'N/A'}\n"
                f"Feedback: "
                f"{issue.feedback or 'N/A'}"
            )
        )

    issue_text = "\n\n".join(
        issues
    )

    return (
        f"{research_context}\n\n"
        f"CURRENT DRAFT:\n"
        f"{request.draft}\n\n"
        f"VERIFIER ISSUES:\n"
        f"{issue_text or '- None'}\n\n"
        f"VERIFIER FEEDBACK:\n"
        f"{request.feedback}"
    )
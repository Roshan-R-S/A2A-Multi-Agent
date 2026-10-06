import json
import logging

from pydantic import ValidationError

from agents.research.schemas import (
    ResearchResult,
)
from agents.verifier.schemas import (
    VerificationResult,
)
from agents.writer.revision import (
    RevisionIssue,
    WriterRevisionRequest,
)


logger = logging.getLogger(__name__)


class RevisionLoop:
    """
    Runs:

    Writer draft
        -> Verifier
        -> PASS: return draft
        -> FAIL: revise draft
        -> Verifier again

    Stops after max_revisions.
    """

    def __init__(
        self,
        client,
        writer_url: str,
        verifier_url: str,
        max_revisions: int = 2,
    ) -> None:
        if max_revisions < 0:
            raise ValueError(
                "max_revisions cannot be negative."
            )

        self.client = client
        self.writer_url = writer_url
        self.verifier_url = verifier_url
        self.max_revisions = max_revisions

    async def run(
        self,
        research_json: str,
        initial_draft: str,
    ) -> str:
        initial_draft = initial_draft.strip()

        if not initial_draft:
            raise ValueError(
                "Initial draft cannot be empty."
            )

        try:
            research = (
                ResearchResult
                .model_validate_json(
                    research_json
                )
            )

        except ValidationError as exc:
            raise ValueError(
                "Invalid structured research result."
            ) from exc

        current_draft = initial_draft

        for revision_number in range(
            self.max_revisions + 1
        ):
            attempt_number = (
                revision_number + 1
            )

            logger.info(
                "Verification attempt %d started.",
                attempt_number,
            )

            verification = await self._verify(
                research,
                current_draft,
            )

            logger.info(
                "Verification attempt %d: %s",
                attempt_number,
                verification.verdict,
            )

            if verification.verdict == "PASS":
                logger.info(
                    "Draft accepted after %d "
                    "verification attempt(s) "
                    "and %d revision(s).",
                    attempt_number,
                    revision_number,
                )

                return current_draft

            if (
                revision_number
                >= self.max_revisions
            ):
                logger.error(
                    "Verification still failing "
                    "after %d revision(s).",
                    self.max_revisions,
                )

                raise RuntimeError(
                    "Verification failed after "
                    f"{self.max_revisions} "
                    "revision attempts. "
                    f"Final feedback: "
                    f"{verification.feedback}"
                )

            next_revision = (
                revision_number + 1
            )

            logger.info(
                "Revision %d requested.",
                next_revision,
            )

            current_draft = await self._revise(
                research,
                current_draft,
                verification,
            )

            logger.info(
                "Revision %d completed.",
                next_revision,
            )

        raise RuntimeError(
            "Revision loop ended unexpectedly."
        )

    async def _verify(
        self,
        research: ResearchResult,
        draft: str,
    ) -> VerificationResult:
        payload = {
            "research": research.model_dump(
                mode="json"
            ),
            "draft": draft,
        }

        raw_result = await self.client.send_text(
            self.verifier_url,
            json.dumps(payload),
        )

        try:
            return (
                VerificationResult
                .model_validate_json(
                    raw_result
                )
            )

        except ValidationError as exc:
            raise RuntimeError(
                "Verifier returned an invalid "
                "verification result."
            ) from exc

    async def _revise(
        self,
        research: ResearchResult,
        draft: str,
        verification: VerificationResult,
    ) -> str:
        feedback = (
            verification.feedback.strip()
            or (
                "Correct all verifier issues "
                "and return an evidence-backed "
                "answer."
            )
        )

        revision_request = (
            WriterRevisionRequest(
                research=research,
                draft=draft,
                feedback=feedback,
                issues=[
                    RevisionIssue(
                        type=issue.type,
                        statement=issue.statement,
                        source_ids=(
                            issue.source_ids
                        ),
                        feedback=(
                            issue.feedback
                        ),
                    )
                    for issue
                    in verification.issues
                ],
            )
        )

        revised_draft = (
            await self.client.send_text(
                self.writer_url,
                revision_request.model_dump_json(),
            )
        )

        revised_draft = revised_draft.strip()

        if not revised_draft:
            raise RuntimeError(
                "Writer returned an empty "
                "revised draft."
            )

        return revised_draft

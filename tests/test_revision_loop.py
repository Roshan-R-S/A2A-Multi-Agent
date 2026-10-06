import json
import logging
from datetime import datetime, timezone

import pytest

from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)
from orchestrator.revision_loop import (
    RevisionLoop,
)


WRITER_URL = "http://writer"
VERIFIER_URL = "http://verifier"


class FakeClient:
    def __init__(
        self,
        verifier_results,
        writer_results=None,
    ) -> None:
        self.verifier_results = list(
            verifier_results
        )

        self.writer_results = list(
            writer_results or []
        )

        self.calls = []

    async def send_text(
        self,
        url: str,
        text: str,
    ) -> str:
        self.calls.append(
            (url, text)
        )

        if url == VERIFIER_URL:
            result = (
                self.verifier_results
                .pop(0)
            )

            return json.dumps(
                result
            )

        if url == WRITER_URL:
            return (
                self.writer_results
                .pop(0)
            )

        raise AssertionError(
            f"Unexpected URL: {url}"
        )


def make_research_result() -> ResearchResult:
    source = Source(
        id="src_1",
        title="Example Source",
        url="https://example.com/rag",
        publisher="example.com",
        published_at=None,
        retrieved_at=datetime(
            2026,
            10,
            6,
            tzinfo=timezone.utc,
        ),
        source_type="web",
    )

    evidence = Evidence(
        id="evidence_1",
        source_id="src_1",
        text=(
            "RAG can reduce hallucinations "
            "by grounding answers."
        ),
        relevance_score=1.0,
    )

    claim = Claim(
        id="claim_1",
        text=(
            "RAG can reduce hallucinations."
        ),
        confidence="high",
        evidence_ids=[
            "evidence_1",
        ],
    )

    return ResearchResult(
        question="Why is RAG useful?",
        summary=(
            "RAG can improve grounded "
            "generation."
        ),
        sources=[
            source,
        ],
        evidence=[
            evidence,
        ],
        claims=[
            claim,
        ],
        caveats=[
            "RAG does not guarantee accuracy."
        ],
    )


def pass_result():
    return {
        "verdict": "PASS",
        "issues": [],
        "feedback": "",
    }


def fail_result():
    return {
        "verdict": "FAIL",
        "issues": [
            {
                "type": (
                    "overstated_certainty"
                ),
                "statement": (
                    "RAG eliminates "
                    "hallucinations."
                ),
                "source_ids": [
                    "src_1"
                ],
                "feedback": (
                    "The research supports "
                    "reduction, not elimination."
                ),
            }
        ],
        "feedback": (
            "Use less absolute language."
        ),
    }


@pytest.mark.asyncio
async def test_passes_without_revision():
    client = FakeClient(
        verifier_results=[
            pass_result(),
        ]
    )

    loop = RevisionLoop(
        client=client,
        writer_url=WRITER_URL,
        verifier_url=VERIFIER_URL,
    )

    result = await loop.run(
        make_research_result()
        .model_dump_json(),
        (
            "RAG can reduce hallucinations. "
            "[src_1]"
        ),
    )

    assert (
        result
        == (
            "RAG can reduce hallucinations. "
            "[src_1]"
        )
    )

    assert len(client.calls) == 1

    assert (
        client.calls[0][0]
        == VERIFIER_URL
    )


@pytest.mark.asyncio
async def test_fail_then_pass_revises_once():
    client = FakeClient(
        verifier_results=[
            fail_result(),
            pass_result(),
        ],
        writer_results=[
            (
                "RAG can reduce "
                "hallucinations. [src_1]"
            )
        ],
    )

    loop = RevisionLoop(
        client=client,
        writer_url=WRITER_URL,
        verifier_url=VERIFIER_URL,
    )

    result = await loop.run(
        make_research_result()
        .model_dump_json(),
        (
            "RAG eliminates "
            "hallucinations. [src_1]"
        ),
    )

    assert (
        "can reduce"
        in result
    )

    urls = [
        url
        for url, _
        in client.calls
    ]

    assert urls == [
        VERIFIER_URL,
        WRITER_URL,
        VERIFIER_URL,
    ]


@pytest.mark.asyncio
async def test_two_revisions_then_pass():
    client = FakeClient(
        verifier_results=[
            fail_result(),
            fail_result(),
            pass_result(),
        ],
        writer_results=[
            (
                "Revision one. "
                "[src_1]"
            ),
            (
                "Revision two. "
                "[src_1]"
            ),
        ],
    )

    loop = RevisionLoop(
        client=client,
        writer_url=WRITER_URL,
        verifier_url=VERIFIER_URL,
        max_revisions=2,
    )

    result = await loop.run(
        make_research_result()
        .model_dump_json(),
        (
            "Initial answer. "
            "[src_1]"
        ),
    )

    assert result == (
        "Revision two. [src_1]"
    )

    writer_calls = [
        call
        for call
        in client.calls
        if call[0] == WRITER_URL
    ]

    assert len(writer_calls) == 2


@pytest.mark.asyncio
async def test_stops_after_max_revisions():
    client = FakeClient(
        verifier_results=[
            fail_result(),
            fail_result(),
            fail_result(),
        ],
        writer_results=[
            "Revision one. [src_1]",
            "Revision two. [src_1]",
        ],
    )

    loop = RevisionLoop(
        client=client,
        writer_url=WRITER_URL,
        verifier_url=VERIFIER_URL,
        max_revisions=2,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "Verification failed after "
            "2 revision attempts"
        ),
    ):
        await loop.run(
            make_research_result()
            .model_dump_json(),
            (
                "Initial answer. "
                "[src_1]"
            ),
        )


@pytest.mark.asyncio
async def test_rejects_empty_initial_draft():
    client = FakeClient(
        verifier_results=[]
    )

    loop = RevisionLoop(
        client=client,
        writer_url=WRITER_URL,
        verifier_url=VERIFIER_URL,
    )

    with pytest.raises(
        ValueError,
        match="Initial draft cannot be empty",
    ):
        await loop.run(
            make_research_result()
            .model_dump_json(),
            "   ",
        )


def test_rejects_negative_revision_limit():
    client = FakeClient(
        verifier_results=[]
    )

    with pytest.raises(
        ValueError,
        match=(
            "max_revisions cannot be negative"
        ),
    ):
        RevisionLoop(
            client=client,
            writer_url=WRITER_URL,
            verifier_url=VERIFIER_URL,
            max_revisions=-1,
        )


@pytest.mark.asyncio
async def test_revision_loop_logs_fail_revision_pass(
    caplog,
):
    client = FakeClient(
        verifier_results=[
            fail_result(),
            pass_result(),
        ],
        writer_results=[
            (
                "RAG can reduce "
                "hallucinations. [src_1]"
            )
        ],
    )

    loop = RevisionLoop(
        client=client,
        writer_url=WRITER_URL,
        verifier_url=VERIFIER_URL,
    )

    caplog.set_level(
        logging.INFO,
        logger=(
            "orchestrator.revision_loop"
        ),
    )

    await loop.run(
        make_research_result()
        .model_dump_json(),
        (
            "RAG eliminates "
            "hallucinations. [src_1]"
        ),
    )

    log_text = caplog.text

    assert (
        "Verification attempt 1: FAIL"
        in log_text
    )

    assert (
        "Revision 1 requested"
        in log_text
    )

    assert (
        "Revision 1 completed"
        in log_text
    )

    assert (
        "Verification attempt 2: PASS"
        in log_text
    )

    assert (
        "Draft accepted after 2 "
        "verification attempt(s) "
        "and 1 revision(s)"
        in log_text
    )

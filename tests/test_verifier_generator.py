from datetime import datetime, timezone

import pytest

import agents.verifier.generator as generator_module
from agents.research.schemas import (
    Claim,
    Evidence,
    ResearchResult,
    Source,
)
from agents.verifier.generator import (
    EvidenceAwareVerifier,
)
from agents.verifier.schemas import (
    VerificationRequest,
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
            "RAG retrieves relevant information "
            "before generation."
        ),
        relevance_score=1.0,
    )

    claim = Claim(
        id="claim_1",
        text=(
            "RAG uses retrieved information "
            "during generation."
        ),
        confidence="high",
        evidence_ids=[
            "evidence_1",
        ],
    )

    return ResearchResult(
        question="What is RAG?",
        summary=(
            "RAG combines retrieval "
            "with generation."
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
            "Retrieval quality matters."
        ],
    )


def make_request(
    draft: str = (
        "RAG uses retrieved information "
        "during generation. [src_1]"
    ),
) -> VerificationRequest:

    return VerificationRequest(
        research=make_research_result(),
        draft=draft,
    )


def test_parse_pass_result():
    raw = """
    {
        "verdict": "PASS",
        "issues": [],
        "feedback": ""
    }
    """

    result = (
        EvidenceAwareVerifier.parse_result(
            raw,
            known_sources={
                "src_1"
            },
        )
    )

    assert result.verdict == "PASS"
    assert result.issues == []


def test_parse_fail_result():
    raw = """
    {
        "verdict": "FAIL",
        "issues": [
            {
                "type": "missing_citation",
                "statement": "A statement.",
                "source_ids": [],
                "feedback": "Add a citation."
            }
        ],
        "feedback": "Revise the answer."
    }
    """

    result = (
        EvidenceAwareVerifier.parse_result(
            raw,
            known_sources={
                "src_1"
            },
        )
    )

    assert result.verdict == "FAIL"

    assert (
        result.issues[0].type
        == "missing_citation"
    )


def test_parse_handles_markdown_fence():
    raw = """
```json
{
    "verdict": "PASS",
    "issues": [],
    "feedback": ""
}
```
    """

    result = (
        EvidenceAwareVerifier.parse_result(
            raw,
            known_sources={
                "src_1"
            },
        )
    )

    assert result.verdict == "PASS"


def test_parse_rejects_invalid_json():
    with pytest.raises(
        RuntimeError,
        match="invalid JSON",
    ):
        EvidenceAwareVerifier.parse_result(
            "not json",
            known_sources={
                "src_1"
            },
        )


def test_pass_cannot_have_issues():
    raw = """
    {
        "verdict": "PASS",
        "issues": [
            {
                "type": "other",
                "statement": "Problem.",
                "source_ids": [],
                "feedback": "Fix it."
            }
        ],
        "feedback": ""
    }
    """

    with pytest.raises(
        RuntimeError,
        match="PASS verification",
    ):
        EvidenceAwareVerifier.parse_result(
            raw,
            known_sources={
                "src_1"
            },
        )


def test_fail_requires_issue():
    raw = """
    {
        "verdict": "FAIL",
        "issues": [],
        "feedback": "Something failed."
    }
    """

    with pytest.raises(
        RuntimeError,
        match="at least one issue",
    ):
        EvidenceAwareVerifier.parse_result(
            raw,
            known_sources={
                "src_1"
            },
        )


def test_parse_rejects_unknown_issue_source():
    raw = """
    {
        "verdict": "FAIL",
        "issues": [
            {
                "type": "citation_mismatch",
                "statement": "Bad claim.",
                "source_ids": [
                    "src_999"
                ],
                "feedback": "Wrong source."
            }
        ],
        "feedback": "Fix citation."
    }
    """

    with pytest.raises(
        RuntimeError,
        match="unknown source IDs",
    ):
        EvidenceAwareVerifier.parse_result(
            raw,
            known_sources={
                "src_1"
            },
        )


@pytest.mark.asyncio
async def test_unknown_citation_fails_without_llm(
    monkeypatch,
):
    async def fake_generate_text(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "LLM should not be called."
        )

    monkeypatch.setattr(
        generator_module,
        "generate_text",
        fake_generate_text,
    )

    verifier = EvidenceAwareVerifier()

    result = await verifier.verify(
        make_request(
            (
                "RAG uses retrieval. "
                "[src_999]"
            )
        )
    )

    assert result.verdict == "FAIL"

    assert (
        result.issues[0].type
        == "unknown_citation"
    )


@pytest.mark.asyncio
async def test_missing_citation_fails_without_llm(
    monkeypatch,
):
    async def fake_generate_text(
        *args,
        **kwargs,
    ):
        raise AssertionError(
            "LLM should not be called."
        )

    monkeypatch.setattr(
        generator_module,
        "generate_text",
        fake_generate_text,
    )

    verifier = EvidenceAwareVerifier()

    result = await verifier.verify(
        make_request(
            "RAG uses retrieved information."
        )
    )

    assert result.verdict == "FAIL"

    assert (
        result.issues[0].type
        == "missing_citation"
    )


@pytest.mark.asyncio
async def test_semantic_verifier_calls_llm(
    monkeypatch,
):
    captured = {}

    async def fake_generate_text(
        prompt: str,
        system_prompt: str,
        temperature: float,
        **kwargs,
    ) -> str:

        captured["prompt"] = prompt
        captured["temperature"] = (
            temperature
        )
        captured["options"] = kwargs

        return """
        {
            "verdict": "PASS",
            "issues": [],
            "feedback": ""
        }
        """

    monkeypatch.setattr(
        generator_module,
        "generate_text",
        fake_generate_text,
    )

    verifier = EvidenceAwareVerifier()

    result = await verifier.verify(
        make_request()
    )

    assert result.verdict == "PASS"

    assert (
        "SUPPORTED CLAIMS AND EVIDENCE"
        in captured["prompt"]
    )

    assert (
        "WRITER DRAFT"
        in captured["prompt"]
    )

    assert (
        "evidence_1"
        in captured["prompt"]
    )

    assert (
        captured["temperature"]
        == 0.0
    )
    assert captured["options"]["response_format"]["json_schema"]["strict"] is True
    assert captured["options"]["reasoning_effort"] == "low"
    assert captured["options"]["max_completion_tokens"] == 1200



# Regression tests for bold headings and abbreviated sentence boundaries.

def test_emphasized_vs_heading_is_not_a_claim():
    draft = (
        "**Retrieval‑augmented generation (RAG) vs. fine‑tuning**\n"
        "RAG uses retrieved information during generation. [src_1]"
    )
    assert generator_module._find_uncited_research_statements(
        make_request(draft)
    ) == []


def test_vs_abbreviation_does_not_split_a_sentence():
    draft = (
        "RAG vs. fine-tuning uses retrieved information "
        "during generation. [src_1]"
    )
    assert generator_module._iter_candidate_statements(draft) == [
        draft
    ]


def test_uncited_factual_statement_after_heading_is_detected():
    draft = (
        "**RAG vs. fine-tuning**\n"
        "RAG uses retrieved information during generation."
    )
    assert generator_module._find_uncited_research_statements(
        make_request(draft)
    ) == [
        "RAG uses retrieved information during generation."
    ]


def test_bold_factual_statement_is_not_automatically_exempt():
    draft = "**RAG uses retrieved information during generation**"
    assert generator_module._find_uncited_research_statements(
        make_request(draft)
    ) == [draft]


def test_strict_verifier_schema_has_required_fields_and_closed_objects():
    spec = generator_module._VERIFICATION_RESPONSE_FORMAT
    assert spec["type"] == "json_schema"
    assert spec["json_schema"]["strict"] is True
    schema = spec["json_schema"]["schema"]
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    issue = schema["properties"]["issues"]["items"]
    assert set(issue["required"]) == set(issue["properties"])
    assert issue["additionalProperties"] is False
    assert set(issue["properties"]["type"]["enum"]) == set(
        generator_module.VerificationIssue.model_fields["type"].annotation.__args__
    )


@pytest.mark.asyncio
async def test_verifier_malformed_structured_result_fails_closed(monkeypatch):
    calls = []

    async def fake_generate_text(**kwargs):
        calls.append(kwargs)
        return '{"verdict": "PASS", "issues": [}'

    monkeypatch.setattr(generator_module, "generate_text", fake_generate_text)
    with pytest.raises(RuntimeError, match="invalid JSON"):
        await EvidenceAwareVerifier().verify(make_request())
    assert len(calls) == 1  # No additional Groq call to repair broken JSON.


@pytest.mark.asyncio
async def test_uncited_research_sentence_fails_without_llm(monkeypatch):
    async def fake_generate_text(*args, **kwargs):
        raise AssertionError("LLM should not be called.")

    monkeypatch.setattr(generator_module, "generate_text", fake_generate_text)
    verifier = EvidenceAwareVerifier()
    result = await verifier.verify(make_request(
        "RAG uses retrieved information during generation. [src_1]\n"
        "Retrieval quality matters."
    ))
    assert result.verdict == "FAIL"
    assert any(
        issue.type == "missing_citation" and issue.statement == "Retrieval quality matters."
        for issue in result.issues
    )


@pytest.mark.asyncio
async def test_fully_cited_sentences_reach_semantic_verifier(monkeypatch):
    captured = {}

    async def fake_generate_text(prompt: str, system_prompt: str,
                                 temperature: float, **kwargs) -> str:
        captured["prompt"] = prompt
        return '{"verdict": "PASS", "issues": [], "feedback": ""}'

    monkeypatch.setattr(generator_module, "generate_text", fake_generate_text)
    verifier = EvidenceAwareVerifier()
    result = await verifier.verify(make_request(
        "RAG uses retrieved information during generation. [src_1]\n"
        "Retrieval quality matters. [src_1]"
    ))
    assert result.verdict == "PASS"
    assert "WRITER DRAFT" in captured["prompt"]


@pytest.mark.asyncio
async def test_markdown_heading_is_not_missing_citation(monkeypatch):
    async def fake_generate_text(prompt: str, system_prompt: str,
                                 temperature: float, **kwargs) -> str:
        return '{"verdict": "PASS", "issues": [], "feedback": ""}'

    monkeypatch.setattr(generator_module, "generate_text", fake_generate_text)
    verifier = EvidenceAwareVerifier()
    result = await verifier.verify(make_request(
        "### How RAG works\n"
        "RAG uses retrieved information during generation. [src_1]"
    ))
    assert result.verdict == "PASS"

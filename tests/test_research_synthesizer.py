from datetime import datetime, timezone

import pytest

import agents.research.synthesizer as synthesizer_module
from agents.research.schemas import (
    Claim,
    Evidence,
    Source,
)
from agents.research.synthesizer import (
    LLMResearchSynthesizer,
    ResearchSynthesizer,
)


def make_source() -> Source:
    return Source(
        id="src_1",
        title="Example RAG Source",
        url="https://example.com/rag",
        publisher="example.com",
        published_at=None,
        retrieved_at=datetime(
            2026,
            10,
            4,
            tzinfo=timezone.utc,
        ),
        source_type="web",
    )


def make_evidence() -> Evidence:
    return Evidence(
        id="evidence_1",
        source_id="src_1",
        text=(
            "RAG retrieves relevant information "
            "before generating an answer."
        ),
        relevance_score=1.0,
    )


def make_claim() -> Claim:
    return Claim(
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


def test_synthesizer_matches_protocol():
    synthesizer = LLMResearchSynthesizer()

    assert isinstance(
        synthesizer,
        ResearchSynthesizer,
    )


def test_parse_valid_result():
    raw = '''
    {
        "summary": "RAG combines retrieval with generation.",
        "caveats": [
            "Retrieval quality matters."
        ]
    }
    '''

    result = (
        LLMResearchSynthesizer.parse_result(
            raw
        )
    )

    assert result.summary == (
        "RAG combines retrieval with generation."
    )

    assert result.caveats == (
        "Retrieval quality matters.",
    )


def test_parse_handles_markdown_fence():
    raw = '''
```json
{
    "summary": "RAG uses retrieval.",
    "caveats": []
}
```
    '''

    result = (
        LLMResearchSynthesizer.parse_result(
            raw
        )
    )

    assert result.summary == (
        "RAG uses retrieval."
    )

    assert result.caveats == ()


def test_parse_rejects_invalid_json():
    with pytest.raises(
        RuntimeError,
        match="invalid JSON",
    ):
        LLMResearchSynthesizer.parse_result(
            "not json"
        )


def test_parse_rejects_empty_summary():
    raw = '''
    {
        "summary": "   ",
        "caveats": []
    }
    '''

    with pytest.raises(
        RuntimeError,
        match="non-empty summary",
    ):
        LLMResearchSynthesizer.parse_result(
            raw
        )


def test_parse_rejects_invalid_caveats():
    raw = '''
    {
        "summary": "Valid summary.",
        "caveats": "Not a list"
    }
    '''

    with pytest.raises(
        RuntimeError,
        match="must be a list",
    ):
        LLMResearchSynthesizer.parse_result(
            raw
        )


def test_parse_cleans_caveats():
    raw = '''
    {
        "summary": "Valid summary.",
        "caveats": [
            "  Retrieval quality matters.  ",
            "",
            "Retrieval quality matters.",
            "Hallucination is still possible."
        ]
    }
    '''

    result = (
        LLMResearchSynthesizer.parse_result(
            raw
        )
    )

    assert result.caveats == (
        "Retrieval quality matters.",
        "Hallucination is still possible.",
    )


@pytest.mark.asyncio
async def test_synthesize_handles_missing_evidence():
    synthesizer = LLMResearchSynthesizer()

    result = await synthesizer.synthesize(
        "What is RAG?",
        claims=[],
        evidence=[],
        sources=[],
    )

    assert (
        "Insufficient supported evidence"
        in result.summary
    )

    assert len(result.caveats) == 1


@pytest.mark.asyncio
async def test_synthesize_uses_llm(
    monkeypatch,
):
    captured = {}

    async def fake_generate_text(
        prompt: str,
        system_prompt: str,
        temperature: float,
    ) -> str:
        captured["prompt"] = prompt
        captured["system_prompt"] = (
            system_prompt
        )
        captured["temperature"] = (
            temperature
        )

        return '''
        {
            "summary": "RAG uses retrieved information.",
            "caveats": [
                "Retrieval quality matters."
            ]
        }
        '''

    monkeypatch.setattr(
        synthesizer_module,
        "generate_text",
        fake_generate_text,
    )

    synthesizer = LLMResearchSynthesizer()

    result = await synthesizer.synthesize(
        "What is RAG?",
        claims=[
            make_claim(),
        ],
        evidence=[
            make_evidence(),
        ],
        sources=[
            make_source(),
        ],
    )

    assert result.summary == (
        "RAG uses retrieved information."
    )

    assert result.caveats == (
        "Retrieval quality matters.",
    )

    assert (
        "claim_1"
        in captured["prompt"]
    )

    assert (
        "evidence_1"
        in captured["prompt"]
    )

    assert (
        "src_1"
        in captured["prompt"]
    )

    assert captured[
        "temperature"
    ] == 0.0

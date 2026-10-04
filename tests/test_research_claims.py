import pytest

from agents.research.claims import (
    ClaimGenerator,
    LLMClaimGenerator,
)
from agents.research.schemas import (
    Evidence,
)


def make_evidence(
    *,
    evidence_id: str = "evidence_1",
    source_id: str = "src_1",
    text: str = (
        "RAG retrieves relevant information "
        "before generating an answer."
    ),
) -> Evidence:
    return Evidence(
        id=evidence_id,
        source_id=source_id,
        text=text,
        relevance_score=1.0,
    )


def test_llm_claim_generator_matches_protocol():
    generator = LLMClaimGenerator()

    assert isinstance(
        generator,
        ClaimGenerator,
    )


def test_parse_valid_claim_result():
    raw = """
    {
        "claims": [
            {
                "text": "RAG uses retrieved information.",
                "confidence": "high",
                "evidence_ids": ["evidence_1"]
            }
        ]
    }
    """

    claims = LLMClaimGenerator.parse_result(
        raw,
        evidence=[
            make_evidence(),
        ],
    )

    assert len(claims) == 1

    assert claims[0].id == "claim_1"

    assert claims[0].text == (
        "RAG uses retrieved information."
    )

    assert claims[0].confidence == "high"

    assert claims[0].evidence_ids == [
        "evidence_1"
    ]


def test_parse_handles_markdown_fence():
    raw = """
```json
{
    "claims": [
        {
            "text": "RAG uses retrieval.",
            "confidence": "high",
            "evidence_ids": ["evidence_1"]
        }
    ]
}
```
    """

    claims = LLMClaimGenerator.parse_result(
        raw,
        evidence=[
            make_evidence(),
        ],
    )

    assert len(claims) == 1

    assert claims[0].id == "claim_1"


def test_parse_rejects_invalid_json():
    with pytest.raises(
        RuntimeError,
        match="invalid JSON",
    ):
        LLMClaimGenerator.parse_result(
            "not json",
            evidence=[
                make_evidence(),
            ],
        )


def test_parse_rejects_unknown_evidence():
    raw = """
    {
        "claims": [
            {
                "text": "Unsupported claim.",
                "confidence": "high",
                "evidence_ids": ["evidence_missing"]
            }
        ]
    }
    """

    with pytest.raises(
        RuntimeError,
        match="unknown evidence",
    ):
        LLMClaimGenerator.parse_result(
            raw,
            evidence=[
                make_evidence(),
            ],
        )


def test_parse_rejects_claim_without_evidence():
    raw = """
    {
        "claims": [
            {
                "text": "Unsupported claim.",
                "confidence": "low",
                "evidence_ids": []
            }
        ]
    }
    """

    with pytest.raises(
        RuntimeError,
        match="must reference evidence",
    ):
        LLMClaimGenerator.parse_result(
            raw,
            evidence=[
                make_evidence(),
            ],
        )


def test_max_claims_is_respected():
    raw = """
    {
        "claims": [
            {
                "text": "Claim one.",
                "confidence": "high",
                "evidence_ids": ["evidence_1"]
            },
            {
                "text": "Claim two.",
                "confidence": "medium",
                "evidence_ids": ["evidence_1"]
            },
            {
                "text": "Claim three.",
                "confidence": "low",
                "evidence_ids": ["evidence_1"]
            }
        ]
    }
    """

    claims = LLMClaimGenerator.parse_result(
        raw,
        evidence=[
            make_evidence(),
        ],
        max_claims=2,
    )

    assert len(claims) == 2

    assert claims[0].id == "claim_1"
    assert claims[1].id == "claim_2"


@pytest.mark.asyncio
async def test_generate_returns_empty_when_no_evidence():
    generator = LLMClaimGenerator()

    claims = await generator.generate(
        "What is RAG?",
        [],
    )

    assert claims == []

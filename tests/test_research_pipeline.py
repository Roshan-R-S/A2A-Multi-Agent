import pytest

from agents.research.claims import (
    ClaimGenerator,
)
from agents.research.evidence import (
    EvidenceExtractor,
)
from agents.research.pipeline import (
    ResearchPipeline,
)
from agents.research.synthesizer import (
    ResearchSynthesis,
    ResearchSynthesizer,
)
from agents.research.schemas import (
    Claim,
    Evidence,
    Source,
)
from agents.research.search import (
    SearchHit,
    SearchService,
)


class FakeSearchProvider:
    name = "fake-search"

    def __init__(
        self,
        results: list[SearchHit],
    ) -> None:
        self.results = results
        self.calls: list[dict] = []

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[SearchHit]:
        self.calls.append(
            {
                "query": query,
                "max_results": max_results,
            }
        )

        return self.results


class FakeEvidenceExtractor:
    name = "fake-evidence"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def extract(
        self,
        query: str,
        hits: list[SearchHit],
        sources: list[Source],
        *,
        max_evidence: int = 10,
    ) -> list[Evidence]:
        self.calls.append(
            {
                "query": query,
                "hits": hits,
                "sources": sources,
                "max_evidence": max_evidence,
            }
        )

        if not sources:
            return []

        return [
            Evidence(
                id="evidence_1",
                source_id=sources[0].id,
                text=(
                    "RAG retrieves relevant "
                    "information before generation."
                ),
                relevance_score=1.0,
            )
        ]


class FakeClaimGenerator:
    name = "fake-claims"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def generate(
        self,
        question: str,
        evidence: list[Evidence],
        *,
        max_claims: int = 8,
    ) -> list[Claim]:
        self.calls.append(
            {
                "question": question,
                "evidence": evidence,
                "max_claims": max_claims,
            }
        )

        if not evidence:
            return []

        return [
            Claim(
                id="claim_1",
                text=(
                    "RAG uses retrieved information "
                    "during generation."
                ),
                confidence="high",
                evidence_ids=[
                    evidence[0].id
                ],
            )
        ]


class FakeResearchSynthesizer:
    name = "fake-synthesizer"

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def synthesize(
        self,
        question: str,
        claims: list[Claim],
        evidence: list[Evidence],
        sources: list[Source],
    ) -> ResearchSynthesis:
        self.calls.append(
            {
                "question": question,
                "claims": claims,
                "evidence": evidence,
                "sources": sources,
            }
        )

        return ResearchSynthesis(
            summary=(
                "RAG combines retrieval "
                "with generation."
            ),
            caveats=(
                "Retrieval quality matters.",
            ),
        )


def make_hit() -> SearchHit:
    return SearchHit(
        title="RAG Example",
        url="https://example.com/rag",
        snippet=(
            "RAG retrieves relevant information "
            "before generation."
        ),
        rank=1,
    )


def make_pipeline(
    hits: list[SearchHit],
):
    search_provider = FakeSearchProvider(
        hits
    )

    evidence_extractor = (
        FakeEvidenceExtractor()
    )

    claim_generator = (
        FakeClaimGenerator()
    )

    synthesizer = (
        FakeResearchSynthesizer()
    )

    pipeline = ResearchPipeline(
        search_service=SearchService(
            search_provider
        ),
        evidence_extractor=evidence_extractor,
        claim_generator=claim_generator,
        synthesizer=synthesizer,
    )

    return (
        pipeline,
        search_provider,
        evidence_extractor,
        claim_generator,
        synthesizer,
    )


def test_fake_evidence_extractor_matches_protocol():
    extractor = FakeEvidenceExtractor()

    assert isinstance(
        extractor,
        EvidenceExtractor,
    )


def test_fake_claim_generator_matches_protocol():
    generator = FakeClaimGenerator()

    assert isinstance(
        generator,
        ClaimGenerator,
    )


def test_fake_synthesizer_matches_protocol():
    synthesizer = FakeResearchSynthesizer()

    assert isinstance(
        synthesizer,
        ResearchSynthesizer,
    )


@pytest.mark.asyncio
async def test_pipeline_creates_research_result():
    (
        pipeline,
        _,
        _,
        _,
        _,
    ) = make_pipeline(
        [
            make_hit(),
        ]
    )

    result = await pipeline.run(
        "What is RAG?"
    )

    assert result.question == (
        "What is RAG?"
    )

    assert result.summary == (
        "RAG combines retrieval with generation."
    )

    assert len(result.sources) == 1
    assert len(result.evidence) == 1
    assert len(result.claims) == 1

    assert result.caveats == [
        "Retrieval quality matters."
    ]


@pytest.mark.asyncio
async def test_pipeline_preserves_reference_chain():
    (
        pipeline,
        _,
        _,
        _,
        _,
    ) = make_pipeline(
        [
            make_hit(),
        ]
    )

    result = await pipeline.run(
        "What is RAG?"
    )

    assert (
        result.claims[0].evidence_ids
        == ["evidence_1"]
    )

    assert (
        result.evidence[0].source_id
        == "src_1"
    )


@pytest.mark.asyncio
async def test_pipeline_passes_limits():
    (
        pipeline,
        search_provider,
        evidence_extractor,
        claim_generator,
        _,
    ) = make_pipeline(
        [
            make_hit(),
        ]
    )

    await pipeline.run(
        "What is RAG?",
        max_results=3,
        max_evidence=4,
        max_claims=5,
    )

    assert (
        search_provider.calls[0][
            "max_results"
        ]
        == 3
    )

    assert (
        evidence_extractor.calls[0][
            "max_evidence"
        ]
        == 4
    )

    assert (
        claim_generator.calls[0][
            "max_claims"
        ]
        == 5
    )


@pytest.mark.asyncio
async def test_pipeline_strips_question():
    (
        pipeline,
        search_provider,
        _,
        _,
        _,
    ) = make_pipeline(
        [
            make_hit(),
        ]
    )

    result = await pipeline.run(
        "   What is RAG?   "
    )

    assert result.question == (
        "What is RAG?"
    )

    assert (
        search_provider.calls[0]["query"]
        == "What is RAG?"
    )


@pytest.mark.asyncio
async def test_pipeline_rejects_empty_question():
    (
        pipeline,
        _,
        _,
        _,
        _,
    ) = make_pipeline([])

    with pytest.raises(
        ValueError,
        match="Question cannot be empty",
    ):
        await pipeline.run("   ")


@pytest.mark.asyncio
async def test_pipeline_handles_no_search_results():
    (
        pipeline,
        _,
        evidence_extractor,
        claim_generator,
        synthesizer,
    ) = make_pipeline([])

    result = await pipeline.run(
        "Unknown topic"
    )

    assert result.sources == []
    assert result.evidence == []
    assert result.claims == []

    assert (
        "No supporting web evidence"
        in result.summary
    )

    assert len(result.caveats) == 1

    assert evidence_extractor.calls == []
    assert claim_generator.calls == []
    assert synthesizer.calls == []
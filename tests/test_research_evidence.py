import pytest

from agents.research.evidence import (
    EvidenceExtractor,
    SnippetEvidenceExtractor,
)
from agents.research.search import SearchHit
from agents.research.sources import (
    search_hits_to_sources,
)


def make_hit(
    *,
    title: str = "Example RAG Source",
    url: str = "https://example.com/rag",
    snippet: str = (
        "RAG retrieves relevant information "
        "before generating an answer."
    ),
    rank: int = 1,
) -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        snippet=snippet,
        rank=rank,
    )


def test_snippet_extractor_matches_protocol():
    extractor = SnippetEvidenceExtractor()

    assert isinstance(
        extractor,
        EvidenceExtractor,
    )


@pytest.mark.asyncio
async def test_extracts_evidence_from_search_hit():
    hits = [
        make_hit()
    ]

    sources = search_hits_to_sources(
        hits
    )

    extractor = SnippetEvidenceExtractor()

    evidence = await extractor.extract(
        "What is RAG?",
        hits,
        sources,
    )

    assert len(evidence) == 1

    assert evidence[0].id == (
        "evidence_1"
    )

    assert evidence[0].text == (
        "RAG retrieves relevant information "
        "before generating an answer."
    )


@pytest.mark.asyncio
async def test_evidence_references_correct_source():
    hits = [
        make_hit()
    ]

    sources = search_hits_to_sources(
        hits
    )

    extractor = SnippetEvidenceExtractor()

    evidence = await extractor.extract(
        "RAG",
        hits,
        sources,
    )

    assert evidence[0].source_id == (
        "src_1"
    )


@pytest.mark.asyncio
async def test_extractor_normalizes_snippet_whitespace():
    hits = [
        make_hit(
            snippet=(
                "RAG   retrieves\n"
                "relevant    information."
            )
        )
    ]

    sources = search_hits_to_sources(
        hits
    )

    extractor = SnippetEvidenceExtractor()

    evidence = await extractor.extract(
        "RAG",
        hits,
        sources,
    )

    assert evidence[0].text == (
        "RAG retrieves relevant information."
    )


@pytest.mark.asyncio
async def test_empty_snippets_are_skipped():
    hits = [
        make_hit(
            snippet="   "
        )
    ]

    sources = search_hits_to_sources(
        hits
    )

    extractor = SnippetEvidenceExtractor()

    evidence = await extractor.extract(
        "RAG",
        hits,
        sources,
    )

    assert evidence == []


@pytest.mark.asyncio
async def test_duplicate_evidence_is_removed():
    hits = [
        make_hit(
            url="https://example.com/rag",
            rank=1,
        ),
        make_hit(
            url="https://example.com/rag/",
            rank=2,
        ),
    ]

    sources = search_hits_to_sources(
        hits
    )

    extractor = SnippetEvidenceExtractor()

    evidence = await extractor.extract(
        "RAG",
        hits,
        sources,
    )

    assert len(evidence) == 1


@pytest.mark.asyncio
async def test_max_evidence_is_respected():
    hits = [
        make_hit(
            title="First",
            url="https://example.com/1",
            snippet="Evidence number one.",
            rank=1,
        ),
        make_hit(
            title="Second",
            url="https://example.com/2",
            snippet="Evidence number two.",
            rank=2,
        ),
        make_hit(
            title="Third",
            url="https://example.com/3",
            snippet="Evidence number three.",
            rank=3,
        ),
    ]

    sources = search_hits_to_sources(
        hits
    )

    extractor = SnippetEvidenceExtractor()

    evidence = await extractor.extract(
        "RAG",
        hits,
        sources,
        max_evidence=2,
    )

    assert len(evidence) == 2


@pytest.mark.asyncio
async def test_empty_evidence_query_is_rejected():
    extractor = SnippetEvidenceExtractor()

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        await extractor.extract(
            "   ",
            [],
            [],
        )
import pytest

from agents.research.search import (
    SearchHit,
    SearchProvider,
    SearchService,
)


class FakeSearchProvider:
    name = "fake"

    def __init__(
        self,
        results: list[SearchHit] | None = None,
    ) -> None:
        self.results = results or []
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


def make_search_hit(
    rank: int = 1,
) -> SearchHit:
    return SearchHit(
        title="Example RAG Article",
        url="https://example.com/rag",
        snippet=(
            "RAG combines retrieval "
            "with language generation."
        ),
        rank=rank,
    )


def test_fake_provider_matches_protocol():
    provider = FakeSearchProvider()

    assert isinstance(
        provider,
        SearchProvider,
    )


def test_search_hit_creation():
    hit = make_search_hit()

    assert hit.title == (
        "Example RAG Article"
    )

    assert hit.url == (
        "https://example.com/rag"
    )

    assert hit.rank == 1


@pytest.mark.asyncio
async def test_search_service_calls_provider():
    provider = FakeSearchProvider(
        [
            make_search_hit(),
        ]
    )

    service = SearchService(
        provider
    )

    results = await service.search(
        "What is RAG?",
        max_results=5,
    )

    assert len(results) == 1

    assert results[0].title == (
        "Example RAG Article"
    )

    assert provider.calls == [
        {
            "query": "What is RAG?",
            "max_results": 5,
        }
    ]


@pytest.mark.asyncio
async def test_search_service_strips_query():
    provider = FakeSearchProvider()

    service = SearchService(
        provider
    )

    await service.search(
        "   What is RAG?   "
    )

    assert provider.calls[0][
        "query"
    ] == "What is RAG?"


@pytest.mark.asyncio
async def test_search_service_rejects_empty_query():
    provider = FakeSearchProvider()

    service = SearchService(
        provider
    )

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        await service.search("   ")


@pytest.mark.asyncio
async def test_search_service_rejects_zero_results_limit():
    provider = FakeSearchProvider()

    service = SearchService(
        provider
    )

    with pytest.raises(
        ValueError,
        match="between 1 and 20",
    ):
        await service.search(
            "RAG",
            max_results=0,
        )


@pytest.mark.asyncio
async def test_search_service_rejects_large_results_limit():
    provider = FakeSearchProvider()

    service = SearchService(
        provider
    )

    with pytest.raises(
        ValueError,
        match="between 1 and 20",
    ):
        await service.search(
            "RAG",
            max_results=21,
        )


@pytest.mark.asyncio
async def test_search_service_limits_results():
    provider = FakeSearchProvider(
        [
            make_search_hit(rank=1),
            make_search_hit(rank=2),
            make_search_hit(rank=3),
        ]
    )

    service = SearchService(
        provider
    )

    results = await service.search(
        "RAG",
        max_results=2,
    )

    assert len(results) == 2
import json

import httpx
import pytest

from agents.research.providers.tavily import (
    TavilySearchError,
    TavilySearchProvider,
)
from agents.research.search import (
    SearchProvider,
)


def test_tavily_matches_search_provider_protocol():
    provider = TavilySearchProvider(
        "test-api-key"
    )

    assert isinstance(
        provider,
        SearchProvider,
    )


def test_tavily_rejects_empty_api_key():
    with pytest.raises(
        ValueError,
        match="API key cannot be empty",
    ):
        TavilySearchProvider(
            "   "
        )


@pytest.mark.asyncio
async def test_tavily_search_maps_results():
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": (
                            "Retrieval-Augmented "
                            "Generation"
                        ),
                        "url": (
                            "https://example.com/rag"
                        ),
                        "content": (
                            "RAG combines retrieval "
                            "with generation."
                        ),
                        "score": 0.95,
                    }
                ]
            },
            request=request,
        )

    transport = httpx.MockTransport(
        handler
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        provider = TavilySearchProvider(
            "test-api-key",
            client=client,
        )

        results = await provider.search(
            "What is RAG?"
        )

    assert len(results) == 1

    assert results[0].title == (
        "Retrieval-Augmented Generation"
    )

    assert results[0].url == (
        "https://example.com/rag"
    )

    assert results[0].snippet == (
        "RAG combines retrieval with generation."
    )

    assert results[0].rank == 1


@pytest.mark.asyncio
async def test_tavily_sends_expected_request():
    captured = {}

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        captured["method"] = (
            request.method
        )

        captured["url"] = str(
            request.url
        )

        captured["authorization"] = (
            request.headers.get(
                "Authorization"
            )
        )

        captured["body"] = json.loads(
            request.content.decode(
                "utf-8"
            )
        )

        return httpx.Response(
            200,
            json={
                "results": []
            },
            request=request,
        )

    transport = httpx.MockTransport(
        handler
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        provider = TavilySearchProvider(
            "secret-key",
            client=client,
        )

        await provider.search(
            "RAG",
            max_results=3,
        )

    assert captured["method"] == (
        "POST"
    )

    assert captured["url"] == (
        "https://api.tavily.com/search"
    )

    assert captured[
        "authorization"
    ] == "Bearer secret-key"

    assert captured["body"]["query"] == (
        "RAG"
    )

    assert (
        captured["body"]["max_results"]
        == 3
    )

    assert (
        captured["body"]["search_depth"]
        == "basic"
    )


@pytest.mark.asyncio
async def test_tavily_strips_query():
    captured = {}

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:

        captured["body"] = json.loads(
            request.content.decode(
                "utf-8"
            )
        )

        return httpx.Response(
            200,
            json={
                "results": []
            },
            request=request,
        )

    transport = httpx.MockTransport(
        handler
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        provider = TavilySearchProvider(
            "test-key",
            client=client,
        )

        await provider.search(
            "   What is RAG?   "
        )

    assert captured["body"]["query"] == (
        "What is RAG?"
    )


@pytest.mark.asyncio
async def test_tavily_rejects_empty_query():
    provider = TavilySearchProvider(
        "test-key"
    )

    with pytest.raises(
        ValueError,
        match="cannot be empty",
    ):
        await provider.search(
            "   "
        )


@pytest.mark.asyncio
async def test_tavily_rejects_invalid_response():
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "unexpected": []
            },
            request=request,
        )

    transport = httpx.MockTransport(
        handler
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        provider = TavilySearchProvider(
            "test-key",
            client=client,
        )

        with pytest.raises(
            TavilySearchError,
            match="results list",
        ):
            await provider.search(
                "RAG"
            )


@pytest.mark.asyncio
async def test_tavily_handles_http_error():
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "detail": "Unauthorized"
            },
            request=request,
        )

    transport = httpx.MockTransport(
        handler
    )

    async with httpx.AsyncClient(
        transport=transport
    ) as client:
        provider = TavilySearchProvider(
            "bad-key",
            client=client,
        )

        with pytest.raises(
            TavilySearchError,
            match="HTTP 401",
        ):
            await provider.search(
                "RAG"
            )
"""Offline webpage evidence extraction tests."""

import httpx
import pytest

from agents.research.schemas import Source
from agents.research.search import SearchHit
import agents.research.web_evidence as module
from agents.research.web_evidence import WebpageEvidenceExtractor


def setup(
    monkeypatch,
    responses,
    urls=("https://example.com/rag",),
):
    async def allow(url):
        return True

    monkeypatch.setattr(
        module, "_is_public_url", allow
    )

    def handler(request):
        return responses[str(request.url)]

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )

    hits = [
        SearchHit(
            title="Source",
            url=url,
            rank=i,
            snippet=(
                f"RAG snippet evidence from source "
                f"number {i} with enough information"
            ),
        )
        for i, url in enumerate(urls, 1)
    ]

    sources = [
        Source(
            id=f"src_{i}",
            title="Source",
            url=url,
            retrieved_at=__import__(
                "datetime"
            ).datetime.now(
                __import__("datetime").timezone.utc
            ),
        )
        for i, url in enumerate(urls, 1)
    ]

    return (
        WebpageEvidenceExtractor(client),
        hits,
        sources,
        client,
    )


@pytest.mark.asyncio
async def test_extracts_relevant_html_paragraph(
    monkeypatch,
):
    url = "https://example.com/rag"
    html = (
        "<script>RAG evil script text ignored "
        "on purpose</script>"
        "<p>Retrieval augmented generation uses "
        "external documents to ground RAG answers.</p>"
    )

    ext, hits, sources, client = setup(
        monkeypatch,
        {
            url: httpx.Response(
                200,
                text=html,
                headers={"content-type": "text/html"},
            )
        },
    )

    try:
        result = await ext.extract(
            "How does RAG use external documents?",
            hits,
            sources,
        )
        assert result[0].source_id == "src_1"
        assert "external documents" in result[0].text
        assert "evil" not in result[0].text
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_falls_back_on_http_404(monkeypatch):
    url = "https://example.com/rag"
    ext, hits, sources, client = setup(
        monkeypatch,
        {url: httpx.Response(404)},
    )

    try:
        result = await ext.extract(
            "RAG", hits, sources
        )
        assert result[0].text == hits[0].snippet
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_pdf_response_falls_back_to_snippet(
    monkeypatch,
):
    url = "https://example.com/rag"
    ext, hits, sources, client = setup(
        monkeypatch,
        {
            url: httpx.Response(
                200,
                content=b"%PDF",
                headers={
                    "content-type": "application/pdf"
                },
            )
        },
    )

    try:
        result = await ext.extract(
            "RAG", hits, sources
        )
        assert result[0].text == hits[0].snippet
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_oversized_page_falls_back(
    monkeypatch,
):
    url = "https://example.com/rag"
    ext, hits, sources, client = setup(
        monkeypatch,
        {
            url: httpx.Response(
                200,
                content=(
                    b"a" * (module.MAX_PAGE_BYTES + 1)
                ),
                headers={
                    "content-type": "text/html"
                },
            )
        },
    )

    try:
        result = await ext.extract(
            "RAG", hits, sources
        )
        assert result[0].text == hits[0].snippet
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_page_and_snippet_preserve_source_ids(
    monkeypatch,
):
    one = "https://example.com/rag"
    two = "https://example.com/tuning"

    good = httpx.Response(
        200,
        text=(
            "<p>RAG can retrieve sources at "
            "generation time for more current "
            "information.</p>"
        ),
        headers={"content-type": "text/html"},
    )

    ext, hits, sources, client = setup(
        monkeypatch,
        {
            one: good,
            two: httpx.Response(500),
        },
        (one, two),
    )

    try:
        result = await ext.extract(
            "RAG and fine tuning",
            hits,
            sources,
        )
        assert [
            item.source_id for item in result
        ] == ["src_1", "src_2"]
        assert result[1].text == hits[1].snippet
        assert [
            item.id for item in result
        ] == ["evidence_1", "evidence_2"]
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_global_evidence_cap(monkeypatch):
    url = "https://example.com/rag"
    html = (
        "<p>RAG first passage explains retrieval "
        "and external documents for answers.</p>"
        "<p>RAG second passage explains ground "
        "truth and retrieval using data.</p>"
    )

    ext, hits, sources, client = setup(
        monkeypatch,
        {
            url: httpx.Response(
                200,
                text=html,
                headers={"content-type": "text/html"},
            )
        },
    )

    try:
        result = await ext.extract(
            "RAG retrieval",
            hits,
            sources,
            max_evidence=1,
        )
        assert len(result) == 1
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_blocks_loopback_and_private_targets():
    assert not await module._is_public_url(
        "http://127.0.0.1/private"
    )
    assert not await module._is_public_url(
        "http://169.254.169.254/latest/meta-data"
    )
    assert not await module._is_public_url(
        "http://localhost/private"
    )
    assert not await module._is_public_url(
        "file:///etc/passwd"
    )


@pytest.mark.asyncio
async def test_blocks_private_dns_resolution(
    monkeypatch,
):
    monkeypatch.setattr(
        module,
        "_public_addresses",
        lambda host, port: False,
    )
    assert not await module._is_public_url(
        "https://example.com/private"
    )


@pytest.mark.asyncio
async def test_validates_input(monkeypatch):
    url = "https://example.com/rag"
    ext, hits, sources, client = setup(
        monkeypatch,
        {url: httpx.Response(200)},
    )

    try:
        with pytest.raises(
            ValueError, match="empty"
        ):
            await ext.extract(
                " ", hits, sources
            )

        with pytest.raises(
            ValueError, match="between"
        ):
            await ext.extract(
                "RAG",
                hits,
                sources,
                max_evidence=0,
            )
    finally:
        await client.aclose()

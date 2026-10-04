from datetime import datetime, timezone

import pytest

from agents.research.search import SearchHit
from agents.research.sources import (
    normalize_url,
    publisher_from_url,
    search_hits_to_sources,
)


def make_hit(
    *,
    title: str = "Example",
    url: str = "https://example.com/rag",
    rank: int = 1,
) -> SearchHit:
    return SearchHit(
        title=title,
        url=url,
        snippet="Example snippet.",
        rank=rank,
    )


def test_normalize_url_removes_fragment():
    result = normalize_url(
        "https://example.com/rag#section"
    )

    assert result == (
        "https://example.com/rag"
    )


def test_normalize_url_removes_tracking_parameters():
    result = normalize_url(
        "https://example.com/rag"
        "?utm_source=test&x=1&gclid=123"
    )

    assert result == (
        "https://example.com/rag?x=1"
    )


def test_normalize_url_removes_trailing_slash():
    result = normalize_url(
        "https://example.com/rag/"
    )

    assert result == (
        "https://example.com/rag"
    )


def test_normalize_url_rejects_invalid_scheme():
    with pytest.raises(
        ValueError,
        match="HTTP and HTTPS",
    ):
        normalize_url(
            "ftp://example.com/file"
        )


def test_publisher_from_url():
    result = publisher_from_url(
        "https://www.example.com/rag"
    )

    assert result == "example.com"


def test_search_hits_to_sources():
    retrieved_at = datetime(
        2026,
        10,
        4,
        tzinfo=timezone.utc,
    )

    sources = search_hits_to_sources(
        [
            make_hit(
                title="First Result",
                url="https://example.com/one",
                rank=1,
            ),
            make_hit(
                title="Second Result",
                url="https://example.org/two",
                rank=2,
            ),
        ],
        retrieved_at=retrieved_at,
    )

    assert len(sources) == 2

    assert sources[0].id == "src_1"
    assert sources[1].id == "src_2"

    assert sources[0].title == (
        "First Result"
    )

    assert sources[0].publisher == (
        "example.com"
    )

    assert (
        sources[0].retrieved_at
        == retrieved_at
    )


def test_duplicate_urls_are_removed():
    sources = search_hits_to_sources(
        [
            make_hit(
                title="First",
                url=(
                    "https://example.com/rag"
                    "?utm_source=test"
                ),
                rank=1,
            ),
            make_hit(
                title="Duplicate",
                url=(
                    "https://example.com/rag"
                ),
                rank=2,
            ),
        ]
    )

    assert len(sources) == 1

    assert sources[0].title == "First"


def test_best_ranked_duplicate_is_preserved():
    sources = search_hits_to_sources(
        [
            make_hit(
                title="Lower Ranked",
                url="https://example.com/rag",
                rank=5,
            ),
            make_hit(
                title="Higher Ranked",
                url="https://example.com/rag/",
                rank=1,
            ),
        ]
    )

    assert len(sources) == 1

    assert sources[0].title == (
        "Higher Ranked"
    )

    assert sources[0].id == "src_1"
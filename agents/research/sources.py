from datetime import datetime, timezone
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)

from agents.research.schemas import Source
from agents.research.search import SearchHit


TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "msclkid",
}


def normalize_url(url: str) -> str:
    """
    Normalize a web URL so duplicate search results can
    be detected reliably.
    """

    url = url.strip()

    if not url:
        raise ValueError("URL cannot be empty.")

    parsed = urlsplit(url)

    if parsed.scheme.lower() not in {
        "http",
        "https",
    }:
        raise ValueError(
            "Only HTTP and HTTPS URLs are supported."
        )

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    if not netloc:
        raise ValueError(
            "URL must contain a hostname."
        )

    path = parsed.path or "/"

    if path != "/":
        path = path.rstrip("/")

    filtered_query = []

    for key, value in parse_qsl(
        parsed.query,
        keep_blank_values=True,
    ):
        lower_key = key.lower()

        if lower_key.startswith("utm_"):
            continue

        if lower_key in TRACKING_QUERY_KEYS:
            continue

        filtered_query.append(
            (
                key,
                value,
            )
        )

    filtered_query.sort()

    query = urlencode(
        filtered_query,
        doseq=True,
    )

    return urlunsplit(
        (
            scheme,
            netloc,
            path,
            query,
            "",
        )
    )


def publisher_from_url(
    url: str,
) -> str:
    """
    Produce a simple publisher name from the hostname.
    """

    hostname = urlsplit(
        url
    ).hostname

    if not hostname:
        return "unknown"

    hostname = hostname.lower()

    if hostname.startswith("www."):
        hostname = hostname[4:]

    return hostname


def search_hits_to_sources(
    hits: list[SearchHit],
    *,
    retrieved_at: datetime | None = None,
) -> list[Source]:
    """
    Convert provider-independent SearchHit objects into
    normalized Source objects.

    Duplicate URLs are removed while preserving the
    highest-ranked occurrence.
    """

    if retrieved_at is None:
        retrieved_at = datetime.now(
            timezone.utc
        )

    ordered_hits = sorted(
        hits,
        key=lambda hit: hit.rank,
    )

    unique_hits: list[
        tuple[SearchHit, str]
    ] = []

    seen_urls: set[str] = set()

    for hit in ordered_hits:
        normalized_url = normalize_url(
            hit.url
        )

        if normalized_url in seen_urls:
            continue

        seen_urls.add(
            normalized_url
        )

        unique_hits.append(
            (
                hit,
                normalized_url,
            )
        )

    sources: list[Source] = []

    for index, (
        hit,
        normalized_url,
    ) in enumerate(
        unique_hits,
        start=1,
    ):
        source = Source(
            id=f"src_{index}",
            title=hit.title.strip(),
            url=normalized_url,
            publisher=publisher_from_url(
                normalized_url
            ),
            published_at=(
                hit.published_at
            ),
            retrieved_at=retrieved_at,
            source_type="web",
        )

        sources.append(
            source
        )

    return sources
"""Bounded webpage extraction with snippet fallback."""

import asyncio
import ipaddress
import logging
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx

from agents.research.evidence import SnippetEvidenceExtractor
from agents.research.schemas import Evidence, Source
from agents.research.search import SearchHit

logger = logging.getLogger(__name__)

MAX_PAGE_BYTES = 500_000
MAX_WEBPAGES = 3
MAX_PASSAGES_PER_PAGE = 2

IGNORED_TAGS = {
    "script", "style", "nav", "footer",
    "header", "noscript", "svg", "form",
}
PASSAGE_TAGS = {
    "p", "li", "blockquote", "h1", "h2", "h3",
}
STOP_WORDS = {
    "the", "and", "for", "are", "was", "what",
    "why", "how", "with", "from", "this",
    "that", "into", "between", "does",
    "about", "their", "which",
}


def _normalize_text(value: str) -> str:
    return " ".join(value.split())


class _HTMLPassages(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.passages: list[str] = []
        self._ignored = 0
        self._tag: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in IGNORED_TAGS:
            self._ignored += 1
        elif (
            not self._ignored
            and tag in PASSAGE_TAGS
            and self._tag is None
        ):
            self._tag = tag
            self._parts = []

    def handle_endtag(self, tag):
        if tag in IGNORED_TAGS:
            self._ignored = max(0, self._ignored - 1)
        elif not self._ignored and tag == self._tag:
            passage = _normalize_text(
                " ".join(self._parts)
            )
            if len(passage) >= 40:
                self.passages.append(passage[:800])
            self._tag = None
            self._parts = []

    def handle_data(self, data):
        if not self._ignored and self._tag is not None:
            self._parts.append(data)


def _public_addresses(host: str, port: int) -> bool:
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            results = socket.getaddrinfo(
                host,
                port,
                type=socket.SOCK_STREAM,
            )
            addresses = [
                ipaddress.ip_address(result[4][0])
                for result in results
            ]
        except (OSError, ValueError):
            return False

    return bool(addresses) and all(
        address.is_global for address in addresses
    )


async def _is_public_url(url: str) -> bool:
    try:
        parts = urlsplit(url)

        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
        ):
            return False

        if (
            parts.username is not None
            or parts.password is not None
        ):
            return False

        standard_port = (
            443 if parts.scheme == "https" else 80
        )
        port = parts.port or standard_port

        if port != standard_port:
            return False

        host = parts.hostname.lower().rstrip(".")

        if (
            host == "localhost"
            or host.endswith(
                (".localhost", ".local", ".internal")
            )
        ):
            return False

        return await asyncio.to_thread(
            _public_addresses,
            host,
            port,
        )
    except (ValueError, OSError):
        return False


def _passages(
    body: str,
    content_type: str,
) -> list[str]:
    if "text/plain" in content_type:
        return [
            text
            for line in body.splitlines()
            if len(
                text := _normalize_text(line)
            ) >= 40
        ]

    parser = _HTMLPassages()
    parser.feed(body)
    parser.close()

    return parser.passages


def _ranked(
    query: str,
    passages: list[str],
) -> list[tuple[str, float]]:
    query_words = {
        word
        for word in re.findall(
            r"[a-z0-9]+", query.lower()
        )
        if len(word) > 2 and word not in STOP_WORDS
    }

    scored = []
    seen = set()

    for index, passage in enumerate(passages):
        key = passage.casefold()

        if key in seen:
            continue

        seen.add(key)

        overlap = len(
            query_words
            & set(
                re.findall(
                    r"[a-z0-9]+",
                    passage.lower(),
                )
            )
        )

        if query_words and overlap == 0:
            continue

        score = min(
            1.0,
            overlap / max(1, len(query_words)),
        )

        scored.append(
            (
                overlap,
                index,
                passage,
                round(score, 4),
            )
        )

    scored.sort(
        key=lambda item: (-item[0], item[1])
    )

    return [
        (passage, score)
        for _, _, passage, score
        in scored[:MAX_PASSAGES_PER_PAGE]
    ]


class WebpageEvidenceExtractor:
    """Fetch public webpages with snippet fallback."""

    name = "webpage-with-snippet-fallback"

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
    ):
        self._client = client
        self._snippets = SnippetEvidenceExtractor()

    async def _fetch_passages(
        self,
        client: httpx.AsyncClient,
        url: str,
        query: str,
    ) -> list[tuple[str, float]]:
        if not await _is_public_url(url):
            return []

        try:
            async with client.stream(
                "GET",
                url,
                follow_redirects=False,
            ) as response:
                response.raise_for_status()

                content_type = response.headers.get(
                    "content-type", ""
                ).lower()

                supported = (
                    "text/html",
                    "text/plain",
                    "application/xhtml+xml",
                )

                if not any(
                    kind in content_type
                    for kind in supported
                ):
                    return []

                raw = bytearray()

                async for chunk in response.aiter_bytes():
                    if (
                        len(raw) + len(chunk)
                        > MAX_PAGE_BYTES
                    ):
                        return []

                    raw.extend(chunk)

                try:
                    body = raw.decode(
                        response.encoding or "utf-8",
                        errors="replace",
                    )
                except LookupError:
                    return []

                return _ranked(
                    query,
                    _passages(body, content_type),
                )

        except (
            httpx.HTTPError,
            ValueError,
            UnicodeError,
        ) as error:
            logger.info(
                "Webpage fetch unavailable for %s: %s",
                urlsplit(url).hostname,
                type(error).__name__,
            )
            return []

    async def _extract_with_client(
        self,
        client: httpx.AsyncClient,
        query: str,
        hits: list[SearchHit],
        sources: list[Source],
        max_evidence: int,
    ) -> list[Evidence]:
        fallback = await self._snippets.extract(
            query,
            hits,
            sources,
            max_evidence=max_evidence,
        )

        fallback_by_source = {
            item.source_id: item
            for item in fallback
        }

        evidence: list[Evidence] = []

        for index, source in enumerate(sources):
            passages = []

            if index < MAX_WEBPAGES:
                passages = await self._fetch_passages(
                    client,
                    source.url,
                    query,
                )

            if passages:
                for text, score in passages:
                    evidence.append(
                        Evidence(
                            id=(
                                f"evidence_"
                                f"{len(evidence) + 1}"
                            ),
                            source_id=source.id,
                            text=text,
                            relevance_score=score,
                        )
                    )

                    if len(evidence) >= max_evidence:
                        return evidence

            elif source.id in fallback_by_source:
                item = fallback_by_source[source.id]

                evidence.append(
                    Evidence(
                        id=(
                            f"evidence_"
                            f"{len(evidence) + 1}"
                        ),
                        source_id=source.id,
                        text=item.text,
                        relevance_score=item.relevance_score,
                    )
                )

                if len(evidence) >= max_evidence:
                    return evidence

        return evidence

    async def extract(
        self,
        query: str,
        hits: list[SearchHit],
        sources: list[Source],
        *,
        max_evidence: int = 10,
    ) -> list[Evidence]:
        if not query.strip():
            raise ValueError(
                "Evidence query cannot be empty."
            )

        if not 1 <= max_evidence <= 50:
            raise ValueError(
                "max_evidence must be between 1 and 50."
            )

        if self._client is not None:
            return await self._extract_with_client(
                self._client,
                query,
                hits,
                sources,
                max_evidence,
            )

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(6.0),
            trust_env=False,
            follow_redirects=False,
            headers={
                "User-Agent": "A2A-Research-Agent/0.1"
            },
        ) as client:
            return await self._extract_with_client(
                client,
                query,
                hits,
                sources,
                max_evidence,
            )

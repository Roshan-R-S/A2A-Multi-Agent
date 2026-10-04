from typing import Protocol, runtime_checkable

from agents.research.schemas import (
    Evidence,
    Source,
)
from agents.research.search import SearchHit
from agents.research.sources import normalize_url


@runtime_checkable
class EvidenceExtractor(Protocol):
    """
    Contract for evidence extraction implementations.
    """

    name: str

    async def extract(
        self,
        query: str,
        hits: list[SearchHit],
        sources: list[Source],
        *,
        max_evidence: int = 10,
    ) -> list[Evidence]:
        ...


class SnippetEvidenceExtractor:
    """
    Extract evidence from search-result snippets.

    This is our first evidence extractor.

    Later it can be replaced by an extractor that reads
    complete web pages, PDFs, documentation, or RAG chunks.
    """

    name = "search-snippet"

    async def extract(
        self,
        query: str,
        hits: list[SearchHit],
        sources: list[Source],
        *,
        max_evidence: int = 10,
    ) -> list[Evidence]:
        query = query.strip()

        if not query:
            raise ValueError(
                "Evidence query cannot be empty."
            )

        if not 1 <= max_evidence <= 50:
            raise ValueError(
                "max_evidence must be between 1 and 50."
            )

        source_by_url = {
            normalize_url(source.url): source
            for source in sources
        }

        ordered_hits = sorted(
            hits,
            key=lambda hit: hit.rank,
        )

        evidence_items: list[Evidence] = []

        seen: set[
            tuple[str, str]
        ] = set()

        for hit in ordered_hits:
            snippet = " ".join(
                hit.snippet.split()
            )

            if not snippet:
                continue

            normalized_url = normalize_url(
                hit.url
            )

            source = source_by_url.get(
                normalized_url
            )

            if source is None:
                continue

            duplicate_key = (
                source.id,
                snippet.casefold(),
            )

            if duplicate_key in seen:
                continue

            seen.add(
                duplicate_key
            )

            relevance_score = round(
                1.0 / hit.rank,
                4,
            )

            evidence_items.append(
                Evidence(
                    id=(
                        f"evidence_"
                        f"{len(evidence_items) + 1}"
                    ),
                    source_id=source.id,
                    text=snippet,
                    relevance_score=relevance_score,
                )
            )

            if (
                len(evidence_items)
                >= max_evidence
            ):
                break

        return evidence_items
from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class SearchHit(BaseModel):
    """
    A single raw result returned by a search provider.

    This is intentionally provider-independent.
    """

    title: str = Field(
        min_length=1,
    )

    url: str = Field(
        min_length=1,
    )

    snippet: str = ""

    rank: int = Field(
        ge=1,
    )

    published_at: datetime | None = None


@runtime_checkable
class SearchProvider(Protocol):
    """
    Contract that every search provider must implement.
    """

    name: str

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[SearchHit]:
        ...


class SearchService:
    """
    High-level search service used by the Research Agent.

    The Research Agent talks to this service rather than
    directly talking to a specific search API.
    """

    def __init__(
        self,
        provider: SearchProvider,
    ) -> None:
        self.provider = provider

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> list[SearchHit]:
        query = query.strip()

        if not query:
            raise ValueError(
                "Search query cannot be empty."
            )

        if not 1 <= max_results <= 20:
            raise ValueError(
                "max_results must be between 1 and 20."
            )

        results = await self.provider.search(
            query,
            max_results=max_results,
        )

        if not isinstance(results, list):
            raise TypeError(
                "Search provider must return a list."
            )

        for result in results:
            if not isinstance(
                result,
                SearchHit,
            ):
                raise TypeError(
                    "Search provider returned an "
                    "invalid search result."
                )

        return results[:max_results]
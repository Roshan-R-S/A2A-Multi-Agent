from datetime import datetime

import httpx

from agents.research.search import (
    SearchHit,
)


class TavilySearchError(RuntimeError):
    """Raised when Tavily search fails."""


class TavilySearchProvider:
    """
    Tavily implementation of our SearchProvider protocol.

    The rest of the Research system does not depend directly
    on Tavily. It only depends on the SearchProvider contract.
    """

    name = "tavily"

    endpoint = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str,
        *,
        timeout_seconds: float = 20.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        api_key = api_key.strip()

        if not api_key:
            raise ValueError(
                "Tavily API key cannot be empty."
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._client = client

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

        payload = {
            "query": query,
            "search_depth": "basic",
            "topic": "general",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }

        headers = {
            "Authorization": (
                f"Bearer {self.api_key}"
            ),
            "Content-Type": "application/json",
        }

        owns_client = self._client is None

        client = (
            self._client
            or httpx.AsyncClient(
                timeout=self.timeout_seconds
            )
        )

        try:
            response = await client.post(
                self.endpoint,
                json=payload,
                headers=headers,
            )

            response.raise_for_status()

            try:
                data = response.json()

            except ValueError as exc:
                raise TavilySearchError(
                    "Tavily returned invalid JSON."
                ) from exc

        except httpx.TimeoutException as exc:
            raise TavilySearchError(
                "Tavily search timed out."
            ) from exc

        except httpx.HTTPStatusError as exc:
            raise TavilySearchError(
                "Tavily search failed with "
                f"HTTP {exc.response.status_code}."
            ) from exc

        except httpx.RequestError as exc:
            raise TavilySearchError(
                "Could not connect to Tavily."
            ) from exc

        finally:
            if owns_client:
                await client.aclose()

        raw_results = data.get(
            "results"
        )

        if not isinstance(
            raw_results,
            list,
        ):
            raise TavilySearchError(
                "Tavily response does not contain "
                "a valid results list."
            )

        hits: list[SearchHit] = []

        for raw_result in raw_results:
            if not isinstance(
                raw_result,
                dict,
            ):
                continue

            title = str(
                raw_result.get(
                    "title",
                    "",
                )
            ).strip()

            url = str(
                raw_result.get(
                    "url",
                    "",
                )
            ).strip()

            if not title or not url:
                continue

            snippet = str(
                raw_result.get(
                    "content",
                    "",
                )
            ).strip()

            published_at = (
                self._parse_datetime(
                    raw_result.get(
                        "published_date"
                    )
                    or raw_result.get(
                        "published_at"
                    )
                )
            )

            hits.append(
                SearchHit(
                    title=title,
                    url=url,
                    snippet=snippet,
                    rank=len(hits) + 1,
                    published_at=published_at,
                )
            )

            if (
                len(hits)
                >= max_results
            ):
                break

        return hits

    @staticmethod
    def _parse_datetime(
        value,
    ) -> datetime | None:
        if not value:
            return None

        if isinstance(
            value,
            datetime,
        ):
            return value

        if not isinstance(
            value,
            str,
        ):
            return None

        value = value.strip()

        if not value:
            return None

        try:
            if value.endswith("Z"):
                value = (
                    value[:-1]
                    + "+00:00"
                )

            return datetime.fromisoformat(
                value
            )

        except ValueError:
            return None
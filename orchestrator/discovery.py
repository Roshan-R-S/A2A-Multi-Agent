from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class DiscoveredAgent:
    name: str
    description: str
    version: str
    url: str
    protocol_binding: str
    protocol_version: str
    skills: tuple[str, ...]


class AgentDiscoveryError(RuntimeError):
    """Raised when an A2A agent cannot be discovered."""


async def discover_agent(
    base_url: str,
    timeout_seconds: float = 10.0,
    *,
    client: httpx.AsyncClient | None = None,
) -> DiscoveredAgent:
    """
    Discover an A2A agent through its standard Agent Card.

    A custom HTTPX client can be supplied for testing.
    """

    card_url = (
        base_url.rstrip("/")
        + "/.well-known/agent-card.json"
    )

    owns_client = client is None

    if client is None:
        client = httpx.AsyncClient(
            timeout=timeout_seconds,
        )

    try:
        response = await client.get(card_url)
        response.raise_for_status()

        card = response.json()

        interfaces = card.get(
            "supportedInterfaces",
            [],
        )

        if not interfaces:
            raise AgentDiscoveryError(
                f"Agent {base_url} advertised no interfaces."
            )

        interface = interfaces[0]

        skills = tuple(
            skill.get("id", "unknown")
            for skill in card.get("skills", [])
        )

        return DiscoveredAgent(
            name=card["name"],
            description=card.get(
                "description",
                "",
            ),
            version=card.get(
                "version",
                "unknown",
            ),
            url=interface["url"],
            protocol_binding=interface.get(
                "protocolBinding",
                "unknown",
            ),
            protocol_version=interface.get(
                "protocolVersion",
                "unknown",
            ),
            skills=skills,
        )

    except httpx.ConnectError as exc:
        raise AgentDiscoveryError(
            f"Could not connect to agent at {base_url}"
        ) from exc

    except httpx.TimeoutException as exc:
        raise AgentDiscoveryError(
            f"Agent discovery timed out: {base_url}"
        ) from exc

    except httpx.HTTPStatusError as exc:
        raise AgentDiscoveryError(
            f"Agent Card request failed with "
            f"HTTP {exc.response.status_code}: {card_url}"
        ) from exc

    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise AgentDiscoveryError(
            f"Invalid Agent Card returned by {base_url}"
        ) from exc

    finally:
        if owns_client:
            await client.aclose()

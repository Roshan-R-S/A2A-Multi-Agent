import uuid

import httpx

from a2a.client import ClientConfig, create_client
from a2a.helpers import get_artifact_text, get_message_text
from a2a.types import (
    Message,
    Part,
    Role,
    SendMessageRequest,
)


class A2AAgentClient:
    """Reusable client for communicating with A2A agents."""

    def __init__(
        self,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.timeout_seconds = timeout_seconds

    async def send_text(
        self,
        agent_url: str,
        text: str,
    ) -> str:
        if not text or not text.strip():
            raise ValueError("Message text cannot be empty.")

        timeout = httpx.Timeout(
            connect=10.0,
            read=self.timeout_seconds,
            write=30.0,
            pool=10.0,
        )

        http_client = httpx.AsyncClient(
            timeout=timeout,
        )

        config = ClientConfig(
            streaming=True,
            supported_protocol_bindings=["JSONRPC"],
            httpx_client=http_client,
        )

        client = None

        try:
            client = await create_client(
                agent_url,
                client_config=config,
            )

            message = Message(
                role=Role.ROLE_USER,
                message_id=str(uuid.uuid4()),
                parts=[
                    Part(text=text.strip()),
                ],
            )

            request = SendMessageRequest(
                message=message,
            )

            artifact_parts: list[str] = []
            message_parts: list[str] = []

            stream = client.send_message(request)

            async for event in stream:
                if event.HasField("artifact_update"):
                    artifact_text = get_artifact_text(
                        event.artifact_update.artifact,
                        delimiter="\n",
                    )

                    if artifact_text:
                        artifact_parts.append(
                            artifact_text
                        )

                elif event.HasField("message"):
                    message_text = get_message_text(
                        event.message,
                        delimiter="\n",
                    )

                    if message_text:
                        message_parts.append(
                            message_text
                        )

            result_parts = artifact_parts or message_parts

            if not result_parts:
                raise RuntimeError(
                    "The agent completed without returning text."
                )

            return "\n".join(
                result_parts
            ).strip()

        finally:
            if client is not None:
                await client.close()
            else:
                await http_client.aclose()

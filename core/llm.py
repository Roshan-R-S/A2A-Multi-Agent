"""Shared Groq client with bounded automatic retries."""

import asyncio
import logging
import math
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from groq import APIConnectionError, APIStatusError, AsyncGroq

from core.config import settings


logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 60.0

_client = AsyncGroq(
    api_key=settings.groq_api_key,
    max_retries=0,
)


async def _sleep(seconds: float) -> None:
    await asyncio.sleep(seconds)


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, APIConnectionError):
        return True

    if isinstance(error, APIStatusError):
        return (
            error.status_code in (408, 409, 429)
            or error.status_code >= 500
        )

    return False


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None

    value = value.strip()

    try:
        seconds = float(value)
    except ValueError:
        try:
            deadline = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            return None

        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        seconds = (
            deadline - datetime.now(timezone.utc)
        ).total_seconds()

    return max(seconds, 0.0) if math.isfinite(seconds) else None


def _server_wait_seconds(error: Exception) -> float | None:
    if isinstance(error, APIStatusError):
        retry_after = _parse_retry_after(
            error.response.headers.get("retry-after")
        )

        if retry_after is not None:
            return retry_after

    match = re.search(
        r"please\s+try\s+again\s+in\s+"
        r"(\d+(?:\.\d+)?)\s*(ms|s|seconds?|m|minutes?)\b",
        str(error),
        flags=re.IGNORECASE,
    )

    if match is None:
        return None

    amount = float(match.group(1))
    unit = match.group(2).lower()

    if unit == "ms":
        return amount / 1000.0

    if unit.startswith("m"):
        return amount * 60.0

    return amount


def _retry_delay(error: Exception, retry_number: int) -> float:
    backoff = (
        BASE_RETRY_DELAY_SECONDS
        * (2 ** (retry_number - 1))
    )

    server_wait = _server_wait_seconds(error)

    if server_wait is not None:
        backoff = max(backoff, server_wait)

    return min(backoff, MAX_RETRY_DELAY_SECONDS)


async def generate_text(
    prompt: str,
    system_prompt: str = "You are a helpful AI assistant.",
    temperature: float = 0.2,
) -> str:
    """Generate text, retrying transient Groq failures."""

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await _client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=temperature,
            )

        except (APIConnectionError, APIStatusError) as error:
            if not _is_retryable(error):
                raise

            if attempt >= MAX_RETRIES:
                logger.error(
                    "Groq request failed after %d attempts.",
                    MAX_RETRIES + 1,
                )
                raise

            retry_number = attempt + 1
            delay = _retry_delay(error, retry_number)

            reason = (
                f"HTTP {error.status_code}"
                if isinstance(error, APIStatusError)
                else type(error).__name__
            )

            logger.warning(
                "Groq request failed (%s); retry %d/%d in %.2fs.",
                reason,
                retry_number,
                MAX_RETRIES,
                delay,
            )

            await _sleep(delay)
            continue

        content = response.choices[0].message.content

        if not content or not content.strip():
            raise RuntimeError(
                "Groq returned an empty response."
            )

        return content.strip()

    raise RuntimeError(
        "Groq retry loop ended unexpectedly."
    )

"""Offline tests of the shared Groq retry policy (zero API tokens)."""

import logging
from types import SimpleNamespace

import httpx
import pytest
from groq import APIConnectionError, APIStatusError, RateLimitError

import core.llm as llm


def _status_error(
    status: int,
    *,
    retry_after: str | None = None,
    message: str = "temporary failure",
) -> APIStatusError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(
        status,
        request=request,
        headers={"retry-after": retry_after} if retry_after else {},
    )
    cls = RateLimitError if status == 429 else APIStatusError
    return cls(message, response=response, body=None)


def _fake_client(monkeypatch, scripted):
    calls = []
    scripted = iter(scripted)

    async def create(**kwargs):
        calls.append(kwargs)
        result = next(scripted)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=result))]
        )

    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    monkeypatch.setattr(llm, "_client", fake)
    return calls


def _fake_sleep(monkeypatch):
    delays = []

    async def sleep(seconds):
        delays.append(seconds)

    monkeypatch.setattr(llm, "_sleep", sleep)
    return delays


@pytest.mark.asyncio
async def test_success_returns_stripped_text_without_retries(monkeypatch):
    calls = _fake_client(monkeypatch, ["  The answer.  "])
    delays = _fake_sleep(monkeypatch)

    result = await llm.generate_text("A question", temperature=0.1)

    assert result == "The answer."
    assert len(calls) == 1
    assert calls[0]["temperature"] == 0.1
    assert calls[0]["messages"][1]["content"] == "A question"
    assert delays == []


@pytest.mark.asyncio
async def test_429_respects_retry_after_header(monkeypatch, caplog):
    calls = _fake_client(
        monkeypatch,
        [_status_error(429, retry_after="1.515"), "Cited. [src_1]"],
    )
    delays = _fake_sleep(monkeypatch)

    with caplog.at_level(logging.WARNING):
        result = await llm.generate_text("question")

    assert result == "Cited. [src_1]"
    assert len(calls) == 2
    assert delays == [pytest.approx(1.515)]
    assert "HTTP 429" in caplog.text
    assert "retry 1/3" in caplog.text


@pytest.mark.asyncio
async def test_429_reads_groq_wait_hint_when_header_missing(monkeypatch):
    _fake_client(
        monkeypatch,
        [_status_error(429, message="Please try again in 2.5s."), "OK"],
    )
    delays = _fake_sleep(monkeypatch)

    assert await llm.generate_text("question") == "OK"
    assert delays == [pytest.approx(2.5)]


@pytest.mark.asyncio
async def test_server_error_uses_exponential_backoff(monkeypatch):
    calls = _fake_client(
        monkeypatch,
        [_status_error(503), _status_error(502), "Recovered"],
    )
    delays = _fake_sleep(monkeypatch)

    assert await llm.generate_text("question") == "Recovered"
    assert delays == [1.0, 2.0]
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_connection_error_is_retryable(monkeypatch):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    calls = _fake_client(
        monkeypatch,
        [APIConnectionError(request=request), "Connected"],
    )
    delays = _fake_sleep(monkeypatch)

    assert await llm.generate_text("question") == "Connected"
    assert len(calls) == 2
    assert delays == [1.0]


@pytest.mark.asyncio
async def test_authentication_error_is_not_retried(monkeypatch):
    calls = _fake_client(monkeypatch, [_status_error(401)])
    delays = _fake_sleep(monkeypatch)

    with pytest.raises(APIStatusError) as caught:
        await llm.generate_text("question")

    assert caught.value.status_code == 401
    assert len(calls) == 1
    assert delays == []


@pytest.mark.asyncio
async def test_retries_stop_after_bounded_attempts(monkeypatch, caplog):
    errors = [_status_error(429) for _ in range(llm.MAX_RETRIES + 1)]
    calls = _fake_client(monkeypatch, errors)
    delays = _fake_sleep(monkeypatch)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(APIStatusError) as caught:
            await llm.generate_text("question")

    assert caught.value.status_code == 429
    assert len(calls) == 4
    assert delays == [1.0, 2.0, 4.0]
    assert "failed after 4 attempts" in caplog.text


@pytest.mark.asyncio
async def test_empty_completion_is_not_retried(monkeypatch):
    calls = _fake_client(monkeypatch, ["  "])
    delays = _fake_sleep(monkeypatch)

    with pytest.raises(RuntimeError, match="empty response"):
        await llm.generate_text("question")

    assert len(calls) == 1
    assert delays == []


def test_backoff_is_capped_and_handles_invalid_server_wait():
    assert llm._retry_delay(_status_error(429, retry_after="garbage"), 7) == 60.0
    assert llm._parse_retry_after("NaN") is None
    assert llm._parse_retry_after("-2") == 0.0
    assert llm._server_wait_seconds(
        _status_error(429, message="Please try again in 750ms.")
    ) == pytest.approx(0.75)


@pytest.mark.asyncio
async def test_structured_generation_options_are_opt_in(monkeypatch):
    calls = _fake_client(monkeypatch, ['{"verdict":"PASS"}', "Text answer"])
    await llm.generate_text(
        "Verify these claims",
        response_format={"type": "json_object"},
        reasoning_effort="low",
        max_completion_tokens=1200,
    )
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert calls[0]["reasoning_effort"] == "low"
    assert calls[0]["max_completion_tokens"] == 1200
    assert await llm.generate_text("Normal question") == "Text answer"
    assert "response_format" not in calls[1]
    assert "reasoning_effort" not in calls[1]
    assert "max_completion_tokens" not in calls[1]


@pytest.mark.asyncio
async def test_invalid_completion_budget_fails_before_provider(monkeypatch):
    calls = _fake_client(monkeypatch, [])
    with pytest.raises(ValueError, match="must be positive"):
        await llm.generate_text("prompt", max_completion_tokens=0)
    assert calls == []

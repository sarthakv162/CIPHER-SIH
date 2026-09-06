"""Async OpenAI-compatible HTTP client for one llama-server (or stub) endpoint."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any

import httpx

from rupantar.core.errors import ModelClientError

_RESET_ERRORS = (
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    httpx.ReadError,
    ConnectionResetError,
)
_PATH = "/v1/chat/completions"


class LlamaClient:
    """Talks `/v1/chat/completions` to a leased model endpoint, with GBNF grammar passthrough."""

    def __init__(
        self,
        endpoint: str,
        *,
        connect_timeout: float = 10.0,
        read_timeout: float = 300.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Bind to `endpoint`; pass `client` only to inject a fake transport in tests."""
        self._owns = client is None
        self._client = client or httpx.AsyncClient(
            base_url=endpoint.rstrip("/"),
            timeout=httpx.Timeout(read_timeout, connect=connect_timeout),
        )

    async def __aenter__(self) -> LlamaClient:
        """Enter as an async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the underlying client on context exit."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying httpx client if this instance owns it."""
        if self._owns:
            await self._client.aclose()

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        grammar: str | None = None,
        max_tokens: int,
        temperature: float,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """POST one chat completion and return `choices[0].message.content`."""
        body = self._body(messages, grammar, max_tokens, temperature, extra, stream=False)
        for attempt in range(2):
            try:
                response = await self._client.post(_PATH, json=body)
            except _RESET_ERRORS:
                if attempt == 1:
                    raise
                continue
            return self._content(response)
        raise AssertionError("unreachable")

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        grammar: str | None = None,
        max_tokens: int,
        temperature: float,
        extra: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """POST a streaming chat completion, yielding content deltas as they arrive."""
        body = self._body(messages, grammar, max_tokens, temperature, extra, stream=True)
        for attempt in range(2):
            produced = False
            try:
                async with self._client.stream("POST", _PATH, json=body) as response:
                    if response.status_code >= 400:
                        text = (await response.aread()).decode("utf-8", "replace")
                        raise ModelClientError(
                            _http_message(response.status_code, text),
                            status=response.status_code,
                            body=text[:500],
                        )
                    async for line in response.aiter_lines():
                        delta = _sse_delta(line)
                        if delta:
                            produced = True
                            yield delta
                return
            except _RESET_ERRORS:
                if attempt == 1 or produced:
                    raise

    def _body(
        self,
        messages: list[dict[str, str]],
        grammar: str | None,
        max_tokens: int,
        temperature: float,
        extra: dict[str, Any] | None,
        *,
        stream: bool,
    ) -> dict[str, Any]:
        """Assemble the chat-completions request body."""
        payload: dict[str, Any] = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if grammar is not None:
            payload["grammar"] = grammar
        if extra:
            payload.update(extra)
        return payload

    def _content(self, response: httpx.Response) -> str:
        """Extract the assistant message content, raising ModelClientError on HTTP error."""
        if response.status_code >= 400:
            raise ModelClientError(
                _http_message(response.status_code, response.text),
                status=response.status_code,
                body=response.text[:500],
            )
        data = response.json()
        return str(data["choices"][0]["message"]["content"])


def _http_message(status: int, body: str) -> str:
    """Human-readable message for a non-2xx response from the model endpoint."""
    return (
        f"model endpoint returned HTTP {status} for {_PATH}; body: {body[:500]!r}. "
        "Check the llama-server log and the request parameters."
    )


def _sse_delta(line: str) -> str | None:
    """Return the content delta carried by one `data:` SSE line, or None."""
    if not line.startswith("data:"):
        return None
    payload = line[len("data:") :].strip()
    if not payload or payload == "[DONE]":
        return None
    try:
        obj = json.loads(payload)
    except json.JSONDecodeError:
        return None
    choices = obj.get("choices") or [{}]
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    return content if isinstance(content, str) else None

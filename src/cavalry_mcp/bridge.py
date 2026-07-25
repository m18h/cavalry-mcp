"""Async HTTP client for the cavalry-mcp bridge running inside Cavalry.

Protocol
--------
1. POST ``/post`` with ``{"id": <uuid>, "code": <javascript>}``.
2. The bridge evaluates the code (IIFE-wrapped, so snippets use ``return`` to
   send a value back) and publishes a JSON result via ``setResultForGet``.
3. We poll ``GET /get`` until the payload's ``id`` matches our request.

Requests are serialized with a lock: the bridge exposes only the *latest*
result, so only one request may be in flight at a time.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8722

ENV_HOST = "CAVALRY_BRIDGE_HOST"
ENV_PORT = "CAVALRY_BRIDGE_PORT"

HINT = (
    "Is Cavalry running with the cavalry-mcp bridge script open? "
    "(Scripts menu → cavalry-mcp-bridge.js — keep its window open)"
)


class BridgeError(Exception):
    """Base error for bridge communication failures."""


class BridgeUnavailableError(BridgeError):
    """The bridge is not reachable (Cavalry not running / script not open)."""


class ScriptError(BridgeError):
    """The script raised an exception inside Cavalry."""

    def __init__(self, message: str, *, stack: str = "", logs: list | None = None):
        super().__init__(message)
        self.stack = stack
        self.logs = logs or []

    def __str__(self) -> str:
        out = self.args[0]
        if self.stack:
            out += f"\n{self.stack}"
        return out


@dataclass
class BridgeResult:
    ok: bool
    value: Any = None
    logs: list[dict] = field(default_factory=list)
    error: dict | None = None

    def raise_for_error(self) -> None:
        if not self.ok:
            error = self.error or {}
            raise ScriptError(
                error.get("message", "Unknown script error"),
                stack=error.get("stack", ""),
                logs=self.logs,
            )


class CavalryBridge:
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        *,
        timeout: float = 30.0,
        poll_interval: float = 0.015,
    ):
        self.host = host or os.environ.get(ENV_HOST, DEFAULT_HOST)
        self.port = int(port or os.environ.get(ENV_PORT, DEFAULT_PORT))
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._client = httpx.AsyncClient(
            base_url=f"http://{self.host}:{self.port}",
            timeout=httpx.Timeout(10.0, connect=2.0),
        )
        self._lock = asyncio.Lock()

    async def close(self) -> None:
        await self._client.aclose()

    async def probe(self) -> dict | None:
        """Return the bridge's current /get payload (hello or last result), if reachable."""
        try:
            resp = await self._client.get("/get")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError):
            return None

    async def available(self) -> bool:
        return await self.probe() is not None

    async def execute(self, code: str, *, timeout: float | None = None) -> BridgeResult:
        """Run JavaScript inside Cavalry and return the structured result.

        The snippet is wrapped in an IIFE by the bridge; use ``return`` to send
        a JSON-serializable value back.
        """
        async with self._lock:
            request_id = uuid.uuid4().hex
            try:
                resp = await self._client.post(
                    "/post", json={"id": request_id, "code": code}
                )
                resp.raise_for_status()
            except httpx.ConnectError as exc:
                raise BridgeUnavailableError(
                    f"Cannot reach the cavalry-mcp bridge at "
                    f"{self.host}:{self.port}. {HINT}"
                ) from exc
            except httpx.HTTPError as exc:
                raise BridgeError(f"POST to bridge failed: {exc}") from exc

            deadline = time.monotonic() + (timeout if timeout is not None else self.timeout)
            while True:
                try:
                    get_resp = await self._client.get("/get")
                    get_resp.raise_for_status()
                    payload = get_resp.json()
                except (httpx.HTTPError, ValueError):
                    payload = None
                if (
                    isinstance(payload, dict)
                    and payload.get("type") == "result"
                    and payload.get("id") == request_id
                ):
                    return BridgeResult(
                        ok=bool(payload.get("ok")),
                        value=payload.get("value"),
                        logs=payload.get("logs") or [],
                        error=payload.get("error"),
                    )
                if time.monotonic() > deadline:
                    raise BridgeError(
                        f"Timed out waiting for Cavalry to return a result. {HINT}"
                    )
                await asyncio.sleep(self.poll_interval)

    async def execute_value(self, code: str, *, timeout: float | None = None) -> Any:
        """Like :meth:`execute` but raises ScriptError on failure and returns just the value."""
        result = await self.execute(code, timeout=timeout)
        result.raise_for_error()
        return result.value

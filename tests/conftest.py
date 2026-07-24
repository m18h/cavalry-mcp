from __future__ import annotations

import struct
import zlib
from collections.abc import Callable
from typing import Any

import pytest
from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent

from cavalry_mcp.bridge import ScriptError
from cavalry_mcp.tools import register_all


def png_1px() -> bytes:
    """Minimal valid 1x1 RGBA PNG."""

    def chunk(typ: bytes, data: bytes) -> bytes:
        out = struct.pack(">I", len(data)) + typ + data
        return out + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00\x00")
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", idat)
        + chunk(b"IEND", b"")
    )


class FakeBridge:
    """Records executed code and answers via a handler callable.

    The handler receives the JS code string and returns the value the tool
    should receive; raise ScriptError from the handler to simulate an
    in-Cavalry exception.
    """

    def __init__(self, handler: Callable[[str], Any] | None = None):
        self.executed: list[str] = []
        self.handler = handler or (lambda code: {"ok": True})
        self.host = "127.0.0.1"
        self.port = 8722

    async def probe(self):
        return {"type": "hello", "bridge": "cavalry-mcp", "bridgeVersion": "0.1.0"}

    async def execute_value(self, code: str, *, timeout: float | None = None):
        self.executed.append(code)
        return self.handler(code)

    async def execute(self, code: str, *, timeout: float | None = None):
        self.executed.append(code)
        from cavalry_mcp.bridge import BridgeResult

        try:
            value = self.handler(code)
        except ScriptError as exc:
            return BridgeResult(
                ok=False,
                logs=[],
                error={"message": exc.args[0], "stack": exc.stack},
            )
        return BridgeResult(ok=True, value=value, logs=[])


@pytest.fixture
def bridge(monkeypatch: pytest.MonkeyPatch) -> FakeBridge:
    fake = FakeBridge()
    for mod in ("meta", "scene", "layers", "attrs", "anim", "render"):
        monkeypatch.setattr(f"cavalry_mcp.tools.{mod}.get_bridge", lambda: fake)
    return fake


@pytest.fixture
def mcp() -> FastMCP:
    server = FastMCP("test-cavalry")
    register_all(server)
    return server


async def call_tool(mcp: FastMCP, name: str, args: dict) -> Any:
    """Call a tool. Returns the parsed JSON payload for data tools, or the raw
    list of content blocks (e.g. ImageContent) for media tools. Raises
    ToolError when the tool itself fails."""
    result = await mcp.call_tool(name, args)
    if (
        isinstance(result, list)
        and result
        and isinstance(result[0], TextContent)
        and result[0].text
    ):
        import json

        try:
            return json.loads(result[0].text)
        except json.JSONDecodeError:
            pass
    return result

"""Protocol tests for the Python side of the bridge (HTTP mocked)."""

from __future__ import annotations

import json

import httpx
import pytest

from cavalry_mcp.bridge import (
    BridgeError,
    BridgeUnavailableError,
    CavalryBridge,
    ScriptError,
)


def make_bridge(handler) -> CavalryBridge:
    bridge = CavalryBridge(timeout=0.5, poll_interval=0.005)
    bridge._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url=f"http://{bridge.host}:{bridge.port}",
    )
    return bridge


def ok_handler(state):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/post":
            body = json.loads(request.content)
            state["payload"] = {
                "type": "result",
                "id": body["id"],
                "ok": True,
                "value": {"frame": 24},
                "logs": [{"level": "log", "message": "hi"}],
                "error": None,
            }
            return httpx.Response(200, text="Success")
        if request.url.path == "/get":
            return httpx.Response(200, json=state.get("payload", {"type": "hello"}))
        return httpx.Response(404)

    return handler


async def test_execute_returns_result():
    bridge = make_bridge(ok_handler({}))
    result = await bridge.execute("return api.getFrame()")
    assert result.ok
    assert result.value == {"frame": 24}
    assert result.logs[0]["message"] == "hi"


async def test_execute_ignores_stale_payload_until_match():
    state = {"gets": 0, "posted_id": None}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/post":
            body = json.loads(request.content)
            state["posted_id"] = body["id"]
            return httpx.Response(200, text="Success")
        state["gets"] += 1
        if state["gets"] < 2:
            payload = {"type": "result", "id": "stale", "ok": True, "value": 1}
        else:
            payload = {
                "type": "result",
                "id": state["posted_id"],
                "ok": True,
                "value": 2,
            }
        return httpx.Response(200, json=payload)

    bridge = make_bridge(handler)
    result = await bridge.execute("return 2")
    assert result.value == 2
    assert state["gets"] >= 2


async def test_execute_value_raises_script_error():
    payload: dict = {"type": "hello"}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal payload
        if request.url.path == "/post":
            body = json.loads(request.content)
            payload = {
                "type": "result",
                "id": body["id"],
                "ok": False,
                "value": None,
                "logs": [],
                "error": {"message": "Layer not found: nope#1", "stack": "at eval:3"},
            }
            return httpx.Response(200, text="Success")
        return httpx.Response(200, json=payload)

    bridge = make_bridge(handler)
    with pytest.raises(ScriptError, match="Layer not found"):
        await bridge.execute_value("api.deleteLayer('nope#1')")


async def test_unavailable_raises_helpful_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    bridge = make_bridge(handler)
    with pytest.raises(BridgeUnavailableError, match="Scripts menu"):
        await bridge.execute("return 1")


async def test_timeout_when_result_never_arrives():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/post":
            return httpx.Response(200, text="Success")
        return httpx.Response(200, json={"type": "hello"})

    bridge = make_bridge(handler)
    with pytest.raises(BridgeError, match="Timed out"):
        await bridge.execute("return 1", timeout=0.05)

"""Tool tests: verify generated JS snippets and structured results."""

from __future__ import annotations

import re

import pytest
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ImageContent

from cavalry_mcp.bridge import ScriptError

from .conftest import FakeBridge, call_tool, png_1px


async def test_create_layer_with_name(mcp, bridge):
    bridge.handler = lambda code: {
        "id": "textShape#1",
        "niceName": "Hero",
        "type": "textShape",
    }
    result = await call_tool(
        mcp, "cavalry_create_layer", {"layer_type": "textShape", "name": "Hero"}
    )
    assert result["id"] == "textShape#1"
    code = bridge.executed[-1]
    assert 'api.create("textShape", "Hero")' in code


async def test_create_layer_without_name(mcp, bridge):
    await call_tool(mcp, "cavalry_create_layer", {"layer_type": "null"})
    code = bridge.executed[-1]
    assert "api.create(" in code
    assert '"null"' in code
    # No name argument when omitted
    assert 'api.create("null")' in code


async def test_set_attribute_json_encodes_value(mcp, bridge):
    await call_tool(
        mcp,
        "cavalry_set_attribute",
        {"layer_id": "basicShape#1", "attr_id": "fill.color", "value": "#ff8800"},
    )
    code = bridge.executed[-1]
    assert 'patch["fill.color"] = "#ff8800"' in code
    assert "api.set(id, patch)" in code


async def test_set_keyframes_batch(mcp, bridge):
    bridge.handler = lambda code: {"keyframeIds": ["keyframe#1", "keyframe#2"]}
    result = await call_tool(
        mcp,
        "cavalry_set_keyframes",
        {
            "layer_id": "basicShape#1",
            "attr_id": "position.x",
            "keys": [{"frame": 0, "value": 0}, {"frame": 24, "value": 200}],
        },
    )
    assert result["keyframeIds"] == ["keyframe#1", "keyframe#2"]
    code = bridge.executed[-1]
    assert '"frame": 0' in code and '"value": 200' in code
    assert "api.keyframe(" in code


async def test_magic_easing_passes_expression_only_when_given(mcp, bridge):
    await call_tool(
        mcp,
        "cavalry_magic_easing",
        {
            "layer_id": "basicShape#1",
            "attr_id": "position.x",
            "frame": 0,
            "easing": "BounceOut",
        },
    )
    code = bridge.executed[-1]
    assert '"BounceOut"' in code
    assert "args.push" in code  # expression appended conditionally in JS


async def test_connect_signature(mcp, bridge):
    await call_tool(
        mcp,
        "cavalry_connect",
        {
            "from_layer": "a#1",
            "from_attr": "position.y",
            "to_layer": "b#1",
            "to_attr": "position.y",
        },
    )
    code = bridge.executed[-1]
    assert '"a#1", "position.y"' in code
    assert '"b#1", "position.y"' in code
    assert "false" in code  # force default


async def test_list_layers_scope_and_filter(mcp, bridge):
    bridge.handler = lambda code: {"count": 0, "truncated": False, "layers": []}
    await call_tool(
        mcp,
        "cavalry_list_layers",
        {"top_level_only": True, "layer_type": "textShape"},
    )
    code = bridge.executed[-1]
    assert "api.getCompLayersOfType(topLevel, type)" in code
    assert "var topLevel = true" in code

    await call_tool(mcp, "cavalry_list_layers", {"scope": "scene"})
    assert "api.getAllSceneLayers()" in bridge.executed[-1]


async def test_run_script_returns_structured_error(mcp, bridge):
    def handler(code):
        raise ScriptError("boom", stack="at eval:1")

    bridge.handler = handler
    result = await call_tool(mcp, "cavalry_run_script", {"code": "nope()"})
    assert result["ok"] is False
    assert result["error"]["message"] == "boom"


async def test_tool_error_propagates(mcp, bridge):
    def handler(code):
        raise ScriptError("Layer not found: nope#9", stack="at eval:2")

    bridge.handler = handler
    with pytest.raises(ToolError, match="Layer not found"):
        await mcp.call_tool("cavalry_delete_layer", {"layer_id": "nope#9"})


def _png_writing_handler(code):
    match = re.search(r'api\.(?:renderPNGFrame|saveViewportContentsAsImage)\("([^"]+)"', code)
    if match:
        with open(match.group(1), "wb") as fh:
            fh.write(png_1px())
        return {"exists": True}
    return {"ok": True}


async def test_render_frame_returns_image(mcp, bridge):
    bridge.handler = _png_writing_handler
    content = await call_tool(mcp, "cavalry_render_frame_png", {"scale_percentage": 50})
    assert any(isinstance(block, ImageContent) for block in content)
    assert any("renderPNGFrame" in code for code in bridge.executed)


async def test_viewport_screenshot_returns_image(mcp, bridge):
    bridge.handler = _png_writing_handler
    content = await call_tool(mcp, "cavalry_viewport_screenshot", {})
    assert any(isinstance(block, ImageContent) for block in content)
    assert any("saveViewportContentsAsImage" in code for code in bridge.executed)


async def test_get_comp_info_defaults_to_active(mcp, bridge):
    bridge.handler = lambda code: {"comp": "comp#1", "settings": {}, "allAttributes": []}
    result = await call_tool(mcp, "cavalry_get_comp_info", {})
    assert result["comp"] == "comp#1"
    assert "api.getActiveComp()" in bridge.executed[-1]


async def test_status_raises_when_bridge_unreachable(mcp, monkeypatch):
    class DeadBridge(FakeBridge):
        async def probe(self):
            return None

    fake = DeadBridge()
    monkeypatch.setattr("cavalry_mcp.tools.meta.get_bridge", lambda: fake)
    with pytest.raises(ToolError, match="cavalry-mcp bridge"):
        await mcp.call_tool("cavalry_status", {})

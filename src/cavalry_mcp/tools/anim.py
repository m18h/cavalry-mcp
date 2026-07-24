"""Animation tools: keyframes, easing, playback."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..state import get_bridge


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def cavalry_set_keyframe(
        layer_id: str, attr_id: str, frame: int, value: Any
    ) -> dict:
        """Set a single keyframe on an attribute.

        Args:
            layer_id: Layer id, e.g. "basicShape#1".
            attr_id: Attribute path, e.g. "position.x".
            frame: Frame number.
            value: Keyframe value.
        """
        code = f"""
var patch = {{}}
patch[{json.dumps(attr_id)}] = {json.dumps(value)}
var kfId = api.keyframe({json.dumps(layer_id)}, {json.dumps(frame)}, patch)
return {{ keyframeId: kfId }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_set_keyframes(
        layer_id: str, attr_id: str, keys: list[dict]
    ) -> dict:
        """Set several keyframes on one attribute in a single call.

        Args:
            layer_id: Layer id, e.g. "basicShape#1".
            attr_id: Attribute path, e.g. "position.x".
            keys: List of {"frame": <int>, "value": <any>} objects,
                e.g. [{"frame": 0, "value": 0}, {"frame": 24, "value": 200}].
        """
        code = f"""
var keys = {json.dumps(keys)}
var ids = []
for (var i = 0; i < keys.length; i++) {{
    var patch = {{}}
    patch[{json.dumps(attr_id)}] = keys[i].value
    ids.push(api.keyframe({json.dumps(layer_id)}, keys[i].frame, patch))
}}
return {{ keyframeIds: ids }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_magic_easing(
        layer_id: str,
        attr_id: str,
        frame: int,
        easing: str,
        expression: str | None = None,
    ) -> dict:
        """Apply Magic Easing to the keyframe at a frame.

        Args:
            layer_id: Layer id.
            attr_id: Attribute path, e.g. "position.x".
            frame: Frame of the keyframe to ease.
            easing: One of "SlowIn", "SlowOut", "SlowInSlowOut", "VerySlowIn",
                "VerySlowOut", "VerySlowInVerySlowOut", "SpringIn", "SpringOut",
                "SpringInSpringOut", "SmallSpringIn", "SmallSpringOut",
                "SmallSpringInSmallSpringOut", "AnticipateIn", "OvershootOut",
                "AnticipateInOvershootOut", "BounceIn", "BounceOut",
                "BounceInBounceOut", "Custom" (required when using expression),
                "None".
            expression: Optional custom easing expression, e.g. "1 - pow(1 - x, 5)".
        """
        code = f"""
var args = [
    {json.dumps(layer_id)}, {json.dumps(attr_id)}, {json.dumps(frame)}, {json.dumps(easing)}
]
var expression = {json.dumps(expression)}
if (expression !== null) {{ args.push(expression) }}
api.magicEasing.apply(null, args)
return {{ applied: true }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_modify_keyframe(
        layer_id: str,
        attr_id: str,
        frame: int,
        new_frame: int | None = None,
        new_value: Any = None,
        keyframe_type: int | None = None,
    ) -> dict:
        """Move/retime a keyframe or change its value/interpolation.

        Args:
            layer_id: Layer id.
            attr_id: Attribute path.
            frame: Current frame of the keyframe.
            new_frame: Optional new frame to move it to.
            new_value: Optional new value.
            keyframe_type: Optional interpolation: 0 = Bezier, 1 = Linear, 2 = Step.
        """
        mod: dict[str, Any] = {"frame": frame}
        if new_frame is not None:
            mod["newFrame"] = new_frame
        if new_value is not None:
            mod["newValue"] = new_value
        if keyframe_type is not None:
            mod["type"] = keyframe_type
        code = f"""
var patch = {{}}
patch[{json.dumps(attr_id)}] = {json.dumps(mod)}
api.modifyKeyframe({json.dumps(layer_id)}, patch)
return {{ modified: true }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_delete_animation(layer_id: str, attr_id: str) -> dict:
        """Delete all keyframes on an attribute.

        Args:
            layer_id: Layer id.
            attr_id: Attribute path.
        """
        code = (
            f"api.deleteAnimation({json.dumps(layer_id)}, {json.dumps(attr_id)})"
            "\nreturn { deleted: true }"
        )
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_play() -> dict:
        """Start playback."""
        return await get_bridge().execute_value("api.play()\nreturn { playing: true }")

    @mcp.tool()
    async def cavalry_stop() -> dict:
        """Stop playback."""
        return await get_bridge().execute_value("api.stop()\nreturn { playing: false }")

    @mcp.tool()
    async def cavalry_set_frame(frame: int) -> dict:
        """Move the playhead to a frame.

        Args:
            frame: Frame number.
        """
        code = f"api.setFrame({json.dumps(frame)})\nreturn {{ frame: api.getFrame() }}"
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_get_frame() -> dict:
        """Get the current playhead frame."""
        return await get_bridge().execute_value("return { frame: api.getFrame() }")

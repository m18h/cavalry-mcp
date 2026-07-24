"""Attribute tools: inspect, set, connect, expressions, generators."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from ..state import get_bridge


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def cavalry_get_attributes(layer_id: str) -> dict:
        """List a layer's attributes (ids usable with get/set/connect).

        Attribute paths differ between layer types and Cavalry versions
        (e.g. the fill color is "material.materialColor" on 2.7.x shapes),
        so check here before guessing paths.

        Args:
            layer_id: Layer id, e.g. "basicShape#1".
        """
        code = f"""
var id = {json.dumps(layer_id)}
var attrs = api.getAttributes(id)
var out = []
for (var i = 0; i < attrs.length; i++) {{
    var a = attrs[i]
    var entry = {{ id: a }}
    try {{ entry.niceName = api.getAttributeNiceName(id, a) }} catch (e) {{}}
    try {{ entry.animated = api.isAnimatedAttribute(id, a) }} catch (e) {{}}
    out.push(entry)
}}
return {{ layer: id, count: out.length, attributes: out }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_get_attribute(layer_id: str, attr_id: str) -> dict:
        """Read an attribute's current value and type.

        Args:
            layer_id: Layer id, e.g. "basicShape#1".
            attr_id: Attribute path, e.g. "position.x", "fill.color", "fontSize".
        """
        code = f"""
var id = {json.dumps(layer_id)}
var attr = {json.dumps(attr_id)}
var result = {{ layer: id, attribute: attr, value: api.get(id, attr) }}
try {{ result.type = api.getAttrType(id, attr) }} catch (e) {{}}
return result
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_set_attribute(
        layer_id: str, attr_id: str, value: Any
    ) -> dict:
        """Set an attribute value. Returns the value as read back after setting.

        Args:
            layer_id: Layer id, e.g. "basicShape#1".
            attr_id: Attribute path, e.g. "position.x", "rotation", "opacity",
                "material.materialColor" (hex string like "#ff8800"),
                "stroke.width", "fontSize", "text".
            value: New value (number, string, boolean, or array/object as appropriate).
        """
        code = f"""
var id = {json.dumps(layer_id)}
var patch = {{}}
patch[{json.dumps(attr_id)}] = {json.dumps(value)}
api.set(id, patch)
return {{ layer: id, attribute: {json.dumps(attr_id)}, value: api.get(id, {json.dumps(attr_id)}) }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_connect(
        from_layer: str,
        from_attr: str,
        to_layer: str,
        to_attr: str,
        force: bool = False,
    ) -> dict:
        """Connect one attribute's output to another attribute's input.

        Args:
            from_layer: Source layer id.
            from_attr: Source attribute path, e.g. "position.y".
            to_layer: Target layer id.
            to_attr: Target attribute path.
            force: Break existing input connection on the target if present.
        """
        code = f"""
api.connect(
    {json.dumps(from_layer)}, {json.dumps(from_attr)},
    {json.dumps(to_layer)}, {json.dumps(to_attr)},
    {json.dumps(force)}
)
return {{ inConnection: api.getInConnection({json.dumps(to_layer)}, {json.dumps(to_attr)}) }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_disconnect_input(layer_id: str, attr_id: str) -> dict:
        """Remove the input connection on an attribute.

        Args:
            layer_id: Layer id.
            attr_id: Attribute path.
        """
        code = f"""
api.disconnectInput({json.dumps(layer_id)}, {json.dumps(attr_id)})
return {{ inConnection: api.getInConnection({json.dumps(layer_id)}, {json.dumps(attr_id)}) }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_disconnect_outputs(layer_id: str, attr_id: str) -> dict:
        """Remove all output connections from an attribute.

        Args:
            layer_id: Layer id.
            attr_id: Attribute path.
        """
        code = (
            f"api.disconnectOutputs({json.dumps(layer_id)}, {json.dumps(attr_id)})"
            "\nreturn { disconnected: true }"
        )
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_set_expression(
        layer_id: str, attr_id: str, expression: str
    ) -> dict:
        """Set an attribute expression (manipulates the attribute's input value).

        Args:
            layer_id: Layer id.
            attr_id: Attribute path, e.g. "position.y".
            expression: Expression, e.g. "*2", "%50", "clamp(-45, value, 45)".
        """
        code = f"""
api.setAttributeExpression({json.dumps(layer_id)}, {json.dumps(attr_id)}, {json.dumps(expression)})
return {{ expression: api.getAttributeExpression({json.dumps(layer_id)}, {json.dumps(attr_id)}) }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_set_generator(
        layer_id: str, attr_id: str, generator_type: str
    ) -> dict:
        """Set a generator on a layer attribute (e.g. the shape generator on basicShape).

        Args:
            layer_id: Layer id, e.g. "basicShape#1".
            attr_id: Attribute path, e.g. "generator".
            generator_type: Generator type, e.g. "ellipse", "rectangle", "polygon", "star".
        """
        code = f"""
api.setGenerator({json.dumps(layer_id)}, {json.dumps(attr_id)}, {json.dumps(generator_type)})
return {{ generator: api.getCurrentGenerator({json.dumps(layer_id)}, {json.dumps(attr_id)}) }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_add_dynamic_attribute(
        layer_id: str, attr_id: str, attr_type: str
    ) -> dict:
        """Add a dynamic attribute to a layer that supports them (e.g. javaScript utility).

        Dynamic attributes are accessed by index path (e.g. "array.0"), not by name.

        Args:
            layer_id: Layer id, e.g. a "javaScript" layer.
            attr_id: Id for the new attribute, e.g. "array".
            attr_type: Value type, e.g. "double", "int", "bool", "string", "color".
        """
        code = (
            f"api.addDynamic("
            f"{json.dumps(layer_id)}, {json.dumps(attr_id)}, {json.dumps(attr_type)})"
            "\nreturn { added: true }"
        )
        return await get_bridge().execute_value(code)

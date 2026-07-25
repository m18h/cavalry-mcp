"""Layer tools: create, inspect, organize, select."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from ..state import get_bridge

_LAYER_INFO_JS = """
function layerInfo(id) {
    return { id: id, niceName: api.getNiceName(id), type: api.getLayerType(id) }
}
"""


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def cavalry_create_layer(
        layer_type: str, name: str | None = None
    ) -> dict:
        """Create a layer in the active composition and return its id.

        Args:
            layer_type: Cavalry layer type, e.g. "basicShape", "textShape",
                "null", "group", "colorPlane", "duplicator", "subMesh",
                "connectShape", "linearGradient", "javaScript", "imageAsset",
                "stagger", "trail", "noiseDeformer".
            name: Optional display name.
        """
        code = f"""
var id = {json.dumps(name)} === null
    ? api.create({json.dumps(layer_type)})
    : api.create({json.dumps(layer_type)}, {json.dumps(name)})
return {{ id: id, niceName: api.getNiceName(id), type: api.getLayerType(id) }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_delete_layer(layer_id: str) -> dict:
        """Delete a layer.

        Args:
            layer_id: Layer id, e.g. "basicShape#1".
        """
        code = f"""
var id = {json.dumps(layer_id)}
var existed = api.layerExists(id)
if (existed) {{ api.deleteLayer(id) }}
return {{ deleted: id, existed: existed }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_rename_layer(layer_id: str, name: str) -> dict:
        """Rename a layer.

        Args:
            layer_id: Layer id, e.g. "basicShape#1".
            name: New display name.
        """
        code = f"""
api.rename({json.dumps(layer_id)}, {json.dumps(name)})
return {{ id: {json.dumps(layer_id)}, niceName: api.getNiceName({json.dumps(layer_id)}) }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_duplicate_layer(
        layer_id: str, with_input_connections: bool = False
    ) -> dict:
        """Duplicate a layer. The duplicate becomes the current selection.

        Args:
            layer_id: Layer id to duplicate.
            with_input_connections: Also duplicate its input connections.
        """
        code = f"""
api.duplicate({json.dumps(layer_id)}, {json.dumps(with_input_connections)})
{_LAYER_INFO_JS}
var sel = api.getSelection()
var out = []
for (var i = 0; i < sel.length; i++) {{ out.push(layerInfo(sel[i])) }}
return {{ source: {json.dumps(layer_id)}, duplicates: out }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_list_layers(
        top_level_only: bool = False,
        layer_type: str | None = None,
        scope: str = "active_comp",
    ) -> dict:
        """List layers with their ids, names and types.

        Args:
            top_level_only: Ignore children of groups/pre-comps.
            layer_type: Optional type filter, e.g. "textShape".
            scope: "active_comp" (default) or "scene" for every layer in the scene.
        """
        code = f"""
var topLevel = {json.dumps(top_level_only)}
var type = {json.dumps(layer_type)}
var scope = {json.dumps(scope)}
var ids
if (scope === 'scene') {{ ids = api.getAllSceneLayers() }}
else if (type) {{ ids = api.getCompLayersOfType(topLevel, type) }}
else {{ ids = api.getCompLayers(topLevel) }}
{_LAYER_INFO_JS}
var limit = 500
var out = []
for (var i = 0; i < ids.length && i < limit; i++) {{ out.push(layerInfo(ids[i])) }}
return {{ count: ids.length, truncated: ids.length > limit, layers: out }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_get_selection() -> dict:
        """Get the currently selected layers."""
        code = f"""
{_LAYER_INFO_JS}
var sel = api.getSelection()
var out = []
for (var i = 0; i < sel.length; i++) {{ out.push(layerInfo(sel[i])) }}
return {{ layers: out }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_select_layers(layer_ids: list[str]) -> dict:
        """Select layers by id (replaces the current selection).

        Args:
            layer_ids: Layer ids to select.
        """
        code = f"api.select({json.dumps(layer_ids)})\nreturn {{ selection: api.getSelection() }}"
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_get_layer_info(layer_id: str) -> dict:
        """Get details about one layer: type, hierarchy, in/out frames, bounding box.

        Args:
            layer_id: Layer id, e.g. "basicShape#1".
        """
        code = f"""
var id = {json.dumps(layer_id)}
if (!api.layerExists(id)) {{ throw new Error('Layer not found: ' + id) }}
var info = {{
    id: id,
    niceName: api.getNiceName(id),
    type: api.getLayerType(id),
    children: api.getChildren(id),
    visible: api.isVisible(id, true),
    isShape: api.isShape(id)
}}
try {{ info.parent = api.getParent(id) }} catch (e) {{ info.parent = null }}
try {{ info.inFrame = api.getInFrame(id) }} catch (e) {{ info.inFrame = null }}
try {{ info.outFrame = api.getOutFrame(id) }} catch (e) {{ info.outFrame = null }}
try {{ info.boundingBox = api.getBoundingBox(id, true) }} catch (e) {{ info.boundingBox = null }}
return info
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_set_parent(layer_id: str, parent_id: str | None = None) -> dict:
        """Parent a layer to another layer (or un-parent it).

        Args:
            layer_id: Layer to move in the hierarchy.
            parent_id: New parent layer id, or null to un-parent.
        """
        code = f"""
var id = {json.dumps(layer_id)}
var parent = {json.dumps(parent_id)}
if (parent === null) {{ api.unParent(id) }} else {{ api.parent(id, parent) }}
try {{ return {{ id: id, parent: api.getParent(id) }} }}
catch (e) {{ return {{ id: id, parent: null }} }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_set_in_out_frames(
        layer_id: str,
        in_frame: int | None = None,
        out_frame: int | None = None,
    ) -> dict:
        """Trim a layer by setting its in and/or out frame.

        Args:
            layer_id: Layer id.
            in_frame: First frame the layer is active, or null to leave unchanged.
            out_frame: Last frame the layer is active, or null to leave unchanged.
        """
        code = f"""
var id = {json.dumps(layer_id)}
var inFrame = {json.dumps(in_frame)}
var outFrame = {json.dumps(out_frame)}
if (inFrame !== null) {{ api.setInFrame(id, inFrame) }}
if (outFrame !== null) {{ api.setOutFrame(id, outFrame) }}
return {{ id: id, inFrame: api.getInFrame(id), outFrame: api.getOutFrame(id) }}
"""
        return await get_bridge().execute_value(code)

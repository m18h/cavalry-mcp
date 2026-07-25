"""Render, preview and asset tools — including visual feedback images."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

from ..state import get_bridge


def _temp_png_path(prefix: str) -> str:
    fd, path = tempfile.mkstemp(prefix=f"cavalry_{prefix}_", suffix=".png")
    Path(path).unlink(missing_ok=True)  # Cavalry will create it
    import os

    os.close(fd)
    return path


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def cavalry_render_frame_png(scale_percentage: int = 100) -> Image:
        """Render the current frame to PNG and return the image.

        Use this to SEE the result of your work and iterate visually.

        Args:
            scale_percentage: Render scale, 1-100 (use lower values for faster previews).
        """
        path = _temp_png_path("frame")
        code = f"""
api.renderPNGFrame({json.dumps(path)}, {json.dumps(scale_percentage)})
return {{ exists: api.filePathExists({json.dumps(path)}) }}
"""
        await get_bridge().execute_value(code, timeout=180.0)
        return Image(path=path)

    @mcp.tool()
    async def cavalry_viewport_screenshot() -> Image:
        """Capture the current viewport contents as an image and return it.

        Faster than a full render for a quick look at the composition.
        """
        path = _temp_png_path("viewport")
        code = f"""
api.saveViewportContentsAsImage({json.dumps(path)})
return {{ exists: api.filePathExists({json.dumps(path)}) }}
"""
        await get_bridge().execute_value(code, timeout=60.0)
        return Image(path=path)

    @mcp.tool()
    async def cavalry_list_render_queue() -> dict:
        """List render queue items (id, name, enabled state)."""
        code = """
var items = api.getRenderQueueItems()
var out = []
for (var i = 0; i < items.length; i++) {
    var entry = { id: items[i] }
    try { entry.niceName = api.getNiceName(items[i]) } catch (e) {}
    try { entry.enabled = api.get(items[i], 'selected') } catch (e) {}
    out.push(entry)
}
return { items: out }
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_add_render_queue_item(comp_id: str | None = None) -> dict:
        """Add a composition to the render queue.

        Args:
            comp_id: Composition id. Defaults to the active comp.
        """
        code = f"""
var comp = {json.dumps(comp_id)} || api.getActiveComp()
if (!comp) {{ throw new Error('No active composition') }}
var id = api.addRenderQueueItem(comp)
return {{ id: id, niceName: api.getNiceName(id) }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_start_render(item_id: str, timeout: float = 600.0) -> dict:
        """Render a render queue item (blocks until the render finishes).

        Args:
            item_id: Render queue item id from cavalry_list_render_queue /
                cavalry_add_render_queue_item.
            timeout: Seconds to wait for the render before failing.
        """
        code = f"api.render({json.dumps(item_id)})\nreturn {{ rendered: {json.dumps(item_id)} }}"
        return await get_bridge().execute_value(code, timeout=timeout)

    @mcp.tool()
    async def cavalry_render_all_background() -> dict:
        """Start rendering all enabled render queue items in the background (non-blocking)."""
        return await get_bridge().execute_value(
            "api.backgroundRenderAll()\nreturn { started: true }"
        )

    @mcp.tool()
    async def cavalry_cancel_render() -> dict:
        """Cancel any ongoing render."""
        return await get_bridge().execute_value(
            "api.cancelRender()\nreturn { cancelled: true }"
        )

    @mcp.tool()
    async def cavalry_load_asset(path: str, is_image_sequence: bool = False) -> dict:
        """Load a file (image, video, SVG, spreadsheet, font...) into the scene's Asset Window.

        Args:
            path: Absolute file path.
            is_image_sequence: Treat numbered image files as an image sequence.
        """
        code = f"""
var id = api.loadAsset({json.dumps(path)}, {json.dumps(is_image_sequence)})
var result = {{ assetId: id }}
try {{ result.assetType = api.getAssetType(id) }} catch (e) {{}}
try {{ result.niceName = api.getNiceName(id) }} catch (e) {{}}
return result
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_add_asset_to_comp(asset_id: str) -> dict:
        """Add an asset from the Asset Window to the active composition as a layer.

        Args:
            asset_id: Asset id from cavalry_load_asset.
        """
        code = f"return {{ layerId: api.addAssetToComp({json.dumps(asset_id)}) }}"
        return await get_bridge().execute_value(code)

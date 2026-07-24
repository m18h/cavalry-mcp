"""Scene and composition tools."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from ..state import get_bridge


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def cavalry_get_scene_info() -> dict:
        """Get info about the open scene: file path, unsaved changes, comps, playhead."""
        return await get_bridge().execute_value("""
return {
    sceneFilePath: api.getSceneFilePath(),
    unsavedChanges: api.sceneHasUnsavedChanges(),
    activeComp: api.getActiveComp(),
    comps: api.getComps(),
    projectPath: api.getProjectPath(),
    currentFrame: api.getFrame()
}
""")

    @mcp.tool()
    async def cavalry_get_comp_info(comp_id: str | None = None) -> dict:
        """Get details about a composition (frame rate, frame range, resolution, etc.).

        Args:
            comp_id: Composition layer id, e.g. "comp#1". Defaults to the active comp.
        """
        code = f"""
var comp = {json.dumps(comp_id)} || api.getActiveComp()
if (!comp) {{
    throw new Error('No active composition')
}}
var attrs = api.getAttributes(comp)
var interesting = {{}}
for (var i = 0; i < attrs.length; i++) {{
    var a = attrs[i]
    if (/fps|frame|range|resol|width|height|duration|background|start|end/i.test(a)) {{
        try {{ interesting[a] = api.get(comp, a) }} catch (e) {{}}
    }}
}}
return {{
    comp: comp,
    niceName: api.getNiceName(comp),
    settings: interesting,
    allAttributes: attrs
}}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_new_scene() -> dict:
        """Close the current scene and start a new empty one."""
        return await get_bridge().execute_value(
            "api.newScene()\n"
            "return { sceneFilePath: api.getSceneFilePath(), comps: api.getComps() }"
        )

    @mcp.tool()
    async def cavalry_open_scene(path: str, force: bool = False) -> dict:
        """Open a .cv scene file.

        Args:
            path: Absolute path to the .cv file.
            force: Discard unsaved changes in the current scene without prompting.
        """
        code = f"""
api.openScene({json.dumps(path)}, {json.dumps(force)})
return {{ sceneFilePath: api.getSceneFilePath(), comps: api.getComps() }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_save_scene() -> dict:
        """Save the current scene to its existing file."""
        return await get_bridge().execute_value(
            "return { saved: api.saveScene(), sceneFilePath: api.getSceneFilePath() }"
        )

    @mcp.tool()
    async def cavalry_save_scene_as(path: str) -> dict:
        """Save the current scene to a new .cv file path.

        Args:
            path: Absolute destination path, e.g. "/tmp/my-scene.cv".
        """
        code = (
            f"return {{ saved: api.saveSceneAs({json.dumps(path)}),"
            " sceneFilePath: api.getSceneFilePath() }"
        )
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_create_comp(name: str) -> dict:
        """Create a new composition.

        Args:
            name: Name for the composition.
        """
        code = f"""
var id = api.createComp({json.dumps(name)})
return {{ id: id, niceName: api.getNiceName(id) }}
"""
        return await get_bridge().execute_value(code)

    @mcp.tool()
    async def cavalry_set_active_comp(comp_id: str) -> dict:
        """Make a composition the active (currently viewed) one.

        Args:
            comp_id: Composition layer id, e.g. "comp#1".
        """
        code = (
            f"api.setActiveComp({json.dumps(comp_id)})"
            "\nreturn { activeComp: api.getActiveComp() }"
        )
        return await get_bridge().execute_value(code)

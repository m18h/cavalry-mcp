"""Meta tools: connection status and the raw script escape hatch."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..bridge import HINT, BridgeUnavailableError
from ..state import get_bridge


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def cavalry_status() -> dict:
        """Check the connection to Cavalry and return version/scene info.

        Use this first if unsure whether Cavalry is running with the
        cavalry-mcp bridge script open.
        """
        bridge = get_bridge()
        probe = await bridge.probe()
        if probe is None:
            raise BridgeUnavailableError(
                f"Cannot reach the cavalry-mcp bridge at {bridge.host}:{bridge.port}. {HINT}"
            )
        value = await bridge.execute_value("""
return {
    cavalryVersion: api.getCavalryVersion(),
    guiSession: api.isGuiSession(),
    platform: api.getPlatform(),
    sceneFilePath: api.getSceneFilePath(),
    unsavedChanges: api.sceneHasUnsavedChanges(),
    activeComp: api.getActiveComp(),
    comps: api.getComps(),
    currentFrame: api.getFrame(),
    restrictedLicence: api.isRestrictedLicence()
}
""")
        return {"connected": True, "bridge": probe, "cavalry": value}

    @mcp.tool()
    async def cavalry_run_script(code: str, timeout: float = 30.0) -> dict:
        """Run arbitrary JavaScript inside Cavalry (the escape hatch).

        The full `api`, `cavalry`, `console` and `ui` scripting namespaces are
        available. The code is wrapped in an IIFE — use `return` to send a
        JSON-serializable value back. Never raises on script errors: the
        structured result is returned as {ok, value, logs, error} so mistakes
        can be inspected and fixed iteratively.

        Args:
            code: JavaScript to execute, e.g. "return api.getFrame()".
            timeout: Seconds to wait for Cavalry before failing.
        """
        result = await get_bridge().execute(code, timeout=timeout)
        return {
            "ok": result.ok,
            "value": result.value,
            "logs": result.logs,
            "error": result.error,
        }

"""cavalry-mcp server entry point.

Run:            cavalry-mcp                 (stdio MCP server)
Install bridge: cavalry-mcp install-bridge  (copies bridge.js into Cavalry's Scripts folder)
"""

from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from . import __version__
from .tools import register_all

# httpx logs every bridge poll at INFO — far too noisy for a long-lived server.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

INSTRUCTIONS = """\
You are controlling Cavalry (2D motion design software) via the cavalry-mcp \
bridge. Everything happens inside the *currently open scene* in the running app.

Ground rules:
- If a call fails with a bridge/connection error, ask the user to open Cavalry \
and run the "cavalry-mcp-bridge" script from Cavalry's Scripts menu (keep its \
window open). cavalry_status checks the connection.
- Layer ids look like "basicShape#1". Get them from create/list/selection tools.
- Useful layer types: basicShape, textShape, null, group, colorPlane, \
duplicator, subMesh, connectShape, linearGradient, javaScript, imageAsset, \
stagger, trail, noiseDeformer.
- Useful attribute paths: position.x, position.y, rotation, scale.x, scale.y, \
opacity, material.materialColor (fill color, hex string like "#ff8800"), \
stroke.color, stroke.width, fontSize, text. Attribute paths differ between \
Cavalry versions — when unsure, list them with cavalry_get_attributes.
- Keyframes: cavalry_set_keyframe(s), then shape timing with \
cavalry_magic_easing (e.g. "SlowOut", "BounceOut", "SpringInSpringOut").
- VISUAL FEEDBACK: after building or changing something, use \
cavalry_render_frame_png or cavalry_viewport_screenshot to actually see the \
result, then iterate. Do this before declaring victory.
- When you need functionality beyond the dedicated tools, look up functions \
with cavalry_search_api (exact signatures) and run them with cavalry_run_script \
(use `return` to get values back). For concepts/how-tos ("how do I loop an \
animation?", "stagger a duplicator"), use cavalry_search_knowledge — semantic \
search over the full official documentation.
- Prefer cavalry_set_keyframes (batch) over many single-keyframe calls.
"""

mcp = FastMCP("cavalry-mcp", instructions=INSTRUCTIONS)
register_all(mcp)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "install-bridge":
        from .install import install_bridge

        target = install_bridge()
        print(f"Installed cavalry-mcp bridge v{__version__} to:\n  {target}")
        print(
            "\nNext: open Cavalry and start the bridge from the Scripts menu "
            "(keep its window open)."
        )
        return
    mcp.run()


if __name__ == "__main__":
    main()

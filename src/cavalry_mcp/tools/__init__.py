"""Tool registration."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import anim, apiref, attrs, knowledge, layers, meta, render, scene


def register_all(mcp: FastMCP) -> None:
    for module in (meta, scene, layers, attrs, anim, render, apiref, knowledge):
        module.register(mcp)

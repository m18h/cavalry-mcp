"""Shared bridge singleton, configured from CAVALRY_BRIDGE_HOST/PORT."""

from __future__ import annotations

from .bridge import CavalryBridge

_bridge: CavalryBridge | None = None


def get_bridge() -> CavalryBridge:
    global _bridge
    if _bridge is None:
        _bridge = CavalryBridge()
    return _bridge

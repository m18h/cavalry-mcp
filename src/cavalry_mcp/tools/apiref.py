"""Searchable Cavalry scripting API reference (bundled from cavalry-types)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files

from mcp.server.fastmcp import FastMCP

_DOC_LIMIT = 800


@lru_cache(maxsize=1)
def _entries() -> list[dict]:
    text = files("cavalry_mcp").joinpath("data/api_reference.json").read_text(
        encoding="utf-8"
    )
    return json.loads(text)["entries"]


def _score(entry: dict, tokens: list[str]) -> int:
    name = entry["name"].lower()
    signature = entry["signature"].lower()
    doc = entry["doc"].lower()
    score = 0
    for token in tokens:
        if name == token:
            score += 12
        elif name.startswith(token):
            score += 6
        if token in name:
            score += 4
        if token in signature:
            score += 2
        if token in doc:
            score += 1
    return score


def search(query: str, namespace: str | None = None, limit: int = 8) -> list[dict]:
    tokens = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if t]
    if not tokens:
        return []
    results = []
    for entry in _entries():
        if namespace and entry["namespace"] != namespace:
            continue
        score = _score(entry, tokens)
        if score > 0:
            results.append((score, entry))
    results.sort(key=lambda item: (-item[0], item[1]["name"]))
    out = []
    for _score_val, entry in results[:limit]:
        doc = entry["doc"]
        if len(doc) > _DOC_LIMIT:
            doc = doc[:_DOC_LIMIT].rstrip() + "…"
        out.append(
            {
                "namespace": entry["namespace"],
                "kind": entry["kind"],
                "name": entry["name"],
                "signature": entry["signature"],
                "doc": doc,
            }
        )
    return out


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    async def cavalry_search_api(
        query: str, namespace: str | None = None, limit: int = 8
    ) -> dict:
        """Search the Cavalry JavaScript API reference (~420 documented functions/classes).

        Use this to discover the right api.* function, exact signature and
        usage examples before writing cavalry_run_script code.

        Args:
            query: Free-text search, e.g. "keyframe", "render png", "bounding box".
            namespace: Optional namespace filter: "api", "cavalry", "ui",
                "console", "ctx", "def", "render", "plugin".
            limit: Max results to return.
        """
        results = search(query, namespace=namespace, limit=limit)
        return {"count": len(results), "results": results}

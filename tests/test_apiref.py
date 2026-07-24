"""API reference search tests."""

from __future__ import annotations

from cavalry_mcp.tools.apiref import search


def test_search_finds_keyframe():
    results = search("keyframe")
    names = [r["name"] for r in results]
    assert "keyframe" in names
    assert results[0]["namespace"] == "api"


def test_search_multi_token():
    results = search("render png frame")
    assert results[0]["name"] == "renderPNGFrame"


def test_search_namespace_filter():
    results = search("add", namespace="ui")
    assert all(r["namespace"] == "ui" for r in results)


def test_search_limit():
    assert len(search("a", limit=3)) <= 3


def test_search_empty_query():
    assert search("") == []


def test_search_returns_signature_and_doc():
    (result,) = [r for r in search("magic easing", limit=1)]
    assert "magicEasing" in result["signature"]
    assert "BounceOut" in result["doc"]

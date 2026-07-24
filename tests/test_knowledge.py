"""Knowledge base tests: chunker (ETL) and search ranking (runtime)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_knowledge_base import (  # noqa: E402
    MAX_CHUNK_CHARS,
    chunk_page,
    clean_heading,
    split_blocks,
)

from cavalry_mcp.tools import knowledge  # noqa: E402

# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------


def test_split_blocks_keeps_fenced_code_atomic():
    md = "Intro paragraph.\n\n```\nvar x = 1\n\nvar y = 2\n```\n\nAfter code."
    blocks = split_blocks(md)
    assert len(blocks) == 3
    assert "var x = 1\n\nvar y = 2" in blocks[1]
    assert blocks[2] == "After code."


def test_chunk_page_heading_breadcrumbs():
    md = (
        "# Intro\n\n"
        "Welcome text that is long enough to be kept as a chunk of its own, "
        "really and truly.\n\n"
        "## Details\n\n"
        "Some detail text that is also long enough to keep around as a proper "
        "chunk of text."
    )
    chunks = chunk_page("My Page", "http://x/docs/p/", md)
    assert len(chunks) == 2
    assert chunks[0]["heading"] == "My Page > Intro"
    assert chunks[1]["heading"] == "My Page > Intro > Details"


def test_chunk_page_respects_max_chars():
    paragraph = "word " * 200
    md = f"## Big\n\n{paragraph}\n\n{paragraph}"
    chunks = chunk_page("T", "http://x/", md)
    assert all(len(c["text"]) <= MAX_CHUNK_CHARS for c in chunks)
    assert len(chunks) >= 2


def test_chunk_page_skips_tiny_chunks():
    md = (
        "## A\n\nok\n\n## B\n\n"
        "This chunk is definitely long enough to survive the minimum size filter, no question."
    )
    chunks = chunk_page("T", "http://x/", md)
    assert len(chunks) == 1
    assert "survive" in chunks[0]["text"]


def test_clean_heading_removes_anchor_residue():
    raw = 'Cavalry[​](#cavalry "Direct link to Cavalry")'
    assert clean_heading(raw) == "Cavalry"


# ---------------------------------------------------------------------------
# Search ranking
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_store(monkeypatch: pytest.MonkeyPatch):
    chunks = [
        {"title": "A", "url": "http://x/a", "heading": "A", "text": "alpha " * 200},
        {"title": "B", "url": "http://x/b", "heading": "B", "text": "beta"},
        {"title": "C", "url": "http://x/c", "heading": "C", "text": "gamma"},
    ]
    vectors = np.array([[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]], dtype=np.float32)

    class FakeEmbedder:
        def query_embed(self, texts):
            return iter([np.array([1.0, 0.0], dtype=np.float32)])

    monkeypatch.setattr(knowledge, "_store", lambda: (chunks, vectors, "fake-model"))
    monkeypatch.setattr(knowledge, "_embedder", lambda: FakeEmbedder())
    return chunks


def test_search_ranks_by_similarity(fake_store):
    results = knowledge.search("anything", limit=3)
    assert [r["title"] for r in results] == ["A", "C", "B"]
    assert results[0]["score"] > results[1]["score"] > results[2]["score"]


def test_search_truncates_long_text(fake_store):
    results = knowledge.search("anything", limit=1)
    assert results[0]["text"].endswith("…")
    assert len(results[0]["text"]) <= 701


def test_search_limit(fake_store):
    assert len(knowledge.search("anything", limit=2)) == 2


async def test_tool_returns_results(mcp, fake_store):
    from .conftest import call_tool

    result = await call_tool(mcp, "cavalry_search_knowledge", {"query": "loop"})
    assert result["available"] is True
    assert result["results"][0]["title"] == "A"


async def test_tool_reports_unavailable(mcp, monkeypatch):
    from .conftest import call_tool

    def boom(query, limit=5):
        raise knowledge.KnowledgeBaseUnavailable(knowledge.KB_SETUP_HINT)

    monkeypatch.setattr(knowledge, "search", boom)
    result = await call_tool(mcp, "cavalry_search_knowledge", {"query": "x"})
    assert result["available"] is False
    assert "build_knowledge_base.py" in result["error"]
